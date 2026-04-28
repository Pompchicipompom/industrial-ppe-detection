from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt


def load_profile(profile_path: Path) -> dict:
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def fmt(value, ndigits: int = 2) -> str:
    try:
        return f"{float(value):.{ndigits}f}"
    except Exception:
        return str(value)


def build_markdown(profile: dict) -> str:
    runtime = profile.get("runtime_summary", {})
    comparison = profile.get("comparison", {})
    rtsp_health = profile.get("rtsp_health", {})
    cfg = profile.get("config", {})
    pipeline = cfg.get("pipeline", {})
    motion = cfg.get("motion", {})
    event_logic = cfg.get("event_logic", {})

    generated_at = profile.get("generated_at_utc", "unknown")
    source = profile.get("source", "unknown")
    is_rtsp = profile.get("is_rtsp", False)
    events_total = profile.get("events_total", 0)

    return f"""# CONTEXT PACKAGE FOR CHATGPT (PPE VIDEO MONITORING)

Generated at: {datetime.now(timezone.utc).isoformat()}
Runtime profile timestamp: {generated_at}

## 1) Project Goal

This project is an industrial video-first PPE monitoring prototype (hard-hat compliance).
It is not an image-only demo. It is designed for:
- video files and RTSP streams
- fixed-camera operation with motion gating
- near-real-time processing
- temporal event logic and cooldown
- event generation and logging
- runtime performance profiling for deployment review

## 2) What Was Engineered

Refactor from monolithic script to modular architecture:
- ppe_monitoring/config.py
- ppe_monitoring/pipeline.py
- ppe_monitoring/detector.py
- ppe_monitoring/tracker.py
- ppe_monitoring/event_logic.py
- ppe_monitoring/motion.py
- ppe_monitoring/profiler.py
- ppe_monitoring/rtsp_health.py
- report_summary.py (commission markdown report generator)

Main entrypoint:
- main.py

## 3) Pipeline Architecture (ASCII)

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

## 4) Current Runtime Snapshot (from runtime_profile.json)

- Source: {source}
- RTSP mode: {is_rtsp}
- Total events: {events_total}

Performance:
- input_fps: {fmt(runtime.get("input_fps"), 2)}
- processing_fps: {fmt(runtime.get("processing_fps"), 2)}
- inference_fps: {fmt(runtime.get("inference_fps"), 2)}
- inference_ms_mean / median / p90:
  {fmt(runtime.get("inference_ms_mean"), 2)} / {fmt(runtime.get("inference_ms_median"), 2)} / {fmt(runtime.get("inference_ms_p90"), 2)}
- loop_ms_mean / median / p90:
  {fmt(runtime.get("loop_ms_mean"), 2)} / {fmt(runtime.get("loop_ms_median"), 2)} / {fmt(runtime.get("loop_ms_p90"), 2)}

Input-vs-Inference comparison:
- input_fps_minus_inference_fps: {fmt(comparison.get("input_fps_minus_inference_fps"), 2)}
- inference_fps_to_input_fps_ratio: {fmt(comparison.get("inference_fps_to_input_fps_ratio"), 4)}

RTSP health:
- open_attempts_total: {rtsp_health.get("open_attempts_total", 0)}
- open_successes: {rtsp_health.get("open_successes", 0)}
- read_failures_total: {rtsp_health.get("read_failures_total", 0)}
- reconnect_attempts_total: {rtsp_health.get("reconnect_attempts_total", 0)}
- reconnect_successes: {rtsp_health.get("reconnect_successes", 0)}
- reconnect_failures: {rtsp_health.get("reconnect_failures", 0)}
- total_downtime_sec: {fmt(rtsp_health.get("total_downtime_sec"), 3)}
- longest_downtime_sec: {fmt(rtsp_health.get("longest_downtime_sec"), 3)}

## 5) Key Runtime Settings (active during this profile)

Pipeline:
- mode: {pipeline.get("mode")}
- sampling_fps: {pipeline.get("sampling_fps")}
- force_infer_every_n_frames: {pipeline.get("force_infer_every_n_frames")}
- max_track_stale_frames: {pipeline.get("max_track_stale_frames")}

Motion:
- enabled: {motion.get("enabled")}
- min_ratio: {motion.get("min_ratio")}
- pixel_threshold: {motion.get("pixel_threshold")}

Temporal event logic:
- no_hardhat_consecutive_frames: {event_logic.get("no_hardhat_consecutive_frames")}
- no_hardhat_seconds_threshold: {event_logic.get("no_hardhat_seconds_threshold")}
- cooldown_frames: {event_logic.get("cooldown_frames")}
- cooldown_seconds: {event_logic.get("cooldown_seconds")}

## 6) Artifacts Produced Per Run

- output_files/processed.mp4
- output_files/events.csv
- output_files/events.jsonl
- output_files/frame_metrics.csv
- output_files/runtime_profile.json
- output_files/commission_report.md (generated by report_summary.py)

## 7) How ChatGPT Should Use This Context

When analyzing new run results, ChatGPT should:
1. Compare input_fps vs processing_fps vs inference_fps.
2. Evaluate inference and loop latency (mean/median/p90) for near-real-time fit.
3. Inspect rtsp_health reconnect/drop statistics for reliability.
4. Analyze event quality from events.csv/jsonl (frequency, cooldown behavior, false-positive patterns).
5. Use frame_metrics.csv to explain gating behavior (sampled/did_infer vs motion_ratio).
6. Produce:
   - engineering conclusions
   - deployment risks
   - tuning recommendations
   - report section text
   - slide-ready bullets/figures

## 8) Prompt Template for Next ChatGPT Session

Use the text below as your first message in a new chat:

```text
You are my technical report assistant for an industrial PPE video monitoring project.
I will provide artifacts from my pipeline run:
1) runtime_profile.json
2) frame_metrics.csv
3) events.csv
4) events.jsonl
5) commission_report.md (optional)

Your task:
- analyze runtime performance (input/processing/inference FPS, latency mean/median/p90)
- analyze RTSP reliability from rtsp_health
- analyze temporal event behavior and potential false positives/false negatives
- provide concrete tuning recommendations (sampling/motion thresholds/cooldown/temporal params)
- produce:
  A) technical report text in formal style
  B) presentation outline (10-12 slides) with speaker notes
  C) concise defense-ready Q&A list (commission questions and robust answers)

Focus on engineering rigor and deployment-readiness.
```

## 9) Notes

- This package is for context transfer to another ChatGPT session.
- Keep this file together with raw artifacts for best results.
"""


