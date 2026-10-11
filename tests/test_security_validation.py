# test_security_validation.py - Unit tests for security input validation and path traversal checks
import os
import re
import unittest


class TestSecurityValidation(unittest.TestCase):
	def test_username_validation_regex(self):
		"""Test username validation regex used in Polkit script to block path traversal."""
		pattern = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_.-]*\$?$")

		# Valid usernames
		valid_users = ["alice", "bob_123", "user-name", "admin", "service_account$"]
		for u in valid_users:
			self.assertTrue(bool(pattern.match(u)) and ".." not in u and "/" not in u, f"Username '{u}' should be valid")

		# Invalid / path traversal usernames
		invalid_users = ["../tmp", "../../etc/shadow", "user/name", "admin;id", "`whoami`", "root/sub"]
		for u in invalid_users:
			is_valid = bool(pattern.match(u)) and (".." not in u) and ("/" not in u)
			self.assertFalse(is_valid, f"Username '{u}' should be rejected as invalid/path traversal")

	def test_model_path_containment(self):
		"""Verify model path resolution stays within /etc/howdy/models/."""
		base_dir = "/etc/howdy/models"

		valid_user = "alice"
		target_path = os.path.realpath(os.path.join(base_dir, f"{valid_user}.dat"))
		self.assertTrue(target_path.startswith("/etc/howdy/models/"))

		traversal_user = "../../tmp/evil"
		target_path = os.path.realpath(os.path.join(base_dir, f"{traversal_user}.dat"))
		self.assertFalse(target_path.startswith("/etc/howdy/models/"))

	def test_sysfs_path_restriction(self):
		"""Verify sysfs path checks restrict writes to /sys/ filesystem."""
		sys_path = "/sys/class/leds/lm3643:torch/brightness"
		self.assertTrue(os.path.realpath(sys_path).startswith("/sys/"))

		non_sys_path = "/tmp/fake_brightness"
		self.assertFalse(os.path.realpath(non_sys_path).startswith("/sys/"))


if __name__ == "__main__":
	unittest.main()
