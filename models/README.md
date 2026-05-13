# Model weights

Detector checkpoints are **not** stored in this repository when they are large binary files.

## Expected paths (defaults)

Configured in `ppe_monitoring/config.py` and YAML presets:

| Role | Default path |
| --- | --- |
| Main PPE detector (`.pt`) | `models/hardhat_detection_yolo11_200_epochs_best_02032025.pt` |
| Person fallback (COCO-style YOLO) | `yolov8s.pt` (repository root; Ultralytics may auto-download) |
| Optional binary hardhat head model | `models/hardhat_binary_best.pt` |

Adjust `model.weights_path`, `model.person_fallback_weights_path`, and related keys in your config to match the files you actually have.

## Obtaining weights

Provide archives separately (team drive, release asset, or Git LFS). Place files at the paths above **after** cloning.

Placeholder links (replace with real distribution):

- Models bundle: `<GOOGLE_DRIVE_LINK_TO_MODELS>`
