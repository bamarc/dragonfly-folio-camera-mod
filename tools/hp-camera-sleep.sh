#!/bin/sh
# hp-camera-sleep.sh - Ensure camera I2C controllers and IPU6 stay active across Modern Standby (s2idle)
# Installed to /usr/lib/systemd/system-sleep/hp-camera-sleep.sh

case "$1/$2" in
  post/*)
    # Ensure PCI power control is active on wake
    for dev in 0000:00:05.0 0000:00:10.1 0000:00:19.0; do
      if [ -f "/sys/bus/pci/devices/$dev/power/control" ]; then
        echo on > "/sys/bus/pci/devices/$dev/power/control" 2>/dev/null || true
      fi
    done
    ;;
esac
