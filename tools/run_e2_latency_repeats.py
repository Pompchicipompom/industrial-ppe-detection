#!/usr/bin/env python3
"""Launch E2-style ablation runs with optional latency repeats (docs/e2_evaluation_protocol.md).

Runs ``tools/run_ablation.py`` N times with distinct ``--run-group`` names so steady-state
latency can be compared across repeats on the same machine.

Example (from repository root):

    python tools/run_e2_latency_repeats.py --repeats 3 --manifest data/video_manifest_e1.csv --max-frames 140
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run E2 ablation matrix N times for latency variance.")
    p.add_argument("--repeats", type=int, default=3, help="Number of full ablation passes.")
    p.add_argument("--manifest", type=str, default="data/video_manifest_e1.csv", help="Video manifest CSV.")
    p.add_argument("--max-frames", type=int, default=140, help="Per-video frame cap (E2 default).")
    p.add_argument("--warmup-frames", type=int, default=20, help="Warmup frame count for phase split.")
    p.add_argument("--steady-min-frames", type=int, default=30, help="Minimum steady frames for reporting.")
    p.add_argument("--tolerance-frames", type=int, default=0, help="GT matching tolerance.")
    p.add_argument("--gt-dir", type=str, default="data/gt_events", help="Ground-truth CSV directory.")
    p.add_argument("--dry-run", action="store_true", help="Pass --dry-run to run_ablation.")
    p.add_argument("--stop-on-error", action="store_true", help="Pass --stop-on-error to run_ablation.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rc_all = 0
    for i in range(max(1, int(args.repeats))):
        run_group = f"e2_{stamp}_r{i + 1}"
        cmd = [
            sys.executable,
            str(repo_root / "tools" / "run_ablation.py"),
            "--manifest",
            args.manifest,
            "--run-group",
            run_group,
            "--max-frames",
            str(int(args.max_frames)),
            "--warmup-frames",
            str(int(args.warmup_frames)),
            "--steady-min-frames",
            str(int(args.steady_min_frames)),
            "--tolerance-frames",
            str(int(args.tolerance_frames)),
            "--gt-dir",
            args.gt_dir,
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.stop_on_error:
            cmd.append("--stop-on-error")
        print("[E2 repeat]", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(repo_root), check=False)
        rc_all = max(rc_all, int(proc.returncode))
    print(f"Done. Largest exit code across repeats: {rc_all}")
    print("Compare latency columns in each run's ablation_analysis/ablation_results.csv under output_files/experiments/")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
