## 2025-05-18 - Unvalidated Sysfs Torch Paths in Privileged Components
**Vulnerability:** Unvalidated `flash_path` / `--torch` arguments allowed opening arbitrary files (such as `/etc/shadow`) for writing when running with root privileges during PAM authentication.
**Learning:** Configurable sysfs paths for hardware devices (e.g., LED torches or sensor nodes) can lead to arbitrary file corruption or privilege escalation if used directly in `open()` or `write()` without canonical path validation.
**Prevention:** Always resolve paths with `realpath` and verify they reside under `/sys/` (`is_sysfs_path`) before opening files for write operations in privileged daemons or PAM plugins.
