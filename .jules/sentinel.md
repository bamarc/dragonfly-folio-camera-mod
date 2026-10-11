## 2025-05-18 - Target User Path Traversal in Polkit Symlink Setup
**Vulnerability:** `enable_polkit_howdy.sh` constructed the Howdy model path `/etc/howdy/models/${TARGET_USER}.dat` directly from `SUDO_USER` without input validation or path canonicalization.
**Learning:** Attacker-controlled environment variables in privilege setup scripts could include relative path components (`..`), pointing `root.dat` to arbitrary face models elsewhere on disk (e.g. `/tmp`) and granting unauthorized root PAM access.
**Prevention:** Always validate username formats against POSIX regex `^[a-zA-Z0-9_][a-zA-Z0-9_.-]*\$?$` and enforce path resolution containment using `realpath` before creating administrative symlinks.
