# Train PPE Model With Vest

This guide trains a unified PPE detector that supports:

- `hardhat`
- `head`
- `person`
- `vest`

It keeps the current `no_hardhat` runtime logic unchanged and lets you switch models via config.

## 1) Verify available datasets

Inspect existing hardhat dataset classes:

```bash
python tools/inspect_model_classes.py --model "models/hardhat_detection_yolo11_200_epochs_best_02032025.pt"
```

Inspect vest dataset YAML manually and check:

- split layout (`train/val/test` or `train/valid/test`)
- `images` and `labels` directories
- `names` in YAML (how vest is named: `vest`, `safety_vest`, `reflective_vest`, etc.)

In this repository, current hardhat dataset YAML is:

- `datasets/hardhat_rf/data.yaml`

## 2) Build unified dataset

Use merge script (recommended when vest dataset does not contain all hardhat/head/person classes):

```bash
python tools/prepare_unified_ppe_dataset.py ^
  --hardhat-yaml "datasets/hardhat_rf/data.yaml" ^
  --vest-yaml "PATH_TO_VEST_DATASET/data.yaml" ^
  --output-dir "datasets/ppe_unified_vest"
```

Expected result:

- `datasets/ppe_unified_vest/data.yaml`
- classes fixed to `[hardhat, head, person, vest]`

## 3) Train / finetune model

Use `.pt` checkpoint as base (OpenVINO directory is not trainable):

```bash
python tools/train_ppe_with_vest.py ^
  --data "datasets/ppe_unified_vest/data.yaml" ^
  --base-model "models/hardhat_detection_yolo11_200_epochs_best_02032025.pt" ^
  --epochs 100 ^
  --imgsz 640 ^
  --batch auto ^
  --patience 20
```

Artifacts:

- `runs/detect/ppe_with_vest/weights/best.pt`
- `runs/detect/ppe_with_vest/results.csv`
- training plots under `runs/detect/ppe_with_vest/`

## 4) Validate trained classes

```bash
python tools/inspect_model_classes.py ^
  --model "runs/detect/ppe_with_vest/weights/best.pt" ^
  --require hardhat head person vest
```

## 5) Export to OpenVINO

```bash
yolo export model="runs/detect/ppe_with_vest/weights/best.pt" format=openvino imgsz=640
```

Expected export folder:

- `runs/detect/ppe_with_vest/weights/best_openvino_model/`

Optional class check on OpenVINO artifact:

```bash
python tools/inspect_model_classes.py ^
  --model "runs/detect/ppe_with_vest/weights/best_openvino_model" ^
  --require hardhat head person vest
```

## 6) Connect model to runtime

Use config:

- `config.ppe_with_vest.example.yaml`

Key points:

- `model.model_path: "models/ppe_with_vest_openvino_model"`
- legacy `model.weights_path` stays supported (fallback)

Copy export folder to:

- `models/ppe_with_vest_openvino_model`

Then run:

```bash
python main.py --config "config.ppe_with_vest.example.yaml" --source "input_files/hardhat_input_video.mp4"
```

## 7) Colab fallback (if local training is too slow)

If training on local CPU is too slow, run the same commands in Google Colab:

1. Upload repository or clone it.
2. Upload both datasets.
3. Run dataset merge script.
4. Run training script with GPU runtime.
5. Export OpenVINO (optional in Colab; can export locally from `best.pt`).

Core command sequence remains identical.
