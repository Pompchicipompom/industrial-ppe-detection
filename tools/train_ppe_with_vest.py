from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train/finetune unified PPE detector with vest support."
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to YOLO data.yaml (prefer unified classes: hardhat, head, person, vest).",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="models/hardhat_detection_yolo11_200_epochs_best_02032025.pt",
        help="Base model for finetuning (.pt). OpenVINO artifacts are not trainable.",
    )
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs.")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size.")
    parser.add_argument(
        "--batch",
        type=str,
        default="auto",
        help="Batch size (int) or 'auto'.",
    )
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience.")
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Device string for Ultralytics (e.g. '', 'cpu', '0').",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Dataloader workers.",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="runs/detect",
        help="Ultralytics project directory.",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="ppe_with_vest",
        help="Ultralytics run name.",
    )
    parser.add_argument(
        "--pretrained",
        action="store_true",
        default=True,
        help="Keep pretrained=True (recommended).",
    )
    return parser.parse_args()


def _parse_batch(value: str) -> int | float | str:
    v = str(value).strip().lower()
    if v == "auto":
        # Ultralytics expects numeric batch. -1 enables auto-batch behavior.
        return -1
    try:
        return int(v)
    except Exception:
        raise ValueError(f"Invalid --batch value: {value!r}. Use integer or 'auto'.")


def main() -> None:
    args = parse_args()
    data_path = Path(args.data).resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_path}")

    base_model_path = Path(args.base_model)
    if not base_model_path.exists():
        raise FileNotFoundError(
            f"Base model not found: {base_model_path}. "
            "Use .pt weights; OpenVINO folders cannot be finetuned."
        )
    if base_model_path.suffix.lower() != ".pt":
        raise ValueError(
            f"Unsupported base model for training: {base_model_path}. "
            "Provide a .pt checkpoint."
        )

    model = YOLO(str(base_model_path))
    batch_value = _parse_batch(args.batch)
    train_kwargs = {
        "data": str(data_path),
        "epochs": int(args.epochs),
        "imgsz": int(args.imgsz),
        "batch": batch_value,
        "patience": int(args.patience),
        "project": str(Path(args.project)),
        "name": str(args.name),
        "pretrained": bool(args.pretrained),
        "workers": int(args.workers),
    }
    if str(args.device).strip():
        train_kwargs["device"] = str(args.device).strip()
    model.train(**train_kwargs)

    run_dir = Path(args.project) / args.name
    print(f"Training completed. Artifacts are expected under: {run_dir.resolve()}")
    print(f"Best checkpoint: {(run_dir / 'weights' / 'best.pt').resolve()}")


if __name__ == "__main__":
    main()
