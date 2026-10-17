## 2026-03-30 - Sysfs Path Traversal in PAM Root Execution
**Vulnerability:** User-configurable `flash_path` / `torch_path` options were opened in write mode (`open(path, "w")`) by Howdy recorder plugins running as root during PAM authentication, creating an arbitrary file write/truncation risk.
**Learning:** Configurable device sysfs paths used by PAM authentication drivers must be validated using canonical `os.path.realpath` / `realpath()` resolution to ensure they reside strictly within allowed sysfs hierarchies (`/sys/class/leds/`, `/sys/devices/`, `/sys/bus/`).
**Prevention:** Always validate configured path attributes against an explicit sysfs path prefix whitelist prior to file write operations in root contexts.
