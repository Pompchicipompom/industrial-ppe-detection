# Ablation summary (single-video run)

## Evaluation setup

- Manifest: one test clip (`video_id=demo_01`), CSV columns `video_id,source_path,split` (see `examples/video_manifest_one.csv`).
- Configs: `baseline`, `proposed`, `proposed_without_motion`, `proposed_without_roi`, `proposed_without_temporal`, `proposed_without_fallback`.
- `max_frames_per_video`: `500`
- `warmup_frames_for_profiling`: `20`

## Key results

| config | precision | recall | f1 | false_alarms_per_hour | mean_delay_sec | steady_fps | steady_p90_ms | bottleneck |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.004762 | 1.000000 | 0.009479 | 113313.253012 | 0.560000 | 0.368950 | 3547.671500 | main_infer_ms |
| proposed | 0.000000 | 0.000000 | 0.000000 | 1626.506024 | n/a | 1.544895 | 2057.294100 | main_infer_ms |
| proposed_without_motion | 0.000000 | 0.000000 | 0.000000 | 1626.506024 | n/a | 1.977953 | 1735.574600 | main_infer_ms |
| proposed_without_roi | 0.000000 | 0.000000 | 0.000000 | 1084.337349 | n/a | 1.686489 | 1972.213200 | main_infer_ms |
| proposed_without_temporal | 0.009259 | 1.000000 | 0.018349 | 58012.048193 | 0.760000 | 2.721977 | 1149.736800 | main_infer_ms |
| proposed_without_fallback | 0.000000 | 0.000000 | 0.000000 | 1084.337349 | n/a | 3.411213 | 877.986100 | main_infer_ms |

## Baseline vs proposed

- recall delta (proposed - baseline): `-1.000000`
- f1 delta (proposed - baseline): `-0.009479`
- steady FPS delta (proposed - baseline): `1.175945`
- steady loop p90 delta ms (proposed - baseline): `-1490.377400`

## Caveats

- Limited ground-truth event count on this clip (`limited_gt_event_count_first_round` in tooling notes).
- Duplicate successful rows in the original `runs_summary.csv` can inflate aggregates if not de-duplicated; prefer `per_video_metrics.csv` for per-config inspection.
