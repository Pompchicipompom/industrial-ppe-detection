# E2 Evaluation Protocol (First Meaningful Round)

## Goal

E2 produces the first **meaningful** baseline/proposed/ablation comparison on non-empty GT with non-smoke runs.

Scope priorities:

- non-smoke execution on `data/video_manifest_e1.csv`
- event-level quality metrics on non-empty GT
- warm-up vs steady-state profiling split
- defense-ready summary artifacts

## Config Matrix

Fixed configuration set (see `tools/run_ablation.py` `DEFAULT_CONFIGS`):

1. `baseline`
2. `proposed`
3. `proposed_without_motion`
4. `proposed_without_roi`
5. `proposed_without_temporal`
6. `proposed_without_fallback` (same as proposed but `model.enable_person_fallback=false`)

For **latency variance** across identical configs, run `tools/run_e2_latency_repeats.py` (default `--repeats 3`).

## Dataset Scope

Manifest (**E2 only**):

- `data/video_manifest_e1.csv`

Do **not** use `data/video_manifest.csv` for E2. That file is a separate reference split with different `video_id` values (`hardhat_input_video`, …). Ground-truth in `data/gt_events/gt_events_e1.csv` is keyed to the **E1/E2** ids (`e1_dev_hardhat_input_video1_seg_a`, …). Mixing manifests produces empty or wrong GT joins and invalid metrics.

Verified pairing (same three ids in both files):

- `e1_dev_hardhat_input_video1_seg_a`
- `e1_test_hardhat_input_video_seg_a`
- `e1_stress_hardhat_input_video4_seg_a`

GT:

- `data/gt_events/gt_events_e1.csv` (typical `--gt-dir data/gt_events`; preflight requires GT `video_id` set to match the selected manifest rows)

Splits included:

- `dev`
- `test`
- `stress`

## Runtime Regime

To avoid smoke behavior while keeping compute tractable:

- `max_frames=140` per video
- no preview windows
- all six configs are executed for each E1 video

This is not a full production benchmark; it is the first defensible round.

## Reproducibility (device and backend)

For comparable latency across the six configs on one machine, presets under `configs/` set:

- `model.auto_backend_resolve: false` — always load the `.pt` at `model.weights_path`; no silent switch to OpenVINO/ONNX/TensorRT even if those artifacts exist beside the checkpoint.
- `model.backend_priority: ["pt"]` — documents intent (used when auto-resolve is enabled elsewhere).
- `model.device: "cpu"` — fixed execution device for stable E2 numbers; on a dedicated CUDA workstation you may set `device: "0"` **once** and keep it fixed for the whole thesis run.

Keeping `auto_backend_resolve: true` would be valid for deployment (pick the fastest present artifact) but is **unsuitable** for thesis-grade latency ablations because two runs could use different backends without an explicit config change.

## Preflight

`tools/run_ablation.py` runs checks before scheduling work (unless `--skip-preflight`):

- manifest and source videos exist
- GT directory contains CSVs with required columns; every selected manifest `video_id` has GT rows
- GT must not list extra `video_id` values absent from the selected manifest unless `--allow-extra-gt-ids` (subset/smoke runs)
- merged config weights exist on disk (and person fallback weights when enabled)
- `output_files/experiments/{run_group}` must be missing or empty unless `--overwrite-run-group`

## Full E2 command (real run)

From the repository root (unique `run_group`; add `--overwrite-run-group` only to intentionally replace a previous directory):

```bash
python tools/run_ablation.py \
  --manifest data/video_manifest_e1.csv \
  --gt-dir data/gt_events \
  --max-frames 140 \
  --run-group e2_20260426_manual \
  --warmup-frames 20 \
  --steady-min-frames 30 \
  --tolerance-frames 0
```

`--manifest` defaults to `data/video_manifest_e1.csv` if omitted. Dry-run (plan only, no `main.py` / no reports):

```bash
python tools/run_ablation.py --manifest data/video_manifest_e1.csv --max-frames 140 --gt-dir data/gt_events --dry-run
```

## Warm-up vs Steady-state

Profiling phases:

- `warmup`: first `N` frames (`warmup_frames`, default used in E2 run)
- `steady`: remaining frames

Outputs explicitly separate phase metrics to avoid mixing cold-start and steady runtime.

## Required E2 Artifacts

Under `output_files/experiments/{run_group}/`:

- `evaluation_ablation/per_video_metrics.csv`
- `evaluation_ablation/aggregate_metrics.csv`
- `ablation_analysis/ablation_results.csv`
- `ablation_analysis/stage_timing_summary.csv`
- `ablation_analysis/warmup_steady_summary.csv`
- `ablation_analysis/performance_report.md`
- `ablation_analysis/defense_summary.md`

## Transparency Rules

If any metric is weakly informative (for example too few steady frames or absent GT coverage), this must be marked in report status/notes fields and not hidden.
