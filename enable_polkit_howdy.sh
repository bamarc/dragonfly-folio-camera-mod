#!/bin/bash
# experiment_enable_polkit_howdy.sh - Enable Howdy IR facial authentication for Polkit & 1Password
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo $0)" >&2
  exit 1
fi

echo "=== 1. Masking polkit-agent-helper.socket to bypass systemd device sandbox ==="
systemctl stop polkit-agent-helper.socket || true
systemctl mask polkit-agent-helper.socket

echo "=== 2. Configuring /etc/pam.d/polkit-1 with pam_howdy ==="
cat << 'EOF' > /etc/pam.d/polkit-1
#%PAM-1.0
auth       sufficient   pam_howdy.so
auth       include      common-auth
account    include      common-account
password   include      common-password
session    include      common-session
session    optional     pam_keyinit.so revoke [force]
EOF
chmod 0644 /etc/pam.d/polkit-1

echo "=== 3. Ensuring root.dat symlink exists for pkexec ==="
if [ ! -e /etc/howdy/models/root.dat ]; then
    ln -s /etc/howdy/models/marc.dat /etc/howdy/models/root.dat
fi

echo ""
echo "=== Experiment Setup Complete! ==="
echo "You can now test:"
echo "  1. In terminal: pkexec whoami"
echo "  2. In 1Password: Unlock with System Authentication"
echo ""
echo "If you wish to revert at any time, run:"
echo "  sudo ./revert_experiment_polkit.sh"
