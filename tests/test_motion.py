from __future__ import annotations

import unittest

import numpy as np

from ppe_monitoring.motion import FrameSampler, InferenceGate, MotionDetector


class TestMotionComponents(unittest.TestCase):
    def test_motion_detector_ratio_changes(self):
        detector = MotionDetector({"enabled": True, "pixel_threshold": 10, "blur_kernel": 1})

        frame_static = np.zeros((32, 32, 3), dtype=np.uint8)
        frame_changed = frame_static.copy()
        frame_changed[8:24, 8:24] = 255

        r1 = detector.update(frame_static)
        r2 = detector.update(frame_static)
        r3 = detector.update(frame_changed)

        self.assertEqual(r1, 0.0)
        self.assertEqual(r2, 0.0)
        self.assertGreater(r3, 0.0)

    def test_frame_sampler(self):
        sampler = FrameSampler(target_fps=2.0)  # every 0.5 sec
        self.assertTrue(sampler.should_sample(0.0))
        self.assertFalse(sampler.should_sample(0.2))
        self.assertTrue(sampler.should_sample(0.5))
        self.assertFalse(sampler.should_sample(0.7))
        self.assertTrue(sampler.should_sample(1.1))

    def test_inference_gate(self):
        gate = InferenceGate(
            pipeline_cfg={"mode": "motion_gated", "force_infer_every_n_frames": 10},
            motion_cfg={
                "enabled": True,
                "min_ratio": 0.01,
                "min_ratio_off": 0.005,
                "hold_frames_after_motion": 2,
            },
        )
        self.assertFalse(gate.should_infer(frame_idx=1, sampled=True, motion_ratio=0.0, last_infer_frame=0))
        self.assertTrue(gate.should_infer(frame_idx=1, sampled=True, motion_ratio=0.02, last_infer_frame=0))
        # Hold keeps motion gate active on the next sampled frame even if motion drops.
        self.assertFalse(gate.should_infer(frame_idx=2, sampled=False, motion_ratio=0.0, last_infer_frame=1))
        self.assertTrue(gate.should_infer(frame_idx=3, sampled=True, motion_ratio=0.0, last_infer_frame=1))
        # After hold expires and low motion persists, gate closes.
        self.assertFalse(gate.should_infer(frame_idx=5, sampled=True, motion_ratio=0.0, last_infer_frame=3))

        gate_every = InferenceGate(
            pipeline_cfg={"mode": "every_sample", "force_infer_every_n_frames": 100},
            motion_cfg={"enabled": True, "min_ratio": 1.0},
        )
        self.assertTrue(gate_every.should_infer(frame_idx=1, sampled=True, motion_ratio=0.0, last_infer_frame=0))
        self.assertFalse(gate_every.should_infer(frame_idx=2, sampled=False, motion_ratio=1.0, last_infer_frame=0))


if __name__ == "__main__":
    unittest.main()
