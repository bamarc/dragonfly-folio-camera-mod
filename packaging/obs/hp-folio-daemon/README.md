# HP Dragonfly Folio G3 - Folio Hinge Daemon (`hp-folio-daemon`)

This directory contains the packaging files for the **`hp-folio-daemon`** RPM package for the [Open Build Service (OBS)](https://build.opensuse.org/).

---

## 🎯 Overview

`hp-folio-daemon` is a high-performance, native background daemon written in **Zig** for the **HP Dragonfly Folio 13.5" G3**:
- **Display Mode Detection**: Real-time relative orientation quaternion filtering to detect Clamshell Laptop, Stage (Media notch), and Flat Tablet modes.
- **Wayland / KDE Plasma 6 Integration**: Emits Linux kernel `SW_TABLET_MODE` switch events via `/dev/uinput` to natively trigger Plasma touch targets, auto-rotation, and virtual keyboard.
- **Hardware Protection**: Dynamically writes to `/sys/class/input/input*/inhibited` to mute the physical keyboard and touchpad when folded/covered, eliminating ghost touches.
- **KDE OSD Bezel Toasts**: Pops up native KDE Plasma on-screen display toasts (`org.kde.osdService`) on mode switches across all active desktop sessions.
- **Zero Overhead**: ~37 KB compiled binary, <800 KB RAM consumption, 0% idle CPU.

---

## 📦 Package Details

- **Name**: `hp-folio-daemon`
- **Architecture**: `x86_64`
- **Build Dependencies**: `zig`, `pkgconfig(systemd)`, `pkgconfig(udev)`, `zstd`
- **Runtime Dependencies**: `systemd`, `udev`
- **Key Files**:
  - `/usr/libexec/hp-folio-daemon`
  - `/usr/lib/systemd/system/hp-folio-daemon.service`

---

## 🚀 Setting Up on OBS via `osc`

### 1. Check out your home project:
```bash
osc checkout home:<your-username>
cd home:<your-username>
```

### 2. Create the package:
```bash
osc mkpac hp-folio-daemon
cd hp-folio-daemon
```

### 3. Copy packaging files:
```bash
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-folio-daemon/* .
```

### 4. Commit to OBS:
```bash
osc add *
osc commit -m "Add hp-folio-daemon package for HP Dragonfly Folio G3"
```

OBS will automatically pull the Git repository, compile the Zig binary, and publish the `x86_64` RPM.

---

## 🛠️ Local Build (Without OBS)

You can build the RPM locally with `rpmbuild`:
```bash
mkdir -p /tmp/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
tar --exclude-vcs --zstd -cf /tmp/rpmbuild/SOURCES/hp-folio-daemon-0.1.0.tar.zst --transform 's,^\.,hp-folio-daemon-0.1.0,' .
rpmbuild -ba packaging/obs/hp-folio-daemon/hp-folio-daemon.spec --define "_topdir /tmp/rpmbuild"

# Install generated RPM:
sudo zypper install /tmp/rpmbuild/RPMS/x86_64/hp-folio-daemon-*.x86_64.rpm
```
