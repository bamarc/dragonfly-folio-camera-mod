## 2025-05-18 - Privileged Sysfs Torch Path Validation
**Vulnerability:** Invoking sysfs write helpers (`ir-grab` and `ir_libcamera_reader.py`) with arbitrary user-supplied paths could truncate or overwrite sensitive files as root during PAM authentication.
**Learning:** Utilities running as root via PAM or Polkit that take device sysfs path arguments must restrict writes exclusively to `/sys/` paths and block relative path traversal (`..`).
**Prevention:** Validate all sysfs target path arguments to ensure they start with `/sys/` and do not contain `..` before attempting to open for writing.
