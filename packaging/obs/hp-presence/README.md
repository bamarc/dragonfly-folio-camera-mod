# HP Dragonfly Folio G3 - Human Presence & Auto-Lock (`hp-presence`)

This directory contains the packaging files for the **`hp-presence`** RPM package for the [Open Build Service (OBS)](https://build.opensuse.org/).

---

## 🎯 Overview

`hp-presence` is a lightweight, pure-Python (`noarch`) background service for the **HP Dragonfly Folio 13.5" G3**:
- **Walk-Away Auto-Lock**: Automatically locks the desktop session when you step away from the laptop.
- **Wake on Approach**: Automatically awakens the screen when you return so Howdy facial recognition can immediately unlock.
- **KDE Plasma System Tray**: Native StatusNotifierItem with live distance readout, pause timers (30 min / 1 hr), toggle button, and quick quit.
- **Intel ISH Integration**: Communicates directly with the built-in ST VL53L5 Time-of-Flight sensor and Biometric Presence Sensor via userspace hidraw nodes (no custom kernel driver required).

---

## 📦 Package Details

- **Name**: `hp-presence`
- **Architecture**: `noarch`
- **Dependencies**: `python3`, `python3-gobject`, `python3-dbus-python`, `udev`, `systemd`
- **Recommends**: `howdy` (for facial unlock on approach)
- **Key Files**:
  - `/usr/libexec/hp-presence/hp_presence_daemon.py`
  - `/usr/lib/systemd/user/hp-presence.service`
  - `/usr/lib/systemd/user-preset/90-hp-presence.preset`
  - `/usr/lib/udev/rules.d/99-hp-presence.rules`
  - `/etc/hp-presence/config.ini`
  - `/usr/share/applications/hp-presence.desktop`

---

## 🚀 Setting Up on OBS via `osc`

### 1. Check out your home project:
```bash
osc checkout home:<your-username>
cd home:<your-username>
```

### 2. Create the package:
```bash
osc mkpac hp-presence
cd hp-presence
```

### 3. Copy packaging files:
```bash
cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/hp-presence/* .
```

### 4. Commit to OBS:
```bash
osc add *
osc commit -m "Add hp-presence package for HP Dragonfly Folio G3"
```

OBS will automatically pull the Git repository, package the daemon, and publish the `noarch` RPM in under a minute.

---

## 🛠️ Local Build (Without OBS)

You can build the RPM locally at any time:
```bash
mkdir -p /tmp/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
tar --exclude-vcs --zstd -cf /tmp/rpmbuild/SOURCES/hp-presence-0.1.0.tar.zst --transform 's,^\.,hp-presence-0.1.0,' .
rpmbuild -ba packaging/obs/hp-presence/hp-presence.spec --define "_topdir /tmp/rpmbuild"

# Install generated RPM:
sudo zypper install /tmp/rpmbuild/RPMS/noarch/hp-presence-*.noarch.rpm
```
