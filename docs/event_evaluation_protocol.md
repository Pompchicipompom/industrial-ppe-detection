# Event Evaluation Protocol (Wave C)

## 1. Unit of Evaluation

Evaluation is performed at the **event level** (violation events), not at frame-level detection.

- Predicted events come from pipeline output `events.csv`.
- Ground truth (GT) events come from `data/gt_events/*.csv`.

An event in this project is currently a `violation_type=no_hardhat` interval on a specific video.

## 2. Inputs

For each run in a run group:

- `video_id`, `config_name`, `split`, `status` from `runs_summary.csv`
- predicted events from `{output_dir}/events.csv`
- optional runtime files for time normalization:
  - `{output_dir}/runtime_profile.json`
  - `{output_dir}/frame_metrics.csv`

GT inputs:

- CSV files from `--gt-dir` following `docs/gt_event_format.md`.

## 3. Matching Rule

A predicted event can match a GT event only if:

1. `video_id` is the same
2. `violation_type` is the same (`event_type` from predictions vs `violation_type` in GT)
3. Predicted frame falls in GT interval with tolerance:

`start_frame - tolerance_frames <= pred_frame <= end_frame + tolerance_frames`

## 4. Tolerance Policy

- `tolerance_frames` is an explicit evaluator parameter.
- Default is strict (`0` frames) unless user sets a different value.

Interpretation:

- `0`: prediction must fall inside GT interval.
- `N > 0`: prediction can be up to `N` frames earlier/later than interval boundaries.

## 5. One-to-One Constraint

- One GT event can be matched by at most one predicted event.
- If multiple predictions satisfy one GT interval:
  - only one is counted as TP
  - remaining predictions are counted as FP

Implementation policy:

- Predictions are processed in ascending `frame_idx`.
- For each prediction, evaluator selects one unmatched GT candidate with minimal temporal distance.

## 6. TP / FP / FN Definitions

Per run (video + config):

- `TP`: matched prediction-GT pairs
- `FP`: unmatched predictions
- `FN`: unmatched GT events

## 7. Metrics

Per run:

- `Precision = TP / (TP + FP)` (0 when denominator is 0)
- `Recall = TP / (TP + FN)` (0 when denominator is 0)
- `F1 = 2PR/(P+R)` (0 when denominator is 0)

`false_alarms_per_hour`:

- `FP / (duration_sec / 3600)`
- `duration_sec` estimated from run artifacts:
  1. `frame_metrics.csv` timeline (preferred)
  2. `frames_total / input_fps` from `runtime_profile.json`
  3. `0` if unavailable

`mean_detection_delay_sec`:

- computed on matched TPs only
- per match: `max(0, pred_frame - gt_start_frame) / fps`
- fps from `runtime_profile.json` input FPS (fallback 30.0)

## 8. Aggregation

Aggregation is done **per `config_name`** across evaluated runs:

- counts are micro-summed: `TP_total`, `FP_total`, `FN_total`
- `Precision/Recall/F1` derived from summed counts
- `false_alarms_per_hour` from total FP and total duration
- `mean_detection_delay_sec` from all matched delays combined

Runs with non-success status are not used for metric aggregation and are reported as skipped.

