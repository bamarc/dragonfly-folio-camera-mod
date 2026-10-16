# test_path_validation.py - Unit tests for sysfs path sanitization
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from video_capture import _is_safe_sysfs_path as vc_is_safe_sysfs_path
from ir_libcamera_reader import _is_safe_sysfs_path as ir_is_safe_sysfs_path


class TestPathValidation(unittest.TestCase):
	def test_valid_sysfs_paths(self):
		"""sysfs paths like /sys/class or /sys/bus should be validated as safe."""
		if os.path.exists("/sys/class"):
			self.assertTrue(vc_is_safe_sysfs_path("/sys/class"))
			self.assertTrue(ir_is_safe_sysfs_path("/sys/class"))

	def test_invalid_non_sysfs_paths(self):
		"""Paths outside /sys/ must be rejected."""
		for path in ["/etc/passwd", "/tmp", "/dev/null", "/bin/bash"]:
			if os.path.exists(path):
				self.assertFalse(vc_is_safe_sysfs_path(path), f"Should reject {path}")
				self.assertFalse(ir_is_safe_sysfs_path(path), f"Should reject {path}")

	def test_nonexistent_or_invalid_types(self):
		"""Non-existent paths or non-string inputs must be rejected."""
		self.assertFalse(vc_is_safe_sysfs_path("/sys/class/nonexistent_led_device_12345"))
		self.assertFalse(vc_is_safe_sysfs_path(""))
		self.assertFalse(vc_is_safe_sysfs_path(None))
		self.assertFalse(vc_is_safe_sysfs_path(123))

		self.assertFalse(ir_is_safe_sysfs_path("/sys/class/nonexistent_led_device_12345"))
		self.assertFalse(ir_is_safe_sysfs_path(""))
		self.assertFalse(ir_is_safe_sysfs_path(None))
		self.assertFalse(ir_is_safe_sysfs_path(123))


if __name__ == "__main__":
	unittest.main()
