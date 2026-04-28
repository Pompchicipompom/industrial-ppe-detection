from __future__ import annotations

import unittest

from ppe_monitoring.person_confirmation import person_soft_confirmed, resolve_person_confirmation_mode
from ppe_monitoring.types import Detection


def _head(xyxy: tuple[float, float, float, float]) -> Detection:
    return Detection(0, "head", 0.9, xyxy, None, "test", None)


class TestPersonSoftConfirmation(unittest.TestCase):
    def _defaults(
        self,
        *,
        high: float = 0.55,
        min_asp: float = 1.4,
        min_ar: float = 0.002,
        min_hits: int = 3,
    ):
        return dict(
            high_conf_threshold=high,
            min_aspect_hw=min_asp,
            min_area_ratio=min_ar,
            min_infer_hits=min_hits,
        )

    def test_person_with_head_confirmed(self):
        person = (0.0, 0.0, 100.0, 100.0)
        head = _head((40.0, 10.0, 60.0, 40.0))
        kw = self._defaults()
        self.assertTrue(
            person_soft_confirmed(person, [head], 0.1, 640, 640, 0, **kw),
        )

    def test_high_confidence_confirms_without_head(self):
        person = (0.0, 0.0, 50.0, 50.0)
        kw = self._defaults()
        self.assertTrue(
            person_soft_confirmed(person, [], 0.56, 640, 640, 0, **kw),
        )

    def test_good_aspect_ratio_confirms(self):
        # tall narrow box: h/w = 100/40 = 2.5 >= 1.4, area on 640 frame
        person = (0.0, 0.0, 40.0, 100.0)
        kw = self._defaults()
        self.assertTrue(
            person_soft_confirmed(person, [], 0.1, 640, 640, 0, **kw),
        )

    def test_stable_track_hits_confirm(self):
        person = (0.0, 0.0, 80.0, 80.0)
        kw = self._defaults()
        self.assertFalse(
            person_soft_confirmed(person, [], 0.1, 640, 640, 2, **kw),
        )
        self.assertTrue(
            person_soft_confirmed(person, [], 0.1, 640, 640, 3, **kw),
        )

    def test_low_conf_bad_aspect_no_head_not_confirmed(self):
        person = (0.0, 0.0, 80.0, 50.0)  # h/w = 0.625 < 1.4
        kw = self._defaults()
        self.assertFalse(
            person_soft_confirmed(person, [], 0.2, 640, 640, 1, **kw),
        )

    def test_soft_does_not_require_head_if_high_conf(self):
        """Real person can be confirmed immediately via score without head in frame."""
        person = (10.0, 10.0, 110.0, 210.0)
        kw = self._defaults()
        self.assertTrue(
            person_soft_confirmed(person, [], 0.9, 640, 640, 1, **kw),
        )

    def test_resolve_mode_legacy_hard(self):
        f = {"person_confirmation_mode": "off", "require_head_or_hardhat_for_person": True}
        self.assertEqual(resolve_person_confirmation_mode(f), "hard")

    def test_resolve_mode_explicit_soft(self):
        f = {"person_confirmation_mode": "soft", "require_head_or_hardhat_for_person": False}
        self.assertEqual(resolve_person_confirmation_mode(f), "soft")


if __name__ == "__main__":
    unittest.main()
