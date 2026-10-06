/*
 * ir_grab.cpp - High-performance raw frame streamer for OmniVision OG0VA1B IR camera
 *
 * Captures raw 10-bit monochrome frames (640x480, formats::R10) via libcamera,
 * synchronizes the Texas Instruments LM3643 IR strobe LED, adjusts sensor gain and
 * exposure via V4L2 subdevice controls, and writes 614,400-byte packed frames to stdout.
 *
 * Guaranteed cleanup: Turns off torch on normal exit, signal (SIGINT/SIGTERM/SIGHUP/SIGPIPE),
 * parent process termination (PR_SET_PDEATHSIG), and hard timeout (--max-seconds).
 */

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <queue>
#include <string>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <vector>

#include <linux/v4l2-subdev.h>
#include <linux/videodev2.h>

#include <libcamera/camera.h>
#include <libcamera/camera_manager.h>
#include <libcamera/control_ids.h>
#include <libcamera/formats.h>
#include <libcamera/framebuffer.h>
#include <libcamera/framebuffer_allocator.h>
#include <libcamera/libcamera.h>
#include <libcamera/request.h>
#include <libcamera/stream.h>

using namespace libcamera;

static std::atomic<bool> g_stop{false};
static std::string g_torch_path = "/sys/class/leds/lm3643:torch/brightness";

// Async-signal-safe torch turn-off helper
static void emergency_torch_off() {
    if (!g_torch_path.empty()) {
        int fd = open(g_torch_path.c_str(), O_WRONLY);
        if (fd >= 0) {
            const char zero[] = "0\n";
            (void)write(fd, zero, sizeof(zero) - 1);
            close(fd);
        }
    }
}

static void signal_handler(int sig) {
    (void)sig;
    g_stop.store(true);
    emergency_torch_off();
}

static bool set_torch_brightness(const std::string &path, int level) {
    if (path.empty()) return false;
    int fd = open(path.c_str(), O_WRONLY);
    if (fd < 0) return false;
    std::string val = std::to_string(level) + "\n";
    ssize_t written = write(fd, val.c_str(), val.size());
    close(fd);
    return written == static_cast<ssize_t>(val.size());
}

static std::string find_og0va1b_subdev() {
    for (int i = 0; i < 32; ++i) {
        std::string name_path = "/sys/class/video4linux/v4l-subdev" + std::to_string(i) + "/name";
        std::ifstream f(name_path);
        if (f.is_open()) {
            std::string line;
            if (std::getline(f, line)) {
                if (line.find("og0va1b") != std::string::npos || line.find("og0ve1b") != std::string::npos) {
                    return "/dev/v4l-subdev" + std::to_string(i);
                }
            }
        }
    }
    return "";
}

static bool get_subdev_ctrls(const std::string &subdev_path, int &orig_gain, int &orig_exposure) {
    int fd = open(subdev_path.c_str(), O_RDWR);
    if (fd < 0) return false;

    struct v4l2_control ctrl;
    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = V4L2_CID_ANALOGUE_GAIN;
    if (ioctl(fd, VIDIOC_G_CTRL, &ctrl) == 0) {
        orig_gain = ctrl.value;
    } else {
        orig_gain = -1;
    }

    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = V4L2_CID_EXPOSURE;
    if (ioctl(fd, VIDIOC_G_CTRL, &ctrl) == 0) {
        orig_exposure = ctrl.value;
    } else {
        orig_exposure = -1;
    }

    close(fd);
    return true;
}

static bool set_subdev_ctrls(const std::string &subdev_path, int gain, int exposure) {
    int fd = open(subdev_path.c_str(), O_RDWR);
    if (fd < 0) return false;

    struct v4l2_query_ext_ctrl qctrl;
    if (gain >= 0) {
        memset(&qctrl, 0, sizeof(qctrl));
        qctrl.id = V4L2_CID_ANALOGUE_GAIN;
        if (ioctl(fd, VIDIOC_QUERY_EXT_CTRL, &qctrl) == 0) {
            if (gain < qctrl.minimum) gain = qctrl.minimum;
            if (gain > qctrl.maximum) gain = qctrl.maximum;
        }
        struct v4l2_control ctrl;
        memset(&ctrl, 0, sizeof(ctrl));
        ctrl.id = V4L2_CID_ANALOGUE_GAIN;
        ctrl.value = gain;
        ioctl(fd, VIDIOC_S_CTRL, &ctrl);
    }

    if (exposure >= 0) {
        memset(&qctrl, 0, sizeof(qctrl));
        qctrl.id = V4L2_CID_EXPOSURE;
        if (ioctl(fd, VIDIOC_QUERY_EXT_CTRL, &qctrl) == 0) {
            if (exposure < qctrl.minimum) exposure = qctrl.minimum;
            if (exposure > qctrl.maximum) exposure = qctrl.maximum;
        }
        struct v4l2_control ctrl;
        memset(&ctrl, 0, sizeof(ctrl));
        ctrl.id = V4L2_CID_EXPOSURE;
        ctrl.value = exposure;
        ioctl(fd, VIDIOC_S_CTRL, &ctrl);
    }

    close(fd);
    return true;
}

