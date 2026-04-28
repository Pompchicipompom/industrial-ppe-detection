from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export YOLO .pt weights to acceleration artifacts: ONNX, OpenVINO, TensorRT engine."
    )
    parser.add_argument("--weights", type=str, required=True, help="Path to source .pt model")
    parser.add_argument("--imgsz", type=int, default=640, help="Export image size")
    parser.add_argument("--half", action="store_true", help="Use FP16 export when supported")
    parser.add_argument("--device", type=str, default="", help='Device for export, e.g. "0" for CUDA')
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["onnx", "openvino"],
        choices=["onnx", "openvino", "engine"],
        help="Export targets",
    )
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset")
    parser.add_argument("--dynamic", action="store_true", help="Dynamic shapes for ONNX")
    parser.add_argument("--simplify", action="store_true", help="Simplify ONNX graph")
    return parser.parse_args()


def main():
    args = parse_args()
    weights = Path(args.weights)
    if not weights.exists():
        raise FileNotFoundError(f"Weights not found: {weights}")
    if weights.suffix.lower() != ".pt":
        raise ValueError("Input weights must be a .pt file")

    model = YOLO(str(weights))
    exported = {}

    if "onnx" in args.formats:
        print("Exporting ONNX...")
        out = model.export(
            format="onnx",
            imgsz=args.imgsz,
            half=args.half,
            opset=args.opset,
            dynamic=args.dynamic,
            simplify=args.simplify,
        )
        exported["onnx"] = str(out)
        print(f"ONNX: {out}")

    if "openvino" in args.formats:
        print("Exporting OpenVINO...")
        out = model.export(
            format="openvino",
            imgsz=args.imgsz,
            half=args.half,
        )
        exported["openvino"] = str(out)
        print(f"OpenVINO: {out}")

    if "engine" in args.formats:
        print("Exporting TensorRT engine...")
        kwargs = {
            "format": "engine",
            "imgsz": args.imgsz,
            "half": args.half,
        }
        if args.device:
            kwargs["device"] = args.device
        out = model.export(**kwargs)
        exported["engine"] = str(out)
        print(f"TensorRT engine: {out}")

    print("Export finished.")
    for k, v in exported.items():
        print(f" - {k}: {v}")


if __name__ == "__main__":
    main()

