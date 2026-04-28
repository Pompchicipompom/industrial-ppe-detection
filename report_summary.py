from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _resolve_paths(profile_path: Path, args) -> dict[str, Path]:
    profile = _read_json(profile_path)
    out_cfg = profile.get("config", {}).get("output", {})

    def choose(arg_value: str | None, cfg_key: str, default_name: str) -> Path:
        if arg_value:
            return Path(arg_value)
        cfg_value = out_cfg.get(cfg_key)
        if cfg_value:
            return Path(cfg_value)
        return profile_path.parent / default_name

    return {
        "profile": profile_path,
        "events_csv": choose(args.events_csv, "events_csv", "events.csv"),
        "events_jsonl": choose(args.events_jsonl, "events_jsonl", "events.jsonl"),
        "metrics_csv": choose(args.metrics_csv, "metrics_csv", "frame_metrics.csv"),
    }


def _summarize_events(events_rows: list[dict]) -> dict:
    if not events_rows:
        return {
            "events_total_csv": 0,
            "unique_persons": 0,
            "event_types": {},
            "first_ts": None,
            "last_ts": None,
            "max_streak": 0,
            "max_no_hardhat_duration_sec": 0.0,
        }

    event_types = Counter(row.get("event_type", "unknown") for row in events_rows)
    persons = {row.get("person_track_id", "") for row in events_rows if row.get("person_track_id", "") != ""}
    ts_values = [_safe_float(row.get("timestamp_sec", 0.0), 0.0) for row in events_rows]
    max_streak = max(_safe_int(row.get("no_hardhat_streak", 0), 0) for row in events_rows)
    max_no_hardhat_duration_sec = max(
        _safe_float(row.get("no_hardhat_duration_sec", 0.0), 0.0) for row in events_rows
    )
    return {
        "events_total_csv": len(events_rows),
        "unique_persons": len(persons),
        "event_types": dict(event_types),
        "first_ts": min(ts_values) if ts_values else None,
        "last_ts": max(ts_values) if ts_values else None,
        "max_streak": max_streak,
        "max_no_hardhat_duration_sec": max_no_hardhat_duration_sec,
    }


def _summarize_metrics(metrics_rows: list[dict]) -> dict:
    if not metrics_rows:
        return {
            "frames_logged": 0,
            "did_infer_count": 0,
            "sampled_count": 0,
            "max_motion_ratio": 0.0,
            "motion_ratio_median": 0.0,
            "active_violations_peak": 0,
            "loop_ms_p95_approx": 0.0,
        }

    motion_values = [_safe_float(r.get("motion_ratio", 0.0), 0.0) for r in metrics_rows]
    loop_ms_values = sorted(_safe_float(r.get("loop_ms", 0.0), 0.0) for r in metrics_rows)
    idx_p95 = max(0, min(len(loop_ms_values) - 1, int(round((len(loop_ms_values) - 1) * 0.95))))

    return {
        "frames_logged": len(metrics_rows),
        "did_infer_count": sum(_safe_int(r.get("did_infer", 0), 0) for r in metrics_rows),
        "sampled_count": sum(_safe_int(r.get("sampled", 0), 0) for r in metrics_rows),
        "max_motion_ratio": max(motion_values) if motion_values else 0.0,
        "motion_ratio_median": median(motion_values) if motion_values else 0.0,
        "active_violations_peak": max(_safe_int(r.get("active_violations", 0), 0) for r in metrics_rows),
        "loop_ms_p95_approx": loop_ms_values[idx_p95] if loop_ms_values else 0.0,
    }


def _table_row(key: str, value) -> str:
    return f"| {key} | {value} |"


