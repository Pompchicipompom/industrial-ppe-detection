# Experimental Protocol (Wave A Foundation)

## 1. Scope

This protocol defines the **minimum reproducible setup** for controlled baseline vs proposed comparisons.
Wave A creates only the foundation:

- fixed video manifest with splits
- baseline/proposed configs
- event-level GT schema
- GT validator

No evaluator/ablation runner/profiling extension is introduced in this wave.

## 2. What Is Compared

Two configuration presets are compared:

- **Baseline**: `configs/baseline.yaml`
- **Proposed**: `configs/proposed.yaml`

Both presets run through the current entrypoint without code changes:

```bash
python main.py --config configs/baseline.yaml
python main.py --config configs/proposed.yaml
```

## 3. Baseline Definition

Baseline is intentionally simplified to approximate a naive frame-first pipeline:

- `pipeline.mode=every_sample`
- `pipeline.sampling_fps=0.0` (sample each frame)
- `motion.enabled=false`
- `roi.enabled=false`
- `model.enable_person_fallback=true` (aligned with proposed/ablations so baseline↔proposed deltas isolate motion/ROI/temporal, not the detector stack)
- temporal logic reduced to immediate trigger:
  - `no_hardhat_consecutive_frames=1`
  - `no_hardhat_seconds_threshold=0.0`
  - `cooldown_frames=1`
  - `cooldown_seconds=0.0`

This keeps the same codebase while reducing architectural components.

## 4. Proposed Definition

Proposed mirrors the current industrial video-first design from repository defaults:

- motion-gated inference (`mode=motion_gated`)
- ROI enabled
- temporal consistency + cooldown
- fallback person detector enabled

`configs/proposed.yaml` explicitly pins these key switches and keeps other values from defaults.

## 5. Dataset Unit of Evaluation

Evaluation is planned at the **event level**, not only at object-detection frame level.

Rationale:

- business output is a violation signal (`no_hardhat`)
- a detector can be visually good frame-by-frame but still weak as an event generator
- commission questions are about practical monitoring behavior

## 6. Video Manifest and Splits

Manifest file: `data/video_manifest.csv`

Required split groups:

- `dev`
- `test`
- `stress`

Conservative decision for this repository:

- only local `input_files/*.mp4` are used now
- split assignment is fixed and documented in manifest notes
- stress split is intentionally small at this stage

## 7. Ground Truth Event Format

GT schema is documented in:

- `docs/gt_event_format.md`

Template location:

- `data/gt_events/gt_events_template.csv`

Validation tool:

- `tools/validate_gt_events.py`

## 8. Compatibility With Current Pipeline

Wave A does **not** modify runtime modules:

- `main.py`
- `ppe_monitoring/pipeline.py`
- `ppe_monitoring/config.py`

All new assets are additive and compatible with existing `--config` loading behavior.

