from __future__ import annotations

import argparse
import statistics
import time

import cv2
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Quick runtime benchmark for YOLO artifact (.pt/.onnx/.engine/OpenVINO).")
    parser.add_argument("--weights", type=str, required=True, help="Path to model artifact")
    parser.add_argument("--source", type=str, default="input_files/hardhat_input_video.mp4", help="Video source for benchmark")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference size")
    parser.add_argument("--frames", type=int, default=60, help="Max benchmark frames")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup frames (not counted)")
    parser.add_argument("--device", type=str, default="", help='Device override, e.g. "cpu" or "0"')
    parser.add_argument("--half", action="store_true", help="FP16 inference when supported")
    return parser.parse_args()


def main():
    args = parse_args()
    model = YOLO(args.weights)
    cap = cv2.VideoCapture(args.source if not str(args.source).isdigit() else int(args.source))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open source: {args.source}")

    latencies = []
    processed = 0
    warmup_done = 0

    while processed < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        kwargs = {
            "imgsz": args.imgsz,
            "verbose": False,
        }
        if args.device:
            kwargs["device"] = args.device
        if args.half:
            kwargs["half"] = True
        _ = model.predict(frame, **kwargs)
        ms = (time.perf_counter() - t0) * 1000.0
        if warmup_done < args.warmup:
            warmup_done += 1
        else:
            latencies.append(ms)
            processed += 1

    cap.release()
    if not latencies:
        print("No benchmark samples collected.")
        return

    mean_ms = statistics.mean(latencies)
    med_ms = statistics.median(latencies)
    p90_ms = sorted(latencies)[int(0.9 * (len(latencies) - 1))]
    fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0

    print(f"Artifact: {args.weights}")
    print(f"Samples: {len(latencies)}")
    print(f"Latency ms (mean/median/p90): {mean_ms:.2f}/{med_ms:.2f}/{p90_ms:.2f}")
    print(f"Approx inference FPS: {fps:.2f}")


if __name__ == "__main__":
    main()

