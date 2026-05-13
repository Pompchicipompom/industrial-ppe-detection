# Single-video ablation snapshot

This directory keeps **small tabular outputs** from one reproducible ablation matrix (six configs, one short clip, `max_frames=500`).

- CSV/JSON: machine-readable metrics aligned with `tools/eval_events.py` and `tools/run_ablation.py`.
- Markdown: human-readable summaries derived from the same run.

Full run directories (per-config `processed.mp4`, `frame_metrics.csv`, logs) are **not** stored in Git; download separately if needed (see root `README.md` → External artifacts).
