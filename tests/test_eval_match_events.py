from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("eval_events", _REPO / "tools" / "eval_events.py")
assert _SPEC and _SPEC.loader
_eval = importlib.util.module_from_spec(_SPEC)
sys.modules["eval_events"] = _eval
_SPEC.loader.exec_module(_eval)
GTEvent = _eval.GTEvent
PredEvent = _eval.PredEvent
match_events = _eval.match_events


class TestEvalMatchEvents(unittest.TestCase):
    def test_one_to_one_two_preds_one_gt_first_wins(self):
        gts = [GTEvent("v1", "g1", 10, 20, "no_hardhat")]
        preds = [
            PredEvent(0, 15, "no_hardhat"),
            PredEvent(1, 16, "no_hardhat"),
        ]
        tp, fp, fn, delays = match_events(preds, gts, tolerance_frames=0)
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 0)
        self.assertEqual(delays, [5.0])

    def test_tolerance_boundary(self):
        gts = [GTEvent("v1", "g1", 10, 20, "no_hardhat")]
        preds = [PredEvent(0, 8, "no_hardhat")]
        tp, fp, fn, _ = match_events(preds, gts, tolerance_frames=2)
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 0)
        self.assertEqual(fn, 0)

    def test_mismatch_type_is_fp(self):
        gts = [GTEvent("v1", "g1", 10, 20, "no_hardhat")]
        preds = [PredEvent(0, 15, "other")]
        tp, fp, fn, _ = match_events(preds, gts, tolerance_frames=0)
        self.assertEqual(tp, 0)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 1)


if __name__ == "__main__":
    unittest.main()
