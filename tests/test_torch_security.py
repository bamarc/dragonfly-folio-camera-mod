# test_torch_security.py - Unit tests for torch/flash sysfs path security validation
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from ir_libcamera_reader import is_sysfs_path as is_sysfs_path_ir
from video_capture import is_sysfs_path as is_sysfs_path_vc


class TestTorchPathSecurity(unittest.TestCase):
	def test_valid_sysfs_paths(self):
		"""Verify sysfs paths are permitted."""
		self.assertTrue(is_sysfs_path_ir("/sys/class/leds/lm3643:torch/brightness"))
		self.assertTrue(is_sysfs_path_vc("/sys/class/leds/lm3643:torch/brightness"))
		self.assertTrue(is_sysfs_path_ir("/sys/devices/virtual/leds/lm3643:torch/brightness"))

	def test_non_sysfs_paths_rejected(self):
		"""Verify arbitrary files outside /sys/ are rejected."""
		self.assertFalse(is_sysfs_path_ir("/etc/passwd"))
		self.assertFalse(is_sysfs_path_vc("/etc/shadow"))
		self.assertFalse(is_sysfs_path_ir("/tmp/malicious_file"))
		self.assertFalse(is_sysfs_path_vc("/var/log/syslog"))

	def test_invalid_types_and_empty(self):
		"""Verify empty strings, None, and non-string inputs are rejected."""
		self.assertFalse(is_sysfs_path_ir(""))
		self.assertFalse(is_sysfs_path_vc(None))
		self.assertFalse(is_sysfs_path_ir(123))


if __name__ == "__main__":
	unittest.main()
