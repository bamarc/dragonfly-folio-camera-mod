# HP Dragonfly Folio 13.5" G3 Linux Camera & IR Enablement

Custom Linux kernel drivers, hardware fixes, and facial authentication tools for the **HP Dragonfly Folio 13.5" G3** (Intel 12th Gen Alder Lake-U15, Intel IPU6 MIPI-CSI2).

This repository enables:
1. **Full RGB Desktop Camera** (OmniVision OV08A10) in PipeWire, Zoom, Teams, WebRTC, and OBS.
2. **Monochrome Near-Infrared Camera** (OmniVision OG0VA1B / OG0VE1B) via libcamera.
3. **Synchronized Active IR Strobe** (Texas Instruments LM3643).
4. **Howdy Facial Authentication** working in 100% total darkness with anti-spoofing protection across `sudo`, SDDM, and the KDE Plasma lock screen.

---

## 🛠️ Hardware Overview

| Component | Hardware Identifier | Linux Interface | Role |
| :--- | :--- | :--- | :--- |
| **RGB Camera** | OmniVision OV08A10 (`OVTI08A1:00`) | `i2c-1` @ `0x36`, IPU6 CSI2-1 (`/dev/video8`) | 8MP High-Resolution Color Webcam |
| **IR Camera** | OmniVision OG0VA1B / OG0VE1B (`OVTI00AB:00`) | `i2c-4` @ `0x60`, IPU6 CSI2-2 (`/dev/video16`) | 640×480 Global-Shutter NIR Sensor |
| **IR Illuminator** | Texas Instruments LM3643 (`TXNW3643:01`) | `i2c-4` @ `0x63`, sysfs class `leds` | 850/940 nm High-Power Flash/Torch LED |
| **Power Controller** | Intel INT3472 Discrete (`INT3472:01`) | GPIO controller & ACPI regulator provider | Powers camera sensors & privacy shutter |
| **Image Signal Processor** | Intel IPU6 ISYS (`8086:465d`) | MIPI CSI-2 receiver & capture DMA engine | Raw CSI-2 frame ingestion |

---

## 🔬 Root Causes & Driver Patches

### 1. `int3472`: Locked GPIO `-EPERM` Regulator Bypass
- **Problem**: On HP Alder Lake platforms, ACPI firmware locks pin 173 (`PADCFG0 = 0x44000300`). Linux `gpiolib` enforces `FLAG_IS_OUT`; attempting to change direction or commit values in standard regulator initialization aborts with `-EPERM` (-1), leaving the sensor unpowered.
- **Fix** ([`drivers/int3472/clk_and_regulator.c`](drivers/int3472/clk_and_regulator.c)): Custom `regulator_ops` decouple the pin from core kernel sanity checks and execute safe best-effort GPIO assertion, allowing sensor rails to power up cleanly.

### 2. `ov08a10`: Privacy Shutter Bus Gating (`-5` / `-EIO`)
- **Problem**: HP wires `gpio-167` (`OVTI08A1_00::privacy_led`) to an internal electronic shutter. When closed (`0`), the sensor is completely disconnected from the I2C bus, causing all transactions to time out with `i2c_designware: controller timed out` (`-EIO` / `-5`).
- **Fix** ([`drivers/ov08a10/ov08a10.c`](drivers/ov08a10/ov08a10.c)): Acquires the privacy LED device and automatically commands it to open (`1`) on `power_on` and close (`0`) on `power_off`.

### 3. `lm3643`: I2C Host Controller Runtime PM Suspend (`-110`)
- **Problem**: The host controller `i2c_designware.4` enters runtime PM suspend when idle. Accessing the LED sysfs node without waking the controller results in an immediate `-110` (`-ETIMEDOUT`).
- **Fix** ([`drivers/lm3643/leds-lm3643.c`](drivers/lm3643/leds-lm3643.c)): Wraps sysfs brightness operations in `pm_runtime_get_sync()` and `pm_runtime_put()` on the parent I2C adapter.

### 4. `tools/ir-grab`: Native libcamera 10-Bit Raw Streamer
- **Problem**: The IR camera outputs 640×480 monochrome 10-bit raw data (`formats::R10`). PipeWire's software ISP and GStreamer debayer modules fail negotiation because they lack monochrome R10 caps.
- **Fix** ([`tools/ir-grab/ir_grab.cpp`](tools/ir-grab/ir_grab.cpp)): A native C++ helper directly accesses the libcamera stream, queries/sets analogue gain (`128`) and exposure (`2000`) on the V4L2 subdevice, turns on the LM3643 strobe, and streams 614,400-byte frames to Howdy.
- **Safety Invariant**: Features death-signal handling (`PR_SET_PDEATHSIG`, SIGTERM), async-signal-safe handlers (`SIGINT`, `SIGTERM`, `SIGHUP`, `SIGPIPE`), and a hard execution timeout to guarantee the IR illuminator is **never left burning** if a process crashes.

---

## 📦 Prerequisites

### openSUSE (Tumbleweed / Slowroll)
```bash
sudo zypper install -y kernel-devel gcc-c++ make meson ninja libcamera-devel
```

### Fedora / RHEL
```bash
sudo dnf install -y kernel-devel gcc-c++ make meson ninja libcamera-devel
```

### Ubuntu / Debian
```bash
sudo apt install -y linux-headers-$(uname -r) g++ make meson ninja-build libcamera-dev
```

