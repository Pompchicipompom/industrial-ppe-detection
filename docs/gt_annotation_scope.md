# GT Annotation Scope (E1 Foundation)

## Purpose

This document fixes the minimal annotation scope for the first **meaningful** event-level evaluation round after smoke validation.

E1 scope goals:

- include all required splits: `dev`, `test`, `stress`
- provide non-empty `no_hardhat` GT events
- keep annotation package small and reproducible

## Scope Manifest

Scope manifest file:

- `data/video_manifest_e1.csv`

Selected segments:

1. `e1_dev_hardhat_input_video1_seg_a` (`dev`) from `input_files/hardhat_input_video1.mp4`
2. `e1_test_hardhat_input_video_seg_a` (`test`) from `input_files/hardhat_input_video.mp4`
3. `e1_stress_hardhat_input_video4_seg_a` (`stress`) from `input_files/hardhat_input_video4.mp4`

## GT Package

GT file:

- `data/gt_events/gt_events_e1.csv`

GT schema follows `docs/gt_event_format.md`.

E2 refinement note:

- event boundaries were updated conservatively to stay inside an E2 capped non-smoke round (`max_frames=140`)
- this keeps the first meaningful evaluation tractable while preserving non-empty GT across all splits

## Annotation Protocol (E1)

- event type: `no_hardhat`
- unit: interval in frame indices (`start_frame`, `end_frame`)
- annotation mode: manual visual annotation on original videos
- each selected split must contain at least one non-empty event interval

## Notes and Constraints

- E1 scope is intentionally minimal and is designed for the **first meaningful comparison**, not final statistical validation.
- Intervals were chosen conservatively from visually clear periods where a worker without a visible hardhat is present.
- Later waves may refine boundaries or add multi-annotator review.
