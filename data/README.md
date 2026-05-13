# Data directory

Place **local** video files and experiment manifests here. Large binaries are not committed to Git (see repository `.gitignore`).

## Suggested layout

- `data/videos/` — input clips referenced from your manifest CSV.
- `data/gt_events/` — one CSV per `video_id` with columns  
  `video_id,event_id,start_frame,end_frame,violation_type` (optional: `zone_id`, `notes`).  
  See `docs/gt_event_format.md` and `examples/sample_gt_events.csv`.

## Manifest format

CSV with header:

```text
video_id,source_path,split
```

- `video_id` — stable string key used in GT filenames and evaluation summaries.
- `source_path` — path relative to repository root or absolute path on your machine.
- `split` — optional grouping label (`dev`, `test`, `stress`, `negative`) used by `tools/run_ablation.py` / `tools/eval_events.py`.

Example: `examples/video_manifest_one.csv`.
