#!/bin/bash
# uninstall.sh - Remove HP Dragonfly Folio G3 camera drivers and helper tools
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo ./uninstall.sh)" >&2
  exit 1
fi

KERNELRELEASE="$(uname -r)"
UPDATES_DIR="/lib/modules/${KERNELRELEASE}/updates"

echo "=== 1. Removing Kernel Modules from ${UPDATES_DIR} ==="
rm -f "$UPDATES_DIR/intel_skl_int3472_discrete.ko"
rm -f "$UPDATES_DIR/ov08a10.ko"
rm -f "$UPDATES_DIR/og0ve1b.ko"
rm -f "$UPDATES_DIR/leds-lm3643.ko"
rm -f "$UPDATES_DIR/ipu-bridge.ko"
depmod -a

echo "=== 2. Removing Udev Rules ==="
rm -f /etc/udev/rules.d/99-lm3643-torch.rules
rm -f /etc/udev/rules.d/99-hp-presence.rules
udevadm control --reload

echo "=== 3. Removing ir-grab & Presence Daemon ==="
rm -f /usr/libexec/howdy/ir-grab
rm -rf /usr/libexec/hp-presence
rm -f /usr/lib/systemd/user/hp-presence.service
rm -f /usr/lib64/howdy/recorders/tof_verifier.py /usr/lib/howdy/recorders/tof_verifier.py 2>/dev/null || true

echo "=== Uninstallation Complete ==="
echo "Stock vendor modules will be restored on next probe or reboot."