---

## 🚀 Installation

### 1. Build and Install Everything
Clone this repository and run the master installer:

```bash
git clone https://github.com/bamarc/dragonfly-folio-camera-mod.git
cd dragonfly-folio-camera-mod
sudo ./install.sh
```

The script will:
1. Compile the 4 custom kernel modules (`intel_skl_int3472_discrete.ko`, `ov08a10.ko`, `og0ve1b.ko`, `leds-lm3643.ko`).
2. Install them to `/lib/modules/$(uname -r)/updates/` (safely taking precedence without overwriting vendor modules).
3. Install the udev rule (`/etc/udev/rules.d/99-lm3643-torch.rules`) allowing group `video` to control the strobe without root elevation.
4. Compile and install `/usr/libexec/howdy/ir-grab`.
5. Install Howdy recorder plugins if Howdy is detected.

### 2. Reboot the System
After initial installation, a clean reboot is required to initialize the IPU6 firmware and load the updated drivers:

```bash
sudo reboot
```

---

## 🖥️ Desktop Camera Setup (PipeWire)

After rebooting, check that PipeWire sees the RGB camera:

```bash
# List video sources
wpctl status | grep -A 10 "Video"

# Set the OV08A10 RGB sensor as your system default camera (replace 112 with your source ID)
wpctl set-default 112
```

Open Cheese, Snapshot, OBS, or a web browser to verify high-definition color video.

---

## 🔒 Howdy IR Facial Authentication Setup

### 1. Configure Howdy
Ensure Howdy is installed, then update `/etc/howdy/config.ini`:

```ini
[video]
# Use the native libcamera IR streamer
recording_plugin = ir_libcamera
ir_grab_path = /usr/libexec/howdy/ir-grab
ir_camera = \_SB_.PC00.LNK1

# Sensor gain and exposure calibrated for IR
ir_gain = 128
ir_exposure = 2000
ir_black_level = 64
ir_normalize = percentile
ir_clahe = false

# Strobe LED control
flash_path = /sys/class/leds/lm3643:torch/brightness
flash_brightness = 60

# Authentication parameters
timeout = 10
dark_threshold = 85
certainty = 3.5
```

### 2. Permissions for KDE Lock Screen
The KDE lock screen (`kscreenlocker_greet`) runs PAM as the logged-in user, not root. Make the model directory group-readable:

```bash
sudo chown root:$USER /etc/howdy/models
sudo chmod 750 /etc/howdy/models
```

### 3. Clear Old Models & Enroll Face Under Active IR
```bash
# Remove any old RGB models
sudo howdy -U $USER clear

# Enroll your face (the IR strobe will illuminate automatically)
sudo howdy -U $USER add
```
*(Tip: Run `sudo howdy -U $USER add` a second time with a slight head tilt or glasses on/off for optimal recognition).*

### 4. Verify Facial Unlock
```bash
# Test sudo authentication
sudo -k && sudo echo "Authenticated by IR face!"
```

### 5. Enable Facial Auth for Polkit, 1Password & pkexec
Modern systemd distributions isolate `polkit-agent-helper` inside a strict sandbox (`PrivateDevices=yes`) that cuts off camera hardware. To enable face unlock for 1Password, `pkexec`, and GUI elevation dialogs:

```bash
sudo ./enable_polkit_howdy.sh
```
This masks `polkit-agent-helper.socket`, causing the desktop Polkit agent to spawn the helper directly with hardware camera permissions. To revert back to password-only Polkit at any time, run:

```bash
sudo ./disable_polkit_howdy.sh
```

---

## ⚠️ Hardware Safety & Invariants

1. **IPU6 Single-Client Concurrency:**  
   Intel IPU6 ISYS firmware does not support multiple processes opening camera nodes simultaneously. If two processes contend for `/dev/video*` or `/dev/media*`, the firmware ring buffer can desynchronize (`wr >= q->size`), causing subsequent streams to fail with `-22` (`-EINVAL`). If this happens, a reboot is required.
2. **Never Unbind IPU6 PCI Device:**  
   Do **NOT** attempt `echo 0000:00:05.0 > /sys/bus/pci/drivers/intel_ipu6/unbind`. Unbinding IPU6 while the subsystem is active triggers a kernel panic (`isys_runtime_pm_suspend` dereferencing NULL `CR2: 0x31c`) and hard-freezes the laptop.

---

## 🔄 Uninstallation

To cleanly revert back to stock kernel drivers:

```bash
sudo ./uninstall.sh
sudo reboot
```

---

## 📄 License
This project is licensed under the **GNU General Public License v2.0** (GPL-2.0). See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments & Upstream Credits

This project builds upon, modifies, and integrates work from the upstream Linux kernel community and open-source projects:

* **Intel Corporation**: For the original `ov08a10` sensor driver (`drivers/media/i2c/ov08a10.c`) and IPU6 camera subsystem architecture.
* **Dan Scally**: For authoring the foundational `intel-skl-int3472` discrete power sequencing driver (`drivers/platform/x86/intel/int3472/`).
* **Linaro Ltd**: For the `og0ve1b` Linux V4L2 sensor driver foundation.
* **libcamera Project**: For modern Linux camera capture APIs, ISP pipelines, and software debayering infrastructure.
* **Boltgolt & Howdy Contributors**: For the Linux facial authentication system.
