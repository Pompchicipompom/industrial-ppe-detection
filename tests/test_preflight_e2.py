from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))

from preflight_e2 import PreflightError, collect_gt_video_ids, run_group_dir_nonempty, run_preflight


class TestPreflightE2(unittest.TestCase):
    def test_collect_gt_video_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "g.csv").write_text(
                "video_id,event_id\na,e1\nb,e2\n", encoding="utf-8"
            )
            self.assertEqual(collect_gt_video_ids(t), {"a", "b"})

    def test_run_group_dir_nonempty(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            self.assertFalse(run_group_dir_nonempty(t))
            t.mkdir(parents=True, exist_ok=True)
            self.assertFalse(run_group_dir_nonempty(t))
            (t / "x").write_text("y", encoding="utf-8")
            self.assertTrue(run_group_dir_nonempty(t))

    def test_preflight_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            (root / "models" / "w.pt").write_bytes(b"")
            man = root / "manifest.csv"
            with man.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["video_id", "source_path", "split", "scenario_tag", "notes"],
                )
                w.writeheader()
                w.writerow(
                    {
                        "video_id": "vid_a",
                        "source_path": "media/a.mp4",
                        "split": "dev",
                        "scenario_tag": "",
                        "notes": "",
                    }
                )
            media = root / "media"
            media.mkdir()
            (media / "a.mp4").write_bytes(b"")

            gt = root / "gt"
            gt.mkdir()
            (gt / "gt.csv").write_text(
                "video_id,event_id,start_frame,end_frame,violation_type\n"
                "vid_a,e1,0,10,no_hardhat\n",
                encoding="utf-8",
            )

            cfg_path = root / "cfg.yaml"
            cfg_path.write_text(
                yaml.safe_dump(
                    {
                        "model": {
                            "weights_path": "models/w.pt",
                            "enable_person_fallback": False,
                        }
                    }
                ),
                encoding="utf-8",
            )

            out = root / "out" / "rg"
            run_preflight(
                repo_root=root,
                manifest_path=man,
                run_group_dir=out,
                gt_dir=gt,
                splits="dev,test,stress",
                video_ids="",
                max_videos=0,
                config_paths=[cfg_path],
                overwrite_run_group=False,
                allow_extra_gt_ids=False,
            )

    def test_preflight_missing_gt_for_manifest_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            (root / "models" / "w.pt").write_bytes(b"")
            man = root / "manifest.csv"
            with man.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["video_id", "source_path", "split", "scenario_tag", "notes"],
                )
                w.writeheader()
                w.writerow(
                    {
                        "video_id": "vid_a",
                        "source_path": "media/a.mp4",
                        "split": "dev",
                        "scenario_tag": "",
                        "notes": "",
                    }
                )
            media = root / "media"
            media.mkdir()
            (media / "a.mp4").write_bytes(b"")

            gt = root / "gt"
            gt.mkdir()
            (gt / "gt.csv").write_text(
                "video_id,event_id,start_frame,end_frame,violation_type\n"
                "other,e1,0,10,no_hardhat\n",
                encoding="utf-8",
            )

            cfg_path = root / "cfg.yaml"
            cfg_path.write_text(
                yaml.safe_dump(
                    {"model": {"weights_path": "models/w.pt", "enable_person_fallback": False}}
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PreflightError):
                run_preflight(
                    repo_root=root,
                    manifest_path=man,
                    run_group_dir=root / "out" / "rg",
                    gt_dir=gt,
                    splits="dev,test,stress",
                    video_ids="",
                    max_videos=0,
                    config_paths=[cfg_path],
                    overwrite_run_group=False,
                    allow_extra_gt_ids=False,
                )

    def test_preflight_extra_gt_requires_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            (root / "models" / "w.pt").write_bytes(b"")
            man = root / "manifest.csv"
            with man.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["video_id", "source_path", "split", "scenario_tag", "notes"],
                )
                w.writeheader()
                for vid in ("vid_a",):
                    w.writerow(
                        {
                            "video_id": vid,
                            "source_path": f"media/{vid}.mp4",
                            "split": "dev",
                            "scenario_tag": "",
                            "notes": "",
                        }
                    )
            media = root / "media"
            media.mkdir()
            (media / "vid_a.mp4").write_bytes(b"")

            gt = root / "gt"
            gt.mkdir()
            (gt / "gt.csv").write_text(
                "video_id,event_id,start_frame,end_frame,violation_type\n"
                "vid_a,e1,0,10,no_hardhat\n"
                "vid_b,e2,0,10,no_hardhat\n",
                encoding="utf-8",
            )

            cfg_path = root / "cfg.yaml"
            cfg_path.write_text(
                yaml.safe_dump(
                    {"model": {"weights_path": "models/w.pt", "enable_person_fallback": False}}
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PreflightError):
                run_preflight(
                    repo_root=root,
                    manifest_path=man,
                    run_group_dir=root / "out" / "rg",
                    gt_dir=gt,
                    splits="dev,test,stress",
                    video_ids="",
                    max_videos=0,
                    config_paths=[cfg_path],
                    overwrite_run_group=False,
                    allow_extra_gt_ids=False,
                )

            run_preflight(
                repo_root=root,
                manifest_path=man,
                run_group_dir=root / "out" / "rg",
                gt_dir=gt,
                splits="dev,test,stress",
                video_ids="",
                max_videos=0,
                config_paths=[cfg_path],
                overwrite_run_group=False,
                allow_extra_gt_ids=True,
            )

    def test_preflight_nonempty_run_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            (root / "models" / "w.pt").write_bytes(b"")
            man = root / "manifest.csv"
            with man.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["video_id", "source_path", "split", "scenario_tag", "notes"],
                )
                w.writeheader()
                w.writerow(
                    {
                        "video_id": "vid_a",
                        "source_path": "media/a.mp4",
                        "split": "dev",
                        "scenario_tag": "",
                        "notes": "",
                    }
                )
            media = root / "media"
            media.mkdir()
            (media / "a.mp4").write_bytes(b"")

            gt = root / "gt"
            gt.mkdir()
            (gt / "gt.csv").write_text(
                "video_id,event_id,start_frame,end_frame,violation_type\n"
                "vid_a,e1,0,10,no_hardhat\n",
                encoding="utf-8",
            )

            cfg_path = root / "cfg.yaml"
            cfg_path.write_text(
                yaml.safe_dump(
                    {"model": {"weights_path": "models/w.pt", "enable_person_fallback": False}}
                ),
                encoding="utf-8",
            )

            rg = root / "out" / "rg"
            rg.mkdir(parents=True)
            (rg / "marker").write_text("x", encoding="utf-8")

            with self.assertRaises(PreflightError):
                run_preflight(
                    repo_root=root,
                    manifest_path=man,
                    run_group_dir=rg,
                    gt_dir=gt,
                    splits="dev,test,stress",
                    video_ids="",
                    max_videos=0,
                    config_paths=[cfg_path],
                    overwrite_run_group=False,
                    allow_extra_gt_ids=False,
                )

            run_preflight(
                repo_root=root,
                manifest_path=man,
                run_group_dir=rg,
                gt_dir=gt,
                splits="dev,test,stress",
                video_ids="",
                max_videos=0,
                config_paths=[cfg_path],
                overwrite_run_group=True,
                allow_extra_gt_ids=False,
            )

    def test_e1_manifest_matches_gt_repo(self):
        """Guardrail: E1 manifest and GT must use the same video_id vocabulary."""
        man = _REPO / "data" / "video_manifest_e1.csv"
        gt = _REPO / "data" / "gt_events"
        if not man.is_file() or not gt.is_dir():
            self.skipTest("E1 fixtures not present")
        mids = set()
        with man.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                mids.add((row.get("video_id") or "").strip())
        gids = collect_gt_video_ids(gt)
        self.assertEqual(mids, gids)


if __name__ == "__main__":
    unittest.main()
