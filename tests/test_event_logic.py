from __future__ import annotations

import unittest

from ppe_monitoring.event_logic import TemporalEventLogic


class TestTemporalEventLogic(unittest.TestCase):
    def _cfg(self) -> dict:
        return {
            "event_logic": {
                "hardhat_confirm_frames": 2,
                "hardhat_revoke_frames": 2,
                "lock_after_confirm": True,
                "no_hardhat_consecutive_frames": 3,
                "no_hardhat_seconds_threshold": 0.6,
                "cooldown_frames": 10,
                "cooldown_seconds": 2.0,
            }
        }

    def test_violation_emits_after_temporal_thresholds_and_cooldown(self):
        logic = TemporalEventLogic(self._cfg())
        person_boxes = {101: (10.0, 10.0, 50.0, 100.0)}

        # First 2 frames: no event yet.
        _, events1, active1, violating1 = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={101: False},
            frame_idx=1,
            timestamp_sec=0.0,
            did_infer=True,
        )
        _, events2, active2, violating2 = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={101: False},
            frame_idx=2,
            timestamp_sec=0.3,
            did_infer=True,
        )
        self.assertEqual(len(events1), 0)
        self.assertEqual(len(events2), 0)
        self.assertEqual(active1, 0)
        self.assertEqual(active2, 0)
        self.assertEqual(len(violating1), 0)
        self.assertEqual(len(violating2), 0)

        # Frame 3: both thresholds are met (3 frames and 0.7s).
        _, events3, active3, violating3 = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={101: False},
            frame_idx=3,
            timestamp_sec=0.7,
            did_infer=True,
        )
        self.assertEqual(len(events3), 1)
        self.assertEqual(events3[0].person_track_id, 101)
        self.assertEqual(active3, 1)
        self.assertIn(101, violating3)

        # Still in cooldown: no new event.
        _, events4, _, _ = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={101: False},
            frame_idx=4,
            timestamp_sec=1.0,
            did_infer=True,
        )
        self.assertEqual(len(events4), 0)

        # After cooldown by both frame and time: a new event is emitted.
        _, events5, _, _ = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={101: False},
            frame_idx=15,
            timestamp_sec=3.2,
            did_infer=True,
        )
        self.assertEqual(len(events5), 1)
        self.assertEqual(events5[0].event_id, 2)

    def test_hardhat_confirmation_locks_after_confirm(self):
        logic = TemporalEventLogic(self._cfg())
        person_boxes = {7: (0.0, 0.0, 10.0, 20.0)}

        statuses1, events1, _, _ = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={7: True},
            frame_idx=1,
            timestamp_sec=0.0,
            did_infer=True,
        )
        self.assertFalse(statuses1[7])
        self.assertEqual(len(events1), 0)

        statuses2, _, _, _ = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={7: True},
            frame_idx=2,
            timestamp_sec=0.1,
            did_infer=True,
        )
        self.assertTrue(statuses2[7])

        # Lock-after-confirm keeps hardhat status even when observation is absent.
        statuses3, _, _, _ = logic.update(
            person_boxes=person_boxes,
            person_hardhat_observed={7: False},
            frame_idx=3,
            timestamp_sec=0.2,
            did_infer=True,
        )
        self.assertTrue(statuses3[7])


if __name__ == "__main__":
    unittest.main()

