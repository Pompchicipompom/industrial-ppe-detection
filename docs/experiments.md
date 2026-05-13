# Experiments

## Ablation runner

`tools/run_ablation.py` executes a fixed matrix of configs (`baseline`, `proposed`, and ablation YAMLs) over a video manifest, then runs `tools/eval_events.py` and optional performance aggregation.

```bash
python tools/run_ablation.py --manifest data/video_manifest_e1.csv --gt-dir data/gt_events --run-group my_run --max-frames 500
```

Defaults and safeguards are documented in `docs/ablation_protocol.md` and `docs/e2_evaluation_protocol.md`.

## Extended grids

`tools/run_experiments_extended.py` schedules larger configuration grids and writes `experiments_summary.csv` plus `EXPERIMENT_REPORT.md` under the chosen run group.

## Archived single-video snapshot

`docs/experiments/single_video_ablation/` contains **small** CSV/JSON/Markdown exports from one short clip (`max_frames=500`, six configs). Full per-run folders (e.g. `processed.mp4`, full `frame_metrics.csv`) are intentionally omitted from Git; treat them as external artifacts if you need to reproduce visuals.

See `docs/experiments/single_video_ablation/README.md` for file roles.
