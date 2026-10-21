# test_polkit_script.py - Unit tests for enable_polkit_howdy.sh security checks
import os
import subprocess
import tempfile
import unittest

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "enable_polkit_howdy.sh"))


class TestPolkitScriptSecurity(unittest.TestCase):
	def setUp(self):
		self.temp_dir = tempfile.TemporaryDirectory()
		self.bin_dir = os.path.join(self.temp_dir.name, "bin")
		self.etc_dir = os.path.join(self.temp_dir.name, "etc")
		os.makedirs(self.bin_dir, exist_ok=True)
		os.makedirs(os.path.join(self.etc_dir, "pam.d"), exist_ok=True)
		os.makedirs(os.path.join(self.etc_dir, "howdy", "models"), exist_ok=True)

		# Create stub binaries in self.bin_dir
		for cmd_name in ["systemctl", "chmod"]:
			stub_path = os.path.join(self.bin_dir, cmd_name)
			with open(stub_path, "w") as f:
				f.write("#!/bin/sh\nexit 0\n")
			os.chmod(stub_path, 0o755)

	def tearDown(self):
		self.temp_dir.cleanup()

	def test_path_traversal_rejection(self):
		"""Test that invalid usernames with path traversal sequences are rejected."""
		invalid_users = [
			"../../tmp/malicious",
			"../evil",
			"/etc/passwd",
			"user/name",
			"user;id",
			"user$NAME",
			"user name",
		]

		for user in invalid_users:
			script_contents = f"""
			export SUDO_USER={user!r}
			sed -e 's/if \\[ "$EUID" -ne 0 \\]; then/if false; then/' \
			    -e 's|/etc/pam.d/polkit-1|{self.etc_dir}/pam.d/polkit-1|g' \
			    -e 's|/etc/howdy/models|{self.etc_dir}/howdy/models|g' "{SCRIPT_PATH}" | bash
			"""

			env = os.environ.copy()
			env["PATH"] = f"{self.bin_dir}:{env['PATH']}"

			proc = subprocess.run(
				["bash", "-c", script_contents],
				env=env,
				capture_output=True,
				text=True
			)
			self.assertNotEqual(proc.returncode, 0, f"Script should reject invalid user: '{user}'")
			self.assertIn("Invalid target username", proc.stderr)

	def test_valid_username_acceptance(self):
		"""Test that valid usernames are accepted."""
		valid_users = ["jules", "user_1", "test-user"]

		for user in valid_users:
			# Create user model file in temp models directory
			model_file = os.path.join(self.etc_dir, "howdy", "models", f"{user}.dat")
			with open(model_file, "w") as f:
				f.write("mock_model_data\n")

			script_contents = f"""
			export SUDO_USER={user!r}
			sed -e 's/if \\[ "$EUID" -ne 0 \\]; then/if false; then/' \
			    -e 's|/etc/pam.d/polkit-1|{self.etc_dir}/pam.d/polkit-1|g' \
			    -e 's|/etc/howdy/models|{self.etc_dir}/howdy/models|g' "{SCRIPT_PATH}" | bash
			"""

			env = os.environ.copy()
			env["PATH"] = f"{self.bin_dir}:{env['PATH']}"

			proc = subprocess.run(
				["bash", "-c", script_contents],
				env=env,
				capture_output=True,
				text=True
			)
			self.assertEqual(proc.returncode, 0, f"Script should accept valid user '{user}'")


if __name__ == "__main__":
	unittest.main()
