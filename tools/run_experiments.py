from __future__ import annotations

import argparse
import copy
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required. Install with: pip install pyyaml") from exc

from ppe_monitoring.config import load_config


MANIFEST_REQUIRED_COLUMNS = ["video_id", "source_path", "split"]
ALLOWED_SPLITS = {"dev", "test", "stress"}
SUMMARY_FIELDS = [
    "timestamp_utc",
    "run_group",
    "config_name",
    "config_path",
    "video_id",
    "split",
    "source_path",
    "status",
    "output_dir",
    "started_at_utc",
    "ended_at_utc",
    "duration_sec",
    "return_code",
    "stdout_log",
    "stderr_log",
    "resolved_config_path",
    "error_message",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_csv_list(value: str | None) -> list[str]:
    if value is None:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


def sanitize_component(raw: str) -> str:
    out = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    result = "".join(out).strip("._")
    return result or "item"


def to_repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path)


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_video_manifest(manifest_path: Path, repo_root: Path) -> list[dict[str, str]]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Video manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Manifest has no header: {manifest_path}")

        missing = [c for c in MANIFEST_REQUIRED_COLUMNS if c not in set(reader.fieldnames)]
        if missing:
            raise ValueError(f"Manifest missing required columns {missing}: {manifest_path}")

        rows: list[dict[str, str]] = []
        seen_video_ids: set[str] = set()
        for line_idx, row in enumerate(reader, start=2):
            video_id = (row.get("video_id") or "").strip()
            source_path = (row.get("source_path") or "").strip()
            split = (row.get("split") or "").strip()
            scenario_tag = (row.get("scenario_tag") or "").strip()
            notes = (row.get("notes") or "").strip()

            if not video_id:
                raise ValueError(f"{manifest_path}:{line_idx} empty video_id")
            if video_id in seen_video_ids:
                raise ValueError(f"{manifest_path}:{line_idx} duplicate video_id '{video_id}'")
            seen_video_ids.add(video_id)

            if not source_path:
                raise ValueError(f"{manifest_path}:{line_idx} empty source_path")
            if split not in ALLOWED_SPLITS:
                raise ValueError(
                    f"{manifest_path}:{line_idx} invalid split '{split}', expected {sorted(ALLOWED_SPLITS)}"
                )

            source_abs = Path(source_path)
            if not source_abs.is_absolute():
                source_abs = (repo_root / source_abs).resolve()
            if not source_abs.exists():
                raise FileNotFoundError(f"{manifest_path}:{line_idx} source file not found: {source_path}")

            rows.append(
                {
                    "video_id": video_id,
                    "source_path": source_path,
                    "split": split,
                    "scenario_tag": scenario_tag,
                    "notes": notes,
                }
            )
    return rows


def select_manifest_rows(
    rows: list[dict[str, str]],
    splits: set[str],
    video_ids: set[str] | None,
    max_videos: int | None,
) -> list[dict[str, str]]:
    selected = [r for r in rows if r["split"] in splits]
    if video_ids:
        selected = [r for r in selected if r["video_id"] in video_ids]
    if max_videos is not None and max_videos > 0:
        selected = selected[:max_videos]
    return selected


def parse_configs(config_args: list[str] | None, repo_root: Path) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    if config_args:
        for item in config_args:
            if "=" not in item:
                raise ValueError(f"Invalid --config format '{item}'. Expected name=path")
            name, raw_path = item.split("=", 1)
            name = name.strip()
            raw_path = raw_path.strip()
            if not name:
                raise ValueError(f"Invalid --config name in '{item}'")
            if not raw_path:
                raise ValueError(f"Invalid --config path in '{item}'")
            cfg_path = Path(raw_path)
            if not cfg_path.is_absolute():
                cfg_path = (repo_root / cfg_path).resolve()
            if not cfg_path.exists():
                raise FileNotFoundError(f"Config file not found for '{name}': {cfg_path}")
            pairs.append((name, cfg_path))
    else:
        defaults = [
            ("baseline", repo_root / "configs" / "baseline.yaml"),
            ("proposed", repo_root / "configs" / "proposed.yaml"),
        ]
        for name, cfg_path in defaults:
            if not cfg_path.exists():
                raise FileNotFoundError(
                    f"Default config not found: {cfg_path}. "
                    "Use --config name=path to provide explicit configs."
                )
            pairs.append((name, cfg_path.resolve()))
    return pairs


def ensure_summary_files(run_group_dir: Path) -> tuple[Path, Path]:
    run_group_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = run_group_dir / "runs_summary.csv"
    summary_jsonl = run_group_dir / "runs_summary.jsonl"

    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
    summary_jsonl.write_text("", encoding="utf-8")
    return summary_csv, summary_jsonl