def markdown_to_pdf(markdown_text: str, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for raw in markdown_text.splitlines():
        if not raw:
            lines.append("")
            continue
        wrapped = textwrap.wrap(raw, width=105, replace_whitespace=False, drop_whitespace=False)
        if not wrapped:
            lines.append("")
        else:
            lines.extend(wrapped)

    lines_per_page = 48
    pages = [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]

    with PdfPages(pdf_path) as pdf:
        for page_lines in pages:
            fig = plt.figure(figsize=(8.27, 11.69))  # A4
            fig.patch.set_facecolor("white")
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
            text = "\n".join(page_lines)
            ax.text(
                0.04,
                0.98,
                text,
                va="top",
                ha="left",
                fontsize=9.5,
                family="DejaVu Sans",
            )
            pdf.savefig(fig)
            plt.close(fig)


def main():
    root = Path(__file__).resolve().parent
    profile_path = root / "output_files" / "runtime_profile.json"
    out_md = root / "output_files" / "chatgpt_handoff.md"
    out_pdf = root / "output_files" / "chatgpt_handoff.pdf"

    profile = load_profile(profile_path)
    markdown = build_markdown(profile)
    out_md.write_text(markdown, encoding="utf-8")
    markdown_to_pdf(markdown, out_pdf)

    print(f"Handoff markdown: {out_md}")
    print(f"Handoff PDF: {out_pdf}")


if __name__ == "__main__":
    main()

