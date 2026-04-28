from __future__ import annotations

import unittest

from ppe_monitoring.tracker import PersonTracker
from ppe_monitoring.types import Detection


def _minimal_cfg() -> dict:
    return {
        "filters": {
            "person": {
                "min_area_ratio": 0.0,
                "max_area_ratio": 1.0,
                "min_aspect_ratio": 0.01,
                "max_aspect_ratio": 10.0,
                "max_width_ratio": 1.0,
                "min_height_ratio": 0.0,
                "max_height_ratio": 1.0,
            },
            "head_hardhat": {
                "min_area_ratio": 0.0,
                "max_area_ratio": 1.0,
                "min_aspect_ratio": 0.01,
                "max_aspect_ratio": 10.0,
                "max_width_ratio": 1.0,
                "max_height_ratio": 1.0,
            },
            "head_vs_person": {
                "max_area_ratio_of_person": 1.0,
                "max_width_ratio_of_person": 1.0,
                "max_height_ratio_of_person": 1.0,
            },
        },
        "tracking": {
            "history_len": 10,
            "max_area_growth_ratio": 10.0,
            "max_width_growth_ratio": 10.0,
            "max_height_growth_ratio": 10.0,
            "min_iou_if_growth_triggered": 0.0,
            "blend_alpha": 1.0,
            "transfer_iou_threshold": 0.1,
            "max_transfer_gap_frames": 20,
            "headlike_dedup_iou": 0.45,
        },
        "roi": {"enabled": False},
        "person_roi": {"x_expand_ratio": 0.2, "y_expand_top_ratio": 0.1, "y_bottom_ratio": 0.6},
        "model": {"person_min_conf": 0.0},
    }


class TestTrackerAssociate(unittest.TestCase):
    def test_hardhat_inside_person_sets_observed(self):
        cfg = _minimal_cfg()
        tr = PersonTracker(cfg, {"person": 0, "head": 1, "hardhat": 2})
        person_boxes = {1: (0.0, 0.0, 100.0, 200.0)}
        dets = [
            Detection(cls_id=2, cls_name="hardhat", conf=0.9, bbox_xyxy=(30.0, 10.0, 70.0, 50.0), owner_person_id=1)
        ]
        obs, heads, hats = tr.associate_head_hardhat(dets, person_boxes, (200, 200, 3))
        self.assertTrue(obs.get(1))
        self.assertEqual(len(hats), 1)
        self.assertEqual(len(heads), 0)


if __name__ == "__main__":
    unittest.main()
