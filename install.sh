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
cp "$SCRIPT_DIR/drivers/int3472/intel_skl_int3472_discrete.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/ov08a10/ov08a10.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/og0va1b/og0ve1b.ko" "$UPDATES_DIR/"
cp "$SCRIPT_DIR/drivers/lm3643/leds-lm3643.ko" "$UPDATES_DIR/"
depmod -a
echo "Modules installed and depmod updated."

echo "=== 3. Installing Udev Rule for LM3643 Strobe ==="
cp "$SCRIPT_DIR/udev/99-lm3643-torch.rules" /etc/udev/rules.d/
udevadm control --reload
udevadm trigger -s leds -c change
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

echo "=== 5. Installing Howdy Recorder Plugins (Optional) ==="
if [ -d /usr/lib64/howdy/recorders ]; then
    cp "$SCRIPT_DIR/howdy/recorders/ir_libcamera_reader.py" /usr/lib64/howdy/recorders/
    cp "$SCRIPT_DIR/howdy/recorders/video_capture.py" /usr/lib64/howdy/recorders/
    chmod 0644 /usr/lib64/howdy/recorders/ir_libcamera_reader.py /usr/lib64/howdy/recorders/video_capture.py
    echo "Installed Howdy plugins to /usr/lib64/howdy/recorders/"
fi

echo ""
echo "=== Installation Completed Successfully! ==="
echo "If this is the first time installing, a reboot is recommended to bind all drivers cleanly."
