from __future__ import annotations

import unittest

from ppe_monitoring.person_head_confirmation import person_confirmed_by_head_or_hardhat
from ppe_monitoring.types import Detection


def _det(cls_name: str, xyxy: tuple[float, float, float, float], conf: float = 0.9) -> Detection:
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=conf,
        bbox_xyxy=xyxy,
        track_id=None,
        source="test",
        owner_person_id=None,
    )


class TestPersonHeadConfirmation(unittest.TestCase):
    def test_person_with_head_in_upper_half_confirmed(self):
        person = (0.0, 0.0, 100.0, 100.0)
        # center (50, 25) in upper half [0, 50]
        head = _det("head", (40.0, 10.0, 60.0, 40.0))
        self.assertTrue(person_confirmed_by_head_or_hardhat(person, [head]))

    def test_person_with_hardhat_in_upper_half_confirmed(self):
        person = (0.0, 0.0, 100.0, 100.0)
        hat = _det("hardhat", (40.0, 10.0, 60.0, 40.0))
        self.assertTrue(person_confirmed_by_head_or_hardhat(person, [hat]))

    def test_person_without_head_or_hardhat_rejected(self):
        person = (0.0, 0.0, 100.0, 100.0)
        self.assertFalse(person_confirmed_by_head_or_hardhat(person, []))

    def test_head_outside_person_rejected(self):
        person = (0.0, 0.0, 100.0, 100.0)
        head = _det("head", (200.0, 10.0, 220.0, 40.0))
        self.assertFalse(person_confirmed_by_head_or_hardhat(person, [head]))

    def test_head_in_lower_half_rejected(self):
        person = (0.0, 0.0, 100.0, 100.0)
        # center (50, 75) in lower half
        head = _det("head", (40.0, 60.0, 60.0, 90.0))
        self.assertFalse(person_confirmed_by_head_or_hardhat(person, [head]))

    def test_boundary_upper_half_included(self):
        person = (0.0, 0.0, 100.0, 100.0)
        y_mid = 50.0
        head = _det("head", (45.0, y_mid - 5.0, 55.0, y_mid + 5.0))
        self.assertTrue(person_confirmed_by_head_or_hardhat(person, [head]))


if __name__ == "__main__":
    unittest.main()
