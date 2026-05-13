# Ablation Protocol (Wave D)

## 1. Goal

Ablation is used to justify why the proposed video-first architecture is stronger than simpler alternatives.

Measured outputs combine:

- event-level quality (from `tools/eval_events.py`)
- runtime/performance (from `runtime_profile.json` + `frame_metrics.csv`)

## 2. Fixed Config Matrix

`tools/run_ablation.py` runs exactly these configs:

1. `baseline` -> `configs/baseline.yaml`
2. `proposed` -> `configs/proposed.yaml`
3. `proposed_without_motion` -> `configs/ablation_proposed_without_motion.yaml`
4. `proposed_without_roi` -> `configs/ablation_proposed_without_roi.yaml`
5. `proposed_without_temporal` -> `configs/ablation_proposed_without_temporal.yaml`
6. `proposed_without_fallback` -> `configs/ablation_proposed_without_fallback.yaml`

### 2.1 Baseline is multi-factor (disclaimer)

`baseline` disables **motion gating, ROI, and temporal event logic** at once (and uses `every_sample` + `sampling_fps=0.0`). It is a *deliberately naive* stack for aggregate comparison to `proposed`.

**Do not** interpret baseline↔proposed deltas as the effect of a single knob. Per-component effects are isolated by rows 3–6 above.

`baseline` uses the **same** `model.enable_person_fallback=true` as `proposed` so the comparison does not conflate fallback with motion/ROI/temporal.

### 2.2 `mode=motion_gated` with `motion.enabled=false`

`proposed_without_motion` keeps `pipeline.mode=motion_gated` but sets `motion.enabled=false`. In that case `InferenceGate` behaves as **sampling-only** (see `ppe_monitoring/motion.py`: when motion is off, infer when `sampled` or forced). This is intentional so sampling rate and `force_infer_every_n_frames` stay aligned with `proposed`.

## 3. What Is Disabled In Each Ablation

### `proposed_without_motion`

Disabled:

- `motion.enabled=false`

Kept:

- ROI logic
- temporal event logic
- same sampling settings as proposed

Interpretation: isolates effect of motion gating signal.

### `proposed_without_roi`

Disabled:

- `roi.enabled=false`
- `roi.person_roi_inference_enabled=false`
- `roi.global_inference_in_roi=false`
- `person_center_must_be_in_roi=false` (and related ROI filters)

Kept:

- motion gating
- temporal event logic

Interpretation: isolates the **structural ROI stage** (scene ROI + person ROI head/hardhat + center-in-ROI rules), not a single boolean.

Verification condition for clean ROI ablation:

- per-frame `roi_infer_ms` must stay `0.0` in `frame_metrics.csv`
- stage summary should report zero ROI stage contribution

### `proposed_without_temporal`

Disabled/degraded:

- temporal smoothing and cooldown are reduced to near-immediate triggering:
  - `hardhat_confirm_frames=1`
  - `hardhat_revoke_frames=1`
  - `lock_after_confirm=false`
  - `no_hardhat_consecutive_frames=1`
  - `no_hardhat_seconds_threshold=0.0`
  - `cooldown_frames=1`
  - `cooldown_seconds=0.0`

Kept:

- motion gating
- ROI

Interpretation: isolates contribution of temporal consistency for event stability.

### `proposed_without_fallback`

Disabled:

- `model.enable_person_fallback=false`

Kept:

- motion gating, ROI, temporal logic (same as `proposed`)

Interpretation: isolates YOLOv8 COCO `person` fallback contribution.

## 4. Execution Flow

`tools/run_ablation.py` orchestrates:

1. `tools/run_experiments.py` (batch runs by manifest)
2. `tools/eval_events.py` (event-level metrics)
3. performance aggregation + report generation

Outputs are written under:

`output_files/experiments/{run_group}/ablation_analysis/`

## 5. Reproducibility Controls

### 5.1 Manifest and GT (E2)

- `tools/run_ablation.py` defaults to `--manifest data/video_manifest_e1.csv` (E2-style manifest with splits). Do not point E2 at `data/video_manifest.csv` unless you maintain a matching GT directory: `video_id` values differ from `gt_events_e1.csv` (see `docs/e2_evaluation_protocol.md`).

### 5.2 Device and backend

All six YAML presets set `model.auto_backend_resolve: false`, `backend_priority: ["pt"]`, and `model.device: "cpu"` so latency ablations use a single explicit inference stack (PyTorch `.pt`, CPU). For faster runs on one fixed GPU, set `device: "0"` consistently and document it in the experiment notes; do not toggle per config mid-study.

### 5.3 Preflight (before experiments)

Unless `--skip-preflight`, `run_ablation.py` verifies manifest media, GT alignment, weights on disk, and refuses a non-empty `output_files/experiments/{run_group}` without `--overwrite-run-group`. For a manifest subset with a full GT folder, pass `--allow-extra-gt-ids`.

### 5.4 Batch filters

Supported filters:

- `--splits dev,test,stress`
- `--video-ids id1,id2`
- `--max-videos N`
- `--max-frames N`
- `--tolerance-frames N`

These controls allow fast smoke checks and full runs with the same protocol.

## 6. Required Artifacts

Wave D produces:

- `ablation_results.csv` (config -> quality + performance)
- `stage_timing_summary.csv` (stage timing stats)
- `performance_report.md` (defense-facing summary)

If event-quality metrics are missing for any config, this is shown explicitly in `quality_status`.

## 7. E2 latency repeats

For the capped E2 regime (`docs/e2_evaluation_protocol.md`), run:

`python tools/run_e2_latency_repeats.py --repeats 3 --manifest data/video_manifest_e1.csv --max-frames 140`

Compare `latency_p90_ms_steady` (and related columns) across repeat run groups under `output_files/experiments/`.
