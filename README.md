# Hard Hat Detection - Industrial Video-First Prototype

## Overview

This project is now structured as a **video-first PPE monitoring pipeline** for industrial deployment scenarios.

The system detects:
- `person`
- `head`
- `hardhat`

and emits violation events (`no_hardhat`) with temporal logic and cooldown.

## What Changed vs. Research Prototype

The previous implementation was a monolithic script. The current implementation is modular and deployment-oriented:

- input from **video file / camera / RTSP**
- frame sampling (target processing FPS)
- motion gating for fixed camera scenes
- YOLO inference + fallback person detector
- stable person IDs and temporal smoothing
- cooldown-based event generation
- CSV + JSONL event logging
- per-frame metrics logging
- runtime profiling with mean/median/p90 latency

## Project Structure

- `main.py` - thin entrypoint
- `ppe_monitoring/config.py` - default config + YAML/JSON loading
- `ppe_monitoring/pipeline.py` - orchestrates full runtime pipeline
- `ppe_monitoring/detector.py` - Ultralytics inference wrapper
- `ppe_monitoring/tracker.py` - person tracking and association logic
- `ppe_monitoring/event_logic.py` - temporal rules and event generation
- `ppe_monitoring/motion.py` - frame sampling and motion gate
- `ppe_monitoring/profiler.py` - FPS/latency profiling
- `ppe_monitoring/rtsp_health.py` - RTSP watchdog and reconnect/drop statistics
- `ppe_monitoring/geometry.py` - geometry utilities
- `ppe_monitoring/types.py` - shared dataclasses
- `ppe_monitoring/video_id.py` - stable `video_id` for events/manifests
- `ppe_monitoring/metrics_constants.py` - `frame_metrics.csv` column contract
- `docs/architecture.md` - canonical pipeline diagram and rationale
- `tests/` - unit tests (`python -m unittest discover -s tests -v`)

## Pipeline diagram

See **[docs/architecture.md](docs/architecture.md)** (single source of truth).

## Dependencies

- **Pipeline only:** `pip install -r requirements-pipeline.txt`
- **Dev / notebooks / reports:** `pip install -r requirements-dev.txt`
- **Legacy full export (pinned Windows stack):** `requirements.txt`

## Why This Architecture

1. **Video-first orchestration**
   The pipeline is organized around streaming frames, not static image inference.

2. **Sampling + motion gating**
   Fixed cameras often have long static periods. Sampling and motion gate reduce unnecessary inference load while preserving responsiveness.

3. **Temporal event logic**
   Violations are generated only after temporal confirmation (`K` consecutive misses + time threshold), reducing false alarms.

4. **Cooldown per person**
   Prevents event spam in persistent violation scenes.

5. **Operational observability**
   The runtime exports processing/inference FPS and latency distribution (mean/median/p90), which is required for deployment validation.

## Configuration

You can run with built-in defaults, or pass YAML/JSON config.

Example keys in default config (`ppe_monitoring/config.py`):
- `pipeline.source`
- `pipeline.sampling_fps`
- `pipeline.mode` (`every_sample` or `motion_gated`)
- `motion.*`
- `roi.*`
- `event_logic.*`
- `output.*`

Ready-to-edit YAML template: `config.example.yaml`

Motion gate tuning (most useful):
- `motion.min_ratio` - activation threshold (lower = more sensitive)
- `motion.min_ratio_off` - deactivation threshold for hysteresis
- `motion.hold_frames_after_motion` - keep gate open for N frames after detected motion
- `motion.pixel_threshold` - per-pixel diff threshold
- `motion.background_alpha` - background adaptation speed
- `motion.use_morphology` / `motion.morph_kernel` - noise cleanup in motion mask

## Run

```bash
python main.py
```

With explicit source:

```bash
python main.py --source input_files/hardhat_input_video.mp4
```

RTSP example:

```bash
python main.py --source rtsp://user:pass@camera-ip:554/stream1
```