def append_summary(summary_csv: Path, summary_jsonl: Path, record: dict[str, Any]) -> None:
    row = {k: record.get(k, "") for k in SUMMARY_FIELDS}
    with summary_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writerow(row)
    with summary_jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_run_plan(run_group_dir: Path, plan_rows: list[dict[str, str]]) -> Path:
    path = run_group_dir / "run_plan.csv"
    fieldnames = [
        "run_group",
        "config_name",
        "config_path",
        "video_id",
        "split",
        "source_path",
        "scenario_tag",
        "notes",
        "output_dir",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan_rows:
            writer.writerow(row)
    return path


def build_resolved_config(
    base_cfg: dict[str, Any],
    source_path: str,
    video_id: str,
    output_dir: Path,
    max_frames: int | None,
    repo_root: Path,
) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg.setdefault("pipeline", {})
    cfg.setdefault("output", {})

    cfg["pipeline"]["source"] = source_path
    cfg["pipeline"]["video_id"] = video_id
    cfg["pipeline"]["display_preview"] = False
    if max_frames is not None:
        cfg["pipeline"]["max_frames"] = int(max_frames)

    cfg["output"]["video_path"] = to_repo_relative(output_dir / "processed.mp4", repo_root)
    cfg["output"]["events_csv"] = to_repo_relative(output_dir / "events.csv", repo_root)
    cfg["output"]["events_jsonl"] = to_repo_relative(output_dir / "events.jsonl", repo_root)
    cfg["output"]["metrics_csv"] = to_repo_relative(output_dir / "frame_metrics.csv", repo_root)
    cfg["output"]["profile_json"] = to_repo_relative(output_dir / "runtime_profile.json", repo_root)
    return cfg


def run_one(
    *,
    repo_root: Path,
    run_group: str,
    config_name: str,
    config_path: Path,
    manifest_row: dict[str, str],
    output_dir: Path,
    python_executable: str,
    max_frames: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    started = utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    stdout_log = output_dir / "stdout.log"
    stderr_log = output_dir / "stderr.log"
    resolved_config_path = output_dir / "resolved_config.yaml"
    run_metadata_path = output_dir / "run_metadata.json"

    summary_record: dict[str, Any] = {
        "timestamp_utc": started,
        "run_group": run_group,
        "config_name": config_name,
        "config_path": to_repo_relative(config_path, repo_root),
        "video_id": manifest_row["video_id"],
        "split": manifest_row["split"],
        "source_path": manifest_row["source_path"],
        "status": "dry_run" if dry_run else "pending",
        "output_dir": to_repo_relative(output_dir, repo_root),
        "started_at_utc": started,
        "ended_at_utc": "",
        "duration_sec": "",
        "return_code": "",
        "stdout_log": to_repo_relative(stdout_log, repo_root),
        "stderr_log": to_repo_relative(stderr_log, repo_root),
        "resolved_config_path": to_repo_relative(resolved_config_path, repo_root),
        "error_message": "",
    }

    base_cfg = load_config(config_path=str(config_path))
    resolved_cfg = build_resolved_config(
        base_cfg=base_cfg,
        source_path=manifest_row["source_path"],
        video_id=manifest_row["video_id"],
        output_dir=output_dir,
        max_frames=max_frames,
        repo_root=repo_root,
    )
    write_yaml(resolved_config_path, resolved_cfg)

    cmd = [
        python_executable,
        "main.py",
        "--config",
        to_repo_relative(resolved_config_path, repo_root),
        "--no-preview",
    ]
    if max_frames is not None:
        cmd.extend(["--max-frames", str(int(max_frames))])

    run_metadata: dict[str, Any] = {
        **summary_record,
        "command": cmd,
        "scenario_tag": manifest_row.get("scenario_tag", ""),
        "notes": manifest_row.get("notes", ""),
    }

    if dry_run:
        ended = utc_now_iso()
        summary_record["status"] = "dry_run"
        summary_record["ended_at_utc"] = ended
        summary_record["duration_sec"] = "0.0"
        run_metadata.update(summary_record)
        run_metadata_path.write_text(json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary_record

    start_dt = datetime.now(timezone.utc)
    with stdout_log.open("w", encoding="utf-8") as stdout_f, stderr_log.open("w", encoding="utf-8") as stderr_f:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            check=False,
        )
    end_dt = datetime.now(timezone.utc)
    ended = end_dt.isoformat()
    duration_sec = max((end_dt - start_dt).total_seconds(), 0.0)

    summary_record["ended_at_utc"] = ended
    summary_record["duration_sec"] = f"{duration_sec:.3f}"
    summary_record["return_code"] = str(proc.returncode)

    if proc.returncode == 0:
        summary_record["status"] = "success"
    else:
        summary_record["status"] = "failed"
        error_message = f"main.py exited with code {proc.returncode}"
        summary_record["error_message"] = error_message

    run_metadata.update(summary_record)
    run_metadata_path.write_text(json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch experiment runner over video manifest for baseline/proposed configs."
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/video_manifest.csv",
        help="Path to video manifest CSV.",
    )
    parser.add_argument(
        "--splits",
        type=str,
        default="dev,test,stress",
        help="Comma-separated splits to run (dev,test,stress).",
    )
    parser.add_argument(
        "--video-ids",
        type=str,
        default="",
        help="Optional comma-separated subset of video_id values.",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=0,
        help="Optional cap on number of selected videos (0 = no limit).",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional max frames per run (forwarded to pipeline).",
    )
    parser.add_argument(
        "--experiments-root",
        type=str,
        default="output_files/experiments",
        help="Root directory for experiment outputs.",
    )
    parser.add_argument(
        "--run-group",
        type=str,
        default="",
        help="Optional run group name. Default: auto timestamp.",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        help="Config mapping in format name=path. Can be repeated. "
        "If omitted, uses baseline/proposed defaults in configs/.",
    )
    parser.add_argument(
        "--python-executable",
        type=str,
        default=sys.executable,
        help="Python executable used for subprocess runs of main.py.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and materialize run structure without executing main.py.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop batch execution on first failed run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    experiments_root = Path(args.experiments_root)
    if not experiments_root.is_absolute():
        experiments_root = (repo_root / experiments_root).resolve()

    run_group = args.run_group.strip() or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_group = sanitize_component(run_group)
    run_group_dir = experiments_root / run_group
    run_group_dir.mkdir(parents=True, exist_ok=True)

    split_values = set(parse_csv_list(args.splits))
    invalid_splits = sorted(split_values - ALLOWED_SPLITS)
    if invalid_splits:
        raise ValueError(f"Invalid split(s): {invalid_splits}. Allowed: {sorted(ALLOWED_SPLITS)}")
    if not split_values:
        raise ValueError("No splits selected.")

    video_ids_list = parse_csv_list(args.video_ids)
    video_ids = set(video_ids_list) if video_ids_list else None

    configs = parse_configs(args.config, repo_root=repo_root)
    manifest_rows = read_video_manifest(manifest_path, repo_root=repo_root)
    selected_rows = select_manifest_rows(
        rows=manifest_rows,
        splits=split_values,
        video_ids=video_ids,
        max_videos=args.max_videos if args.max_videos and args.max_videos > 0 else None,
    )
    if not selected_rows:
        raise RuntimeError("No videos selected after applying split/video filters.")

    summary_csv, summary_jsonl = ensure_summary_files(run_group_dir)

    plan_rows: list[dict[str, str]] = []
    for config_name, config_path in configs:
        safe_config_name = sanitize_component(config_name)
        for row in selected_rows:
            safe_video_id = sanitize_component(row["video_id"])
            out_dir = run_group_dir / safe_config_name / safe_video_id
            plan_rows.append(
                {
                    "run_group": run_group,
                    "config_name": safe_config_name,
                    "config_path": to_repo_relative(config_path, repo_root),
                    "video_id": row["video_id"],
                    "split": row["split"],
                    "source_path": row["source_path"],
                    "scenario_tag": row.get("scenario_tag", ""),
                    "notes": row.get("notes", ""),
                    "output_dir": to_repo_relative(out_dir, repo_root),
                }
            )
    run_plan_path = write_run_plan(run_group_dir, plan_rows)

    print(f"Run group: {run_group}")
    print(f"Manifest: {to_repo_relative(manifest_path, repo_root)}")
    print(f"Selected videos: {len(selected_rows)}")
    print(f"Configs: {[name for name, _ in configs]}")
    print(f"Planned runs: {len(plan_rows)}")
    print(f"Run plan: {to_repo_relative(run_plan_path, repo_root)}")
    if args.dry_run:
        print("Dry-run mode: execution skipped.")

    failed_runs = 0
    for config_name, config_path in configs:
        safe_config_name = sanitize_component(config_name)
        for row in selected_rows:
            safe_video_id = sanitize_component(row["video_id"])
            out_dir = run_group_dir / safe_config_name / safe_video_id
            print(
                f"[RUN] config={safe_config_name} video_id={row['video_id']} "
                f"split={row['split']} dry_run={args.dry_run}"
            )
            record = run_one(
                repo_root=repo_root,
                run_group=run_group,
                config_name=safe_config_name,
                config_path=config_path,
                manifest_row=row,
                output_dir=out_dir,
                python_executable=args.python_executable,
                max_frames=args.max_frames,
                dry_run=args.dry_run,
            )
            append_summary(summary_csv, summary_jsonl, record)

            if record["status"] == "failed":
                failed_runs += 1
                print(f"[FAIL] config={safe_config_name} video_id={row['video_id']} -> {record['error_message']}")
                if args.stop_on_error:
                    print("Stopping due to --stop-on-error.")
                    print(f"Summary CSV: {to_repo_relative(summary_csv, repo_root)}")
                    print(f"Summary JSONL: {to_repo_relative(summary_jsonl, repo_root)}")
                    return 1
            else:
                print(f"[OK] status={record['status']} output={record['output_dir']}")

    print(f"Summary CSV: {to_repo_relative(summary_csv, repo_root)}")
    print(f"Summary JSONL: {to_repo_relative(summary_jsonl, repo_root)}")
    print(f"Failed runs: {failed_runs}")
    return 1 if failed_runs > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
