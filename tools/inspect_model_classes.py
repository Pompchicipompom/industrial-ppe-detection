from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect class names in YOLO .pt/.onnx/.engine/OpenVINO models."
    )
    parser.add_argument("--model", type=str, required=True, help="Path to model artifact.")
    parser.add_argument(
        "--require",
        type=str,
        nargs="*",
        default=[],
        help="Optional required class names (e.g. hardhat head person vest).",
    )
    return parser.parse_args()


def _names_to_id_map(names_obj) -> dict[int, str]:
    if isinstance(names_obj, dict):
        return {int(k): str(v) for k, v in names_obj.items()}
    return {idx: str(name) for idx, name in enumerate(names_obj)}


def main() -> None:
    args = parse_args()
    model_path = Path(args.model).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    model = YOLO(str(model_path), task="detect")
    classes = _names_to_id_map(model.names)
    print(f"Model: {model_path}")
    print(f"Total classes: {len(classes)}")
    for idx in sorted(classes.keys()):
        print(f"{idx}: {classes[idx]}")

    if args.require:
        present = {name.lower() for name in classes.values()}
        required = [str(x).strip().lower() for x in args.require]
        missing = [name for name in required if name not in present]
        if missing:
            print(f"Missing required classes: {missing}")
            raise SystemExit(2)
        print(f"All required classes are present: {required}")


if __name__ == "__main__":
    main()
