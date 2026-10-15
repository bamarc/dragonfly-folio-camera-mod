## 2025-05-18 - [Sysfs Path Validation for LED Torch Controls]
**Vulnerability:** Howdy authentication plugins run with root privileges under PAM. Writing flash/torch LED brightness to `flash_path` / `torch_path` without sysfs path validation allowed potential arbitrary file truncation/overwrites if configured with non-sysfs paths.
**Learning:** Signal handlers in C++ utilities (e.g. `emergency_torch_off()`) must remain strictly async-signal-safe and cannot invoke `realpath()`. Path validation must occur at configuration/startup before populating global path buffers.
**Prevention:** Always validate that target hardware paths resolve (`realpath`) under `/sys/` before opening and writing, and pre-validate paths in C++ prior to signal handler setup.
