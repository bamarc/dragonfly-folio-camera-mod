#!/bin/bash
# enable_polkit_howdy.sh - Enable Howdy IR facial authentication for Polkit & 1Password
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo $0)" >&2
  exit 1
fi

echo "=== 1. Masking polkit-agent-helper.socket to bypass systemd device sandbox ==="
systemctl stop polkit-agent-helper.socket || true
systemctl mask polkit-agent-helper.socket

echo "=== 2. Configuring /etc/pam.d/polkit-1 with pam_howdy ==="
# Preserve pre-existing PAM configuration if present
if [ -f /etc/pam.d/polkit-1 ] && [ ! -f /etc/pam.d/polkit-1.howdy-backup ]; then
    cp -a /etc/pam.d/polkit-1 /etc/pam.d/polkit-1.howdy-backup
    echo "Backed up existing /etc/pam.d/polkit-1 to /etc/pam.d/polkit-1.howdy-backup"
fi

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
TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
if [ "$TARGET_USER" = "root" ]; then
    # If run in pure root shell, pick first available non-root user model
    DETECTED_MODEL="$(find /etc/howdy/models -maxdepth 1 -name '*.dat' ! -name 'root.dat' 2>/dev/null | head -n 1)"
    if [ -n "$DETECTED_MODEL" ]; then
        TARGET_USER="$(basename "$DETECTED_MODEL" .dat)"
    fi
fi

USER_MODEL="/etc/howdy/models/${TARGET_USER}.dat"
if [ -f "$USER_MODEL" ]; then
    if [ ! -e /etc/howdy/models/root.dat ]; then
        ln -s "$USER_MODEL" /etc/howdy/models/root.dat
        echo "Created symlink: /etc/howdy/models/root.dat -> $USER_MODEL"
    else
        echo "Root model /etc/howdy/models/root.dat already exists."
    fi
else
    echo "Warning: Model file $USER_MODEL not found."
    echo "Please enroll your face by running: sudo howdy -U $TARGET_USER add"
fi

echo ""
echo "=== Polkit IR Setup Complete! ==="
echo "You can now test:"
echo "  1. In terminal: pkexec whoami"
echo "  2. In 1Password: Unlock with System Authentication"
echo ""
echo "If you wish to revert at any time, run:"
echo "  sudo ./disable_polkit_howdy.sh"
