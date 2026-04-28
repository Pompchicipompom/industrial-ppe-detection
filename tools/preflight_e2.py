"""E2 / ablation preflight checks: manifest, media, GT alignment, weights, run_group overwrite guard."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ppe_monitoring.config import load_config
from run_experiments import parse_csv_list, read_video_manifest, select_manifest_rows


class PreflightError(RuntimeError):
    pass


def collect_gt_video_ids(gt_dir: Path) -> set[str]:
    if not gt_dir.is_dir():
        raise PreflightError(f"GT directory does not exist or is not a directory: {gt_dir}")
    files = sorted(p for p in gt_dir.glob("*.csv") if p.is_file())
    if not files:
        raise PreflightError(f"No GT CSV files found in: {gt_dir}")
    ids: set[str] = set()
    for gt_path in files:
        with gt_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                continue
            if "video_id" not in reader.fieldnames:
                raise PreflightError(f"GT file missing 'video_id' column: {gt_path}")
            for row in reader:
                vid = (row.get("video_id") or "").strip()
                if vid:
                    ids.add(vid)
    if not ids:
        raise PreflightError(f"No non-empty video_id rows in GT CSV files under: {gt_dir}")
    return ids


def run_group_dir_nonempty(run_group_dir: Path) -> bool:
    if not run_group_dir.exists():
        return False
    try:
        next(run_group_dir.iterdir())
    except StopIteration:
        return False
    return True


def check_model_weights(repo_root: Path, config_path: Path) -> None:
    cfg = load_config(config_path=str(config_path))
    model = cfg["model"]
    w = model.get("weights_path", "")
    p = Path(str(w))
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    if not p.exists():
        raise PreflightError(f"Model weights not found for config {config_path.name}: {p}")

    if bool(model.get("enable_person_fallback", True)):
        fb = str(model.get("person_fallback_weights_path", "")).strip()
        if not fb:
            raise PreflightError(f"person_fallback_weights_path is empty in {config_path.name}")
        fb_path = Path(fb)
        if not fb_path.is_absolute():
            fb_path = (repo_root / fb_path).resolve()
        if not fb_path.exists():
            raise PreflightError(
                f"Person fallback weights not found for config {config_path.name}: {fb_path}"
            )


def run_preflight(
    *,
    repo_root: Path,
    manifest_path: Path,
    run_group_dir: Path,
    gt_dir: Path,
    splits: str,
    video_ids: str,
    max_videos: int,
    config_paths: list[Path],
    overwrite_run_group: bool,
    allow_extra_gt_ids: bool = False,
) -> None:
    if not manifest_path.is_file():
        raise PreflightError(f"Video manifest not found: {manifest_path}")

    split_values = set(parse_csv_list(splits))
    if not split_values:
        raise PreflightError("No splits selected for preflight (empty --splits).")

    video_ids_list = parse_csv_list(video_ids)
    video_ids_set = set(video_ids_list) if video_ids_list else None

    manifest_rows = read_video_manifest(manifest_path, repo_root=repo_root)
    selected = select_manifest_rows(
        rows=manifest_rows,
        splits=split_values,
        video_ids=video_ids_set,
        max_videos=max_videos if max_videos and max_videos > 0 else None,
    )
    if not selected:
        raise PreflightError("No videos selected after applying split/video filters (preflight).")

    manifest_ids = {r["video_id"] for r in selected}
    gt_dir_resolved = gt_dir.resolve()
    gt_ids = collect_gt_video_ids(gt_dir_resolved)

    missing_gt = sorted(manifest_ids - gt_ids)
    if missing_gt:
        raise PreflightError(
            "No GT rows for manifest video_id(s): "
            f"{missing_gt}\n"
            "Use data/video_manifest_e1.csv with data/gt_events/gt_events_e1.csv for E2, "
            "or fix --video-ids / GT files."
        )

    extra_gt = sorted(gt_ids - manifest_ids)
    if extra_gt and not allow_extra_gt_ids:
        raise PreflightError(
            "GT contains video_id(s) not in the selected manifest run set: "
            f"{extra_gt}\n"
            "This often means the wrong manifest (e.g. data/video_manifest.csv vs "
            "data/video_manifest_e1.csv) or mixed GT CSVs. "
            "For a subset run with a full GT directory, pass --allow-extra-gt-ids."
        )

    for cfg_path in config_paths:
        if not cfg_path.is_file():
            raise PreflightError(f"Config file not found: {cfg_path}")
        check_model_weights(repo_root, cfg_path)

    if run_group_dir_nonempty(run_group_dir) and not overwrite_run_group:
        raise PreflightError(
            f"Run group directory already exists and is not empty: {run_group_dir}\n"
            "Refusing to overwrite previous experiment artifacts. "
            "Choose a new --run-group or pass --overwrite-run-group to proceed."
        )


def run_preflight_or_exit(**kwargs: object) -> None:
    try:
        run_preflight(**kwargs)  # type: ignore[arg-type]
    except PreflightError as exc:
        print(f"[preflight] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
