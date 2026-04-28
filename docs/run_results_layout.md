# Run Results Layout (Wave B)

This document defines the output structure produced by `tools/run_experiments.py`.

## 1. Root

All experiment runs are stored under:

`output_files/experiments/`

Each batch execution gets a run group:

`output_files/experiments/{run_group}/`

If `--run-group` is not set, it is auto-generated:

`run_YYYYMMDD_HHMMSS`

## 2. Group-Level Files

Inside each run group:

- `run_plan.csv`  
  Planned matrix of `(config_name x video_id)` before execution.
- `runs_summary.csv`  
  Aggregated per-run status/metadata in tabular form.
- `runs_summary.jsonl`  
  Same summary in JSONL for downstream tooling.

## 3. Per-Run Layout

For each run:

`output_files/experiments/{run_group}/{config_name}/{video_id}/`

Files:

- `resolved_config.yaml` (fully resolved config used for this run)
- `stdout.log`
- `stderr.log`
- `run_metadata.json`
- `processed.mp4`
- `events.csv`
- `events.jsonl`
- `frame_metrics.csv`
- `runtime_profile.json`

## 4. Naming Rules

- `config_name` and `video_id` are path-sanitized for filesystem safety.
- Summary files keep original `video_id` and `source_path` values from manifest.

## 5. Metadata Fields (summary)

`runs_summary.csv/jsonl` includes:

- `timestamp_utc`
- `run_group`
- `config_name`
- `config_path`
- `video_id`
- `split`
- `source_path`
- `status` (`success`, `failed`, `dry_run`)
- `output_dir`
- `started_at_utc`
- `ended_at_utc`
- `duration_sec`
- `return_code`
- `stdout_log`
- `stderr_log`
- `resolved_config_path`
- `error_message`

