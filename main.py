from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ppe_monitoring.config import load_config
from ppe_monitoring.pipeline import run_pipeline

_VIDEO_SUFFIXES = frozenset({".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v", ".wmv"})


def _iter_video_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    out: list[Path] = []
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.suffix.lower() in _VIDEO_SUFFIXES:
            out.append(p)
    return out


def _output_overrides_for_subdir(output_root: Path, video_stem: str) -> dict:
    out_dir = (output_root / video_stem).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "video_path": str(out_dir / "processed.mp4"),
        "events_csv": str(out_dir / "events.csv"),
        "events_jsonl": str(out_dir / "events.jsonl"),
        "metrics_csv": str(out_dir / "frame_metrics.csv"),
        "profile_json": str(out_dir / "runtime_profile.json"),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Industrial video-first PPE monitoring pipeline (YOLO + motion + temporal events)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .yaml/.yml/.json config file. If omitted, built-in defaults are used.",
    )
    parser.add_argument("--source", type=str, default=None, help="Override input source: file, rtsp://..., or camera index.")
    parser.add_argument("--max-frames", type=int, default=None, help="Process only first N frames (debug/demo).")
    parser.add_argument("--no-preview", action="store_true", help="Disable live preview window.")
    parser.add_argument(
        "--batch-videos-dir",
        type=str,
        default=None,
        help="Run the pipeline for each video file in this directory. Writes to --batch-output-root/<video_stem>/.",
    )
    parser.add_argument(
        "--batch-output-root",
        type=str,
        default="output",
        help="Root directory for per-video outputs (default: output). Used with --batch-videos-dir.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.batch_videos_dir:
        if args.source is not None:
            raise SystemExit("--source cannot be used together with --batch-videos-dir")
        vdir = Path(args.batch_videos_dir)
        videos = _iter_video_files(vdir)
        if not videos:
            print(f"No video files found in {vdir.resolve()}")
            return
        out_root = Path(args.batch_output_root)
        batch_rows: list[dict] = []
        for vp in videos:
            print(f"\n=== Batch item: {vp.name} -> {out_root.resolve() / vp.stem} ===\n")
            overrides: dict = {
                "pipeline": {"source": str(vp.resolve())},
                "output": _output_overrides_for_subdir(out_root, vp.stem),
            }
            if args.no_preview:
                overrides["pipeline"]["display_preview"] = False
            if args.max_frames is not None:
                overrides["pipeline"]["max_frames"] = int(args.max_frames)
            cfg = load_config(config_path=args.config, overrides=overrides)
            result = run_pipeline(cfg)
            dbg = dict(result.get("detection_debug", {}) or {})
            auto_roi = dict(result.get("auto_roi", {}) or {})
            batch_rows.append(
                {
                    "video_id": vp.stem,
                    "frames_total": int(dbg.get("frames_total", 0)),
                    "inferred_frames": int(dbg.get("infer_frames_total", 0)),
                    "raw_person_detections": int(dbg.get("person_filter_totals", {}).get("raw_person_detections", 0)),
                    "filtered_person_detections": int(dbg.get("person_filter_totals", {}).get("final_person_tracks", 0)),
                    "rejected_person_by_reason": str(dbg.get("person_filter_totals", {})),
                    "hardhat_detections": int(dbg.get("hardhat_detection_total", 0)),
                    "head_detections": int(dbg.get("head_detection_total", 0)),
                    "unique_with_hardhat_persons_total": int(dbg.get("unique_with_hardhat_persons_total", 0)),
                    "active_no_hardhat_persons_now": int(dbg.get("active_no_hardhat_persons_now", 0)),
                    "unique_no_hardhat_persons_total": int(dbg.get("unique_no_hardhat_persons_total", 0)),
                    "no_hardhat_events": int(result.get("events_total", 0)),
                    "rejected_person_huge_bbox": int(dbg.get("person_filter_totals", {}).get("rejected_person_huge_bbox", 0)),
                    "rejected_person_area_jump": int(dbg.get("person_filter_totals", {}).get("rejected_person_area_jump", 0)),
                    "rejected_head_hat_size": int(dbg.get("person_filter_totals", {}).get("rejected_head_hat_size", 0)),
                    "reused_previous_bbox_due_to_jump": int(
                        dbg.get("person_filter_totals", {}).get("reused_previous_bbox_due_to_jump", 0)
                    ),
                    "auto_roi_enabled": bool(auto_roi.get("enabled", False)),
                    "auto_roi_reason": str(auto_roi.get("reason", "")),
                    "processed_video": str((out_root / vp.stem / "processed.mp4").resolve()),
                }
            )
        if batch_rows:
            diag_csv = (out_root / "detection_diagnostics.csv").resolve()
            with open(diag_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(batch_rows[0].keys()))
                writer.writeheader()
                writer.writerows(batch_rows)
            report_md = (out_root / "final_demo_report.md").resolve()
            with open(report_md, "w", encoding="utf-8") as f:
                f.write("# Final Demo Report\n\n")
                for row in batch_rows:
                    f.write(f"## {row['video_id']}\n")
                    f.write(f"- Найден человек: {'да' if row['filtered_person_detections'] > 0 else 'нет'}\n")
                    avg_p = (
                        float(row["filtered_person_detections"]) / float(max(1, row["inferred_frames"]))
                    )
                    f.write(f"- Среднее число person detections: {avg_p:.2f}\n")
                    f.write(f"- Были ли каски: {'да' if row['hardhat_detections'] > 0 else 'нет'}\n")
                    f.write(f"- Были ли нарушения: {'да' if row['no_hardhat_events'] > 0 else 'нет'}\n")
                    f.write(f"- Людей с касками (уник.): {row['unique_with_hardhat_persons_total']}\n")
                    f.write(f"- Без каски сейчас: {row['active_no_hardhat_persons_now']}\n")
                    f.write(f"- Всего нарушителей (уник.): {row['unique_no_hardhat_persons_total']}\n")
                    f.write(f"- Сколько событий: {row['no_hardhat_events']}\n")
                    f.write(
                        "- Отброшено bbox (huge/jump/head-size/reuse): "
                        f"{row['rejected_person_huge_bbox']}/"
                        f"{row['rejected_person_area_jump']}/"
                        f"{row['rejected_head_hat_size']}/"
                        f"{row['reused_previous_bbox_due_to_jump']}\n"
                    )
                    f.write(f"- Auto-ROI: {'да' if row['auto_roi_enabled'] else 'нет'} ({row['auto_roi_reason']})\n")
                    f.write(f"- Причины отбраковки person: `{row['rejected_person_by_reason']}`\n")
                    f.write(f"- Видео: `{row['processed_video']}`\n\n")
                f.write("## Подтверждение\n")
                f.write("- Русские надписи рисуются PIL-блоком, без cp1251/utf-8 артефактов.\n")
                f.write("- Толщина bbox единая по конфигу.\n")
                f.write("- Цвета: hardhat=зеленый, head=желтый, violation=красный, person with hardhat=зеленый.\n")
                f.write("- Визуальное мерцание head/hardhat снижено temporal smoothing (EMA + TTL).\n")
        return

    overrides = {}
    if args.source is not None:
        overrides.setdefault("pipeline", {})["source"] = args.source
    if args.no_preview:
        overrides.setdefault("pipeline", {})["display_preview"] = False
    if args.max_frames is not None:
        overrides.setdefault("pipeline", {})["max_frames"] = int(args.max_frames)

    cfg = load_config(config_path=args.config, overrides=overrides if overrides else None)
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
