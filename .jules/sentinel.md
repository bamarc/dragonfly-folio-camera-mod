## 2026-03-31 - Privileged Torch Path Writes via Sysfs Traversal
**Vulnerability:** In Howdy PAM authentication, `flash_path` / `torch_path` configuration values were opened and written directly as root without path restriction, enabling arbitrary file overwrite or truncation if configured maliciously or manipulated.
**Learning:** Biometric PAM modules execute with root privileges during user authentication. Any file path retrieved from configuration or device parameters used in file write operations must be strictly validated before opening.
**Prevention:** Restrict torch and brightness sysfs writes by validating `os.path.realpath(path)` against `/sys/` using `_is_safe_sysfs_path`.
