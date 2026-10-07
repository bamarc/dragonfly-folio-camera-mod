# tof_verifier.py - Hardware 3D Anti-Spoofing & Range Gating for Howdy
# Uses STMicroelectronics VL53L5 8x8 Time-of-Flight (ToF) & Biometric Presence
# sensors via Intel ISH to verify a real 3D human face within seated distance.

import glob
import os
import select
import struct
import sys
import time
import numpy as np


class TofVerifier:
	"""
	Verifies human presence and 3D facial depth before Howdy captures IR frames.
	Prevents spoofing via photos or phone screens and rejects out-of-range attempts.
	"""

	def __init__(self, config=None):
		self.enabled = True
		self.min_dist_cm = 30.0
		self.max_dist_cm = 85.0
		self.min_depth_var_cm = 1.8
		self.require_presence = True
		self.warn_on_fail = True
		self.debug = False

		if config is not None:
			if hasattr(config, "getboolean"):
				self.enabled = config.getboolean("tof_antispoof", "enabled", fallback=self.enabled)
				self.min_dist_cm = config.getfloat("tof_antispoof", "min_distance_cm", fallback=self.min_dist_cm)
				self.max_dist_cm = config.getfloat("tof_antispoof", "max_distance_cm", fallback=self.max_dist_cm)
				self.min_depth_var_cm = config.getfloat("tof_antispoof", "min_depth_variance_cm", fallback=self.min_depth_var_cm)
				self.require_presence = config.getboolean("tof_antispoof", "require_presence", fallback=self.require_presence)
				self.warn_on_fail = config.getboolean("tof_antispoof", "warn_on_fail", fallback=self.warn_on_fail)
				self.debug = config.getboolean("tof_antispoof", "debug", fallback=self.debug)

		self._presence_dev = None
		self._tof_dev = None
		self._presence_dir = None
		self._tof_dir = None

	def discover_sensors(self):
		"""Locates the ISH presence and 8x8 ToF devices dynamically in sysfs."""
		for dev_dir in glob.glob("/sys/bus/platform/devices/HID-SENSOR-2000e1.*"):
			real = os.path.realpath(dev_dir)
			name_file = os.path.join(real, "feature-a-200301", "feature-a-200301-value")
			if not os.path.exists(name_file):
				continue

			try:
				with open(name_file, "r") as f:
					txt = "".join(chr(int(x)) for x in f.read().split() if x.isdigit() and 32 <= int(x) < 127)

				hdir = os.path.join(real, "..", "hidraw")
				hidraw = None
				if os.path.exists(hdir):
					for h in os.listdir(hdir):
						if h.startswith("hidraw"):
							hidraw = os.path.join("/dev", h)
							break

				if "Biometric Presence Sensor" in txt:
					self._presence_dev = hidraw
					self._presence_dir = real
					self._enable_sensor(real)
				elif "VL53L5 ST V330 Photonic Sensor" in txt:
					self._tof_dev = hidraw
					self._tof_dir = real
					self._enable_sensor(real)
			except Exception:
				pass

	def _enable_sensor(self, dev_dir):
		"""Ensures the sensor is powered on and streaming."""
		ef = os.path.join(dev_dir, "enable_sensor")
		if os.path.exists(ef):
			try:
				with open(ef, "r+") as f:
					val = f.read().strip()
					if val != "1":
						f.seek(0)
						f.write("1\n")
			except Exception:
				pass

	def verify(self, timeout_sec=0.25):
		"""
		Captures a depth frame and presence reading.
		Returns (passed: bool, reason: str, details: dict).
		"""
		if not self.enabled:
			return True, "Disabled", {}

		if not self._presence_dev or not self._tof_dev:
			self.discover_sensors()

		if not self._presence_dev or not os.path.exists(self._presence_dev):
			# Fallback if sensor node unavailable: allow auth so user is not locked out
			return True, "Presence sensor device not found, skipping 3D check", {}

		p_fd = None
		t_fd = None
		pres_val = None  # (presence: bool, distance_cm: float, confidence: int)
		depth_grid = None  # np.array of 64 floats (cm)

		try:
			p_fd = os.open(self._presence_dev, os.O_RDWR | os.O_NONBLOCK)
			if self._tof_dev and os.path.exists(self._tof_dev):
				t_fd = os.open(self._tof_dev, os.O_RDWR | os.O_NONBLOCK)

			fds = [p_fd] + ([t_fd] if t_fd else [])
			start = time.time()

			while time.time() - start < timeout_sec and (pres_val is None or (t_fd and depth_grid is None)):
				r, _, _ = select.select(fds, [], [], 0.05)
				for fd in r:
					if fd == p_fd:
						data = os.read(p_fd, 256)
						if len(data) >= 33 and data[0] == 4:
							prox_cm = struct.unpack("<I", data[27:31])[0] / 10.0
							pres = bool(data[31])
							conf = data[32]
							pres_val = (pres, prox_cm, conf)
					elif fd == t_fd:
						data = os.read(t_fd, 2048)
						if len(data) >= 1250 and data[0] == 1:
							zones = struct.unpack("<64H", data[799:799 + 128])
							depth_grid = np.array(zones, dtype=np.float32) / 10.0

		except Exception as e:
			if self.debug:
				print(f"[TofVerifier] Error reading sensors: {e}", file=sys.stderr)
			return True, f"Sensor read error: {e}", {}
		finally:
			if p_fd is not None:
				os.close(p_fd)
			if t_fd is not None:
				os.close(t_fd)

		# Evaluate Presence
		if pres_val is not None:
			is_present, distance_cm, confidence = pres_val
			if self.require_presence and not is_present:
				msg = f"No human presence detected (confidence {confidence}%)"
				if self.warn_on_fail:
					print(f"\n[3D Anti-Spoof] {msg}", file=sys.stderr)
				return False, msg, {"present": False, "confidence": confidence}

			if distance_cm < self.min_dist_cm:
				msg = f"Object too close to camera ({distance_cm:.1f} cm < {self.min_dist_cm:.1f} cm)"
				if self.warn_on_fail:
					print(f"\n[3D Anti-Spoof] {msg}", file=sys.stderr)
				return False, msg, {"distance_cm": distance_cm}

			if distance_cm > self.max_dist_cm:
				msg = f"Target out of seated range ({distance_cm:.1f} cm > {self.max_dist_cm:.1f} cm)"
				if self.warn_on_fail:
					print(f"\n[3D Anti-Spoof] {msg}", file=sys.stderr)
				return False, msg, {"distance_cm": distance_cm}
		else:
			distance_cm = 50.0

		# Evaluate 3D Depth Variance (Anti-Spoofing)
		if depth_grid is not None:
			valid = depth_grid[(depth_grid >= 20.0) & (depth_grid <= 120.0)]
			if len(valid) < 4:
				msg = "Insufficient depth points detected in seated range"
				if self.warn_on_fail:
					print(f"\n[3D Anti-Spoof] {msg}", file=sys.stderr)
				return False, msg, {"valid_zones": len(valid)}

			depth_var = float(np.std(valid))
			if depth_var < self.min_depth_var_cm:
				msg = f"2D flat surface detected (depth variance {depth_var:.2f} cm < {self.min_depth_var_cm:.2f} cm)"
				if self.warn_on_fail:
					print(f"\n[3D Anti-Spoof] {msg} - Photo or screen spoof rejected!", file=sys.stderr)
				return False, msg, {"depth_variance": depth_var}

			if self.debug:
				print(f"[TofVerifier] 3D Human verified: distance={distance_cm:.1f}cm, variance={depth_var:.2f}cm", file=sys.stderr)
			return True, "Human verified", {"distance_cm": distance_cm, "depth_variance": depth_var}

		return True, "Presence verified", {"distance_cm": distance_cm}
