from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REQUIRED_GT_COLUMNS = [
    "video_id",
    "event_id",
    "start_frame",
    "end_frame",
    "violation_type",
]
OPTIONAL_GT_COLUMNS = ["zone_id", "notes"]
KNOWN_VIOLATION_TYPES = {"no_hardhat"}
KNOWN_SPLITS = {"dev", "test", "stress"}


def _is_non_negative_int(value: str) -> bool:
    return value.isdigit()


def _read_manifest_video_ids(manifest_path: Path) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    if not manifest_path.exists():
        errors.append(f"Manifest not found: {manifest_path}")
        return set(), errors

    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            errors.append(f"Manifest has no header: {manifest_path}")
            return set(), errors

        required_manifest_cols = {"video_id", "source_path", "split"}
        missing = sorted(required_manifest_cols - set(reader.fieldnames))
        if missing:
            errors.append(f"Manifest missing required columns {missing}: {manifest_path}")
            return set(), errors

        video_ids: set[str] = set()
        for line_idx, row in enumerate(reader, start=2):
            video_id = (row.get("video_id") or "").strip()
            source_path = (row.get("source_path") or "").strip()
            split = (row.get("split") or "").strip()

            if not video_id:
                errors.append(f"{manifest_path}:{line_idx} empty video_id")
            if not source_path:
                errors.append(f"{manifest_path}:{line_idx} empty source_path")
            if split not in KNOWN_SPLITS:
                errors.append(
                    f"{manifest_path}:{line_idx} invalid split '{split}', expected one of {sorted(KNOWN_SPLITS)}"
                )
            if video_id in video_ids:
                errors.append(f"{manifest_path}:{line_idx} duplicate video_id '{video_id}'")
            video_ids.add(video_id)

    return video_ids, errors


def _discover_gt_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.csv") if p.is_file())
    return []


def _validate_gt_file(
    gt_path: Path,
    manifest_video_ids: set[str] | None,
    allow_unknown_violation_types: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    with gt_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            errors.append(f"{gt_path}: missing CSV header")
            return errors, warnings

        columns = set(reader.fieldnames)
        missing = [c for c in REQUIRED_GT_COLUMNS if c not in columns]
        if missing:
            errors.append(f"{gt_path}: missing required columns {missing}")
            return errors, warnings

        unknown_cols = sorted(columns - set(REQUIRED_GT_COLUMNS) - set(OPTIONAL_GT_COLUMNS))
        if unknown_cols:
            warnings.append(f"{gt_path}: unknown columns {unknown_cols}")

        seen_keys: set[tuple[str, str]] = set()
        row_count = 0
        for line_idx, row in enumerate(reader, start=2):
            row_count += 1
            video_id = (row.get("video_id") or "").strip()
            event_id = (row.get("event_id") or "").strip()
            start_frame_raw = (row.get("start_frame") or "").strip()
            end_frame_raw = (row.get("end_frame") or "").strip()
            violation_type = (row.get("violation_type") or "").strip()
            zone_id = (row.get("zone_id") or "").strip() if "zone_id" in columns else ""

            if not video_id:
                errors.append(f"{gt_path}:{line_idx} empty video_id")
                continue
            if manifest_video_ids is not None and video_id not in manifest_video_ids:
                errors.append(f"{gt_path}:{line_idx} video_id '{video_id}' not found in manifest")

            if not event_id:
                errors.append(f"{gt_path}:{line_idx} empty event_id")
            else:
                key = (video_id, event_id)
                if key in seen_keys:
                    errors.append(f"{gt_path}:{line_idx} duplicate event_id '{event_id}' for video_id '{video_id}'")
                seen_keys.add(key)

            if not _is_non_negative_int(start_frame_raw):
                errors.append(f"{gt_path}:{line_idx} invalid start_frame '{start_frame_raw}' (must be integer >= 0)")
                continue
            if not _is_non_negative_int(end_frame_raw):
                errors.append(f"{gt_path}:{line_idx} invalid end_frame '{end_frame_raw}' (must be integer >= 0)")
                continue

            start_frame = int(start_frame_raw)
            end_frame = int(end_frame_raw)
            if end_frame < start_frame:
                errors.append(
                    f"{gt_path}:{line_idx} invalid interval: end_frame ({end_frame}) < start_frame ({start_frame})"
                )

            if not violation_type:
                errors.append(f"{gt_path}:{line_idx} empty violation_type")
            elif (not allow_unknown_violation_types) and (violation_type not in KNOWN_VIOLATION_TYPES):
                errors.append(
                    f"{gt_path}:{line_idx} unsupported violation_type '{violation_type}', "
                    f"expected one of {sorted(KNOWN_VIOLATION_TYPES)}"
                )

            if "zone_id" in columns and zone_id == "":
                # Optional field, empty is acceptable.
                pass

        if row_count == 0:
            warnings.append(f"{gt_path}: file has header only and no events")

    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate event-level GT CSV files for hard-hat monitoring experiments."
    )
    parser.add_argument(
        "--gt",
        type=str,
        default="data/gt_events",
        help="Path to GT CSV file or directory containing GT CSV files.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/video_manifest.csv",
        help="Path to video manifest CSV. Use --no-manifest-check to disable cross-check.",
    )
    parser.add_argument(
        "--no-manifest-check",
        action="store_true",
        help="Disable checking that GT video_id exists in manifest.",
    )
    parser.add_argument(
        "--allow-unknown-violation-types",
        action="store_true",
        help="Allow violation_type values beyond current known set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gt_path = Path(args.gt)
    gt_files = _discover_gt_files(gt_path)

    if not gt_files:
        print(f"[ERROR] No GT CSV files found at: {gt_path}")
        return 1

    manifest_video_ids: set[str] | None = None
    manifest_errors: list[str] = []
    if not args.no_manifest_check:
        manifest_video_ids, manifest_errors = _read_manifest_video_ids(Path(args.manifest))
        if manifest_errors:
            for err in manifest_errors:
                print(f"[ERROR] {err}")
            return 1

    all_errors: list[str] = []
    all_warnings: list[str] = []

    for gt_file in gt_files:
        errors, warnings = _validate_gt_file(
            gt_path=gt_file,
            manifest_video_ids=manifest_video_ids,
            allow_unknown_violation_types=args.allow_unknown_violation_types,
        )
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    for warning in all_warnings:
        print(f"[WARN] {warning}")

    if all_errors:
        for err in all_errors:
            print(f"[ERROR] {err}")
        print(f"[FAIL] GT validation failed: {len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        return 1

    print(
        f"[OK] GT validation passed for {len(gt_files)} file(s): "
        f"{len(all_errors)} error(s), {len(all_warnings)} warning(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

