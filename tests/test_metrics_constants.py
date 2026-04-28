from __future__ import annotations

import unittest

from ppe_monitoring.metrics_constants import STAGE_TIMING_FIELDS, metrics_csv_fieldnames, validate_metrics_csv_header


class TestMetricsConstants(unittest.TestCase):
    def test_header_matches_stages(self):
        names = metrics_csv_fieldnames()
        loop_i = names.index("loop_ms")
        slice_stages = names[loop_i + 1 : loop_i + 1 + len(STAGE_TIMING_FIELDS)]
        self.assertEqual(list(STAGE_TIMING_FIELDS), slice_stages)

    def test_validate_header_ok(self):
        validate_metrics_csv_header(metrics_csv_fieldnames())

    def test_validate_header_rejects_wrong_order(self):
        bad = list(metrics_csv_fieldnames())
        bad[0] = "wrong"
        with self.assertRaises(ValueError):
            validate_metrics_csv_header(bad)


if __name__ == "__main__":
    unittest.main()
