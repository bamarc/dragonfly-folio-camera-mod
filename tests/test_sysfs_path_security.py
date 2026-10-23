# test_sysfs_path_security.py - Unit tests for sysfs torch path safety validation
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from ir_libcamera_reader import _is_safe_sysfs_path as ir_is_safe_sysfs_path
from video_capture import _is_safe_sysfs_path as vc_is_safe_sysfs_path


class TestSysfsPathSecurity(unittest.TestCase):
	def test_unsafe_paths_rejected(self):
		"""Verify that non-sysfs paths and path traversal attempts are rejected."""
		unsafe_paths = [
			"/etc/shadow",
			"/etc/passwd",
			"/tmp/malicious.txt",
			"../../etc/shadow",
			"/sys/../etc/passwd",
			"",
			None,
			123,
			"/dev/null",
		]

		for path in unsafe_paths:
			self.assertFalse(
				ir_is_safe_sysfs_path(path),
				f"ir_libcamera_reader should reject unsafe path: {path}"
			)
			self.assertFalse(
				vc_is_safe_sysfs_path(path),
				f"video_capture should reject unsafe path: {path}"
			)

	def test_valid_sysfs_path_accepted(self):
		"""Verify that valid existing /sys/ files are accepted."""
		# Test with an existing /sys/ path if available (e.g. /sys/class or /sys/kernel)
		sys_files = [
			"/sys/class/leds/lm3643:torch/brightness",
			"/sys/kernel/uevent_seqnum",
		]
		for path in sys_files:
			if os.path.exists(path):
				self.assertTrue(ir_is_safe_sysfs_path(path))
				self.assertTrue(vc_is_safe_sysfs_path(path))


if __name__ == "__main__":
	unittest.main()