static bool write_all(int fd, const void *buf, size_t count) {
    const uint8_t *ptr = static_cast<const uint8_t *>(buf);
    while (count > 0) {
        ssize_t ret = write(fd, ptr, count);
        if (ret < 0) {
            if (errno == EINTR)
                continue;
            return false;
        }
        if (ret == 0)
            return false;
        ptr += ret;
        count -= ret;
    }
    return true;
}

// Queue for completed requests from libcamera callback thread
static std::mutex g_queue_mutex;
static std::condition_variable g_queue_cv;
static std::queue<Request *> g_completed_requests;

static void request_complete(Request *request) {
    {
        std::lock_guard<std::mutex> lock(g_queue_mutex);
        g_completed_requests.push(request);
    }
    g_queue_cv.notify_one();
}

int main(int argc, char *argv[]) {
    std::string camera_id = "\\_SB_.PC00.LNK1";
    uint64_t max_frames = 0; // 0 = infinite / until EOF/stop
    int gain = 128;
    int exposure = 2000;
    std::string torch_path = "/sys/class/leds/lm3643:torch/brightness";
    int torch_level = 60;
    bool torch_required = false;
    bool restore_defaults = true;
    int max_seconds = 15;
    bool verbose = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--camera" && i + 1 < argc) {
            camera_id = argv[++i];
        } else if (arg == "--frames" && i + 1 < argc) {
            max_frames = std::stoull(argv[++i]);
        } else if (arg == "--gain" && i + 1 < argc) {
            gain = std::stoi(argv[++i]);
        } else if (arg == "--exposure" && i + 1 < argc) {
            exposure = std::stoi(argv[++i]);
        } else if (arg == "--torch" && i + 1 < argc) {
            torch_path = argv[++i];
        } else if (arg == "--torch-level" && i + 1 < argc) {
            torch_level = std::stoi(argv[++i]);
        } else if (arg == "--torch-required") {
            torch_required = true;
        } else if (arg == "--no-restore-defaults") {
            restore_defaults = false;
        } else if (arg == "--max-seconds" && i + 1 < argc) {
            max_seconds = std::stoi(argv[++i]);
        } else if (arg == "--verbose") {
            verbose = true;
        } else if (arg == "--help" || arg == "-h") {
            std::cerr << "Usage: ir-grab [options]\n"
                      << "  --camera <id>         libcamera camera ID (default: \\_SB_.PC00.LNK1)\n"
                      << "  --frames <N>          Number of frames to output (0 = stream until EOF/signal, default: 0)\n"
                      << "  --gain <N>            Sensor analogue gain (default: 128)\n"
                      << "  --exposure <N>        Sensor exposure lines (default: 2000)\n"
                      << "  --torch <path>        Sysfs path for strobe brightness\n"
                      << "  --torch-level <N>     Strobe brightness level (0-127, default: 60)\n"
                      << "  --torch-required      Exit with code 5 if torch brightness write fails\n"
                      << "  --no-restore-defaults Do not restore sensor gain/exposure on exit\n"
                      << "  --max-seconds <N>     Hard timeout in seconds (default: 15)\n"
                      << "  --verbose             Do not silence stderr\n";
            return 0;
        }
    }

    g_torch_path = torch_path;

    // 1. Silence libcamera logging unless verbose
    if (!verbose) {
        setenv("LIBCAMERA_LOG_LEVELS", "*:4", 1);
        int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) {
            dup2(devnull, STDERR_FILENO);
            close(devnull);
        }
    }

    // 2. Set death signal so ir-grab terminates if parent dies
    prctl(PR_SET_PDEATHSIG, SIGTERM);
    if (getppid() == 1) {
        // Parent already dead
        return 0;
    }

    // 3. Register signal handlers
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigaction(SIGTERM, &sa, nullptr);
    sigaction(SIGINT, &sa, nullptr);
    sigaction(SIGHUP, &sa, nullptr);
    sigaction(SIGPIPE, &sa, nullptr);

    // 4. Discover subdev and set sensor gain/exposure
    std::string subdev_path = find_og0va1b_subdev();
    int orig_gain = -1;
    int orig_exposure = -1;
    if (!subdev_path.empty()) {
        get_subdev_ctrls(subdev_path, orig_gain, orig_exposure);
        set_subdev_ctrls(subdev_path, gain, exposure);
    } else if (verbose) {
        std::cerr << "Warning: og0va1b subdevice not found in sysfs\n";
    }

    // 5. Activate IR strobe torch
    if (torch_level > 0 && !torch_path.empty()) {
        bool torch_ok = set_torch_brightness(torch_path, torch_level);
        if (!torch_ok) {
            if (verbose) {
                std::cerr << "Warning: Failed to set torch brightness on " << torch_path << "\n";
            }
            if (torch_required) {
                return 5;
            }
        }
    }

    // RAII guard to guarantee torch turn-off and control restoration on any return
    struct TeardownGuard {
        std::string torch_path;
        std::string subdev_path;
        bool restore_defaults;
        int orig_gain;
        int orig_exposure;

        ~TeardownGuard() {
            // Torch OFF first
            set_torch_brightness(torch_path, 0);
            if (restore_defaults && !subdev_path.empty() && orig_gain >= 0 && orig_exposure >= 0) {
                set_subdev_ctrls(subdev_path, orig_gain, orig_exposure);
            }
        }
    } teardown_guard{torch_path, subdev_path, restore_defaults, orig_gain, orig_exposure};

    // 6. Initialize libcamera
    std::unique_ptr<CameraManager> cm = std::make_unique<CameraManager>();
    int ret = cm->start();
    if (ret < 0) {
        if (verbose) std::cerr << "CameraManager::start() failed: " << ret << "\n";
        return 2;
    }

    std::shared_ptr<Camera> camera = cm->get(camera_id);
    if (!camera) {
        // Fallback: check matching cameras by name
        for (const auto &c : cm->cameras()) {
            if (c->id().find("PC00.LNK1") != std::string::npos || c->id().find(camera_id) != std::string::npos) {
                camera = c;
                break;
            }
        }
    }

    if (!camera) {
        if (verbose) std::cerr << "Camera " << camera_id << " not found\n";
        cm->stop();
        return 2;
    }

    ret = camera->acquire();
    if (ret < 0) {
        if (verbose) std::cerr << "Camera::acquire() failed: " << ret << "\n";
        cm->stop();
        return 2;
    }

    std::unique_ptr<CameraConfiguration> config = camera->generateConfiguration({StreamRole::Raw});
    if (!config || config->empty()) {
        if (verbose) std::cerr << "generateConfiguration failed\n";
        camera->release();
        cm->stop();
        return 3;
    }

    StreamConfiguration &stream_cfg = config->at(0);
    stream_cfg.size = Size(640, 480);
    stream_cfg.pixelFormat = formats::R10;

    CameraConfiguration::Status status = config->validate();
    if (status == CameraConfiguration::Invalid) {
        if (verbose) std::cerr << "CameraConfiguration is invalid\n";
        camera->release();
        cm->stop();
        return 3;
    }

    ret = camera->configure(config.get());
    if (ret < 0) {
        if (verbose) std::cerr << "Camera::configure() failed: " << ret << "\n";
        camera->release();
        cm->stop();
        return 3;
    }

    Stream *stream = stream_cfg.stream();
    unsigned int stride = stream_cfg.stride;
    constexpr size_t FRAME_WIDTH = 640;
    constexpr size_t FRAME_HEIGHT = 480;
    constexpr size_t ROW_BYTES = FRAME_WIDTH * 2; // 1280 bytes
    constexpr size_t FRAME_SIZE = ROW_BYTES * FRAME_HEIGHT; // 614,400 bytes

    // Buffer allocation
    FrameBufferAllocator *allocator = new FrameBufferAllocator(camera);
    ret = allocator->allocate(stream);
    if (ret < 0) {
        if (verbose) std::cerr << "Failed to allocate buffers: " << ret << "\n";
        delete allocator;
        camera->release();
        cm->stop();
        return 3;
    }

    // Map memory buffers
    std::map<FrameBuffer *, void *> mapped_buffers;
    std::vector<std::pair<void *, size_t>> mapped_planes;
    for (const std::unique_ptr<FrameBuffer> &buffer : allocator->buffers(stream)) {
        if (buffer->planes().empty()) continue;
        const FrameBuffer::Plane &plane = buffer->planes()[0];
        void *mem = mmap(nullptr, plane.length, PROT_READ, MAP_SHARED, plane.fd.get(), 0);
        if (mem == MAP_FAILED) {
            if (verbose) std::cerr << "mmap plane failed\n";
            continue;
        }
        mapped_buffers[buffer.get()] = mem;
        mapped_planes.emplace_back(mem, plane.length);
    }

    if (mapped_buffers.empty()) {
        if (verbose) std::cerr << "No mapped buffers available\n";
        delete allocator;
        camera->release();
        cm->stop();
        return 3;
    }

    // Create requests
    std::vector<std::unique_ptr<Request>> requests;
    for (const std::unique_ptr<FrameBuffer> &buffer : allocator->buffers(stream)) {
        std::unique_ptr<Request> request = camera->createRequest();
        if (!request) continue;
        if (request->addBuffer(stream, buffer.get()) < 0) continue;
        requests.push_back(std::move(request));
    }

    camera->requestCompleted.connect(request_complete);

    ret = camera->start();
    if (ret < 0) {
        if (verbose) std::cerr << "Camera::start() failed: " << ret << "\n";
        for (auto &p : mapped_planes) munmap(p.first, p.second);
        delete allocator;
        camera->release();
        cm->stop();
        return 3;
    }

    for (auto &req : requests) {
        camera->queueRequest(req.get());
    }

    // Main capture & streaming loop
    auto start_time = std::chrono::steady_clock::now();
    uint64_t frames_sent = 0;
    std::vector<uint8_t> pack_buf;
    if (stride != ROW_BYTES) {
        pack_buf.resize(FRAME_SIZE);
    }

    while (!g_stop.load()) {
        // Check timeout
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();
        if (max_seconds > 0 && elapsed >= max_seconds) {
            break;
        }

        Request *req = nullptr;
        {
            std::unique_lock<std::mutex> lock(g_queue_mutex);
            if (g_completed_requests.empty()) {
                g_queue_cv.wait_for(lock, std::chrono::milliseconds(50), [&]() {
                    return !g_completed_requests.empty() || g_stop.load();
                });
            }
            if (!g_completed_requests.empty()) {
                req = g_completed_requests.front();
                g_completed_requests.pop();
            }
        }

        if (!req) {
            continue;
        }

        if (req->status() == Request::RequestComplete) {
            FrameBuffer *fb = req->buffers().at(stream);
            auto it = mapped_buffers.find(fb);
            if (it != mapped_buffers.end()) {
                const uint8_t *src = static_cast<const uint8_t *>(it->second);
                bool ok = false;
                if (stride == ROW_BYTES) {
                    ok = write_all(STDOUT_FILENO, src, FRAME_SIZE);
                } else {
                    for (size_t r = 0; r < FRAME_HEIGHT; ++r) {
                        memcpy(&pack_buf[r * ROW_BYTES], src + (r * stride), ROW_BYTES);
                    }
                    ok = write_all(STDOUT_FILENO, pack_buf.data(), FRAME_SIZE);
                }

                if (!ok) {
                    // Pipe closed or write error (e.g. EPIPE)
                    g_stop.store(true);
                    break;
                }

                frames_sent++;
                if (max_frames > 0 && frames_sent >= max_frames) {
                    g_stop.store(true);
                    break;
                }
            }
        }

        req->reuse(Request::ReuseBuffers);
        camera->queueRequest(req);
    }

    // Teardown camera cleanly
    camera->stop();
    requests.clear();

    for (auto &p : mapped_planes) {
        munmap(p.first, p.second);
    }
    mapped_buffers.clear();

    delete allocator;
    camera->release();
    camera.reset();
    cm->stop();

    return (frames_sent > 0 || max_frames == 0) ? 0 : 6;
}
