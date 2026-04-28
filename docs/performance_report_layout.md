# Performance Report Layout (Wave D/E2)

## 1. Location

For each run group:

`output_files/experiments/{run_group}/ablation_analysis/`

Expected files:

- `ablation_results.csv`
- `stage_timing_summary.csv`
- `warmup_steady_summary.csv`
- `performance_report.md`
- `defense_summary.md`
- `ablation_metadata.json`

## 2. `ablation_results.csv`

One row per config.

Contains linked quality + performance view:

- quality columns from event evaluator (`tp/fp/fn`, `precision/recall/f1`, FA/h, delay)
- runtime summary columns (`input_fps_mean`, `processing_fps_mean`, `inference_fps_mean`)
- phase-specific profiling columns:
  - `processing_fps_warmup`, `processing_fps_steady`
  - `latency_p90_ms_warmup`, `latency_p90_ms_steady`
  - frame counts for `all/warmup/steady`
- bottleneck columns and transparency notes/status

## 3. `stage_timing_summary.csv`

Per config, per stage, per phase (`all/warmup/steady`) stats:

- `mean_ms`, `median_ms`, `p90_ms`, `total_ms`
- `share_of_total_loop_pct`
- `data_status`

## 4. `warmup_steady_summary.csv`

Compact phase-comparison table per config:

- `frames_count`, `inferred_frames_count`
- `processing_fps_est`, `inference_fps_est`
- loop and inference latency stats
- `data_status`

## 5. `performance_report.md`

Narrative report with:

- quality + performance summary table
- warm-up vs steady-state table
- data completeness section

## 6. `defense_summary.md`

Short defense-focused summary:

- setup snapshot
- key metrics per config
- baseline vs proposed deltas
- caveats

## 7. Missing/Insufficient Data Policy

- Missing GT or weakly informative quality must be visible via `quality_status`/notes.
- Too few steady frames must be marked (for example `insufficient_steady_frames`) and reflected in summary notes.