Disable preview window:

```bash
python main.py --no-preview
```

Use external config:

```bash
python main.py --config config.yaml
```

## Outputs

- processed video: `output_files/processed.mp4`
- events CSV: `output_files/events.csv`
- events JSONL: `output_files/events.jsonl`
- per-frame metrics: `output_files/frame_metrics.csv`
- final runtime profile report: `output_files/runtime_profile.json`

## Runtime Metrics

Console summary includes:
- input FPS (camera/file)
- processing FPS
- inference FPS
- inference latency mean/median/p90
- loop latency mean/median/p90
- total generated events
- RTSP watchdog health (reconnect attempts/success/fail, drop and downtime statistics)

This allows direct comparison of source speed vs. model execution speed for near-real-time validation.

## Tests

Run unit tests (OpenCV required for motion tests):

```bash
python -m unittest discover -s tests -v
```

CI runs the same suite on push (see `.github/workflows/ci.yml`).

## E2 ablation + latency repeats

E2 uses **`data/video_manifest_e1.csv` only** (not `data/video_manifest.csv`) so `video_id` matches `data/gt_events/gt_events_e1.csv`. See `docs/e2_evaluation_protocol.md`.

Presets pin **`model.auto_backend_resolve: false`** and **`device: "cpu"`** for reproducible latency; set `device: "0"` on a fixed CUDA box if needed.

**Full E2 ablation** (pick a unique `--run-group`; use `--overwrite-run-group` only to replace an existing directory):

```bash
python tools/run_ablation.py \
  --manifest data/video_manifest_e1.csv \
  --gt-dir data/gt_events \
  --max-frames 140 \
  --run-group e2_my_run \
  --warmup-frames 20 \
  --steady-min-frames 30
```

Preflight checks paths, GT/manifest `video_id` alignment, and weights (including `yolov8s.pt` when fallback is on). Plan-only:

```bash
python tools/run_ablation.py --manifest data/video_manifest_e1.csv --max-frames 140 --gt-dir data/gt_events --dry-run
```

For **N** full passes to sample latency variance:

```bash
python tools/run_e2_latency_repeats.py --repeats 3 --manifest data/video_manifest_e1.csv --max-frames 140
```

Each repeat writes `output_files/experiments/e2_<timestamp>_rK/ablation_analysis/` including `performance_report.md` and `defense_summary.md`.

## Commission Report Generator

Generate a commission-ready markdown report from:
- `runtime_profile.json`
- `events.csv`
- `events.jsonl`
- `frame_metrics.csv`

```bash
python report_summary.py
```

Output:
- `output_files/commission_report.md`

## Priority 1: Inference Acceleration

Implemented acceleration knobs:
- lower default input size (`pipeline.resize_to = [640, 640]`)
- runtime model size (`model.imgsz`, `model.roi_imgsz`)
- FP16 toggle (`model.use_half`)
- backend auto-resolve (`model.backend_priority`):
  - TensorRT `.engine`
  - OpenVINO `_openvino_model`
  - ONNX `.onnx`
  - fallback `.pt`
- optional lighter model switch (`model.weights_path_lite`, `model.prefer_lite_model`)

### Export acceleration artifacts

```bash
python tools/export_acceleration_artifacts.py --weights models/hardhat_detection_yolo11_200_epochs_best_02032025.pt --formats onnx openvino
```

TensorRT (requires NVIDIA GPU + TensorRT):

```bash
python tools/export_acceleration_artifacts.py --weights models/hardhat_detection_yolo11_200_epochs_best_02032025.pt --formats engine --device 0 --half
```

### Benchmark artifact speed

```bash
python tools/benchmark_model_runtime.py --weights models/hardhat_detection_yolo11_200_epochs_best_02032025.onnx --frames 60 --imgsz 640
```

## Environment

- Windows
- Python 3.11
- Ultralytics
- OpenCV

