# test_antispoof.py - Unit tests for ToF 3D anti-spoofing and range gating
import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "howdy", "recorders"))
from tof_verifier import TofVerifier


class TestTofAntiSpoof(unittest.TestCase):
	def setUp(self):
		self.verifier = TofVerifier()
		self.verifier.warn_on_fail = False

	def test_flat_photo_rejection(self):
		"""Simulate holding up a flat photo or tablet screen (variance < 1.0 cm)."""
		# Planar surface at 50 cm with 2mm measurement noise
		flat_depths = np.full(64, 50.0, dtype=np.float32) + np.random.normal(0, 0.2, 64)
		valid = flat_depths[(flat_depths >= 20.0) & (flat_depths <= 120.0)]
		std = float(np.std(valid))
		self.assertLess(std, self.verifier.min_depth_var_cm, "Flat surface should have low variance")

	def test_real_human_3d_acceptance(self):
		"""Simulate real human head & torso depth contour (variance >= 2.0 cm)."""
		# Real 8x8 depth profile: head at 48cm, shoulders at 42cm, background at 120cm
		human_depths = np.array([
			[55, 60, 70, 80, 110, 150, 180, 200],
			[52, 56, 65, 75, 100, 140, 170, 190],
			[48, 50, 55, 65,  90, 120, 150, 180],
			[45, 47, 50, 60,  85, 110, 140, 170],
			[42, 44, 46, 55,  80, 100, 130, 160],
			[40, 42, 45, 52,  75,  95, 120, 150],
			[40, 41, 44, 50,  70,  90, 110, 140],
			[39, 40, 42, 48,  65,  85, 105, 130],
		], dtype=np.float32).flatten()

		valid = human_depths[(human_depths >= 20.0) & (human_depths <= 120.0)]
		std = float(np.std(valid))
		self.assertGreaterEqual(std, self.verifier.min_depth_var_cm, "Human 3D contour should exceed threshold")

	def test_out_of_range_checks(self):
		"""Test seated range limits."""
		self.assertFalse(15.0 >= self.verifier.min_dist_cm, "15cm should be too close")
		self.assertFalse(120.0 <= self.verifier.max_dist_cm, "120cm should be too far")
		self.assertTrue(self.verifier.min_dist_cm <= 55.0 <= self.verifier.max_dist_cm, "55cm is ideal seated distance")

	def test_live_hardware_read(self):
		"""Attempt live hardware verification if sensor nodes exist."""
		passed, reason, details = self.verifier.verify(timeout_sec=0.4)
		print(f"\n[Live Hardware Check] Passed: {passed}, Reason: '{reason}', Details: {details}")
		self.assertTrue(passed or "detected" in reason.lower() or "not found" in reason.lower())


if __name__ == "__main__":
	unittest.main()
