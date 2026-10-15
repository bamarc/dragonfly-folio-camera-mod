# test_flash_path_security.py - Unit tests for flash/torch sysfs path safety checks
import configparser
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from ir_libcamera_reader import ir_libcamera_reader


class TestFlashPathSecurity(unittest.TestCase):
	def test_non_sysfs_torch_path_rejected(self):
		"""Verify that a non-sysfs flash_path setting in config is safely sanitized."""
		with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
			tmp_file.write("sensitive data\n")
			tmp_path = tmp_file.name

		try:
			config = configparser.ConfigParser()
			config.add_section("video")
			config.set("video", "flash_path", tmp_path)
			config.set("video", "recording_plugin", "ir_libcamera")

			reader = ir_libcamera_reader(config)
			self.assertNotEqual(reader.torch_path, tmp_path, "Non-sysfs path should be rejected and reset to safe fallback")
			self.assertTrue(reader.torch_path.startswith("/sys/"), "Torch path must be under /sys/")

			# Ensure file content was not overwritten
			with open(tmp_path, "r") as f:
				content = f.read()
			self.assertEqual(content, "sensitive data\n", "Target file should not be modified")
		finally:
			if os.path.exists(tmp_path):
				os.remove(tmp_path)


if __name__ == "__main__":
	unittest.main()
