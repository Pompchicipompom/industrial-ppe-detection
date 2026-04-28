from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from ppe_monitoring.metrics_constants import STAGE_TIMING_FIELDS
from preflight_e2 import run_preflight_or_exit


DEFAULT_CONFIGS: list[tuple[str, str]] = [
    ("baseline", "configs/baseline.yaml"),
    ("proposed", "configs/proposed.yaml"),
    ("proposed_without_motion", "configs/ablation_proposed_without_motion.yaml"),
    ("proposed_without_roi", "configs/ablation_proposed_without_roi.yaml"),
    ("proposed_without_temporal", "configs/ablation_proposed_without_temporal.yaml"),
    ("proposed_without_fallback", "configs/ablation_proposed_without_fallback.yaml"),
]

STAGE_NAMES = list(STAGE_TIMING_FIELDS)

PHASES = ["all", "warmup", "steady"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_component(raw: str) -> str:
    out = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    value = "".join(out).strip("._")
    return value or "item"


def to_repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    pos = (len(arr) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(arr) - 1)
    frac = pos - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "mean": 0.0, "median": 0.0, "p90": 0.0, "sum": 0.0}
    arr = [float(v) for v in values]
    total = float(sum(arr))
    return {
        "count": float(len(arr)),
        "mean": total / float(len(arr)),
        "median": percentile(arr, 0.5),
        "p90": percentile(arr, 0.9),
        "sum": total,
    }


def fmt(value: float | None, ndigits: int = 6) -> str:
    if value is None:
        return ""
    return f"{float(value):.{ndigits}f}"


def try_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return list(reader)