def generate_markdown_report(
    profile: dict,
    events_rows: list[dict],
    metrics_rows: list[dict],
    paths: dict[str, Path],
    top_events: int,
) -> str:
    runtime = profile.get("runtime_summary", {})
    comparison = profile.get("comparison", {})
    rtsp = profile.get("rtsp_health", {})
    cfg = profile.get("config", {})

    event_summary = _summarize_events(events_rows)
    metric_summary = _summarize_metrics(metrics_rows)

    source = profile.get("source", "unknown")
    generated_at = profile.get("generated_at_utc", "")
    events_total_profile = profile.get("events_total", 0)

    lines: list[str] = []
    lines.append("# PPE Monitoring Commission Report")
    lines.append("")
    lines.append(f"- Generated from profile: `{paths['profile']}`")
    lines.append(f"- Report generated at: `{datetime.utcnow().isoformat()}Z`")
    lines.append(f"- Source: `{source}`")
    lines.append(f"- Profile timestamp: `{generated_at}`")
    lines.append("")

    lines.append("## 1) Runtime KPI")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(_table_row("Input FPS", f"{_safe_float(runtime.get('input_fps', 0.0)):.2f}"))
    lines.append(_table_row("Processing FPS", f"{_safe_float(runtime.get('processing_fps', 0.0)):.2f}"))
    lines.append(_table_row("Inference FPS", f"{_safe_float(runtime.get('inference_fps', 0.0)):.2f}"))
    lines.append(_table_row("Inference ms mean", f"{_safe_float(runtime.get('inference_ms_mean', 0.0)):.2f}"))
    lines.append(_table_row("Inference ms median", f"{_safe_float(runtime.get('inference_ms_median', 0.0)):.2f}"))
    lines.append(_table_row("Inference ms p90", f"{_safe_float(runtime.get('inference_ms_p90', 0.0)):.2f}"))
    lines.append(_table_row("Loop ms mean", f"{_safe_float(runtime.get('loop_ms_mean', 0.0)):.2f}"))
    lines.append(_table_row("Loop ms median", f"{_safe_float(runtime.get('loop_ms_median', 0.0)):.2f}"))
    lines.append(_table_row("Loop ms p90", f"{_safe_float(runtime.get('loop_ms_p90', 0.0)):.2f}"))
    lines.append(_table_row("Frames total", _safe_int(runtime.get("frames_total", 0), 0)))
    lines.append(_table_row("Frames inferred", _safe_int(runtime.get("frames_inferred", 0), 0)))
    lines.append("")

    lines.append("## 2) Input vs Inference")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(
        _table_row(
            "Input FPS - Inference FPS",
            f"{_safe_float(comparison.get('input_fps_minus_inference_fps', 0.0)):.2f}",
        )
    )
    lines.append(
        _table_row(
            "Inference/Input ratio",
            f"{_safe_float(comparison.get('inference_fps_to_input_fps_ratio', 0.0)):.4f}",
        )
    )
    lines.append("")

    lines.append("## 3) RTSP Health Watchdog")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(_table_row("is_rtsp", rtsp.get("is_rtsp", False)))
    lines.append(_table_row("open_attempts_total", _safe_int(rtsp.get("open_attempts_total", 0), 0)))
    lines.append(_table_row("open_successes", _safe_int(rtsp.get("open_successes", 0), 0)))
    lines.append(_table_row("open_failures", _safe_int(rtsp.get("open_failures", 0), 0)))
    lines.append(_table_row("frames_read_ok", _safe_int(rtsp.get("frames_read_ok", 0), 0)))
    lines.append(_table_row("read_failures_total", _safe_int(rtsp.get("read_failures_total", 0), 0)))
    lines.append(_table_row("disconnect_events", _safe_int(rtsp.get("disconnect_events", 0), 0)))
    lines.append(_table_row("reconnect_cycles", _safe_int(rtsp.get("reconnect_cycles", 0), 0)))
    lines.append(_table_row("reconnect_attempts_total", _safe_int(rtsp.get("reconnect_attempts_total", 0), 0)))
    lines.append(_table_row("reconnect_successes", _safe_int(rtsp.get("reconnect_successes", 0), 0)))
    lines.append(_table_row("reconnect_failures", _safe_int(rtsp.get("reconnect_failures", 0), 0)))
    lines.append(_table_row("total_downtime_sec", f"{_safe_float(rtsp.get('total_downtime_sec', 0.0)):.3f}"))
    lines.append(_table_row("longest_downtime_sec", f"{_safe_float(rtsp.get('longest_downtime_sec', 0.0)):.3f}"))
    lines.append("")

    lines.append("## 4) Event Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(_table_row("Events total (profile)", _safe_int(events_total_profile, 0)))
    lines.append(_table_row("Events total (CSV)", event_summary["events_total_csv"]))
    lines.append(_table_row("Unique person IDs", event_summary["unique_persons"]))
    lines.append(_table_row("Event types", event_summary["event_types"]))
    lines.append(_table_row("First event ts, sec", event_summary["first_ts"]))
    lines.append(_table_row("Last event ts, sec", event_summary["last_ts"]))
    lines.append(_table_row("Max no_hardhat_streak", event_summary["max_streak"]))
    lines.append(
        _table_row(
            "Max no_hardhat_duration_sec",
            f"{_safe_float(event_summary['max_no_hardhat_duration_sec']):.3f}",
        )
    )
    lines.append("")

    lines.append("## 5) Frame Metrics Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(_table_row("Frames logged", metric_summary["frames_logged"]))
    lines.append(_table_row("Sampled frames", metric_summary["sampled_count"]))
    lines.append(_table_row("Inference frames", metric_summary["did_infer_count"]))
    lines.append(_table_row("Peak active_violations", metric_summary["active_violations_peak"]))
    lines.append(_table_row("Max motion_ratio", f"{_safe_float(metric_summary['max_motion_ratio']):.6f}"))
    lines.append(_table_row("Median motion_ratio", f"{_safe_float(metric_summary['motion_ratio_median']):.6f}"))
    lines.append(_table_row("Loop ms p95 (approx)", f"{_safe_float(metric_summary['loop_ms_p95_approx']):.2f}"))
    lines.append("")

    lines.append("## 6) Top Events")
    lines.append("")
    if not events_rows:
        lines.append("No events in `events.csv` for this run.")
    else:
        lines.append("| event_id | frame_idx | timestamp_sec | person_track_id | event_type | streak | duration_sec |")
        lines.append("|---|---:|---:|---:|---|---:|---:|")
        for row in events_rows[: max(0, top_events)]:
            lines.append(
                f"| {row.get('event_id','')} | {row.get('frame_idx','')} | {row.get('timestamp_sec','')} | "
                f"{row.get('person_track_id','')} | {row.get('event_type','')} | "
                f"{row.get('no_hardhat_streak','')} | {row.get('no_hardhat_duration_sec','')} |"
            )
    lines.append("")

    lines.append("## 7) Run Configuration (key fields)")
    lines.append("")
    pipeline_cfg = cfg.get("pipeline", {})
    motion_cfg = cfg.get("motion", {})
    event_cfg = cfg.get("event_logic", {})
    lines.append("| Config key | Value |")
    lines.append("|---|---|")
    lines.append(_table_row("pipeline.source", pipeline_cfg.get("source")))
    lines.append(_table_row("pipeline.mode", pipeline_cfg.get("mode")))
    lines.append(_table_row("pipeline.sampling_fps", pipeline_cfg.get("sampling_fps")))
    lines.append(_table_row("pipeline.force_infer_every_n_frames", pipeline_cfg.get("force_infer_every_n_frames")))
    lines.append(_table_row("motion.enabled", motion_cfg.get("enabled")))
    lines.append(_table_row("motion.min_ratio", motion_cfg.get("min_ratio")))
    lines.append(_table_row("event_logic.no_hardhat_consecutive_frames", event_cfg.get("no_hardhat_consecutive_frames")))
    lines.append(_table_row("event_logic.no_hardhat_seconds_threshold", event_cfg.get("no_hardhat_seconds_threshold")))
    lines.append(_table_row("event_logic.cooldown_frames", event_cfg.get("cooldown_frames")))
    lines.append(_table_row("event_logic.cooldown_seconds", event_cfg.get("cooldown_seconds")))
    lines.append("")

    lines.append("## 8) Artifacts")
    lines.append("")
    lines.append(f"- Profile JSON: `{paths['profile']}`")
    lines.append(f"- Events CSV: `{paths['events_csv']}`")
    lines.append(f"- Events JSONL: `{paths['events_jsonl']}`")
    lines.append(f"- Frame metrics CSV: `{paths['metrics_csv']}`")
    lines.append("")

    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate commission-ready markdown report from pipeline artifacts.")
    parser.add_argument(
        "--profile",
        type=str,
        default="output_files/runtime_profile.json",
        help="Path to runtime_profile.json",
    )
    parser.add_argument("--events-csv", type=str, default=None, help="Optional override path to events.csv")
    parser.add_argument("--events-jsonl", type=str, default=None, help="Optional override path to events.jsonl")
    parser.add_argument("--metrics-csv", type=str, default=None, help="Optional override path to frame_metrics.csv")
    parser.add_argument(
        "--out",
        type=str,
        default="output_files/commission_report.md",
        help="Output markdown report path",
    )
    parser.add_argument("--top-events", type=int, default=20, help="How many events to include in Top Events table")
    return parser.parse_args()


def main():
    args = parse_args()
    profile_path = Path(args.profile)
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile file not found: {profile_path}")

    paths = _resolve_paths(profile_path, args)
    profile = _read_json(paths["profile"])
    events_rows = _read_csv_rows(paths["events_csv"])
    metrics_rows = _read_csv_rows(paths["metrics_csv"])

    report_md = generate_markdown_report(
        profile=profile,
        events_rows=events_rows,
        metrics_rows=metrics_rows,
        paths=paths,
        top_events=max(0, int(args.top_events)),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")

    print(f"Report generated: {out_path}")
    print(f"Profile: {paths['profile']}")
    print(f"Events CSV: {paths['events_csv']} (rows={len(events_rows)})")
    print(f"Metrics CSV: {paths['metrics_csv']} (rows={len(metrics_rows)})")


if __name__ == "__main__":
    main()

