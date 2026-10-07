# Open Build Service (OBS) & RPM Packaging

This directory contains the packaging files to build modular RPM packages for the **HP Dragonfly Folio 13.5" G3** on the [Open Build Service (OBS)](https://build.opensuse.org/) or locally with `rpmbuild`.

---

## 🏛️ Modular Package Architecture

To ensure your setup **reliably survives kernel updates and zypper dup**, the project is split into three independent, self-contained packages:

| Package | Directory | Architecture | Purpose & Update Behavior |
| :--- | :--- | :--- | :--- |
| **`hp-presence`** | [`hp-presence/`](file:///home/marc/antigravity/nifty-volta/hp-dragonfly-folio-g3-linux-camera/packaging/obs/hp-presence) | `noarch` | **Walk-Away Auto-Lock & Wake Daemon + KDE Plasma Tray Applet**.<br>Pure Python userland service (`/usr/libexec/hp-presence`). Survives all kernel updates without recompile. |
| **`hp-folio-daemon`** | [`hp-folio-daemon/`](file:///home/marc/antigravity/nifty-volta/hp-dragonfly-folio-g3-linux-camera/packaging/obs/hp-folio-daemon) | `x86_64` | **Folio Hinge & Display Mode Switch Daemon (Zig)**.<br>Native Zig daemon (`/usr/libexec/hp-folio-daemon`). Emits `SW_TABLET_MODE`, mutes covered keyboard/touchpad, and shows KDE OSD toasts. |
| **`hp-dragonfly-folio-howdy`** | [`hp-dragonfly-folio-howdy/`](file:///home/marc/antigravity/nifty-volta/hp-dragonfly-folio-g3-linux-camera/packaging/obs/hp-dragonfly-folio-howdy) | `x86_64` | **Howdy Integration & 3D ToF Anti-Spoofing**.<br>`ir-grab` helper, `tof_verifier.py`, `ir_libcamera_reader.py`, torch udev rules, Polkit scripts. Independent of kernel version. |
| **`hp-dragonfly-folio-camera`** | [`hp-dragonfly-folio-camera/`](file:///home/marc/antigravity/nifty-volta/hp-dragonfly-folio-g3-linux-camera/packaging/obs/hp-dragonfly-folio-camera) | `x86_64` (KMP) | **Kernel Module Package (KMP)**.<br>Builds `int3472`, `ov08a10`, `og0ve1b`, `lm3643`, `ipu-bridge`. Survives kernel updates via openSUSE **weak-updates** and automatic OBS rebuilds. |

---

## 💡 Why This Survives System Updates

1. **Kernel Updates (`zypper dup`)**:
   - `hp-presence` and `hp-dragonfly-folio-howdy` are strictly userland packages and do not depend on `kernel-default-devel`. They remain active, installed, and functional through any kernel upgrade.
   - `hp-dragonfly-folio-camera-kmp` automatically generates symlinks in `/lib/modules/<new-kernel>/weak-updates/` on kABI-compatible kernel updates, or OBS rebuilds it automatically when a new kernel arrives.
2. **RPM Tracking (`rpm -V`)**:
   - All files, systemd user units, presets, udev rules, and recorder plugins are tracked by the RPM database. System updates will never silently erase or overwrite your configuration.

---

## 🚀 Setting Up on OBS via `osc`

### Step 1: Check Out Your Home Project
```bash
osc checkout home:<your-username>
cd home:<your-username>
```

### Step 2: Create the Packages

#### 1. Presence Daemon (`hp-presence`):
```bash
osc mkpac hp-presence
cd hp-presence
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-presence/* .
osc add *
osc commit -m "Add hp-presence package"
cd ..
```

#### 2. Howdy & ToF Anti-Spoofing (`hp-dragonfly-folio-howdy`):
```bash
osc mkpac hp-dragonfly-folio-howdy
cd hp-dragonfly-folio-howdy
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-dragonfly-folio-howdy/* .
osc add *
osc commit -m "Add hp-dragonfly-folio-howdy package"
cd ..
```

#### 3. Camera Kernel Drivers (`hp-dragonfly-folio-camera`):
```bash
osc mkpac hp-dragonfly-folio-camera
cd hp-dragonfly-folio-camera
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-dragonfly-folio-camera/* .
osc add *
osc commit -m "Add hp-dragonfly-folio-camera KMP package"
cd ..
```

---

## 🛠️ Building Locally with `rpmbuild`

If you want to build and install the RPMs locally right now without waiting for OBS:

```bash
# Prepare rpmbuild directory tree
mkdir -p /tmp/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Build hp-presence (noarch)
tar --exclude-vcs --zstd -cf /tmp/rpmbuild/SOURCES/hp-presence-0.1.0.tar.zst --transform 's,^\.,hp-presence-0.1.0,' .
rpmbuild -ba packaging/obs/hp-presence/hp-presence.spec --define "_topdir /tmp/rpmbuild"

# Build hp-dragonfly-folio-howdy (x86_64)
tar --exclude-vcs --zstd -cf /tmp/rpmbuild/SOURCES/hp-dragonfly-folio-howdy-0.1.0.tar.zst --transform 's,^\.,hp-dragonfly-folio-howdy-0.1.0,' .
rpmbuild -ba packaging/obs/hp-dragonfly-folio-howdy/hp-dragonfly-folio-howdy.spec --define "_topdir /tmp/rpmbuild"

# Install both RPMs with zypper
sudo zypper install --allow-unsigned-rpm \
  /tmp/rpmbuild/RPMS/noarch/hp-presence-*.noarch.rpm \
  /tmp/rpmbuild/RPMS/x86_64/hp-dragonfly-folio-howdy-*.x86_64.rpm
```

---

## 📥 Adding Your OBS Repository to Zypper

Once OBS finishes building:

```bash
# Add your OBS repository:
sudo zypper addrepo -f https://download.opensuse.org/repositories/home:/<your-username>/openSUSE_Tumbleweed/ hp-hardware

# Refresh and install:
sudo zypper refresh
sudo zypper install hp-presence hp-dragonfly-folio-howdy hp-dragonfly-folio-camera hp-dragonfly-folio-camera-kmp-default
```
