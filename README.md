# Video-based PPE compliance monitoring

Industrial-style **video-first** pipeline for hard-hat (and optional high-visibility vest) monitoring on file, camera, or RTSP sources. The system turns per-frame detections into **time-stabilised violation events** (`no_hardhat`, optionally `no_vest`) with CSV/JSONL exports and lightweight runtime profiling.

## Features

- Video-first processing loop with configurable frame sampling.
- Motion-based inference gating for fixed-camera scenes.
- YOLO (Ultralytics) object detection with optional COCO-style **person fallback** detector.
- Person tracking and association between `person`, `head`, `hardhat`, and optional `vest`.
- Temporal event logic plus cooldown-style anti-spam for repeated alerts.
- Structured logs: `events.csv`, `events.jsonl`, `frame_metrics.csv`, `runtime_profile.json`.
- Event-level evaluation and ablation tooling (`tools/eval_events.py`, `tools/run_ablation.py`, `tools/run_experiments_extended.py`).

## Architecture

High-level data path:

**video source → decode/resize → sampling + motion gate → (optional ROI) → YOLO + tracking → head/hardhat association → temporal event logic → annotated video + metrics/events.**

Details and a module map: [`docs/architecture.md`](docs/architecture.md).

## Repository layout

| Path | Description |
| --- | --- |
| `main.py` | CLI entrypoint. |
| `ppe_monitoring/` | Core pipeline, detector wrapper, tracker, motion, events, profiling, visualisation. |
| `configs/` | YAML presets (`baseline`, `proposed`, ablations, extended demos). |
| `tools/` | Ablation runner, evaluation, benchmarks, dataset helpers. |
| `docs/` | Architecture, protocols, evaluation notes, archived small experiment tables. |
| `examples/` | Sample config, manifest, and GT snippets. |
| `models/` | Placeholder `README.md`; place large `.pt` weights locally (see below). |
| `data/` | Placeholder `README.md`; place manifests and GT CSVs locally. |

Generated outputs should go under `output_files/` or another path configured in YAML — these directories are git-ignored by default.

## Requirements

- **Python 3.11** (aligned with project docs; slightly older 3.10+ may work with dependency pins adjusted locally).
- A virtual environment is recommended.

Minimal runtime dependencies:

```bash
pip install -r requirements-pipeline.txt
```

`requirements.txt` in the repository root may represent a broader frozen environment (notebooks, dev tools). For reproducing the monitoring pipeline alone, prefer `requirements-pipeline.txt`.

## Model weights

Large checkpoints are **not** committed here. After cloning, install weights to the paths expected by your YAML / defaults (see `models/README.md` and `ppe_monitoring/config.py`), for example:

- `models/hardhat_detection_yolo11_200_epochs_best_02032025.pt` — main detector.
- `yolov8s.pt` — person fallback (often auto-downloaded by Ultralytics when missing).

| Artifact | Purpose | Expected location | Distribution |
| --- | --- | --- | --- |
| Main PPE detector | `person` / `head` / `hardhat` (+ optional `vest`) | `models/*.pt` per config | `<GOOGLE_DRIVE_LINK_TO_MODELS>` |
| Person fallback | COCO-style person detector | `yolov8s.pt` (repo root by default) | Ultralytics hub or same bundle as above |

## Data layout

1. Put input videos where your manifest points (commonly `input_files/` or `data/videos/`).
2. Add a manifest CSV `video_id,source_path,split` (see `examples/video_manifest_one.csv`).
3. Add GT event CSVs under `data/gt_events/` following `docs/gt_event_format.md` (`examples/sample_gt_events.csv`).

## Running the pipeline

Single file or stream (override `pipeline.source` from the CLI):

```bash
python main.py --config config.example.yaml --source input_files/hardhat_input_video4.mp4 --no-preview
```

RTSP example:

```bash
python main.py --config config.example.yaml --source rtsp://user:password@host:554/stream --no-preview
```

Batch directory (one output folder per input video stem under `--batch-output-root`):

```bash
python main.py --config configs/proposed.yaml --batch-videos-dir input_files --batch-output-root output_files/batch_demo --no-preview
```

CLI reference:

```bash
python main.py --help
```

## Evaluation

After producing runs under `output_files/experiments/<run_group>/…`:

```bash
python tools/eval_events.py --run-group <run_group> --experiments-root output_files/experiments --gt-dir data/gt_events --tolerance-frames 0
```

Metrics are described in [`docs/evaluation.md`](docs/evaluation.md): TP/FP/FN, precision, recall, F1, false alarms per hour, and detection delay statistics where applicable.

## Experiments

- **Baseline** — naive frame-sampled configuration without motion gating, ROI, or rich temporal logic (`configs/baseline.yaml`).
- **Proposed** — video-first configuration with motion gating, ROI, temporal event logic, and optional fallback (`configs/proposed.yaml`).
- **Ablations** — `configs/ablation_proposed_without_*.yaml` disable one factor at a time (motion, ROI, temporal logic, person fallback).

Protocol details: [`docs/experiments.md`](docs/experiments.md), [`docs/ablation_protocol.md`](docs/ablation_protocol.md), [`docs/e2_evaluation_protocol.md`](docs/e2_evaluation_protocol.md).

## Limitations

- Detection quality depends on camera placement, lighting, resolution, and helmet pixel size.
- Automated `no_hardhat` / `no_vest` events are **assistive signals** and require human review before operational or legal consequences.
- The repository is an **engineering prototype**, not a certified safety system; production deployments need site-specific calibration, monitoring, and governance.
- RTSP stability depends on network conditions and encoder settings.

## External artifacts

| Artifact | Purpose | Expected path after download | Suggested hosting |
| --- | --- | --- | --- |
| Trained PPE weights | Main inference | Under `models/` as referenced in config | `<GOOGLE_DRIVE_LINK_TO_MODELS>` |
| Sample industrial clips | Demos / tuning | `data/videos/` or `input_files/` | `<GOOGLE_DRIVE_LINK_TO_SAMPLE_VIDEOS>` |
| Full experiment run folders | Videos, logs, per-frame metrics | e.g. `output_files/experiments/<run_group>/` | `<GOOGLE_DRIVE_LINK_TO_FULL_EXPERIMENTS>` or GitHub Release / Git LFS |

## License

This project is licensed under the **Apache License 2.0** — see [`LICENSE`](LICENSE).

## Repository hygiene

See [`CLEANUP_REPORT.md`](CLEANUP_REPORT.md) for the public-readiness audit (removed paths, `.gitignore` policy, and verification commands).
