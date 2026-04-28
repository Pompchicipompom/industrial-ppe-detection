# Pipeline architecture (video-first PPE)

Single-process frame loop: **VideoSource** → resize → **MotionDetector** + **FrameSampler** + **InferenceGate** → (optional) **PPEDetector** main YOLO `track` + person fallback → **PersonTracker** → ROI head/hardhat passes → **TemporalEventLogic** → draw → **VideoWriter** + CSV/JSONL metrics.

## ASCII diagram

```text
+------------------+      +----------------+      +-------------------+
| Video/RTSP Input | ---> | Frame Sampler  | ---> | Motion Gate (fixed|
| (cv2.VideoCapture)|     | (target FPS)   |      | camera assumption) |
+------------------+      +----------------+      +---------+---------+
                                                           |
                                                           v
                                                  +--------+--------+
                                                  | YOLO Inference  |
                                                  | (track + person |
                                                  | fallback + ROI) |
                                                  +--------+--------+
                                                           |
                                                           v
+------------------+      +----------------+      +-------------------+
| Video Writer     | <--- | Visualization  | <--- | Tracker + Temporal|
| (annotated out)  |      | (optional ROI) |      | Logic + Events    |
+------------------+      +----------------+      +----+---------+----+
                                                        |         |
                                                        v         v
                                                events.csv/jsonl  frame_metrics.csv
```

## Rationale

1. Sampling + motion gate reduce inference load while staying responsive on fixed cameras.
2. Temporal logic + cooldown turn per-frame detections into stable violation events.
3. Profiling (processing vs inference FPS, latency percentiles) supports deployment validation.

## Code map

- Entry: [main.py](../main.py) → [ppe_monitoring/pipeline.py](../ppe_monitoring/pipeline.py) `run_pipeline` / `PipelineRunner`
- Config: [ppe_monitoring/config.py](../ppe_monitoring/config.py)
- Metrics column contract: [ppe_monitoring/metrics_constants.py](../ppe_monitoring/metrics_constants.py)
