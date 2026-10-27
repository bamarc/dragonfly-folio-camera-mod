#!/bin/sh
# hp-camera-sleep.sh - Protect Intel IPU6 from sleep/hibernate firmware lockups
# and keep camera LPSS I2C controllers active across Modern Standby (s2idle) / S4.
# Installed to /usr/lib/systemd/system-sleep/hp-camera-sleep.sh

SLEEP_FLAG="/run/hp-camera-sleeping"

case "$1/$2" in
  pre/*)
    # 1. Block Howdy / ir-grab from starting during lock-screen-on-sleep race
    touch "$SLEEP_FLAG" 2>/dev/null || true

    # 2. Terminate any active ir-grab capture immediately and turn off IR strobe
    pkill -TERM -x ir-grab 2>/dev/null || true
    if [ -w /sys/class/leds/lm3643:torch/brightness ]; then
      echo 0 > /sys/class/leds/lm3643:torch/brightness 2>/dev/null || true
    fi

    # 3. Ensure IPU6 (0000:00:05.0) is allowed to runtime-suspend cleanly before sleep
    if [ -f /sys/bus/pci/devices/0000:00:05.0/power/control ]; then
      echo auto > /sys/bus/pci/devices/0000:00:05.0/power/control 2>/dev/null || true
    fi

    # 4. Wait briefly (up to ~500ms) for ir-grab to exit and IPU6 ISYS to close
    for _ in 1 2 3 4 5; do
      if ! pgrep -x ir-grab >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
    done
    ;;

  post/*)
    # 1. Keep LPSS PCI bridges and DesignWare I2C adapters active on wake
    for dev in 0000:00:10.1 0000:00:19.0; do
      if [ -f "/sys/bus/pci/devices/$dev/power/control" ]; then
        echo on > "/sys/bus/pci/devices/$dev/power/control" 2>/dev/null || true
      fi
    done
    for pdev in i2c_designware.1 i2c_designware.4; do
      if [ -f "/sys/bus/platform/devices/$pdev/power/control" ]; then
        echo on > "/sys/bus/platform/devices/$pdev/power/control" 2>/dev/null || true
      fi
    done

    # 2. Ensure IPU6 stays on runtime auto-suspend
    if [ -f /sys/bus/pci/devices/0000:00:05.0/power/control ]; then
      echo auto > /sys/bus/pci/devices/0000:00:05.0/power/control 2>/dev/null || true
    fi

    # 3. Clear sleep flag so Howdy can use the camera again
    rm -f "$SLEEP_FLAG" 2>/dev/null || true
    ;;
esac

