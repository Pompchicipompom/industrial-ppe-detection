from __future__ import annotations

import unittest

from ppe_monitoring.config import load_config, validate_config


class TestConfigValidate(unittest.TestCase):
    def test_unknown_top_level_key_raises(self):
        from copy import deepcopy

        from ppe_monitoring.config import DEFAULT_CONFIG

        bad = deepcopy(DEFAULT_CONFIG)
        bad["typo_section"] = {}
        with self.assertRaises(ValueError) as ctx:
            validate_config(bad)
        self.assertIn("typo_section", str(ctx.exception))

    def test_load_baseline_config(self):
        cfg = load_config(config_path="configs/baseline.yaml")
        self.assertTrue(cfg["model"]["enable_person_fallback"])


if __name__ == "__main__":
    unittest.main()
