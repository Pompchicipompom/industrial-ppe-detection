# Event-level evaluation

## Tooling

`tools/eval_events.py` matches predicted `no_hardhat` / `no_vest` events from pipeline outputs against ground-truth intervals.

Typical invocation (from repository root):

```bash
python tools/eval_events.py --run-group <run_group_name> --experiments-root output_files/experiments --gt-dir data/gt_events --tolerance-frames 0
```

- `--run-group` — either a directory name under `--experiments-root` or an absolute path to that directory.
- Outputs are written under `<run_group>/evaluation/` (or `--output-subdir`): `per_video_metrics.csv`, `aggregate_metrics.csv`, `baseline_vs_proposed.csv`, `evaluation_metadata.json`.

## Ground truth format

Per manifest `video_id`, provide a CSV (see `docs/gt_event_format.md`) with at least:

`video_id`, `event_id`, `start_frame`, `end_frame`, `violation_type`

Optional columns: `zone_id`, `notes`.

## Prediction format

Predictions are read from each run’s `events.csv` / `events.jsonl` using columns compatible with `tools/eval_events.py` (see implementation for the exact schema used in your export).

## Metrics

For each configuration and clip:

- **TP** — predicted event matches a GT interval within `tolerance_frames`.
- **FP** — predicted event with no matching GT.
- **FN** — GT interval with no matching prediction.
- **Precision / recall / F1** — standard definitions from TP/FP/FN totals.
- **False alarms per hour** — FP count normalised by evaluated wall-clock duration.
- **Mean detection delay** — average temporal offset between prediction and GT start for TPs (when timestamps/frames allow).

See also `docs/event_evaluation_protocol.md` and `docs/e2_evaluation_protocol.md` for end-to-end experiment discipline.
