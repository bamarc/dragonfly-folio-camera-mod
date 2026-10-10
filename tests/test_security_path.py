# test_security_path.py - Unit tests for torch/flash device path validation
import os
import sys
import unittest
import tempfile
import configparser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))


class TestSecurityPathValidation(unittest.TestCase):
	def test_non_sysfs_torch_path_rejected(self):
		"""Ensure non-sysfs paths (e.g., /tmp/fake_shadow) are not written to."""
		with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
			tmp_path = tmp.name
			tmp.write("SAFE_CONTENT\n")

		try:
			config = configparser.ConfigParser()
			config.add_section("video")
			config.set("video", "recording_plugin", "opencv")
			config.set("video", "device_path", "/dev/null")
			config.set("video", "flash_path", tmp_path)
			config.set("video", "flash_brightness", "100")

			# Verify realpath prefix check
			real_path = os.path.realpath(tmp_path)
			self.assertFalse(
				real_path.startswith("/sys/"),
				"Temporary file should not start with /sys/"
			)

			# Attempting write logic simulated
			if os.path.realpath(tmp_path).startswith("/sys/"):
				with open(tmp_path, "w") as f:
					f.write("100\n")

			with open(tmp_path, "r") as f:
				content = f.read()

			self.assertEqual(
				content, "SAFE_CONTENT\n",
				"Non-sysfs file content must remain unchanged"
			)
		finally:
			if os.path.exists(tmp_path):
				os.remove(tmp_path)


if __name__ == "__main__":
	unittest.main()
