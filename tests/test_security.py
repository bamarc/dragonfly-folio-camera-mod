# test_security.py - Security unit tests for sysfs path validation
import os
import sys
import unittest

from unittest.mock import MagicMock

sys.modules["cv2"] = MagicMock()
sys.modules["i18n"] = MagicMock()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from video_capture import is_safe_sysfs_path


class TestSecuritySysfsValidation(unittest.TestCase):
	def test_invalid_types_and_empty_paths(self):
		"""Empty or non-string paths must be rejected."""
		self.assertFalse(is_safe_sysfs_path(None))
		self.assertFalse(is_safe_sysfs_path(""))
		self.assertFalse(is_safe_sysfs_path(123))
		self.assertFalse(is_safe_sysfs_path([]))

	def test_arbitrary_system_files_rejected(self):
		"""System configuration files must be strictly rejected."""
		self.assertFalse(is_safe_sysfs_path("/etc/passwd"))
		self.assertFalse(is_safe_sysfs_path("/etc/shadow"))
		self.assertFalse(is_safe_sysfs_path("/etc/pam.d/polkit-1"))

	def test_path_traversal_rejected(self):
		"""Directory traversal sequences attempting to break out of /sys/ must be rejected."""
		self.assertFalse(is_safe_sysfs_path("/sys/class/leds/../../etc/passwd"))
		self.assertFalse(is_safe_sysfs_path("/sys/devices/../../tmp/malicious"))

	def test_valid_sysfs_path(self):
		"""Valid sysfs files (if available on system) should pass validation."""
		sys_files = [
			"/sys/class/leds/lm3643:torch/brightness",
			"/sys/devices/system/cpu/online"
		]
		for path in sys_files:
			if os.path.exists(path):
				self.assertTrue(is_safe_sysfs_path(path), f"Path {path} should be recognized as a valid sysfs file")


if __name__ == "__main__":
	unittest.main()
