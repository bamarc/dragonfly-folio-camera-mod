#!/bin/bash
# disable_polkit_howdy.sh - Instantly revert Polkit to stock configuration
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo $0)" >&2
  exit 1
fi

echo "=== 1. Restoring /etc/pam.d/polkit-1 ==="
if [ -f /etc/pam.d/polkit-1.howdy-backup ]; then
    mv -f /etc/pam.d/polkit-1.howdy-backup /etc/pam.d/polkit-1
    echo "Restored original /etc/pam.d/polkit-1 from backup."
else
    rm -f /etc/pam.d/polkit-1
    echo "Removed /etc/pam.d/polkit-1 (system fallback in /usr/lib/pam.d/ active)."
fi

echo "=== 2. Unmasking and starting polkit-agent-helper.socket ==="
systemctl unmask polkit-agent-helper.socket
systemctl start polkit-agent-helper.socket || true

echo "=== 3. Cleaning up root.dat symlink ==="
if [ -L /etc/howdy/models/root.dat ]; then
    rm -f /etc/howdy/models/root.dat
    echo "Removed /etc/howdy/models/root.dat symlink."
fi

echo ""
echo "=== Polkit successfully reverted to stock (sandboxed password authentication) ==="
