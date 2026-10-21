## 2026-03-31 - Unvalidated SUDO_USER Environment Variable Path Traversal
**Vulnerability:** Root helper scripts relying on `$SUDO_USER` to construct paths in `/etc/howdy/models/` without sanitization allowed attackers to pass path traversal strings (e.g., `../../tmp/malicious`). This created symlinks from `/etc/howdy/models/root.dat` to arbitrary attacker-controlled model files, allowing root privilege escalation via Howdy facial authentication.
**Learning:** Environment variables supplied by unprivileged users during `sudo` execution cannot be trusted as clean filesystem names.
**Prevention:** Always validate `$SUDO_USER` and target usernames against a strict regex `^[a-zA-Z0-9_-]+$` and verify `realpath` directory bounds before performing privileged file or symlink operations.
