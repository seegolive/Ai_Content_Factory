"""
Facecam auto-detector — samples frames from video to find facecam region.

Uses FFmpeg to extract frames (handles AV1/HEVC/any codec) then OpenCV to analyze.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
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


def _get_video_duration(video_path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _extract_frame_ffmpeg(video_path: str, timestamp: float, out_path: str) -> bool:
    """Extract single frame at timestamp using FFmpeg software decode.
    Uses zscale to convert TV→PC range so limited-range AV1 looks correct.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-vframes",
                "1",
                "-vf",
                "scale=1280:-2,zscale=rangein=tv:range=pc",
                "-f",
                "image2",
                out_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            # fallback: without zscale (might not be available)
            result2 = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(timestamp),
                    "-i",
                    video_path,
                    "-vframes",
                    "1",
                    "-vf",
                    "scale=1280:-2",
                    "-f",
                    "image2",
                    out_path,
                ],
                capture_output=True,
                timeout=30,
            )
            return result2.returncode == 0 and os.path.exists(out_path)
        return os.path.exists(out_path)
    except Exception as exc:
        logger.warning(f"[FacecamDetector] FFmpeg frame extract failed: {exc}")
        return False


class FacecamDetector:
    def _find_bright_frames(
        self,
        video_path: str,
        start: float,
        duration: float,
        cv2,
        np,
        target: int = 5,
        min_brightness: float = 15.0,
    ) -> list:
        """
        Scan for timestamps where the frame has real content (not black/loading).
        Tries up to 20 candidate timestamps and returns up to `target` bright frames.
        """
        remaining = duration - start
        # Spread candidates across the video (skip first 5% and last 5% of remaining)
        candidates = [
            start + remaining * r
            for r in [
                0.05,
                0.12,
                0.20,
                0.28,
                0.35,
                0.42,
                0.50,
                0.58,
                0.65,
                0.72,
                0.78,
                0.83,
                0.88,
                0.92,
                0.95,
                0.15,
                0.25,
                0.45,
                0.55,
                0.70,
            ]
        ]

        good_frames = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, ts in enumerate(candidates):
                if len(good_frames) >= target:
                    break
                out_path = os.path.join(tmpdir, f"scan_{i}.jpg")
                if _extract_frame_ffmpeg(video_path, ts, out_path):
                    frame = cv2.imread(out_path)
                    if frame is not None:
                        brightness = float(np.mean(frame))
                        logger.debug(
                            f"[FacecamDetector] scan ts={ts:.0f}s brightness={brightness:.1f}"
                        )
                        if brightness >= min_brightness:
                            good_frames.append((ts, frame.copy()))

        logger.info(
            f"[FacecamDetector] Found {len(good_frames)} bright frames out of {len(candidates)} scanned"
        )
        return good_frames

    def detect_facecam_region(
        self, video_path: str, start_offset: float = 0.0
    ) -> Optional[FacecamRegion]:
        """
        Detect facecam corner region in a video.

        Strategy:
        1. Scan for timestamps with bright/visible content (not loading screens)
        2. Find the content bounding box (crop out black bars from OBS canvas)
        3. Within the content area, compare corners: lowest motion = facecam overlay

        Uses FFmpeg for frame extraction (AV1/HEVC/H264 compatible).
        start_offset: seconds to skip from the start (e.g. for intro).
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

        duration = _get_video_duration(video_path)
        if duration < 5:
            logger.warning(f"[FacecamDetector] Video too short: {duration}s")
            return None

        start = min(max(start_offset, 0.0), duration * 0.9)

        # Step 1: find frames that actually have content
        bright_frame_data = self._find_bright_frames(
            video_path, start, duration, cv2, np
        )
        if len(bright_frame_data) < 2:
            logger.info(
                "[FacecamDetector] Could not find enough bright frames — video may be too dark or have no facecam"
            )
            return None

        sample_frames = [f for _, f in bright_frame_data]
        logger.info(
            f"[FacecamDetector] Using {len(sample_frames)} bright frames for analysis"
        )

        height, width = sample_frames[0].shape[:2]

        # Step 2: find content bounding box (ignore black bars from OBS canvas)
        # Build a mask of non-black pixels across all sample frames
        combined_mask = np.zeros((height, width), dtype=np.uint8)
        for frame in sample_frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 8, 255, cv2.THRESH_BINARY)
            combined_mask = cv2.bitwise_or(combined_mask, mask)

        # Find bounding rect of content area
        content_cols = np.any(combined_mask > 0, axis=0)
        content_rows = np.any(combined_mask > 0, axis=1)
        if not np.any(content_cols) or not np.any(content_rows):
            logger.info("[FacecamDetector] No content area found")
            return None

        x_min = int(np.argmax(content_cols))
        x_max = int(len(content_cols) - np.argmax(content_cols[::-1]) - 1)
        y_min = int(np.argmax(content_rows))
        y_max = int(len(content_rows) - np.argmax(content_rows[::-1]) - 1)
        content_w = x_max - x_min
        content_h = y_max - y_min
        logger.info(
            f"[FacecamDetector] Content area: ({x_min},{y_min}) {content_w}x{content_h} (canvas: {width}x{height})"
        )

        if content_w < 100 or content_h < 100:
            logger.info("[FacecamDetector] Content area too small")
            return None

        # Step 3: analyze corners WITHIN the content area
        qw = content_w // 4
        qh = content_h // 4

        def crop_corner(frame, pos):
            if pos == "top_left":
                return frame[y_min : y_min + qh, x_min : x_min + qw]
            elif pos == "top_right":
                return frame[y_min : y_min + qh, x_max - qw : x_max]
            elif pos == "bottom_left":
                return frame[y_max - qh : y_max, x_min : x_min + qw]
            else:  # bottom_right
                return frame[y_max - qh : y_max, x_max - qw : x_max]

        corner_scores: dict[str, float] = {}
        for position in ["top_left", "top_right", "bottom_left", "bottom_right"]:
            crops = [crop_corner(f, position) for f in sample_frames]
            mean_brightness = float(np.mean(crops[0]))
            if mean_brightness < 5:
                logger.info(
                    f"[FacecamDetector] {position}: skipped (dark, brightness={mean_brightness:.1f})"
                )
                continue
            diffs = [
                np.mean(cv2.absdiff(crops[i], crops[i + 1]))
                for i in range(len(crops) - 1)
            ]
            mean_diff = float(np.mean(diffs)) if diffs else 999.0
            score = 1.0 / (mean_diff + 1.0) * 100.0
            corner_scores[position] = score
            logger.info(
                f"[FacecamDetector] {position}: brightness={mean_brightness:.1f} mean_diff={mean_diff:.2f} score={score:.2f}"
            )

        if not corner_scores:
            logger.info("[FacecamDetector] No scoreable corners found")
            return None

        best_corner = max(corner_scores, key=lambda k: corner_scores[k])
        best_score = corner_scores[best_corner]
        other_scores = [v for k, v in corner_scores.items() if k != best_corner]
        avg_other = float(np.mean(other_scores)) if other_scores else 0.0

        logger.info(
            f"[FacecamDetector] Best: {best_corner} score={best_score:.2f}, avg_other={avg_other:.2f}"
        )

        # Accept if best corner is at least 1.4x more stable than others
        if len(other_scores) == 0 or best_score < avg_other * 1.4 or best_score < 2.0:
            logger.info(
                f"[FacecamDetector] No clear facecam (best={best_score:.2f}, avg_other={avg_other:.2f})"
            )
            return None

        # Map corner to absolute pixel coordinates
        abs_coords = {
            "top_left": (x_min, y_min, qw, qh),
            "top_right": (x_max - qw, y_min, qw, qh),
            "bottom_left": (x_min, y_max - qh, qw, qh),
            "bottom_right": (x_max - qw, y_max - qh, qw, qh),
        }
        x, y, w, h = abs_coords[best_corner]
        region = FacecamRegion(x=x, y=y, width=w, height=h, position=best_corner)
        logger.info(
            f"[FacecamDetector] Detected {best_corner} (score={best_score:.1f}): {region}"
        )
        return region

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
