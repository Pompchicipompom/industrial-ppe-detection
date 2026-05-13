# Repository cleanup report

Date: 2026-05-13

This report summarises the repository preparation work for public publication.

## Inventory

### Source code

- `main.py` — command-line entry point.
- `ppe_monitoring/` — runtime pipeline, detector wrapper, tracking, motion gate, event logic, profiling, visualisation, geometry helpers, and shared types.
- `tools/` — experiment runners, event evaluation, benchmarking, model inspection, dataset preparation, and training helpers.

### Configuration

- `config.example.yaml` and root example configs.
- `configs/baseline.yaml`, `configs/proposed.yaml`, ablation presets, and extended experiment presets.

### Documentation

- Kept technical docs for architecture, evaluation protocols, event schemas, and training.
- Added concise public docs:
  - `docs/configuration.md`
  - `docs/evaluation.md`
  - `docs/experiments.md`
  - `docs/figures/README.md`

### Examples

- `examples/sample_config.yaml`
- `examples/sample_gt_events.csv`
- `examples/video_manifest_one.csv`

### Data and models

- `data/README.md` describes where to place local videos, manifests, and ground-truth event files.
- `models/README.md` describes expected model weight paths.
- Large videos, model weights, exported inference artifacts, and generated outputs are not intended for normal Git storage.

## Removed or untracked content

### Removed from the working tree

- Old report documents: `report.docx`, `report_submission.docx`, `report.md`.
- Old handoff/report-generation helper: `build_handoff.py`.
- Non-public documentation packs, presentation assets, draft material, duplicated experiment trees, and full run outputs under `docs/`.
- Tool scripts that only served the removed document-generation workflow.

### Removed from Git tracking but kept locally

- `models/hardhat_binary_best.pt`
- `models/hardhat_detection_yolo11_200_epochs_best_02032025.pt`
- `yolov8s.pt`

These files remain on disk for local runs, but are now ignored by `.gitignore`.

## Large artifacts to provide separately

| Artifact | Approx. size | Purpose | Suggested hosting | Expected local path |
| --- | ---: | --- | --- | --- |
| Main detector `.pt` | 109 MB | Primary PPE detector | Release asset, object storage, or Git LFS | `models/hardhat_detection_yolo11_200_epochs_best_02032025.pt` |
| Optional ONNX export | 218 MB + side data | Accelerated inference | Release asset or Git LFS | `models/` |
| Optional OpenVINO export | 217 MB | Intel runtime inference | Release asset or Git LFS | `models/*_openvino_model/` |
| Person fallback weights | 21.5 MB | Fallback person detector | Auto-download or release asset | `yolov8s.pt` |
| Large demo video | 170 MB | Optional demo input | Object storage or release asset | `input_files/` or `data/videos/` |
| Full experiment outputs | varies | Reproducibility and visual review | Object storage or release asset | `output_files/experiments/<run_group>/` |

Placeholder links for future publication:

- Models: `<GOOGLE_DRIVE_LINK_TO_MODELS>`
- Sample videos: `<GOOGLE_DRIVE_LINK_TO_SAMPLE_VIDEOS>`
- Full experiment outputs: `<GOOGLE_DRIVE_LINK_TO_FULL_EXPERIMENTS>`

## Files kept for public usefulness

- Runtime code and reusable tools.
- Config presets required for normal runs and ablations.
- Small tabular experiment snapshot under `docs/experiments/single_video_ablation/`.
- Project docs, examples, and README files for empty local artifact directories.
- `LICENSE`, `requirements-pipeline.txt`, and `requirements.txt`.

## Ignore policy

`.gitignore` now excludes:

- Python caches and virtual environments.
- Local secrets and environment files.
- Generated outputs, logs, temporary files, and run directories.
- Archives, videos, model checkpoints, exported inference blobs, and local training trackers.
- Local data payloads, while keeping README files.

`.gitattributes` sets normal text handling and marks image files as binary.

## Commands after clone

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-pipeline.txt
python -m compileall -q ppe_monitoring tools main.py
python main.py --help
python -c "from ppe_monitoring.pipeline import run_pipeline; from ppe_monitoring.config import load_config; print('imports_ok')"
```

Example event evaluation after experiment runs exist:

```bash
python tools/eval_events.py --run-group <run_group> --experiments-root output_files/experiments --gt-dir data/gt_events --tolerance-frames 0
```

## Verification performed

- `python -m compileall -q ppe_monitoring tools main.py` — OK.
- `python main.py --help` — OK.
- Import smoke check for core modules — OK.

## Publication notes

- Before publishing, verify `git status` and the list of staged files.
- If large binary files were committed in earlier history, a normal deletion commit does not remove them from repository history. History cleanup requires a separate maintainer decision and a dedicated history-rewrite tool.
