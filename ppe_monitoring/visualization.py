from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

from .geometry import bbox_iou
from .types import Detection


def _draw_dashed_rectangle(
    frame,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple[int, int, int],
    thickness: int = 1,
    dash: int = 8,
    gap: int = 5,
) -> None:
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    step = dash + gap
    for x in range(x1, x2, step):
        cv2.line(frame, (x, y1), (min(x + dash, x2), y1), color, thickness)
    for x in range(x1, x2, step):
        cv2.line(frame, (x, y2), (min(x + dash, x2), y2), color, thickness)
    for y in range(y1, y2, step):
        cv2.line(frame, (x1, y), (x1, min(y + dash, y2)), color, thickness)
    for y in range(y1, y2, step):
        cv2.line(frame, (x2, y), (x2, min(y + dash, y2)), color, thickness)


@dataclass
class _VisualTrack:
    bbox: tuple[float, float, float, float]
    ttl: int


class VisualizationRenderer:
    def __init__(self, vis_cfg: dict):
        self.vis_cfg = vis_cfg
        self.head_tracks: dict[str, _VisualTrack] = {}
        self.hardhat_tracks: dict[str, _VisualTrack] = {}
        self.person_hardhat_locked: set[int] = set()
        self.person_last_seen_frame: dict[int, int] = {}
        self.skipped_stale_visual_bbox = 0

    def _smooth_headlike(
        self,
        detections: list[Detection],
        tracks: dict[str, _VisualTrack],
        frame_idx: int,
    ) -> list[Detection]:
        enabled = bool(self.vis_cfg.get("smoothing_enabled", True))
        if not enabled:
            return detections
        alpha = float(self.vis_cfg.get("bbox_smoothing_alpha", 0.4))
        alpha = max(0.05, min(0.95, alpha))
        ttl = int(self.vis_cfg.get("head_hat_ttl_frames", self.vis_cfg.get("bbox_ttl_frames", 3)))
        iou_th = float(self.vis_cfg.get("bbox_smoothing_match_iou", 0.20))
        used: set[str] = set()
        out: list[Detection] = []

        for det in detections:
            key = f"f{frame_idx}-{len(out)}"
            best_key = None
            best_iou = 0.0
            for old_key, tr in tracks.items():
                if old_key in used:
                    continue
                iou = bbox_iou(det.bbox_xyxy, tr.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_key = old_key
            if best_key is not None and best_iou >= iou_th:
                prev = tracks[best_key].bbox
                x1 = prev[0] * (1.0 - alpha) + det.bbox_xyxy[0] * alpha
                y1 = prev[1] * (1.0 - alpha) + det.bbox_xyxy[1] * alpha
                x2 = prev[2] * (1.0 - alpha) + det.bbox_xyxy[2] * alpha
                y2 = prev[3] * (1.0 - alpha) + det.bbox_xyxy[3] * alpha
                smooth_box = (x1, y1, x2, y2)
                tracks[best_key] = _VisualTrack(bbox=smooth_box, ttl=ttl)
                used.add(best_key)
                out.append(
                    Detection(
                        cls_id=det.cls_id,
                        cls_name=det.cls_name,
                        conf=det.conf,
                        bbox_xyxy=smooth_box,
                        track_id=det.track_id,
                        source=det.source,
                        owner_person_id=det.owner_person_id,
                        hardhat_state=det.hardhat_state,
                    )
                )
            else:
                tracks[key] = _VisualTrack(bbox=det.bbox_xyxy, ttl=ttl)
                used.add(key)
                out.append(det)

        for key in list(tracks.keys()):
            if key in used:
                continue
            tracks[key].ttl -= 1
            if tracks[key].ttl <= 0:
                tracks.pop(key, None)
        return out

    def draw_runtime_overlay(
        self,
        frame,
        last_main_detections: list[Detection],
        accepted_heads: list[Detection],
        accepted_hardhats: list[Detection],
        person_boxes: dict[int, tuple[float, float, float, float]],
        confirmed_ids_for_draw: set[int],
        statuses: dict[int, bool],
        event_logic,
        violating_person_ids: set[int],
        frame_idx: int,
        input_fps: float,
        person_confirm_mode: str,
        active_violations: int,
        total_events: int,
        person_hardhat_observed: dict[int, bool],
        active_no_hardhat_now: int,
        unique_no_hardhat_total: int,
    ) -> None:
        vis_cfg = self.vis_cfg
        smoothed_heads = self._smooth_headlike(accepted_heads, self.head_tracks, frame_idx)
        smoothed_hardhats = self._smooth_headlike(accepted_hardhats, self.hardhat_tracks, frame_idx)
        draw_raw = bool(vis_cfg.get("draw_raw_detections", vis_cfg.get("draw_all_main_detections", False)))
        color_person = tuple(vis_cfg.get("person_color", (255, 0, 0)))
        color_head = tuple(vis_cfg.get("head_color", (0, 255, 255)))
        color_hardhat = tuple(vis_cfg.get("hardhat_color", (0, 255, 0)))
        color_violation = tuple(vis_cfg.get("violation_color", (0, 0, 255)))
        color_text = tuple(vis_cfg.get("text_color", (255, 255, 255)))
        thickness = int(vis_cfg.get("bbox_thickness", 2))
        label_scale = 0.52
        color_person_neutral = color_violation
        color_person_with_hardhat = color_hardhat
        person_ttl = int(vis_cfg.get("person_ttl_frames", 12))

        for pid in person_boxes:
            self.person_last_seen_frame[pid] = frame_idx
        for pid, observed in person_hardhat_observed.items():
            if observed:
                self.person_hardhat_locked.add(pid)
                self.person_last_seen_frame[pid] = frame_idx
        for pid in list(self.person_hardhat_locked):
            if (frame_idx - self.person_last_seen_frame.get(pid, -10**9)) > person_ttl:
                self.person_hardhat_locked.discard(pid)
                self.person_last_seen_frame.pop(pid, None)

        if draw_raw and last_main_detections:
            show_conf = vis_cfg.get("draw_detection_confidence_labels", False)
            skip_raw = {"person", "head", "hardhat"}
            default_color = (180, 180, 180)
            for d in last_main_detections:
                if d.cls_name in skip_raw:
                    continue
                x1, y1, x2, y2 = [int(v) for v in d.bbox_xyxy]
                cv2.rectangle(frame, (x1, y1), (x2, y2), default_color, 1)
                label = f"{d.cls_name} {d.conf:.2f}" if show_conf else d.cls_name
                cv2.putText(frame, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, default_color, 1)

        if vis_cfg.get("draw_head_hardhat_boxes", True):
            for det in smoothed_heads:
                x1, y1, x2, y2 = [int(v) for v in det.bbox_xyxy]
                cv2.rectangle(frame, (x1, y1), (x2, y2), color_head, thickness)
                cv2.putText(frame, "head", (x1, max(12, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color_head, 1)
            for det in smoothed_hardhats:
                x1, y1, x2, y2 = [int(v) for v in det.bbox_xyxy]
                cv2.rectangle(frame, (x1, y1), (x2, y2), color_hardhat, thickness)
                cv2.putText(frame, "hardhat", (x1, max(12, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color_hardhat, 1)

        draw_tracker_boxes = bool(vis_cfg.get("draw_tracker_boxes", vis_cfg.get("draw_person_boxes", True)))
        if draw_tracker_boxes:
            show_weak = bool(vis_cfg.get("show_weak_person", False))
            for person_id, (x1, y1, x2, y2) in person_boxes.items():
                is_confirmed = person_id in confirmed_ids_for_draw
                if person_confirm_mode == "soft" and not is_confirmed and not show_weak:
                    continue
                xi1, yi1, xi2, yi2 = int(x1), int(y1), int(x2), int(y2)
                if not is_confirmed:
                    weak_col = (0, 200, 255)
                    _draw_dashed_rectangle(frame, xi1, yi1, xi2, yi2, weak_col, thickness=thickness)
                    cv2.putText(
                        frame, f"weak | id:{person_id}", (xi1, max(12, yi1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, weak_col, 1
                    )
                    continue

                has_hardhat = bool(statuses.get(person_id, False) or (person_id in self.person_hardhat_locked))
                if has_hardhat:
                    person_color = color_person_with_hardhat
                elif person_id in violating_person_ids:
                    person_color = color_violation
                else:
                    person_color = color_person_neutral
                seen_seconds = event_logic.seen_seconds(person_id, frame_idx, input_fps)
                person_status = "with hardhat" if has_hardhat else "person"
                cv2.rectangle(frame, (xi1, yi1), (xi2, yi2), person_color, thickness)
                cv2.putText(
                    frame,
                    f"{person_status} | t: {seen_seconds:.1f}s | id:{person_id}",
                    (xi1, max(12, yi1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    label_scale,
                    person_color,
                    2,
                )

                if vis_cfg.get("show_violation_dot", True) and person_id in violating_person_ids:
                    blink_period = max(2, int(vis_cfg.get("dot_blink_period_frames", 14)))
                    blink_on = (frame_idx % blink_period) < (blink_period // 2)
                    if blink_on:
                        dot_x = int((x1 + x2) / 2.0)
                        dot_y = max(8, int(y1) - 14)
                        dot_r = max(2, int(vis_cfg.get("dot_radius", 8)))
                        cv2.circle(frame, (dot_x, dot_y), dot_r + 2, (0, 0, 0), -1)
                        cv2.circle(frame, (dot_x, dot_y), dot_r, color_violation, -1)

        if vis_cfg.get("show_violation_banner", True):
            _draw_status_panel(
                frame=frame,
                active_violations=active_violations,
                unique_no_hardhat_total=unique_no_hardhat_total,
                text_color=color_text,
                accent_color=color_violation,
                hide_when_idle=bool(vis_cfg.get("hide_panel_when_idle", False)),
            )


def _draw_violation_banner(
    frame,
    text: str,
    top_left: tuple[int, int],
    bg_color_bgr: tuple[int, int, int],
    text_color_bgr: tuple[int, int, int],
) -> None:
    x, y = top_left
    if Image is None or ImageFont is None:
        cv2.rectangle(frame, (x, y), (x + 420, y + 38), bg_color_bgr, -1)
        cv2.putText(frame, text, (x + 8, y + 27), cv2.FONT_HERSHEY_SIMPLEX, 0.78, text_color_bgr, 2)
        return

    font = _load_cyrillic_font(30)
    if font is None:
        cv2.rectangle(frame, (x, y), (x + 420, y + 38), bg_color_bgr, -1)
        cv2.putText(frame, text, (x + 8, y + 27), cv2.FONT_HERSHEY_SIMPLEX, 0.78, text_color_bgr, 2)
        return

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x = 10
    pad_y = 6
    draw.rectangle((x, y, x + tw + 2 * pad_x, y + th + 2 * pad_y), fill=_bgr_to_rgb(bg_color_bgr))
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=_bgr_to_rgb(text_color_bgr))
    frame[:, :, :] = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _draw_status_panel(
    frame,
    active_violations: int,
    unique_no_hardhat_total: int,
    text_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    hide_when_idle: bool = False,
) -> None:
    if hide_when_idle and unique_no_hardhat_total <= 0 and active_violations <= 0:
        return
    lines: list[str] = ["Нарушение: нет каски", f"Нарушений: {int(unique_no_hardhat_total)}"]

    panel_x = 12
    panel_y = 12
    pad = max(8, int(frame.shape[0] * 0.012))
    font_px = max(16, int(frame.shape[0] * 0.034))
    if Image is None or ImageFont is None:
        y = panel_y + 24
        for line in lines:
            cv2.putText(frame, line, (panel_x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, text_color, 2)
            y += 26
        return

    font = _load_cyrillic_font(font_px)
    if font is None:
        y = panel_y + 24
        for line in lines:
            cv2.putText(frame, line, (panel_x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, text_color, 2)
            y += 26
        return

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)
    widths = []
    heights = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])
    text_h = sum(heights) + (len(lines) - 1) * max(4, int(font_px * 0.20))
    panel_w = max(widths) + 2 * pad
    panel_h = text_h + 2 * pad

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    panel_bg = (18, 18, 18, 170)
    od.rounded_rectangle((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h), radius=8, fill=panel_bg)
    if active_violations > 0:
        ax = panel_x
        ay = panel_y
        od.rounded_rectangle((ax, ay, ax + 6, ay + panel_h), radius=3, fill=_bgr_to_rgb(accent_color) + (255,))

    ty = panel_y + pad
    for i, line in enumerate(lines):
        color = _bgr_to_rgb(accent_color) if i == 0 else _bgr_to_rgb(text_color)
        od.text((panel_x + pad + 4, ty), line, font=font, fill=color + (255,))
        ty += heights[i] + max(4, int(font_px * 0.20))

    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    frame[:, :, :] = cv2.cvtColor(np.array(composed), cv2.COLOR_RGB2BGR)


def _load_cyrillic_font(size: int):
    if ImageFont is None:
        return None
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    return None


def _bgr_to_rgb(color_bgr: tuple[int, int, int]) -> tuple[int, int, int]:
    b, g, r = color_bgr
    return (r, g, b)
