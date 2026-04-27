"""
Facecam auto-detector — samples frames from video to find facecam region.

Requires: opencv-python-headless (add to requirements.txt before docker rebuild).
Falls back gracefully if cv2 is not installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class FacecamRegion:
    x: int
    y: int
    width: int
    height: int
    position: str  # top_left | top_right | bottom_left | bottom_right


class FacecamDetector:

    def detect_facecam_region(self, video_path: str) -> Optional[FacecamRegion]:
        """
        Sample 5 frames from video → detect facecam corner region.

        Strategy: A facecam overlay is typically a small, spatially stable
        region in one corner. We compare adjacent sampled frames — the corner
        with the *lowest* absolute-difference variance is likely the facecam
        (stable/person vs high-motion gameplay).

        Returns FacecamRegion or None if not detected / cv2 unavailable.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning(
                "[FacecamDetector] opencv-python-headless not installed — "
                "skipping auto-detect. Add it to requirements.txt and rebuild."
            )
            return None

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.warning(f"[FacecamDetector] Cannot open video: {video_path}")
                return None

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if total_frames < 10 or width == 0 or height == 0:
                cap.release()
                return None

            # Sample 5 frames spread across the video
            sample_frames = []
            for ratio in [0.10, 0.25, 0.40, 0.60, 0.75]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * ratio))
                ret, frame = cap.read()
                if ret:
                    sample_frames.append(frame)
            cap.release()

            if len(sample_frames) < 2:
                return None

            # Quarter-corner regions
            qw, qh = width // 4, height // 4
            corners: dict[str, list] = {
                "top_left":     [f[0:qh, 0:qw] for f in sample_frames],
                "top_right":    [f[0:qh, width - qw:] for f in sample_frames],
                "bottom_left":  [f[height - qh:, 0:qw] for f in sample_frames],
                "bottom_right": [f[height - qh:, width - qw:] for f in sample_frames],
            }

            # Score each corner: low frame-diff variance → stable content → facecam
            best_corner: Optional[str] = None
            best_score = 0.0

            for position, frames in corners.items():
                diffs = [
                    np.mean(cv2.absdiff(frames[i], frames[i + 1]))
                    for i in range(len(frames) - 1)
                ]
                mean_diff = float(np.mean(diffs)) if diffs else 0.0
                # Avoid pure-black corners (mean brightness < 10)
                mean_brightness = float(np.mean(frames[0]))
                if mean_brightness < 10:
                    continue
                score = 1.0 / (mean_diff + 1.0) * 100.0
                if score > best_score:
                    best_score = score
                    best_corner = position

            if not best_corner or best_score < 10.0:
                logger.info("[FacecamDetector] No facecam corner detected")
                return None

            region_coords = {
                "top_left":     (0,          0,           qw, qh),
                "top_right":    (width - qw, 0,           qw, qh),
                "bottom_left":  (0,          height - qh, qw, qh),
                "bottom_right": (width - qw, height - qh, qw, qh),
            }
            x, y, w, h = region_coords[best_corner]
            region = FacecamRegion(x=x, y=y, width=w, height=h, position=best_corner)
            logger.info(f"[FacecamDetector] Detected {best_corner} (score={best_score:.1f}): {region}")
            return region

        except Exception as exc:
            logger.warning(f"[FacecamDetector] Detection error: {exc}")
            return None

    def suggest_crop_config(self, region: FacecamRegion) -> dict:
        """Translate detected region into a crop config suggestion."""
        anchor = "left" if "left" in region.position else "right"
        return {
            "vertical_crop_mode": "smart_offset",
            "facecam_position": region.position,
            "crop_x_offset": region.x,
            "crop_anchor": anchor,
            "facecam_x": region.x,
            "facecam_y": region.y,
            "facecam_width": region.width,
            "facecam_height": region.height,
        }
