# Performance report (single-video ablation)

- generated_at_utc: `2026-05-11T12:03:14.791965+00:00`
- analysis_dir: `docs/experiments/single_video_ablation/`
- manifest: `examples/video_manifest_one.csv` (schema: `video_id,source_path,split`)
- max_frames_per_video: `500`
- warmup_frames: `20`
- steady_min_frames: `30`
- near_real_time_rule: `steady.processing_fps_est >= 0.8 * input_fps_mean`

## Quality + performance summary

| config | precision | recall | f1 | false_alarms_per_hour | mean_delay_sec | steady_fps | steady_loop_p90_ms | near_real_time | bottleneck | notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline | 0.004762 | 1.000000 | 0.009479 | 113313.253012 | 0.560000 | 0.368950 | 3547.671500 | no | main_infer_ms | limited_gt_event_count_first_round |
| proposed | 0.000000 | 0.000000 | 0.000000 | 1626.506024 | n/a | 1.544895 | 2057.294100 | no | main_infer_ms | limited_gt_event_count_first_round |
| proposed_without_motion | 0.000000 | 0.000000 | 0.000000 | 1626.506024 | n/a | 1.977953 | 1735.574600 | no | main_infer_ms | limited_gt_event_count_first_round |
| proposed_without_roi | 0.000000 | 0.000000 | 0.000000 | 1084.337349 | n/a | 1.686489 | 1972.213200 | no | main_infer_ms | limited_gt_event_count_first_round |
| proposed_without_temporal | 0.009259 | 1.000000 | 0.018349 | 58012.048193 | 0.760000 | 2.721977 | 1149.736800 | no | main_infer_ms | limited_gt_event_count_first_round |
| proposed_without_fallback | 0.000000 | 0.000000 | 0.000000 | 1084.337349 | n/a | 3.411213 | 877.986100 | no | main_infer_ms | limited_gt_event_count_first_round |

## Warm-up vs steady-state

| config | phase | frames | inferred_frames | processing_fps_est | inference_fps_est | loop_p90_ms | data_status |
|---|---|---:|---:|---:|---:|---:|---|
| baseline | warmup | 20 | 20 | 0.446520 | 0.446520 | 2642.612800 | ok |
| baseline | steady | 146 | 146 | 0.368950 | 0.368950 | 3547.671500 | ok |
| proposed | warmup | 40 | 2 | 3.847241 | 0.192362 | 30.820000 | ok |
| proposed | steady | 292 | 96 | 1.544895 | 0.507911 | 2057.294100 | ok |
| proposed_without_motion | warmup | 40 | 14 | 0.624857 | 0.218700 | 6202.753600 | ok |
| proposed_without_motion | steady | 292 | 96 | 1.977953 | 0.650286 | 1735.574600 | ok |
| proposed_without_roi | warmup | 40 | 2 | 8.219149 | 0.410957 | 14.217200 | ok |
| proposed_without_roi | steady | 292 | 96 | 1.686489 | 0.554462 | 1972.213200 | ok |
| proposed_without_temporal | warmup | 40 | 2 | 9.077961 | 0.453898 | 13.970200 | ok |
| proposed_without_temporal | steady | 292 | 96 | 2.721977 | 0.894897 | 1149.736800 | ok |
| proposed_without_fallback | warmup | 40 | 2 | 7.463639 | 0.373182 | 15.862700 | ok |
| proposed_without_fallback | steady | 292 | 96 | 3.411213 | 1.121495 | 877.986100 | ok |

## Data completeness

- `baseline`: quality_status=`available_with_gt`, performance_status=`available`.
- `proposed`: quality_status=`available_with_gt`, performance_status=`available`.
- `proposed_without_motion`: quality_status=`available_with_gt`, performance_status=`available`.
- `proposed_without_roi`: quality_status=`available_with_gt`, performance_status=`available`.
- `proposed_without_temporal`: quality_status=`available_with_gt`, performance_status=`available`.
- `proposed_without_fallback`: quality_status=`available_with_gt`, performance_status=`available`.
