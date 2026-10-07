# HP Dragonfly Folio G3 - Howdy & 3D ToF Anti-Spoofing (`hp-dragonfly-folio-howdy`)

This directory contains the packaging files for the **`hp-dragonfly-folio-howdy`** RPM package for the [Open Build Service (OBS)](https://build.opensuse.org/).

---

## 🎯 Overview

`hp-dragonfly-folio-howdy` packages the userland facial authentication integration for the **HP Dragonfly Folio 13.5" G3**:
- **Native IR Grabber (`ir-grab`)**: High-performance C++ utility using `libcamera` to capture 10-bit raw IR frames from the OmniVision OG0VA1B / OG0VE1B sensor synchronized with the TI LM3643 infrared LED torch.
- **3D Time-of-Flight Anti-Spoofing (`tof_verifier.py`)**: Interrogates the STMicroelectronics VL53L5 8×8 Time-of-Flight sensor in real time before triggering facial recognition. Rejects 2D flat photographs, tablet screens, and phone displays by measuring facial contour depth variance ($\sigma \ge 1.8\text{ cm}$).
- **Howdy Integration (`ir_libcamera_reader.py`)**: Drop-in custom camera recorder module for Howdy.
- **Hardware Strobe Permissions**: Udev rule for unprivileged `video` group access to the IR torch.
- **System-wide PAM / Polkit Integration**: Ready-to-use scripts to enable facial unlock for `sudo`, lockscreen, and KDE authentication.

---

## 📦 Package Details

- **Name**: `hp-dragonfly-folio-howdy`
- **Architecture**: `x86_64`
- **Build Dependencies**: `gcc-c++`, `libcamera-devel`, `meson`, `ninja`, `pkgconfig(udev)`, `zstd`
- **Runtime Dependencies**: `libcamera`, `python3`, `python3-numpy`, `udev`
- **Recommends**: `howdy`, `hp-dragonfly-folio-camera-kmp`, `hp-presence`
- **Key Files**:
  - `/usr/libexec/howdy/ir-grab`
  - `/usr/lib64/howdy/recorders/ir_libcamera_reader.py`
  - `/usr/lib64/howdy/recorders/tof_verifier.py`
  - `/usr/lib64/howdy/recorders/video_capture.py`
  - `/usr/lib/udev/rules.d/99-lm3643-torch.rules`
  - `/usr/share/howdy/config.ini.example`
  - `/usr/sbin/enable_polkit_howdy.sh`
  - `/usr/sbin/disable_polkit_howdy.sh`

---

## 🚀 Setting Up on OBS via `osc`

### 1. Check out your home project:
```bash
osc checkout home:<your-username>
cd home:<your-username>
```

### 2. Create the package:
```bash
osc mkpac hp-dragonfly-folio-howdy
cd hp-dragonfly-folio-howdy
```

### 3. Copy packaging files:
```bash
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-dragonfly-folio-howdy/* .
```

### 4. Commit to OBS:
```bash
osc add *
osc commit -m "Add hp-dragonfly-folio-howdy package"
```

OBS will build `ir-grab` with `meson`/`ninja` and publish the `x86_64` RPM.

---

## 🛠️ Local Build (Without OBS)

You can build the RPM locally at any time:
```bash
mkdir -p /tmp/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
tar --exclude-vcs --zstd -cf /tmp/rpmbuild/SOURCES/hp-dragonfly-folio-howdy-0.1.0.tar.zst --transform 's,^\.,hp-dragonfly-folio-howdy-0.1.0,' .
rpmbuild -ba packaging/obs/hp-dragonfly-folio-howdy/hp-dragonfly-folio-howdy.spec --define "_topdir /tmp/rpmbuild"

# Install generated RPM:
sudo zypper install /tmp/rpmbuild/RPMS/x86_64/hp-dragonfly-folio-howdy-*.x86_64.rpm
```
