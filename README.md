# HP Dragonfly Folio 13.5" G3 Linux Camera & IR Enablement
[![build result](https://build.opensuse.org/projects/home:gmarc/packages/hp-dragonfly-folio-camera/badge.svg?type=default)](https://build.opensuse.org/package/show/home:gmarc/hp-dragonfly-folio-camera)

Custom Linux kernel drivers, hardware fixes, and facial authentication tools for the **HP Dragonfly Folio 13.5" G3** (Intel 12th Gen Alder Lake-U15, Intel IPU6 MIPI-CSI2).

This repository enables:
1. **Full RGB Desktop Camera** (OmniVision OV08A10) in PipeWire, Zoom, Teams, WebRTC, and OBS.
2. **Monochrome Near-Infrared Camera** (OmniVision OG0VA1B / OG0VE1B) via libcamera.
3. **Synchronized Active IR Strobe** (Texas Instruments LM3643).
4. **Howdy Facial Authentication** working in 100% total darkness with anti-spoofing protection across `sudo`, SDDM, and the KDE Plasma lock screen.
5. **Hardware 3D Anti-Spoofing**: Validates real 3D facial curvature using the $8 \times 8$ ToF grid, stopping photos or phone screens before face matching.
6. **Walk-Away Auto-Lock & Wake on Approach**: Background daemon with KDE Plasma system tray toggle that locks when you leave and wakes the screen as you return.

---

## 🛠️ Hardware Identification & Search Index

| Component | Hardware / Device ID | ACPI / PCI String | Linux Bus / Interface | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Laptop Model** | HP Product ID `8A05` | DMI: `HP Dragonfly Folio 13.5 inch G3 2-in-1 Notebook PC` | Platform | Intel Alder Lake-U15 |
| **Image Processor** | `8086:465d` | PCI: `0000:00:05.0` (`intel_ipu6`) | PCI Express | Intel IPU6 ISYS MIPI CSI-2 |
| **Sensor Hub** | `8086:51fc` | PCI: `0000:00:12.0` (`intel_ish_ipc`) | PCI Express | Intel Integrated Sensor Hub (ISH) |
| **ToF Depth Sensor**| `ST VL53L5` | ISH HID `8087:0AC2` (`HID-SENSOR-2000e1.2`) | `hidraw` | 8x8 multi-zone FlightSense ToF (64 depth zones) |
| **Presence Sensor**| `Biometric Presence` | ISH HID `8087:0AC2` (`HID-SENSOR-2000e1.31`)| `hidraw` | Millimeter proximity & presence confidence |
| **Lattice AI Sensor**| `Lattice NX AI` | ISH HID `8087:0AC2` (`HID-SENSOR-2000e1.7`) | `hidraw` | Ultra-low power neural presence accelerator |
| **RGB Camera** | `OVTI08A1` | ACPI: `\_SB.PC00.LNK0` (`OVTI08A1:00`) | `i2c-1` @ `0x36` | OmniVision OV08A10 (Chip ID `0x560841`) |
| **IR Camera** | `OVTI00AB` | ACPI: `\_SB.PC00.LNK1` (`OVTI00AB:00`) | `i2c-4` @ `0x60` | OmniVision OG0VA1B / OG0VE1B (Global Shutter NIR) |
| **IR Flash Strobe**| `TXNW3643` | ACPI: `TXNW3643:01` (`leds-lm3643`) | `i2c-4` @ `0x63` | Texas Instruments LM3643 Dual IR Torch |
| **Power Controller**| `INT3472` | ACPI: `INT3472:01` (`intel_skl_int3472_discrete`) | Platform | Power sequencing & clk provider |
| **PCH GPIO** | `INTC1055` | ACPI: `INTC1055:00` (`INT3455:00`) | Memory mapped | Pin 173 (`avdd` rail), Pin 167 (privacy shutter) |

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

### 3. Modular RPM Packages via Open Build Service (OBS)
To survive kernel upgrades and system updates (`zypper dup`) cleanly, this repository provides three independent RPM packages:

1. **`hp-presence`** (`noarch`): Walk-away auto-lock, wake daemon, and KDE Plasma tray widget.
2. **`hp-dragonfly-folio-howdy`** (`x86_64`): Native `ir-grab` helper, Howdy camera reader, and 3D Time-of-Flight anti-spoofing verifier.
3. **`hp-dragonfly-folio-camera`** (`x86_64` KMP): Kernel module package for custom camera drivers with weak-updates support.

See [**`packaging/obs/README.md`**](packaging/obs/README.md) for step-by-step OBS/osc setup and local `rpmbuild` instructions.

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

## 🚶 Human Presence Detection, Walk-Away Auto-Lock & 3D Anti-Spoofing

The HP Dragonfly Folio G3 includes an ultra-low-power **STMicroelectronics VL53L5 8×8 Time-of-Flight (ToF)** laser distance sensor and a **Lattice NX AI Sensor** connected to the **Intel Integrated Sensor Hub (ISH)**.

### 1. Hardware 3D Anti-Spoofing for Howdy
Before firing the high-draw IR illuminator and opening the camera, Howdy checks the $8 \times 8$ ToF depth grid:
- **3D Curvature Check**: A flat photo, phone screen, or printed paper held up to the camera has uniform planar depth ($\sigma < 1.0\text{ cm}$). A real human face and head contour has depth curvature $\sigma \ge 1.8\text{ cm}$. Spoofs are rejected instantly.
- **Seated Distance Envelope**: Only triggers when the person is in front of the laptop ($30\text{ cm} \le d \le 85\text{ cm}$).

Configuration in `/etc/howdy/config.ini`:
```ini
[tof_antispoof]
enabled = true
min_distance_cm = 30
max_distance_cm = 85
min_depth_variance_cm = 1.8
require_presence = true
warn_on_fail = true
```

### 2. Walk-Away Auto-Lock & Wake on Approach
A lightweight background daemon (`hp-presence-daemon`) continuously monitors distance via Intel ISH ($< 15\text{ mW}$):
- **Walk-Away Lock**: Automatically locks the screen (`loginctl lock-session`) when you step away for $\ge 10\text{ seconds}$ or move $> 110\text{ cm}$.
- **Wake on Approach**: Automatically powers on the display when you return within seated proximity ($< 80\text{ cm}$), triggering Howdy for **completely hands-free unlock**.
- **KDE Plasma System Tray Applet**: Integrates directly into your KDE system tray:
  - 🟢 **Active**: Click to pause/resume auto-locking.
  - ⚪ **Paused**: Suspends auto-lock (e.g. during presentations or movies). Right-click menu allows pausing for 30m or 1h.

Manage the service:
```bash
# Check status
systemctl --user status hp-presence.service

# View live presence logs
journalctl --user -u hp-presence.service -f
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