def run_cmd(cmd: list[str], cwd: Path) -> int:
    print("[CMD]", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    return int(proc.returncode)


def resolve_output_dir(repo_root: Path, output_dir_value: str) -> Path:
    p = Path(output_dir_value)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def load_runtime_summary(output_dir: Path) -> dict[str, Any]:
    profile_path = output_dir / "runtime_profile.json"
    if not profile_path.exists():
        return {}
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    runtime = data.get("runtime_summary")
    if not isinstance(runtime, dict):
        return {}
    return runtime


def _empty_phase_samples() -> dict[str, Any]:
    return {
        "stage_samples": {phase: {stage: [] for stage in STAGE_NAMES} for phase in PHASES},
        "loop_samples": {phase: [] for phase in PHASES},
        "infer_samples": {phase: [] for phase in PHASES},
        "frame_counts": {phase: 0 for phase in PHASES},
        "inferred_counts": {phase: 0 for phase in PHASES},
    }


def collect_phase_samples(frame_metrics_path: Path, warmup_frames: int) -> dict[str, Any]:
    out = _empty_phase_samples()
    if not frame_metrics_path.exists():
        return out

    warmup_frames = max(0, int(warmup_frames))
    with frame_metrics_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return out
        fields = set(reader.fieldnames)
        has_loop = "loop_ms" in fields
        has_infer = "infer_ms" in fields
        has_did_infer = "did_infer" in fields

        for row_idx, row in enumerate(reader, start=1):
            phases = ["all"]
            if warmup_frames > 0 and row_idx <= warmup_frames:
                phases.append("warmup")
            else:
                phases.append("steady")

            did_infer = 0
            if has_did_infer:
                did_raw = row.get("did_infer", "")
                did_val = try_float(did_raw)
                if did_val is not None and did_val > 0.0:
                    did_infer = 1

            loop_v = try_float(row.get("loop_ms", "")) if has_loop else None
            infer_v = try_float(row.get("infer_ms", "")) if has_infer else None

            stage_values: dict[str, float | None] = {}
            for stage in STAGE_NAMES:
                if stage in fields:
                    stage_values[stage] = try_float(row.get(stage, ""))
                else:
                    stage_values[stage] = None

            for phase in phases:
                out["frame_counts"][phase] += 1
                out["inferred_counts"][phase] += did_infer
                if loop_v is not None:
                    out["loop_samples"][phase].append(loop_v)
                if infer_v is not None:
                    out["infer_samples"][phase].append(infer_v)
                for stage_name, stage_v in stage_values.items():
                    if stage_v is not None:
                        out["stage_samples"][phase][stage_name].append(stage_v)
    return out


def read_quality_map(aggregate_metrics_csv: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(aggregate_metrics_csv)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        cfg = (row.get("config_name") or "").strip()
        if cfg:
            out[cfg] = row
    return out


def build_stage_timing_summary(
    *,
    run_group: str,
    config_order: list[str],
    phase_stage_samples_by_cfg: dict[str, dict[str, dict[str, list[float]]]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cfg in config_order:
        for phase in PHASES:
            cfg_stage_samples = phase_stage_samples_by_cfg.get(cfg, {}).get(
                phase, {name: [] for name in STAGE_NAMES}
            )
            total_loop_stats = stats(cfg_stage_samples.get("total_loop_ms", []))
            total_loop_mean = total_loop_stats["mean"]
            for stage_name in STAGE_NAMES:
                st = stats(cfg_stage_samples.get(stage_name, []))
                if st["count"] <= 0:
                    rows.append(
                        {
                            "run_group": run_group,
                            "config_name": cfg,
                            "phase": phase,
                            "stage_name": stage_name,
                            "samples_count": "0",
                            "mean_ms": "",
                            "median_ms": "",
                            "p90_ms": "",
                            "total_ms": "",
                            "share_of_total_loop_pct": "",
                            "data_status": "missing",
                        }
                    )
                    continue

                if stage_name == "total_loop_ms":
                    share = 100.0
                elif total_loop_mean > 0:
                    share = (st["mean"] / total_loop_mean) * 100.0
                else:
                    share = None

                rows.append(
                    {
                        "run_group": run_group,
                        "config_name": cfg,
                        "phase": phase,
                        "stage_name": stage_name,
                        "samples_count": str(int(st["count"])),
                        "mean_ms": fmt(st["mean"]),
                        "median_ms": fmt(st["median"]),
                        "p90_ms": fmt(st["p90"]),
                        "total_ms": fmt(st["sum"]),
                        "share_of_total_loop_pct": fmt(share) if share is not None else "",
                        "data_status": "ok",
                    }
                )
    return rows


def pick_primary_bottleneck(stage_samples: dict[str, list[float]]) -> tuple[str, float | None, float | None]:
    candidates: list[tuple[str, float]] = []
    total_loop_mean = stats(stage_samples.get("total_loop_ms", []))["mean"]
    for stage_name in STAGE_NAMES:
        if stage_name == "total_loop_ms":
            continue
        mean_ms = stats(stage_samples.get(stage_name, []))["mean"]
        if mean_ms > 0:
            candidates.append((stage_name, mean_ms))
    if not candidates:
        return "", None, None
    candidates.sort(key=lambda x: x[1], reverse=True)
    stage_name, mean_ms = candidates[0]
    share = (mean_ms / total_loop_mean * 100.0) if total_loop_mean > 0 else None
    return stage_name, mean_ms, share


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def phase_perf_stats(
    *,
    frame_count: int,
    inferred_count: int,
    loop_values: list[float],
    infer_values: list[float],
    steady_min_frames: int,
    phase: str,
) -> dict[str, Any]:
    loop_stats = stats(loop_values)
    infer_stats = stats(infer_values)
    processing_fps_est = 0.0
    if loop_stats["mean"] > 0:
        processing_fps_est = 1000.0 / loop_stats["mean"]
    inference_fps_est = 0.0
    if frame_count > 0:
        inference_fps_est = processing_fps_est * (float(inferred_count) / float(frame_count))

    if frame_count <= 0:
        data_status = "missing"
    elif phase == "steady" and frame_count < steady_min_frames:
        data_status = "insufficient_steady_frames"
    else:
        data_status = "ok"

    return {
        "frame_count": frame_count,
        "inferred_count": inferred_count,
        "loop_stats": loop_stats,
        "infer_stats": infer_stats,
        "processing_fps_est": processing_fps_est,
        "inference_fps_est": inference_fps_est,
        "data_status": data_status,
    }


def build_warmup_steady_summary_rows(
    *,
    run_group: str,
    config_order: list[str],
    phase_frame_counts_by_cfg: dict[str, dict[str, int]],
    phase_inferred_counts_by_cfg: dict[str, dict[str, int]],
    phase_loop_samples_by_cfg: dict[str, dict[str, list[float]]],
    phase_infer_samples_by_cfg: dict[str, dict[str, list[float]]],
    steady_min_frames: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cfg in config_order:
        for phase in ["warmup", "steady"]:
            st = phase_perf_stats(
                frame_count=phase_frame_counts_by_cfg[cfg][phase],
                inferred_count=phase_inferred_counts_by_cfg[cfg][phase],
                loop_values=phase_loop_samples_by_cfg[cfg][phase],
                infer_values=phase_infer_samples_by_cfg[cfg][phase],
                steady_min_frames=steady_min_frames,
                phase=phase,
            )
            rows.append(
                {
                    "run_group": run_group,
                    "config_name": cfg,
                    "phase": phase,
                    "frames_count": str(st["frame_count"]),
                    "inferred_frames_count": str(st["inferred_count"]),
                    "processing_fps_est": fmt(st["processing_fps_est"]),
                    "inference_fps_est": fmt(st["inference_fps_est"]),
                    "loop_mean_ms": fmt(st["loop_stats"]["mean"]) if st["loop_stats"]["count"] > 0 else "",
                    "loop_median_ms": fmt(st["loop_stats"]["median"]) if st["loop_stats"]["count"] > 0 else "",
                    "loop_p90_ms": fmt(st["loop_stats"]["p90"]) if st["loop_stats"]["count"] > 0 else "",
                    "infer_mean_ms": fmt(st["infer_stats"]["mean"]) if st["infer_stats"]["count"] > 0 else "",
                    "infer_median_ms": fmt(st["infer_stats"]["median"]) if st["infer_stats"]["count"] > 0 else "",
                    "infer_p90_ms": fmt(st["infer_stats"]["p90"]) if st["infer_stats"]["count"] > 0 else "",
                    "data_status": st["data_status"],
                }
            )
    return rows


def build_performance_report_md(
    *,
    run_group: str,
    analysis_dir: Path,
    config_order: list[str],
    ablation_rows: list[dict[str, str]],
    warmup_steady_rows: list[dict[str, str]],
    manifest: str,
    max_frames: int | None,
    warmup_frames: int,
    steady_min_frames: int,
) -> str:
    now_utc = utc_now_iso()
    near_rt_rule = "steady.processing_fps_est >= 0.8 * input_fps_mean"

    row_by_cfg = {row["config_name"]: row for row in ablation_rows}
    phase_by_cfg: dict[tuple[str, str], dict[str, str]] = {}
    for row in warmup_steady_rows:
        phase_by_cfg[(row["config_name"], row["phase"])] = row

    lines: list[str] = []
    lines.append(f"# Performance Report ({run_group})")
    lines.append("")
    lines.append(f"- generated_at_utc: `{now_utc}`")
    lines.append(f"- analysis_dir: `{analysis_dir}`")
    lines.append(f"- manifest: `{manifest}`")
    lines.append(f"- max_frames_per_video: `{max_frames if max_frames is not None else 'full'}`")
    lines.append(f"- warmup_frames: `{warmup_frames}`")
    lines.append(f"- steady_min_frames: `{steady_min_frames}`")
    lines.append(f"- near_real_time_rule: `{near_rt_rule}`")
    lines.append("")
    lines.append("## Quality + Performance Summary")
    lines.append("")
    lines.append(
        "| config | precision | recall | f1 | false_alarms_per_hour | mean_delay_sec | steady_fps | steady_loop_p90_ms | near_real_time | bottleneck | notes |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|")
    for cfg in config_order:
        row = row_by_cfg.get(cfg, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    cfg,
                    row.get("precision", "n/a") or "n/a",
                    row.get("recall", "n/a") or "n/a",
                    row.get("f1", "n/a") or "n/a",
                    row.get("false_alarms_per_hour", "n/a") or "n/a",
                    row.get("mean_detection_delay_sec", "n/a") or "n/a",
                    row.get("processing_fps_steady", "n/a") or "n/a",
                    row.get("latency_p90_ms_steady", "n/a") or "n/a",
                    row.get("near_real_time", "n/a") or "n/a",
                    row.get("primary_bottleneck_stage", "n/a") or "n/a",
                    row.get("notes", "") or "",
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Warm-up vs Steady-state")
    lines.append("")
    lines.append("| config | phase | frames | inferred_frames | processing_fps_est | inference_fps_est | loop_p90_ms | data_status |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for cfg in config_order:
        for phase in ["warmup", "steady"]:
            row = phase_by_cfg.get((cfg, phase), {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        cfg,
                        phase,
                        row.get("frames_count", "0") or "0",
                        row.get("inferred_frames_count", "0") or "0",
                        row.get("processing_fps_est", "n/a") or "n/a",
                        row.get("inference_fps_est", "n/a") or "n/a",
                        row.get("loop_p90_ms", "n/a") or "n/a",
                        row.get("data_status", "missing") or "missing",
                    ]
                )
                + " |"
            )

    lines.append("")
    lines.append("## Data Completeness")
    lines.append("")
    for cfg in config_order:
        cfg_row = row_by_cfg.get(cfg, {})
        q_status = cfg_row.get("quality_status", "missing")
        p_status = cfg_row.get("performance_status", "missing")
        lines.append(f"- `{cfg}`: quality_status=`{q_status}`, performance_status=`{p_status}`.")

    return "\n".join(lines) + "\n"


def build_defense_summary_md(
    *,
    run_group: str,
    config_order: list[str],
    ablation_rows: list[dict[str, str]],
    manifest: str,
    max_frames: int | None,
    warmup_frames: int,
) -> str:
    row_by_cfg = {row["config_name"]: row for row in ablation_rows}
    lines: list[str] = []
    lines.append(f"# Defense Summary ({run_group})")
    lines.append("")
    lines.append("## Evaluation Setup")
    lines.append("")
    lines.append(f"- manifest: `{manifest}`")
    lines.append(f"- configs: `{', '.join(config_order)}`")
    lines.append(f"- max_frames_per_video: `{max_frames if max_frames is not None else 'full'}`")
    lines.append(f"- warmup_frames_for_profiling: `{warmup_frames}`")
    lines.append("")
    lines.append("## Key Results")
    lines.append("")
    lines.append("| config | precision | recall | f1 | false_alarms_per_hour | mean_delay_sec | steady_fps | steady_p90_ms | bottleneck |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for cfg in config_order:
        row = row_by_cfg.get(cfg, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    cfg,
                    row.get("precision", "n/a") or "n/a",
                    row.get("recall", "n/a") or "n/a",
                    row.get("f1", "n/a") or "n/a",
                    row.get("false_alarms_per_hour", "n/a") or "n/a",
                    row.get("mean_detection_delay_sec", "n/a") or "n/a",
                    row.get("processing_fps_steady", "n/a") or "n/a",
                    row.get("latency_p90_ms_steady", "n/a") or "n/a",
                    row.get("primary_bottleneck_stage", "n/a") or "n/a",
                ]
            )
            + " |"
        )

    baseline = row_by_cfg.get("baseline")
    proposed = row_by_cfg.get("proposed")
    lines.append("")
    lines.append("## Baseline vs Proposed")
    lines.append("")
    if baseline and proposed:
        def _delta(key: str) -> str:
            try:
                return f"{float(proposed.get(key, '0')) - float(baseline.get(key, '0')):.6f}"
            except Exception:
                return "n/a"

        lines.append(f"- recall delta (proposed - baseline): `{_delta('recall')}`")
        lines.append(f"- f1 delta (proposed - baseline): `{_delta('f1')}`")
        lines.append(f"- steady FPS delta (proposed - baseline): `{_delta('processing_fps_steady')}`")
        lines.append(f"- steady loop p90 delta ms (proposed - baseline): `{_delta('latency_p90_ms_steady')}`")
    else:
        lines.append("- baseline/proposed rows are missing in ablation results.")

    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    for cfg in config_order:
        row = row_by_cfg.get(cfg, {})
        notes = row.get("notes", "")
        if notes:
            lines.append(f"- `{cfg}`: {notes}")
    if all(not (row_by_cfg.get(cfg, {}).get("notes", "")) for cfg in config_order):
        lines.append("- no additional caveats flagged by the summary generator.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fixed ablation matrix and build quality/performance summary artifacts."
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/video_manifest_e1.csv",
        help="Video manifest CSV (E2: data/video_manifest_e1.csv only; do not use data/video_manifest.csv).",
    )
    parser.add_argument("--experiments-root", type=str, default="output_files/experiments")
    parser.add_argument("--run-group", type=str, default="")
    parser.add_argument("--splits", type=str, default="dev,test,stress")
    parser.add_argument("--video-ids", type=str, default="")
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--gt-dir", type=str, default="data/gt_events")
    parser.add_argument("--tolerance-frames", type=int, default=0)
    parser.add_argument("--warmup-frames", type=int, default=20)
    parser.add_argument("--steady-min-frames", type=int, default=30)
    parser.add_argument("--python-executable", type=str, default=sys.executable)
    parser.add_argument("--evaluation-subdir", type=str, default="evaluation_ablation")
    parser.add_argument("--analysis-subdir", type=str, default="ablation_analysis")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--overwrite-run-group",
        action="store_true",
        help="Allow reusing a non-empty output_files/experiments/{run_group} directory (overwrites artifacts).",
    )
    parser.add_argument(
        "--allow-extra-gt-ids",
        action="store_true",
        help="Allow GT CSVs to list video_ids not present in the selected manifest rows (subset/smoke runs).",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip manifest/GT/weights/overwrite preflight (not recommended for E2).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    experiments_root = Path(args.experiments_root)
    if not experiments_root.is_absolute():
        experiments_root = (repo_root / experiments_root).resolve()
    experiments_root.mkdir(parents=True, exist_ok=True)

    run_group = (
        sanitize_component(args.run_group.strip())
        if args.run_group.strip()
        else f"ablation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    run_group_dir = experiments_root / run_group

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    gt_dir = Path(args.gt_dir)
    if not gt_dir.is_absolute():
        gt_dir = (repo_root / gt_dir).resolve()

    config_paths = [(repo_root / rel).resolve() for _, rel in DEFAULT_CONFIGS]

    if not args.skip_preflight:
        run_preflight_or_exit(
            repo_root=repo_root,
            manifest_path=manifest_path,
            run_group_dir=run_group_dir,
            gt_dir=gt_dir,
            splits=args.splits,
            video_ids=args.video_ids,
            max_videos=int(args.max_videos),
            config_paths=config_paths,
            overwrite_run_group=bool(args.overwrite_run_group),
            allow_extra_gt_ids=bool(args.allow_extra_gt_ids),
        )

    run_group_dir.mkdir(parents=True, exist_ok=True)

    config_order = [name for name, _ in DEFAULT_CONFIGS]

    run_experiments_cmd = [
        args.python_executable,
        "tools/run_experiments.py",
        "--manifest",
        args.manifest,
        "--experiments-root",
        to_repo_relative(experiments_root, repo_root),
        "--run-group",
        run_group,
        "--splits",
        args.splits,
        "--video-ids",
        args.video_ids,
        "--max-videos",
        str(int(args.max_videos)),
    ]
    if args.max_frames is not None:
        run_experiments_cmd.extend(["--max-frames", str(int(args.max_frames))])
    if args.stop_on_error:
        run_experiments_cmd.append("--stop-on-error")
    if args.dry_run:
        run_experiments_cmd.append("--dry-run")
    for cfg_name, cfg_path in DEFAULT_CONFIGS:
        run_experiments_cmd.extend(["--config", f"{cfg_name}={cfg_path}"])

    run_rc = run_cmd(run_experiments_cmd, cwd=repo_root)
    if args.stop_on_error and run_rc != 0:
        print("Ablation aborted because run_experiments failed and --stop-on-error is set.")
        return run_rc

    if args.dry_run:
        print("Dry-run mode: evaluator and summary reports are skipped.")
        print(f"Run group directory: {run_group_dir}")
        return 0 if run_rc == 0 else run_rc

    eval_cmd = [
        args.python_executable,
        "tools/eval_events.py",
        "--run-group",
        str(run_group_dir),
        "--experiments-root",
        to_repo_relative(experiments_root, repo_root),
        "--gt-dir",
        args.gt_dir,
        "--tolerance-frames",
        str(int(args.tolerance_frames)),
        "--output-subdir",
        args.evaluation_subdir,
    ]
    eval_rc = run_cmd(eval_cmd, cwd=repo_root)

    runs_summary_path = run_group_dir / "runs_summary.csv"
    runs = read_csv_rows(runs_summary_path)
    if not runs:
        raise RuntimeError(f"No runs found in summary: {runs_summary_path}")

    success_runs_by_cfg: dict[str, int] = {cfg: 0 for cfg in config_order}
    input_fps_by_cfg: dict[str, list[float]] = {cfg: [] for cfg in config_order}
    processing_fps_by_cfg: dict[str, list[float]] = {cfg: [] for cfg in config_order}
    inference_fps_by_cfg: dict[str, list[float]] = {cfg: [] for cfg in config_order}

    phase_stage_samples_by_cfg: dict[str, dict[str, dict[str, list[float]]]] = {
        cfg: {phase: {stage: [] for stage in STAGE_NAMES} for phase in PHASES} for cfg in config_order
    }
    phase_loop_samples_by_cfg: dict[str, dict[str, list[float]]] = {
        cfg: {phase: [] for phase in PHASES} for cfg in config_order
    }
    phase_infer_samples_by_cfg: dict[str, dict[str, list[float]]] = {
        cfg: {phase: [] for phase in PHASES} for cfg in config_order
    }
    phase_frame_counts_by_cfg: dict[str, dict[str, int]] = {
        cfg: {phase: 0 for phase in PHASES} for cfg in config_order
    }
    phase_inferred_counts_by_cfg: dict[str, dict[str, int]] = {
        cfg: {phase: 0 for phase in PHASES} for cfg in config_order
    }

    for run in runs:
        cfg = (run.get("config_name") or "").strip()
        status = (run.get("status") or "").strip()
        output_dir_val = (run.get("output_dir") or "").strip()
        if cfg not in success_runs_by_cfg:
            continue
        if status != "success":
            continue
        run_output_dir = resolve_output_dir(repo_root, output_dir_val)
        success_runs_by_cfg[cfg] += 1

        runtime = load_runtime_summary(run_output_dir)
        if runtime:
            v = try_float(runtime.get("input_fps"))
            if v is not None:
                input_fps_by_cfg[cfg].append(v)
            v = try_float(runtime.get("processing_fps"))
            if v is not None:
                processing_fps_by_cfg[cfg].append(v)
            v = try_float(runtime.get("inference_fps"))
            if v is not None:
                inference_fps_by_cfg[cfg].append(v)

        frame_metrics_path = run_output_dir / "frame_metrics.csv"
        phase_samples = collect_phase_samples(frame_metrics_path, warmup_frames=int(args.warmup_frames))
        for phase in PHASES:
            phase_frame_counts_by_cfg[cfg][phase] += int(phase_samples["frame_counts"][phase])
            phase_inferred_counts_by_cfg[cfg][phase] += int(phase_samples["inferred_counts"][phase])
            phase_loop_samples_by_cfg[cfg][phase].extend(phase_samples["loop_samples"][phase])
            phase_infer_samples_by_cfg[cfg][phase].extend(phase_samples["infer_samples"][phase])
            for stage_name in STAGE_NAMES:
                phase_stage_samples_by_cfg[cfg][phase][stage_name].extend(
                    phase_samples["stage_samples"][phase][stage_name]
                )

    quality_map: dict[str, dict[str, str]] = {}
    aggregate_metrics_path = run_group_dir / args.evaluation_subdir / "aggregate_metrics.csv"
    if aggregate_metrics_path.exists():
        quality_map = read_quality_map(aggregate_metrics_path)

    stage_rows = build_stage_timing_summary(
        run_group=run_group,
        config_order=config_order,
        phase_stage_samples_by_cfg=phase_stage_samples_by_cfg,
    )

    warmup_steady_rows = build_warmup_steady_summary_rows(
        run_group=run_group,
        config_order=config_order,
        phase_frame_counts_by_cfg=phase_frame_counts_by_cfg,
        phase_inferred_counts_by_cfg=phase_inferred_counts_by_cfg,
        phase_loop_samples_by_cfg=phase_loop_samples_by_cfg,
        phase_infer_samples_by_cfg=phase_infer_samples_by_cfg,
        steady_min_frames=int(args.steady_min_frames),
    )

    ablation_rows: list[dict[str, str]] = []
    for cfg in config_order:
        q = quality_map.get(cfg, {})
        gt_total_val = 0
        q_status = "missing_evaluation"
        if q:
            eval_status = (q.get("eval_status") or "").strip()
            gt_total_val = int(float(q.get("gt_total", "0") or 0))
            if eval_status == "evaluated" and gt_total_val > 0:
                q_status = "available_with_gt"
            elif eval_status == "evaluated" and gt_total_val == 0:
                q_status = "evaluated_no_gt"
            else:
                q_status = eval_status or "present"

        input_stats = stats(input_fps_by_cfg[cfg])
        processing_stats = stats(processing_fps_by_cfg[cfg])
        inference_stats = stats(inference_fps_by_cfg[cfg])

        all_perf = phase_perf_stats(
            frame_count=phase_frame_counts_by_cfg[cfg]["all"],
            inferred_count=phase_inferred_counts_by_cfg[cfg]["all"],
            loop_values=phase_loop_samples_by_cfg[cfg]["all"],
            infer_values=phase_infer_samples_by_cfg[cfg]["all"],
            steady_min_frames=int(args.steady_min_frames),
            phase="all",
        )
        warmup_perf = phase_perf_stats(
            frame_count=phase_frame_counts_by_cfg[cfg]["warmup"],
            inferred_count=phase_inferred_counts_by_cfg[cfg]["warmup"],
            loop_values=phase_loop_samples_by_cfg[cfg]["warmup"],
            infer_values=phase_infer_samples_by_cfg[cfg]["warmup"],
            steady_min_frames=int(args.steady_min_frames),
            phase="warmup",
        )
        steady_perf = phase_perf_stats(
            frame_count=phase_frame_counts_by_cfg[cfg]["steady"],
            inferred_count=phase_inferred_counts_by_cfg[cfg]["steady"],
            loop_values=phase_loop_samples_by_cfg[cfg]["steady"],
            infer_values=phase_infer_samples_by_cfg[cfg]["steady"],
            steady_min_frames=int(args.steady_min_frames),
            phase="steady",
        )

        if success_runs_by_cfg[cfg] <= 0:
            perf_status = "no_success_runs"
        elif all_perf["data_status"] == "missing":
            perf_status = "missing_frame_metrics"
        elif steady_perf["data_status"] == "insufficient_steady_frames":
            perf_status = "limited_steady_state"
        else:
            perf_status = "available"

        steady_has_data = steady_perf["data_status"] != "missing"
        near_real_time = ""
        if input_stats["count"] > 0 and input_stats["mean"] > 0:
            fps_for_rule = steady_perf["processing_fps_est"] if steady_has_data else all_perf["processing_fps_est"]
            near_real_time = "yes" if fps_for_rule >= (0.8 * input_stats["mean"]) else "no"

        bottleneck_phase = "steady" if steady_has_data and steady_perf["frame_count"] > 0 else "all"
        bottleneck_name, bottleneck_mean, bottleneck_share = pick_primary_bottleneck(
            phase_stage_samples_by_cfg[cfg][bottleneck_phase]
        )

        notes = []
        if q_status in {"missing_evaluation", "evaluated_no_gt"}:
            notes.append("quality_metrics_not_strongly_informative")
        if gt_total_val > 0 and gt_total_val < 10:
            notes.append("limited_gt_event_count_first_round")
        if steady_perf["data_status"] == "insufficient_steady_frames":
            notes.append("steady_state_sample_too_small")
        if steady_perf["frame_count"] <= 0:
            notes.append("no_steady_state_frames")

        ablation_rows.append(
            {
                "run_group": run_group,
                "config_name": cfg,
                "quality_status": q_status,
                "eval_status": q.get("eval_status", ""),
                "videos_evaluated": q.get("videos_evaluated", ""),
                "gt_total": q.get("gt_total", ""),
                "tp_total": q.get("tp_total", ""),
                "fp_total": q.get("fp_total", ""),
                "fn_total": q.get("fn_total", ""),
                "precision": q.get("precision", ""),
                "recall": q.get("recall", ""),
                "f1": q.get("f1", ""),
                "false_alarms_per_hour": q.get("false_alarms_per_hour", ""),
                "mean_detection_delay_sec": q.get("mean_detection_delay_sec", ""),
                "performance_status": perf_status,
                "successful_runs": str(success_runs_by_cfg[cfg]),
                "input_fps_mean": fmt(input_stats["mean"]) if input_stats["count"] > 0 else "",
                "processing_fps_mean": fmt(processing_stats["mean"]) if processing_stats["count"] > 0 else "",
                "inference_fps_mean": fmt(inference_stats["mean"]) if inference_stats["count"] > 0 else "",
                "frames_all": str(all_perf["frame_count"]),
                "frames_warmup": str(warmup_perf["frame_count"]),
                "frames_steady": str(steady_perf["frame_count"]),
                "processing_fps_all": fmt(all_perf["processing_fps_est"]) if all_perf["frame_count"] > 0 else "",
                "processing_fps_warmup": fmt(warmup_perf["processing_fps_est"]) if warmup_perf["frame_count"] > 0 else "",
                "processing_fps_steady": fmt(steady_perf["processing_fps_est"]) if steady_perf["frame_count"] > 0 else "",
                "inference_fps_all": fmt(all_perf["inference_fps_est"]) if all_perf["frame_count"] > 0 else "",
                "inference_fps_warmup": fmt(warmup_perf["inference_fps_est"]) if warmup_perf["frame_count"] > 0 else "",
                "inference_fps_steady": fmt(steady_perf["inference_fps_est"]) if steady_perf["frame_count"] > 0 else "",
                "latency_mean_ms": fmt(all_perf["loop_stats"]["mean"]) if all_perf["loop_stats"]["count"] > 0 else "",
                "latency_median_ms": fmt(all_perf["loop_stats"]["median"]) if all_perf["loop_stats"]["count"] > 0 else "",
                "latency_p90_ms": fmt(all_perf["loop_stats"]["p90"]) if all_perf["loop_stats"]["count"] > 0 else "",
                "latency_p90_ms_warmup": fmt(warmup_perf["loop_stats"]["p90"]) if warmup_perf["loop_stats"]["count"] > 0 else "",
                "latency_p90_ms_steady": fmt(steady_perf["loop_stats"]["p90"]) if steady_perf["loop_stats"]["count"] > 0 else "",
                "near_real_time": near_real_time,
                "primary_bottleneck_phase": bottleneck_phase,
                "primary_bottleneck_stage": bottleneck_name,
                "primary_bottleneck_stage_mean_ms": fmt(bottleneck_mean) if bottleneck_mean is not None else "",
                "primary_bottleneck_share_pct": fmt(bottleneck_share) if bottleneck_share is not None else "",
                "notes": ";".join(notes),
            }
        )

    analysis_dir = run_group_dir / args.analysis_subdir
    analysis_dir.mkdir(parents=True, exist_ok=True)

    ablation_results_path = analysis_dir / "ablation_results.csv"
    stage_timing_summary_path = analysis_dir / "stage_timing_summary.csv"
    warmup_summary_path = analysis_dir / "warmup_steady_summary.csv"
    performance_report_path = analysis_dir / "performance_report.md"
    defense_summary_path = analysis_dir / "defense_summary.md"
    metadata_path = analysis_dir / "ablation_metadata.json"

    write_csv(
        ablation_results_path,
        fieldnames=[
            "run_group",
            "config_name",
            "quality_status",
            "eval_status",
            "videos_evaluated",
            "gt_total",
            "tp_total",
            "fp_total",
            "fn_total",
            "precision",
            "recall",
            "f1",
            "false_alarms_per_hour",
            "mean_detection_delay_sec",
            "performance_status",
            "successful_runs",
            "input_fps_mean",
            "processing_fps_mean",
            "inference_fps_mean",
            "frames_all",
            "frames_warmup",
            "frames_steady",
            "processing_fps_all",
            "processing_fps_warmup",
            "processing_fps_steady",
            "inference_fps_all",
            "inference_fps_warmup",
            "inference_fps_steady",
            "latency_mean_ms",
            "latency_median_ms",
            "latency_p90_ms",
            "latency_p90_ms_warmup",
            "latency_p90_ms_steady",
            "near_real_time",
            "primary_bottleneck_phase",
            "primary_bottleneck_stage",
            "primary_bottleneck_stage_mean_ms",
            "primary_bottleneck_share_pct",
            "notes",
        ],
        rows=ablation_rows,
    )
    write_csv(
        stage_timing_summary_path,
        fieldnames=[
            "run_group",
            "config_name",
            "phase",
            "stage_name",
            "samples_count",
            "mean_ms",
            "median_ms",
            "p90_ms",
            "total_ms",
            "share_of_total_loop_pct",
            "data_status",
        ],
        rows=stage_rows,
    )
    write_csv(
        warmup_summary_path,
        fieldnames=[
            "run_group",
            "config_name",
            "phase",
            "frames_count",
            "inferred_frames_count",
            "processing_fps_est",
            "inference_fps_est",
            "loop_mean_ms",
            "loop_median_ms",
            "loop_p90_ms",
            "infer_mean_ms",
            "infer_median_ms",
            "infer_p90_ms",
            "data_status",
        ],
        rows=warmup_steady_rows,
    )

    report_md = build_performance_report_md(
        run_group=run_group,
        analysis_dir=analysis_dir,
        config_order=config_order,
        ablation_rows=ablation_rows,
        warmup_steady_rows=warmup_steady_rows,
        manifest=args.manifest,
        max_frames=args.max_frames,
        warmup_frames=int(args.warmup_frames),
        steady_min_frames=int(args.steady_min_frames),
    )
    performance_report_path.write_text(report_md, encoding="utf-8")

    defense_summary_md = build_defense_summary_md(
        run_group=run_group,
        config_order=config_order,
        ablation_rows=ablation_rows,
        manifest=args.manifest,
        max_frames=args.max_frames,
        warmup_frames=int(args.warmup_frames),
    )
    defense_summary_path.write_text(defense_summary_md, encoding="utf-8")

    metadata = {
        "generated_at_utc": utc_now_iso(),
        "run_group": run_group,
        "run_group_dir": str(run_group_dir),
        "analysis_dir": str(analysis_dir),
        "evaluation_subdir": args.evaluation_subdir,
        "analysis_subdir": args.analysis_subdir,
        "manifest": args.manifest,
        "max_frames": args.max_frames,
        "warmup_frames": int(args.warmup_frames),
        "steady_min_frames": int(args.steady_min_frames),
        "gt_dir": args.gt_dir,
        "tolerance_frames": int(args.tolerance_frames),
        "configs": [{"name": name, "path": path} for name, path in DEFAULT_CONFIGS],
        "run_experiments_rc": int(run_rc),
        "eval_events_rc": int(eval_rc),
        "ablation_results_csv": str(ablation_results_path),
        "stage_timing_summary_csv": str(stage_timing_summary_path),
        "warmup_steady_summary_csv": str(warmup_summary_path),
        "performance_report_md": str(performance_report_path),
        "defense_summary_md": str(defense_summary_path),
        "quality_available": bool(quality_map),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Run group: {run_group_dir}")
    print(f"Ablation results: {ablation_results_path}")
    print(f"Stage timing summary: {stage_timing_summary_path}")
    print(f"Warm-up vs steady summary: {warmup_summary_path}")
    print(f"Performance report: {performance_report_path}")
    print(f"Defense summary: {defense_summary_path}")
    print(f"Metadata: {metadata_path}")
    if eval_rc != 0:
        print("Warning: eval_events returned non-zero. Quality columns may be incomplete.")

    return 0 if (run_rc == 0 and eval_rc == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
