from __future__ import annotations

from collections import defaultdict

from .types import ViolationEvent


class TemporalEventLogic:
    def __init__(self, cfg: dict):
        event_cfg = cfg["event_logic"]
        self.confirm_frames = int(event_cfg.get("hardhat_confirm_frames", 2))
        self.revoke_frames = int(event_cfg.get("hardhat_revoke_frames", 4))
        self.lock_after_confirm = bool(event_cfg.get("lock_after_confirm", True))
        self.no_hardhat_consecutive_frames = int(event_cfg.get("no_hardhat_consecutive_frames", 20))
        self.no_hardhat_seconds_threshold = float(event_cfg.get("no_hardhat_seconds_threshold", 2.0))
        self.cooldown_frames = int(event_cfg.get("cooldown_frames", 90))
        self.cooldown_seconds = float(event_cfg.get("cooldown_seconds", 3.0))
        self.max_no_hardhat_hold_frames_without_infer = int(
            event_cfg.get("max_no_hardhat_hold_frames_without_infer", 4)
        )

        self.hardhat_confirmed = defaultdict(lambda: False)
        self.hardhat_positive_streak = defaultdict(int)
        self.hardhat_miss_streak = defaultdict(int)
        self.no_hardhat_streak = defaultdict(int)
        self.last_hardhat_seen_ts: dict[int, float] = {}
        self.last_infer_frame: dict[int, int] = {}
        self.violation_active_state = defaultdict(lambda: False)
        self.last_alert_frame = defaultdict(lambda: -10**9)
        self.last_alert_ts = defaultdict(lambda: -10**9)
        self.first_seen_frame: dict[int, int] = {}
        self.first_seen_ts: dict[int, float] = {}
        self.event_counter = 0
        self.has_hardhat_ever: set[int] = set()
        self.active_no_hardhat_persons: set[int] = set()
        self.unique_no_hardhat_persons: set[int] = set()

    def update(
        self,
        person_boxes: dict[int, tuple[float, float, float, float]],
        person_hardhat_observed: dict[int, bool],
        frame_idx: int,
        timestamp_sec: float,
        did_infer: bool,
    ) -> tuple[dict[int, bool], list[ViolationEvent], int, set[int]]:
        statuses: dict[int, bool] = {}
        events: list[ViolationEvent] = []
        active_violations = 0
        violating_person_ids: set[int] = set()

        for person_id in person_boxes:
            if person_id not in self.first_seen_frame:
                self.first_seen_frame[person_id] = frame_idx
                self.first_seen_ts[person_id] = timestamp_sec

            if person_id not in self.last_hardhat_seen_ts:
                self.last_hardhat_seen_ts[person_id] = self.first_seen_ts[person_id]

            if did_infer:
                self.last_infer_frame[person_id] = frame_idx
                observed = bool(person_hardhat_observed.get(person_id, False))
                if observed:
                    self.has_hardhat_ever.add(person_id)
                    self.hardhat_positive_streak[person_id] += 1
                    self.hardhat_miss_streak[person_id] = 0
                    self.last_hardhat_seen_ts[person_id] = timestamp_sec
                else:
                    self.hardhat_positive_streak[person_id] = 0
                    self.hardhat_miss_streak[person_id] += 1

                if (
                    not self.hardhat_confirmed[person_id]
                    and self.hardhat_positive_streak[person_id] >= self.confirm_frames
                ):
                    self.hardhat_confirmed[person_id] = True
                if (
                    not self.lock_after_confirm
                    and self.hardhat_confirmed[person_id]
                    and self.hardhat_miss_streak[person_id] >= self.revoke_frames
                ):
                    self.hardhat_confirmed[person_id] = False

            has_hardhat = bool(person_id in self.has_hardhat_ever) or (
                bool(self.hardhat_confirmed[person_id]) and (self.hardhat_miss_streak[person_id] < self.revoke_frames)
            )
            statuses[person_id] = has_hardhat

            if did_infer:
                if has_hardhat:
                    self.no_hardhat_streak[person_id] = 0
                else:
                    self.no_hardhat_streak[person_id] += 1

            no_hardhat_duration = max(0.0, timestamp_sec - self.last_hardhat_seen_ts[person_id])
            meets_frames = self.no_hardhat_streak[person_id] >= self.no_hardhat_consecutive_frames
            meets_seconds = no_hardhat_duration >= self.no_hardhat_seconds_threshold
            if person_id in self.has_hardhat_ever:
                self.no_hardhat_streak[person_id] = 0
                self.violation_active_state[person_id] = False
            elif did_infer:
                self.violation_active_state[person_id] = (not has_hardhat) and meets_frames and meets_seconds
            elif (frame_idx - self.last_infer_frame.get(person_id, -10**9)) > self.max_no_hardhat_hold_frames_without_infer:
                self.violation_active_state[person_id] = False
            violation_active = bool(self.violation_active_state[person_id])

            if violation_active:
                active_violations += 1
                violating_person_ids.add(person_id)
                self.unique_no_hardhat_persons.add(person_id)
                cooldown_by_frames = (frame_idx - self.last_alert_frame[person_id]) >= self.cooldown_frames
                cooldown_by_time = (timestamp_sec - self.last_alert_ts[person_id]) >= self.cooldown_seconds
                if cooldown_by_frames and cooldown_by_time:
                    self.event_counter += 1
                    event = ViolationEvent(
                        event_id=self.event_counter,
                        frame_idx=frame_idx,
                        timestamp_sec=timestamp_sec,
                        person_track_id=person_id,
                        event_type="no_hardhat",
                        no_hardhat_streak=self.no_hardhat_streak[person_id],
                        no_hardhat_duration_sec=no_hardhat_duration,
                    )
                    events.append(event)
                    self.last_alert_frame[person_id] = frame_idx
                    self.last_alert_ts[person_id] = timestamp_sec

        self.active_no_hardhat_persons = set(violating_person_ids)
        return statuses, events, active_violations, violating_person_ids

    def seen_seconds(self, person_id: int, frame_idx: int, input_fps: float) -> float:
        if person_id not in self.first_seen_frame:
            return 0.0
        seen_frames = frame_idx - self.first_seen_frame[person_id] + 1
        fps = input_fps if input_fps > 0 else 30.0
        return seen_frames / float(fps)

    def remove_ids(self, person_ids: list[int]) -> None:
        for person_id in person_ids:
            self.hardhat_confirmed.pop(person_id, None)
            self.hardhat_positive_streak.pop(person_id, None)
            self.hardhat_miss_streak.pop(person_id, None)
            self.no_hardhat_streak.pop(person_id, None)
            self.last_hardhat_seen_ts.pop(person_id, None)
            self.last_infer_frame.pop(person_id, None)
            self.violation_active_state.pop(person_id, None)
            self.last_alert_frame.pop(person_id, None)
            self.last_alert_ts.pop(person_id, None)
            self.first_seen_frame.pop(person_id, None)
            self.first_seen_ts.pop(person_id, None)
            self.has_hardhat_ever.discard(person_id)
            self.active_no_hardhat_persons.discard(person_id)
