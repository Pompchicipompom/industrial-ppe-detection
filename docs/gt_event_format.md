# GT Event Format Specification

Ground-truth annotations are stored as UTF-8 CSV and represent **violation events**.

## 1. File Location

- Recommended folder: `data/gt_events/`
- Template: `data/gt_events/gt_events_template.csv`

## 2. Required Columns

Required columns must exist exactly with these names:

- `video_id`
- `event_id`
- `start_frame`
- `end_frame`
- `violation_type`

Optional columns:

- `zone_id`
- `notes`

## 3. Field Rules

- `video_id`: non-empty string, should match `video_id` from `data/video_manifest.csv`
- `event_id`: non-empty string, unique within one `video_id`
- `start_frame`: integer, `>= 0`
- `end_frame`: integer, `>= start_frame`
- `violation_type`: non-empty string  
  Conservative rule for current repo: expected value is `no_hardhat`
- `zone_id` (optional): empty or non-empty string
- `notes` (optional): free text

## 4. Interval Convention

- Interval is inclusive: event is active on `[start_frame, end_frame]`.
- If single-frame event is needed, use `start_frame == end_frame`.

## 5. Example Header

```csv
video_id,event_id,start_frame,end_frame,violation_type,zone_id,notes
```

