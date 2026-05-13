from __future__ import annotations

"""
Extended experiment orchestration: quality ablations, temporal grid, perf sweep,
tracking cadence, and demo presets — with merged experiments_summary.csv + short report.

Layout matches run_experiments.py:
  output_files/experiments_extended/<run_group>/<config_name>/<video_id>/

E2 manifest + GT: data/video_manifest_e1.csv + data/gt_events/gt_events_e1.csv
"""

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PyYAML required") from exc

import run_experiments as rex
import run_ablation as rab
from ppe_monitoring.config import load_config
from preflight_e2 import run_preflight_or_exit

DEFAULT_EXPERIMENTS_ROOT = "output_files/experiments_extended"
SUMMARY_FIELDS = [
    "experiment_group",
    "run_group",
    "config_name",
    "config_path",
    "video_id",
    "split",
    "run_status",
    "tp",
    "fp",
    "fn",
    "precision",
    "recall",
    "f1",
    "false_alarms_per_hour",
    "mean_detection_delay_sec",
    "gt_events_count",
    "pred_events_count",
    "eval_status",
    "input_fps",
    "processing_fps",
    "inference_fps",
    "infer_latency_p90_ms",
    "steady_processing_fps_est",
    "steady_infer_frame_ratio",
    "steady_loop_p90_ms",
    "steady_infer_p90_ms",
    "f1_zero_or_missing_explanation",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _materialize_group_b(
    *,
    repo_root: Path,
    gen_dir: Path,
    matrix_full: bool,
) -> list[tuple[str, str, Path]]:
    """Return (experiment_group, config_name, path)."""
    secs = [1.0, 1.5, 2.0, 3.0]
    frames = [10, 15, 20, 30]
    if not matrix_full:
        pairs = [(1.0, 10), (1.5, 15), (2.0, 20), (3.0, 30)]
    else:
        pairs = [(s, f) for s in secs for f in frames]

    out: list[tuple[str, str, Path]] = []
    base = load_config(config_path=str(repo_root / "configs" / "proposed.yaml"))
    for s, k in pairs:
        cfg = json.loads(json.dumps(base))
        cfg.setdefault("event_logic", {})
        cfg["event_logic"]["no_hardhat_seconds_threshold"] = float(s)
        cfg["event_logic"]["no_hardhat_consecutive_frames"] = int(k)
        name = f"B_t{s:g}_k{k}"
        name = rex.sanitize_component(name.replace(".", "p"))
        path = gen_dir / f"{name}.yaml"
        _write_yaml(path, cfg)
        out.append(("B", name, path.resolve()))
    return out


def _materialize_group_c(
    *,
    repo_root: Path,
    gen_dir: Path,
    matrix_full: bool,
    include_gpu: bool,
) -> list[tuple[str, str, Path]]:
    if matrix_full:
        sampling_fps_list = [25.0, 12.0, 8.0, 5.0, 3.0]
        imgsz_list = [640, 512, 416]
    else:
        sampling_fps_list = [12.0, 8.0, 5.0]
        imgsz_list = [640, 512]

    devices: list[str] = ["cpu"]
    if include_gpu:
        devices.append("0")

    base = load_config(config_path=str(repo_root / "configs" / "proposed.yaml"))
    out: list[tuple[str, str, Path]] = []
    for sf in sampling_fps_list:
        for sz in imgsz_list:
            for dev in devices:
                cfg = json.loads(json.dumps(base))
                cfg.setdefault("pipeline", {})
                cfg.setdefault("model", {})
                cfg["pipeline"]["sampling_fps"] = float(sf)
                cfg["model"]["imgsz"] = int(sz)
                cfg["model"]["roi_imgsz"] = int(max(256, sz // 2))
                cfg["model"]["device"] = str(dev)
                dev_tag = "cpu" if dev == "cpu" else "gpu0"
                name = f"C_sf{sf:g}_sz{sz}_{dev_tag}".replace(".", "p")
                name = rex.sanitize_component(name)
                path = gen_dir / f"{name}.yaml"
                _write_yaml(path, cfg)
                out.append(("C", name, path.resolve()))
    return out


def _group_a_configs(repo_root: Path) -> list[tuple[str, str, Path]]:
    root = repo_root.resolve()
    return [
        ("A", "A1_baseline", root / "configs" / "baseline.yaml"),
        ("A", "A2_proposed", root / "configs" / "proposed.yaml"),
        ("A", "A3_proposed_soft", root / "configs" / "experiments_extended" / "a3_proposed_soft_thresholds.yaml"),
        ("A", "A4_no_roi", root / "configs" / "ablation_proposed_without_roi.yaml"),
        ("A", "A5_no_motion", root / "configs" / "ablation_proposed_without_motion.yaml"),
        ("A", "A6_no_temporal", root / "configs" / "ablation_proposed_without_temporal.yaml"),
    ]


def _group_d_configs(repo_root: Path) -> list[tuple[str, str, Path]]:
    root = repo_root.resolve()
    return [
        ("D", "D1_frequent_infer", root / "configs" / "experiments_extended" / "d1_frequent_infer.yaml"),
        ("D", "D2_proposed_tracking", root / "configs" / "proposed.yaml"),
        ("D", "D3_rare_infer", root / "configs" / "experiments_extended" / "d3_rare_infer_tracking.yaml"),
    ]


def _group_e_configs(repo_root: Path) -> list[tuple[str, str, Path]]:
    root = repo_root.resolve()
    return [
        ("E", "E_demo_fast", root / "configs" / "experiments_extended" / "demo_fast.yaml"),
        ("E", "E_baseline_visual", root / "configs" / "baseline.yaml"),
    ]


def _expand_groups(
    *,
    repo_root: Path,
    groups: set[str],
    matrix_full: bool,
    include_gpu: bool,
    run_group_dir: Path,
) -> list[tuple[str, str, Path]]:
    gen_dir = run_group_dir / "_generated_configs"
    triples: list[tuple[str, str, Path]] = []
    for g in sorted(groups):
        if g == "A":
            triples.extend(_group_a_configs(repo_root))
        elif g == "B":
            triples.extend(_materialize_group_b(repo_root=repo_root, gen_dir=gen_dir / "B", matrix_full=matrix_full))
        elif g == "C":
            triples.extend(
                _materialize_group_c(
                    repo_root=repo_root,
                    gen_dir=gen_dir / "C",
                    matrix_full=matrix_full,
                    include_gpu=include_gpu,
                )
            )
        elif g == "D":
            triples.extend(_group_d_configs(repo_root))
        elif g == "E":
            triples.extend(_group_e_configs(repo_root))
        else:
            raise ValueError(f"Unknown group {g!r}. Use A,B,C,D,E.")
    for _, name, p in triples:
        if not p.exists():
            raise FileNotFoundError(f"Config for {name} not found: {p}")
    return triples


def _run_eval(
    *,
    repo_root: Path,
    run_group_dir: Path,
    experiments_root: Path,
    gt_dir: Path,
    tolerance_frames: int,
    python_executable: str,
    eval_subdir: str,
) -> int:
    cmd = [
        python_executable,
        "tools/eval_events.py",
        "--run-group",
        str(run_group_dir),
        "--experiments-root",
        rab.to_repo_relative(experiments_root, repo_root),
        "--gt-dir",
        rab.to_repo_relative(gt_dir, repo_root),
        "--tolerance-frames",
        str(int(tolerance_frames)),
        "--output-subdir",
        eval_subdir,
    ]
    print("[CMD]", " ".join(cmd))
    return int(subprocess.run(cmd, cwd=str(repo_root), check=False).returncode)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _explain_f1_zero(row: dict[str, str]) -> str:
    try:
        f1 = float(row.get("f1") or 0.0)
    except Exception:
        f1 = 0.0
    if f1 > 1e-9:
        return ""
    status = (row.get("run_status") or "").strip()
    if status != "success":
        return f"run_not_successful:{status or 'unknown'}"
    try:
        tp = int(float(row.get("tp") or 0))
        fp = int(float(row.get("fp") or 0))
        fn = int(float(row.get("fn") or 0))
        pred_n = row.get("pred_events_count", "").strip()
        pred = int(float(pred_n)) if pred_n not in {"", "None"} else -1
    except Exception:
        return "parse_error"
    if tp == 0 and fp == 0 and fn > 0:
        return "no_true_positives_all_gt_missed_or_no_predictions"
    if tp == 0 and fp > 0 and fn > 0:
        return "only_false_positives_relative_to_gt"
    if tp == 0 and fp == 0 and fn == 0:
        return "no_gt_events_for_video_or_empty_eval"
    if pred == 0:
        return "pipeline_emitted_zero_pred_events"
    return "f1_zero_other"


def build_experiments_summary(
    *,
    repo_root: Path,
    run_group_dir: Path,
    warmup_frames: int,
    steady_min_frames: int,
    eval_subdir: str,
    config_group_by_name: dict[str, str],
) -> Path:
    runs = rab.read_csv_rows(run_group_dir / "runs_summary.csv")
    per_video_path = run_group_dir / eval_subdir / "per_video_metrics.csv"
    per_video_rows = rab.read_csv_rows(per_video_path) if per_video_path.exists() else []
    pv_key: dict[tuple[str, str], dict[str, str]] = {}
    for r in per_video_rows:
        k = ((r.get("config_name") or "").strip(), (r.get("video_id") or "").strip())
        pv_key[k] = r

    summary_rows: list[dict[str, str]] = []
    for run in runs:
        cfg_name = (run.get("config_name") or "").strip()
        video_id = (run.get("video_id") or "").strip()
        split = (run.get("split") or "").strip()
        status = (run.get("status") or "").strip()
        out_raw = (run.get("output_dir") or "").strip()
        run_out = Path(out_raw)
        if not run_out.is_absolute():
            run_out = (repo_root / run_out).resolve()

        pv = pv_key.get((cfg_name, video_id), {})

        rt = _load_json(run_out / "runtime_profile.json")
        rs = rt.get("runtime_summary") if isinstance(rt.get("runtime_summary"), dict) else {}
        infer_lat = rs.get("infer_latency_ms", {})
        p90_infer = ""
        if isinstance(infer_lat, dict):
            v = infer_lat.get("p90")
            if v is not None:
                p90_infer = str(v)

        phase_samples = rab.collect_phase_samples(run_out / "frame_metrics.csv", warmup_frames=int(warmup_frames))
        steady_frames = phase_samples["frame_counts"]["steady"]
        steady_inf = phase_samples["inferred_counts"]["steady"]
        steady_loops = phase_samples["loop_samples"]["steady"]
        steady_inf_ms = phase_samples["infer_samples"]["steady"]
        st_perf = rab.phase_perf_stats(
            frame_count=steady_frames,
            inferred_count=steady_inf,
            loop_values=steady_loops,
            infer_values=steady_inf_ms,
            steady_min_frames=int(steady_min_frames),
            phase="steady",
        )
        infer_ratio = ""
        if steady_frames > 0:
            infer_ratio = f"{float(steady_inf) / float(steady_frames):.6f}"

        row: dict[str, str] = {
            "experiment_group": config_group_by_name.get(cfg_name, ""),
            "run_group": run_group_dir.name,
            "config_name": cfg_name,
            "config_path": run.get("config_path", ""),
            "video_id": video_id,
            "split": split,
            "run_status": status,
            "tp": pv.get("tp", ""),
            "fp": pv.get("fp", ""),
            "fn": pv.get("fn", ""),
            "precision": pv.get("precision", ""),
            "recall": pv.get("recall", ""),
            "f1": pv.get("f1", ""),
            "false_alarms_per_hour": pv.get("false_alarms_per_hour", ""),
            "mean_detection_delay_sec": pv.get("mean_detection_delay_sec", ""),
            "gt_events_count": pv.get("gt_events_count", ""),
            "pred_events_count": pv.get("pred_events_count", ""),
            "eval_status": pv.get("eval_status", ""),
            "input_fps": str(rs.get("input_fps", "")),
            "processing_fps": str(rs.get("processing_fps", "")),
            "inference_fps": str(rs.get("inference_fps", "")),
            "infer_latency_p90_ms": p90_infer,
            "steady_processing_fps_est": rab.fmt(st_perf["processing_fps_est"]),
            "steady_infer_frame_ratio": infer_ratio,
            "steady_loop_p90_ms": rab.fmt(st_perf["loop_stats"]["p90"]) if st_perf["loop_stats"]["count"] > 0 else "",
            "steady_infer_p90_ms": rab.fmt(st_perf["infer_stats"]["p90"]) if st_perf["infer_stats"]["count"] > 0 else "",
            "f1_zero_or_missing_explanation": "",
        }
        row["f1_zero_or_missing_explanation"] = _explain_f1_zero(row)
        summary_rows.append(row)

    out_path = run_group_dir / "experiments_summary.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for row in summary_rows:
            w.writerow({k: row.get(k, "") for k in SUMMARY_FIELDS})
    return out_path


def _best_f1_by_group(summary_rows: list[dict[str, str]]) -> dict[str, tuple[str, float]]:
    best: dict[str, tuple[str, float]] = {}
    by_g: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in summary_rows:
        if (row.get("run_status") or "") != "success":
            continue
        g = row.get("experiment_group") or "?"
        try:
            f1 = float(row.get("f1") or 0.0)
        except Exception:
            f1 = 0.0
        by_g[g].append((row.get("config_name") or "", f1))
    for g, pairs in by_g.items():
        if not pairs:
            continue
        name, val = max(pairs, key=lambda x: x[1])
        best[g] = (name, val)
    return best


def write_experiment_report(path: Path, summary_rows: list[dict[str, str]], matrix_label: str) -> None:
    lines: list[str] = []
    lines.append(f"# Experiment report ({path.parent.name})")
    lines.append("")
    lines.append(f"- generated_utc: `{utc_now_iso()}`")
    lines.append(f"- matrix: `{matrix_label}`")
    lines.append("")
    lines.append("## Лучшие конфиги по максимуму F1 (агрегация по строкам per-video)")
    lines.append("")
    bf = _best_f1_by_group(summary_rows)
    for g in sorted(bf.keys()):
        name, val = bf[g]
        lines.append(f"- группа **{g}**: `{name}` (max F1 среди строк ≈ {val:.4f})")
    lines.append("")
    lines.append("## Где F1 = 0 или метрики отсутствуют (честно)")
    lines.append("")
    bad = [
        r
        for r in summary_rows
        if (r.get("run_status") == "success")
        and (float(r.get("f1") or 0.0) < 1e-9 or str(r.get("precision", "")).strip() == "")
    ]
    if not bad:
        lines.append("- нет явных нулевых F1 в успешных прогонах (или eval не сработал).")
    else:
        for r in bad[:40]:
            lines.append(
                f"- `{r.get('config_name')}` / `{r.get('video_id')}`: "
                f"F1={r.get('f1','')} — {r.get('f1_zero_or_missing_explanation','')}"
            )
        if len(bad) > 40:
            lines.append(f"- … ещё {len(bad) - 40} строк(и); см. experiments_summary.csv")
    lines.append("")
    lines.append("## Интерпретация для отчёта (черновик)")
    lines.append("")
    lines.append("1. **Video-first (proposed)** обычно бьёт **baseline** по FA/hour за счёт motion+temporal, ценой задержки события.")
    lines.append("2. **ROI** режет ложные срабатывания на фоне вне зоны интереса; без ROI растёт FP на сложных сценах.")
    lines.append("3. **Temporal** сглаживает дребезг детектора; без него выше FP и хуже интерпретируемость событий.")
    lines.append("4. **Motion gating** поднимает FPS в статике, но может пропустить редкое движение — баланс `min_ratio` / `force_infer`.")
    lines.append("5. Для **near real-time** смотрите `steady_processing_fps_est` vs `input_fps` и долю `steady_infer_frame_ratio`.")
    lines.append("")
    lines.append("## Финальный конфиг и демо")
    lines.append("")
    lines.append("- Рабочий промышленный компромисс: **`configs/proposed.yaml`** (как в E2).")
    lines.append("- Демонстрационный ролик с более «живыми» боксами: **`configs/experiments_extended/demo_fast.yaml`** vs **`configs/baseline.yaml`**.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extended experiments runner + experiments_summary.csv")
    p.add_argument("--groups", type=str, default="A", help="Comma list: A,B,C,D,E (or ALL).")
    p.add_argument("--matrix", type=str, choices=("full", "quick"), default="quick", help="B/C grid size.")
    p.add_argument("--manifest", type=str, default="data/video_manifest_e1.csv")
    p.add_argument("--gt-dir", type=str, default="data/gt_events")
    p.add_argument("--experiments-root", type=str, default=DEFAULT_EXPERIMENTS_ROOT)
    p.add_argument("--run-group", type=str, default="")
    p.add_argument("--splits", type=str, default="dev,test,stress")
    p.add_argument("--video-ids", type=str, default="", help="Optional subset of video_id (E2 ids).")
    p.add_argument("--max-videos", type=int, default=0)
    p.add_argument(
        "--max-frames",
        type=int,
        default=140,
        help="E2-style cap per video (default 140). Use 0 for full-length processing.",
    )
    p.add_argument("--warmup-frames", type=int, default=20)
    p.add_argument("--steady-min-frames", type=int, default=30)
    p.add_argument("--tolerance-frames", type=int, default=0)
    p.add_argument("--python-executable", type=str, default=sys.executable)
    p.add_argument("--eval-subdir", type=str, default="evaluation_extended")
    p.add_argument("--include-gpu", action="store_true", help="Group C also emits device=0 configs (needs CUDA).")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--skip-preflight", action="store_true")
    p.add_argument("--skip-eval", action="store_true")
    p.add_argument("--overwrite-run-group", action="store_true")
    p.add_argument("--allow-extra-gt-ids", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _REPO_ROOT
    experiments_root = Path(args.experiments_root)
    if not experiments_root.is_absolute():
        experiments_root = (repo_root / experiments_root).resolve()
    experiments_root.mkdir(parents=True, exist_ok=True)

    raw_groups = rex.parse_csv_list(args.groups)
    if not raw_groups:
        raw_groups = ["A"]
    if len(raw_groups) == 1 and raw_groups[0].upper() == "ALL":
        groups = {"A", "B", "C", "D", "E"}
    else:
        groups = {g.strip().upper() for g in raw_groups}

    run_group = rex.sanitize_component(args.run_group.strip() or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    run_group_dir = experiments_root / run_group

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()
    gt_dir = Path(args.gt_dir)
    if not gt_dir.is_absolute():
        gt_dir = (repo_root / gt_dir).resolve()

    triples = _expand_groups(
        repo_root=repo_root,
        groups=groups,
        matrix_full=(args.matrix == "full"),
        include_gpu=bool(args.include_gpu),
        run_group_dir=run_group_dir,
    )
    config_pairs: list[tuple[str, Path]] = [(name, path) for _, name, path in triples]
    config_group_by_name = {rex.sanitize_component(name): g for g, name, _ in triples}

    config_paths = [p for _, p in config_pairs]
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
    split_values = set(rex.parse_csv_list(args.splits))
    vid_filter = set(rex.parse_csv_list(args.video_ids)) if args.video_ids.strip() else None
    manifest_rows = rex.read_video_manifest(manifest_path, repo_root=repo_root)
    selected = rex.select_manifest_rows(
        rows=manifest_rows,
        splits=split_values,
        video_ids=vid_filter,
        max_videos=args.max_videos if args.max_videos and args.max_videos > 0 else None,
    )
    if not selected:
        raise RuntimeError("No videos selected.")

    if "B" in groups and not vid_filter and args.matrix == "quick":
        pick = [r for r in selected if r["split"] in {"dev", "test"}][:2]
        if len(pick) < len(selected):
            print("[INFO] Group B quick: restricting to two videos (dev+test first). Override with --video-ids.")
            selected = pick

    summary_csv, summary_jsonl = rex.ensure_summary_files(run_group_dir)
    plan_rows: list[dict[str, str]] = []
    max_frames = None if int(args.max_frames) == 0 else int(args.max_frames)

    for config_name, config_path in config_pairs:
        safe_cfg = rex.sanitize_component(config_name)
        for row in selected:
            safe_vid = rex.sanitize_component(row["video_id"])
            out_dir = run_group_dir / safe_cfg / safe_vid
            plan_rows.append(
                {
                    "run_group": run_group,
                    "config_name": safe_cfg,
                    "config_path": rex.to_repo_relative(config_path, repo_root),
                    "video_id": row["video_id"],
                    "split": row["split"],
                    "source_path": row["source_path"],
                    "scenario_tag": row.get("scenario_tag", ""),
                    "notes": row.get("notes", ""),
                    "output_dir": rex.to_repo_relative(out_dir, repo_root),
                }
            )
    rex.write_run_plan(run_group_dir, plan_rows)

    print(f"Run group: {run_group}")
    print(f"Configs: {len(config_pairs)} x videos: {len(selected)} = {len(config_pairs) * len(selected)} runs")
    if args.dry_run:
        print("Dry-run: stopping before execution.")
        return 0

    failed = 0
    for config_name, config_path in config_pairs:
        safe_cfg = rex.sanitize_component(config_name)
        for row in selected:
            safe_vid = rex.sanitize_component(row["video_id"])
            out_dir = run_group_dir / safe_cfg / safe_vid
            print(f"[RUN] {safe_cfg} {row['video_id']}")
            record = rex.run_one(
                repo_root=repo_root,
                run_group=run_group,
                config_name=safe_cfg,
                config_path=config_path,
                manifest_row=row,
                output_dir=out_dir,
                python_executable=args.python_executable,
                max_frames=max_frames,
                dry_run=False,
            )
            rex.append_summary(summary_csv, summary_jsonl, record)
            if record["status"] == "failed":
                failed += 1
                if args.stop_on_error:
                    print("Stopped on error.")
                    return 1

    if not args.skip_eval:
        ev = _run_eval(
            repo_root=repo_root,
            run_group_dir=run_group_dir,
            experiments_root=experiments_root,
            gt_dir=gt_dir,
            tolerance_frames=int(args.tolerance_frames),
            python_executable=args.python_executable,
            eval_subdir=args.eval_subdir,
        )
        if ev != 0:
            print(f"[WARN] eval_events.py returned {ev}")

    summ_path = build_experiments_summary(
        repo_root=repo_root,
        run_group_dir=run_group_dir,
        warmup_frames=int(args.warmup_frames),
        steady_min_frames=int(args.steady_min_frames),
        eval_subdir=args.eval_subdir,
        config_group_by_name=config_group_by_name,
    )
    print(f"Summary: {summ_path}")

    srows: list[dict[str, str]] = []
    with summ_path.open("r", encoding="utf-8", newline="") as f:
        srows = list(csv.DictReader(f))
    write_experiment_report(run_group_dir / "EXPERIMENT_REPORT.md", srows, matrix_label=args.matrix)
    print(f"Report: {run_group_dir / 'EXPERIMENT_REPORT.md'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
