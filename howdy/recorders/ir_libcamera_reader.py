# ir_libcamera_reader.py - Howdy video recorder plugin for libcamera raw IR streaming
# Spawns ir-grab, reads packed 10-bit raw frames (640x480 uint16), normalizes to 8-bit,
# and outputs 3-channel BGR frames for Howdy and dlib.

import atexit
import configparser
import os
import subprocess
import sys
import time
import cv2
import numpy as np
from cv2 import CAP_PROP_FRAME_HEIGHT, CAP_PROP_FRAME_WIDTH

try:
	from .tof_verifier import TofVerifier
except ImportError:
	try:
		from tof_verifier import TofVerifier
	except ImportError:
		TofVerifier = None

try:
	from i18n import _
except ImportError:
	def _(text):
		return text

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 2  # 614,400 bytes


class ir_libcamera_reader:
	"""
	Implements the OpenCV VideoCapture interface for Howdy using ir-grab
	"""

	def __init__(self, config):
		if isinstance(config, str):
			self.config = configparser.ConfigParser()
			self.config.read(config)
		else:
			self.config = config

		# Locate ir-grab binary
		default_bin = "/usr/libexec/howdy/ir-grab"
		local_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..", "tools", "ir-grab", "build", "ir-grab")
		if os.path.isfile(default_bin) and os.access(default_bin, os.X_OK):
			self.ir_grab_bin = self.config.get("video", "ir_grab_path", fallback=default_bin)
		elif os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
			self.ir_grab_bin = self.config.get("video", "ir_grab_path", fallback=local_bin)
		else:
			self.ir_grab_bin = self.config.get("video", "ir_grab_path", fallback=default_bin)

		self.camera_id = self.config.get("video", "ir_camera", fallback=r"\_SB_.PC00.LNK1")
		self.gain = self.config.getint("video", "ir_gain", fallback=128)
		self.exposure = self.config.getint("video", "ir_exposure", fallback=2000)
		self.black_level = self.config.getint("video", "ir_black_level", fallback=64)
		self.normalize_mode = self.config.get("video", "ir_normalize", fallback="percentile")
		self.use_clahe = self.config.getboolean("video", "ir_clahe", fallback=False)
		self.torch_path = self.config.get("video", "flash_path", fallback="/sys/class/leds/lm3643:torch/brightness")
		self.torch_level = self.config.getint("video", "flash_brightness", fallback=60)
		self.timeout = self.config.getint("video", "timeout", fallback=10)

		if self.use_clahe:
			self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
		else:
			self.clahe = None

		self.proc = None
		self.width = FRAME_WIDTH
		self.height = FRAME_HEIGHT
		self._atexit_registered = False

		if TofVerifier is not None:
			self.tof_verifier = TofVerifier(self.config)
		else:
			self.tof_verifier = None

		self._start_ir_grab()

	def _start_ir_grab(self):
		if self.tof_verifier is not None and self.tof_verifier.enabled:
			passed, reason, _ = self.tof_verifier.verify()
			if not passed:
				# 3D Anti-spoofing rejected the attempt
				return

		if not os.path.exists(self.ir_grab_bin):
			print(_("ir-grab binary not found at %s") % self.ir_grab_bin, file=sys.stderr)
			return

		cmd = [
			self.ir_grab_bin,
			"--camera", self.camera_id,
			"--frames", "0",
			"--gain", str(self.gain),
			"--exposure", str(self.exposure),
			"--torch", self.torch_path,
			"--torch-level", str(self.torch_level),
			"--max-seconds", str(max(15, self.timeout + 5))
		]

		try:
			self.proc = subprocess.Popen(
				cmd,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.DEVNULL,
				bufsize=0
			)
			if not self._atexit_registered:
				atexit.register(self.release)
				self._atexit_registered = True
		except Exception as e:
			print(_("Failed to start ir-grab: %s") % str(e), file=sys.stderr)
			self.proc = None

	def set(self, prop, setting):
		if prop == CAP_PROP_FRAME_WIDTH:
			self.width = int(setting)
		elif prop == CAP_PROP_FRAME_HEIGHT:
			self.height = int(setting)
		return True

	def get(self, prop):
		if prop == CAP_PROP_FRAME_WIDTH:
			return float(self.width)
		elif prop == CAP_PROP_FRAME_HEIGHT:
			return float(self.height)
		return 0.0

	def _read_exact(self, nbytes):
		if self.proc is None or self.proc.stdout is None:
			return None

		buf = bytearray(nbytes)
		view = memoryview(buf)
		pos = 0
		while pos < nbytes:
			chunk = self.proc.stdout.read(nbytes - pos)
			if not chunk:
				return None
			view[pos:pos + len(chunk)] = chunk
			pos += len(chunk)
		return buf

	def read(self):
		raw_bytes = self._read_exact(FRAME_SIZE)
		if raw_bytes is None:
			return False, None

		# Convert raw little-endian uint16 (10-bit raw)
		raw = np.frombuffer(raw_bytes, dtype="<u2").reshape((FRAME_HEIGHT, FRAME_WIDTH))

		# Subtract black level
		diff = np.maximum(0, raw.astype(np.float32) - self.black_level)

		# Normalization to 8-bit
		if self.normalize_mode == "percentile":
			p99 = np.percentile(diff, 99.5)
			if p99 > 1.0:
				norm = np.clip(diff * (255.0 / p99), 0, 255).astype(np.uint8)
			else:
				norm = np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)
		else:
			scale = 255.0 / max(1.0, 1023.0 - self.black_level)
			norm = np.clip(diff * scale, 0, 255).astype(np.uint8)

		if self.clahe is not None:
			norm = self.clahe.apply(norm)

		# Create 3-channel BGR frame where all 3 channels are identical
		bgr = np.dstack((norm, norm, norm))
		return True, bgr

	def grab(self):
		"""
		Discards a single frame to keep the pipeline fresh
		"""
		self._read_exact(FRAME_SIZE)
		return True

	def release(self):
		"""
		Gracefully stops ir-grab and ensures torch is turned off
		"""
		if self.proc is not None:
			try:
				if self.proc.stdin:
					self.proc.stdin.close()
				self.proc.terminate()
				self.proc.wait(timeout=2.0)
			except Exception:
				try:
					self.proc.kill()
					self.proc.wait(timeout=1.0)
				except Exception:
					pass
			self.proc = None

		if getattr(self, "_atexit_registered", False):
			try:
				atexit.unregister(self.release)
			except Exception:
				pass
			self._atexit_registered = False

		# Fallback torch turn off
		if self.torch_path and os.path.exists(self.torch_path):
			try:
				with open(self.torch_path, "w") as f:
					f.write("0\n")
			except Exception:
				pass

	def __del__(self):
		self.release()
