#!/bin/bash
# revert_experiment_polkit.sh - Instantly revert Polkit to stock password-only configuration
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g. sudo $0)" >&2
  exit 1
fi

echo "=== 1. Removing /etc/pam.d/polkit-1 ==="
rm -f /etc/pam.d/polkit-1

echo "=== 2. Unmasking and starting polkit-agent-helper.socket ==="
systemctl unmask polkit-agent-helper.socket
systemctl start polkit-agent-helper.socket

echo ""
echo "=== Polkit successfully reverted to stock (sandboxed password authentication) ==="
