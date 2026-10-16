## 2025-05-18 - Sysfs Path Validation for Root LED Control
**Vulnerability:** Unsanitized `flash_path` and `torch_path` configuration values allowed potential arbitrary file truncation when Howdy recorder plugins ran with root privileges during PAM authentication.
**Learning:** Configurable device paths accessed by PAM processes running as root can be manipulated if opened in write (`"w"`) mode without validating that the realpath resolves strictly within the sysfs (`/sys/`) subsystem.
**Prevention:** Always verify using `os.path.realpath(path).startswith("/sys/")` before opening sysfs control nodes for writing under root context.
