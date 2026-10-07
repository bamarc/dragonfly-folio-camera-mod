#!/bin/bash
# install.sh - Build and install HP Dragonfly Folio G3 camera drivers, udev rules & tools
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo ./install.sh)" >&2
  exit 1
fi

KERNELRELEASE="$(uname -r)"
UPDATES_DIR="/lib/modules/${KERNELRELEASE}/updates"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1. Building Kernel Modules ==="
make -C "$SCRIPT_DIR" modules

echo "=== 2. Installing Kernel Modules to ${UPDATES_DIR} ==="
mkdir -p "$UPDATES_DIR"

# Create a safety backup of existing module binaries if present
BACKUP_DIR="${UPDATES_DIR}/.backup-$(date +%Y%m%d-%H%M%S)"
HAS_EXISTING=0
for mod in intel_skl_int3472_discrete.ko ov08a10.ko og0ve1b.ko leds-lm3643.ko ipu-bridge.ko; do
    if [ -f "${UPDATES_DIR}/${mod}" ]; then
        if [ "$HAS_EXISTING" -eq 0 ]; then
            mkdir -p "$BACKUP_DIR"
            HAS_EXISTING=1
        fi
        cp -a "${UPDATES_DIR}/${mod}" "$BACKUP_DIR/"
    fi
done
if [ "$HAS_EXISTING" -eq 1 ]; then
    echo "Backed up existing modules to ${BACKUP_DIR}"
fi

cp "$SCRIPT_DIR/drivers/int3472/intel_skl_int3472_discrete.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/ov08a10/ov08a10.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/og0va1b/og0ve1b.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/lm3643/leds-lm3643.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/ipu-bridge/ipu-bridge.ko" "$UPDATES_DIR/"
depmod -a
echo "Modules installed and depmod updated."

echo "=== 3. Installing Udev Rules for Strobe & Presence Sensors ==="
cp "$SCRIPT_DIR/udev/99-lm3643-torch.rules" /etc/udev/rules.d/
cp "$SCRIPT_DIR/udev/99-hp-presence.rules" /etc/udev/rules.d/
udevadm control --reload
udevadm trigger -s leds -c change
udevadm trigger --subsystem-match=hidraw
udevadm trigger --subsystem-match=platform
if [ -f /sys/class/leds/lm3643:torch/brightness ]; then
    chgrp video /sys/class/leds/lm3643:torch/brightness || true
    chmod 0664 /sys/class/leds/lm3643:torch/brightness || true
fi

echo "=== 4. Building and Installing ir-grab ==="
if command -v meson >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1; then
    make -C "$SCRIPT_DIR" ir-grab
    mkdir -p /usr/libexec/howdy
    cp "$SCRIPT_DIR/tools/ir-grab/build/ir-grab" /usr/libexec/howdy/ir-grab
    chmod 0755 /usr/libexec/howdy/ir-grab
    chown root:root /usr/libexec/howdy/ir-grab
    echo "ir-grab installed to /usr/libexec/howdy/ir-grab"
else
    echo "Warning: meson or ninja not found. Skipped ir-grab build."
    echo "Install meson, ninja, and libcamera-devel to build ir-grab."
fi

echo "=== 5. Installing Howdy Recorder Plugins & 3D Anti-Spoofing ==="
HOWDY_RECORDER_DIRS=(/usr/lib64/howdy/recorders /usr/lib/howdy/recorders)
INSTALLED_HOWDY=0
for rdir in "${HOWDY_RECORDER_DIRS[@]}"; do
    if [ -d "$rdir" ]; then
        cp "$SCRIPT_DIR/howdy/recorders/ir_libcamera_reader.py" "$rdir/"
        cp "$SCRIPT_DIR/howdy/recorders/tof_verifier.py" "$rdir/"
        cp "$SCRIPT_DIR/howdy/recorders/video_capture.py" "$rdir/"
        chmod 0644 "$rdir/ir_libcamera_reader.py" "$rdir/tof_verifier.py" "$rdir/video_capture.py"
        echo "Installed Howdy plugins to $rdir"
        INSTALLED_HOWDY=1
    fi
done
if [ "$INSTALLED_HOWDY" -eq 0 ]; then
    echo "Note: Howdy recorder directory not found. Skipped plugin installation."
fi

echo "=== 6. Installing HP Presence Daemon & User Service ==="
mkdir -p /usr/libexec/hp-presence
cp "$SCRIPT_DIR/tools/hp-presence/hp_presence_daemon.py" /usr/libexec/hp-presence/hp_presence_daemon.py
chmod 0755 /usr/libexec/hp-presence/hp_presence_daemon.py
chown root:root /usr/libexec/hp-presence/hp_presence_daemon.py

mkdir -p /usr/lib/systemd/user
cp "$SCRIPT_DIR/tools/hp-presence/hp-presence.service" /usr/lib/systemd/user/hp-presence.service
chmod 0644 /usr/lib/systemd/user/hp-presence.service

if [ -n "$SUDO_USER" ]; then
    USER_ID="$(id -u "$SUDO_USER")"
    if [ -d "/run/user/${USER_ID}" ]; then
        sudo -u "$SUDO_USER" XDG_RUNTIME_DIR="/run/user/${USER_ID}" systemctl --user daemon-reload || true
        sudo -u "$SUDO_USER" XDG_RUNTIME_DIR="/run/user/${USER_ID}" systemctl --user enable hp-presence.service || true
        echo "Enabled hp-presence.service for user $SUDO_USER"
    fi
fi

echo ""
echo "=== Installation Completed Successfully! ==="
echo "If this is the first time installing, a reboot is recommended to bind all drivers cleanly."

