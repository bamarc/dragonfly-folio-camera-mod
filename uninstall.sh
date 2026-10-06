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
depmod -a

echo "=== 2. Removing Udev Rule ==="
rm -f /etc/udev/rules.d/99-lm3643-torch.rules
udevadm control --reload

echo "=== 3. Removing ir-grab ==="
rm -f /usr/libexec/howdy/ir-grab

echo "=== Uninstallation Complete ==="
echo "Stock vendor modules will be restored on next probe or reboot."
