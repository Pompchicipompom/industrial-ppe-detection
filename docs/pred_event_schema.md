# Predicted Event Schema (Hardening Patch)

This document defines the output schema of predicted violation events produced by the runtime pipeline.

## 1. Files

Per run, predicted events are exported to:

- `events.csv`
- `events.jsonl`

Both contain the same logical fields.

## 2. Schema Version

- `schema_version` is currently fixed to `1`.
- Purpose: explicit contract versioning for evaluator/report tooling.

## 3. Fields

### Required fields (schema v1)

- `video_id`
- `schema_version`
- `event_id`
- `frame_idx`
- `timestamp_sec`
- `person_track_id`
- `event_type`
- `no_hardhat_streak`
- `no_hardhat_duration_sec`

### Field meaning

- `video_id`: logical video identifier for this run.  
  Resolution policy:
  1) if `pipeline.video_id` is provided, use it;
  2) otherwise derive from source (file stem / camera index / RTSP token).
- `schema_version`: integer schema version (now `1`).
- `event_id`: monotonic event sequence ID within a run.
- `frame_idx`: frame index where event is emitted.
- `timestamp_sec`: event timestamp in seconds.
- `person_track_id`: internal person track identifier.
- `event_type`: violation type (currently expected `no_hardhat`).
- `no_hardhat_streak`: consecutive no-hardhat evidence count at emit time.
- `no_hardhat_duration_sec`: continuous no-hardhat duration at emit time.

## 4. CSV Header (v1)

```csv
video_id,schema_version,event_id,frame_idx,timestamp_sec,person_track_id,event_type,no_hardhat_streak,no_hardhat_duration_sec
```

## 5. Backward Compatibility

- Existing historical run outputs without `video_id` and `schema_version` remain readable by current evaluator.
- Evaluator matching continues to rely on `frame_idx` and `event_type`, so old artifacts are still valid for analysis.

