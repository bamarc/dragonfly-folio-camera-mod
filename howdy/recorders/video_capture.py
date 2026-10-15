# Import required modules
import atexit
import os
import sys

# Silence libcamera, GStreamer, and OpenCV verbosity
os.environ["LIBCAMERA_LOG_LEVELS"] = "*:4"
os.environ["GST_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

import configparser
import cv2

from i18n import _

# Class to provide boilerplate code to build a video recorder with the
# correct settings from the config file.
#
# The internal recorder can be accessed with 'video_capture.internal'


class VideoCapture:
	def __init__(self, config):
		"""
		Creates a new VideoCapture instance depending on the settings in the
		provided config file.

		Config can either be a string to the path, or a pre-setup configparser.
		"""

		# Parse config from string if needed
		if isinstance(config, str):
			self.config = configparser.ConfigParser()
			self.config.read(config)
		else:
			self.config = config

		self.recording_plugin = self.config.get("video", "recording_plugin", fallback="opencv")

		# Check device path (not required for ir_libcamera)
		if self.recording_plugin != "ir_libcamera":
			device_path = self.config.get("video", "device_path", fallback="")
			is_pipeline = device_path.startswith("pipewire") or device_path.startswith("libcamera")
			if not is_pipeline and not os.path.exists(device_path):
				if self.config.getboolean("video", "warn_no_device", fallback=True):
					print(_("Howdy could not find a camera device at the path specified in the config file."))
					print(_("It is very likely that the path is not configured correctly, please edit the 'device_path' config value by running:"))
					print("\n\tsudo howdy config\n")
				sys.exit(14)

		# Turn on flash / torch if configured (ir_libcamera handles torch inside ir-grab)
		self.flash_path = self.config.get("video", "flash_path", fallback="")
		self.flash_brightness = self.config.get("video", "flash_brightness", fallback="50")
		if self.recording_plugin != "ir_libcamera" and self.flash_path and os.path.exists(self.flash_path):
			try:
				if os.path.realpath(self.flash_path).startswith("/sys/"):
					with open(self.flash_path, "w") as f:
						f.write(f"{self.flash_brightness}\n")
			except Exception:
				pass

		# Mute C-level stderr (libcamera, EGL, GStreamer, OpenCV) to prevent terminal noise
		self.saved_stderr = None
		self.devnull = None
		try:
			self.devnull = os.open(os.devnull, os.O_WRONLY)
			self.saved_stderr = os.dup(2)
			os.dup2(self.devnull, 2)
		except Exception:
			pass

		# Create reader
		# The internal video recorder
		self.internal = None
		# The frame width
		self.fw = None
		# The frame height
		self.fh = None
		self._create_reader()

		# Request a frame to wake the camera up
		self.internal.grab()

		# Ensure release is always called when the process terminates
		atexit.register(self.release)

	def __del__(self):
		"""
		Frees resources when destroyed
		"""
		self.release()

	def release(self):
		"""
		Release cameras and turn off flash
		"""
		if getattr(self, "flash_path", None) and os.path.exists(self.flash_path):
			try:
				if os.path.realpath(self.flash_path).startswith("/sys/"):
					with open(self.flash_path, "w") as f:
						f.write("0\n")
			except Exception:
				pass

		if self is not None and getattr(self, "internal", None) is not None:
			try:
				self.internal.release()
			except Exception:
				pass

		# Restore stderr
		if getattr(self, "saved_stderr", None) is not None:
			try:
				os.dup2(self.saved_stderr, 2)
				os.close(self.saved_stderr)
				if getattr(self, "devnull", None) is not None:
					os.close(self.devnull)
				self.saved_stderr = None
				self.devnull = None
			except Exception:
				pass

	def read_frame(self):
		"""
		Reads a frame, returns the frame and an attempted grayscale conversion of
		the frame in a tuple:

		(frame, grayscale_frame)

		If the grayscale conversion fails, both items in the tuple are identical.
		"""

		# Grab a single frame of video
		# Don't remove ret, it doesn't work without it
		ret, frame = self.internal.read()
		if not ret:
			print(_("Failed to read camera specified in the 'device_path' config option, aborting"))
			sys.exit(14)

		try:
			# Convert from color to grayscale
			# First processing of frame, so frame errors show up here
			gsframe = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		except RuntimeError:
			gsframe = frame
		except cv2.error:
			print("\nAn error occurred in OpenCV\n")
			raise
		return frame, gsframe

	def _create_reader(self):
		"""
		Sets up the video reader instance
		"""
		recording_plugin = self.config.get("video", "recording_plugin", fallback="opencv")

		if recording_plugin == "ir_libcamera":
			from recorders.ir_libcamera_reader import ir_libcamera_reader
			self.internal = ir_libcamera_reader(self.config)

		elif recording_plugin == "ffmpeg":
			# Set the capture source for ffmpeg
			from recorders.ffmpeg_reader import ffmpeg_reader
			self.internal = ffmpeg_reader(
				self.config.get("video", "device_path"),
				self.config.get("video", "device_format", fallback="v4l2")
			)

		elif recording_plugin == "pyv4l2":
			# Set the capture source for pyv4l2
			from recorders.pyv4l2_reader import pyv4l2_reader
			self.internal = pyv4l2_reader(
				self.config.get("video", "device_path"),
				self.config.get("video", "device_format", fallback="v4l2")
			)

		else:
			# Start video capture through OpenCV
			device_path = self.config.get("video", "device_path")
			is_pipeline = device_path.startswith("pipewire") or device_path.startswith("libcamera")
			if is_pipeline:
				self.internal = cv2.VideoCapture(device_path, cv2.CAP_GSTREAMER)
			else:
				self.internal = cv2.VideoCapture(device_path, cv2.CAP_V4L)
			# Set the capture frame rate
			# Without this the first detected (and possibly lower) frame rate is used, -1 seems to select the highest
			# Use 0 as a fallback to avoid breaking an existing setup, new installs should default to -1
			self.fps = self.config.getint("video", "device_fps", fallback=0)
			if self.fps != 0:
				self.internal.set(cv2.CAP_PROP_FPS, self.fps)

		# Force MJPEG decoding if true
		if self.config.getboolean("video", "force_mjpeg", fallback=False):
			# Set a magic number, will enable MJPEG but is badly documentated
			self.internal.set(cv2.CAP_PROP_FOURCC, 1196444237)

		# Set the frame width and height if requested
		self.fw = self.config.getint("video", "frame_width", fallback=-1)
		self.fh = self.config.getint("video", "frame_height", fallback=-1)
		if self.fw != -1:
			self.internal.set(cv2.CAP_PROP_FRAME_WIDTH, self.fw)
		if self.fh != -1:
			self.internal.set(cv2.CAP_PROP_FRAME_HEIGHT, self.fh)
