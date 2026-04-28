"""Layer 2 — Pipeline Duration Validator.

Receives raw moments from AI Brain (any duration) and adjusts them
to YouTube Shorts format (60–180 seconds).

Four operations:
- EXTEND  — clip 15–59s: add build-up and resolution context
- PASS    — clip 60–180s: pass through unchanged
- SPLIT   — clip >180s: split into 2+ valid clips
- REJECT  — clip <15s (unsalvageable): log and discard
"""

import copy
from typing import List, Optional, Tuple

from loguru import logger

from app.services.ai_brain import (
    FALLBACK_DURATION_RULE,
    MOMENT_DURATION_RULES,
    SHORTS_MAX_DURATION,
    SHORTS_MIN_DURATION,
    ClipSuggestion,
)

# Clips below this threshold cannot be meaningfully extended
UNSALVAGEABLE_THRESHOLD = 15  # seconds


def validate_and_adjust_clips(
    clips: List[ClipSuggestion],
    video_duration: float,
    transcript_segments: Optional[list] = None,
) -> Tuple[List[ClipSuggestion], List[dict]]:
    """Layer 2: Adjust all clips to YouTube Shorts format (60–180s).

    Returns:
        (adjusted_clips, action_log) where action_log records every decision
        for debugging and analytics.
    """
    adjusted: List[ClipSuggestion] = []
    log: List[dict] = []

    for clip in clips:
        duration = clip.end_time - clip.start_time
        rule = MOMENT_DURATION_RULES.get(clip.moment_type, FALLBACK_DURATION_RULE)
        title = clip.titles[0] if clip.titles else "?"

        # ── CASE 1: UNSALVAGEABLE (< 15s) ────────────────────────────────────
        if duration < UNSALVAGEABLE_THRESHOLD:
            log.append({
                "action": "REJECTED",
                "reason": f"Too short ({duration:.0f}s) — unsalvageable",
                "clip_title": title,
                "moment_type": clip.moment_type,
                "original_duration": round(duration, 1),
                "viral_score": clip.viral_score,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
            })
            logger.debug(
                f"[Validator] REJECTED {clip.moment_type} {clip.start_time:.0f}s "
                f"({duration:.0f}s < {UNSALVAGEABLE_THRESHOLD}s)"
            )
            continue

        # ── CASE 2: TOO SHORT (15–59s) → EXTEND ──────────────────────────────
        if duration < SHORTS_MIN_DURATION:
            extended = _try_extend_clip(
                clip=clip,
                target_duration=rule["ideal_min"],
                video_duration=video_duration,
                buildup=rule.get("buildup", 12),
                resolution=rule.get("resolution", 12),
                transcript_segments=transcript_segments,
            )
            if extended is not None:
                new_dur = extended.end_time - extended.start_time
                log.append({
                    "action": "EXTENDED",
                    "reason": f"{duration:.0f}s -> {new_dur:.0f}s",
                    "clip_title": title,
                    "moment_type": clip.moment_type,
                    "original_duration": round(duration, 1),
                    "new_duration": round(new_dur, 1),
                    "start_time": extended.start_time,
                    "end_time": extended.end_time,
                })
                logger.info(
                    f"[Validator] EXTENDED {clip.moment_type} "
                    f"{clip.start_time:.0f}s ({duration:.0f}s -> {new_dur:.0f}s)"
                )
                adjusted.append(extended)
            else:
                log.append({
                    "action": "REJECTED",
                    "reason": f"Cannot extend to {SHORTS_MIN_DURATION}s (original {duration:.0f}s)",
                    "clip_title": title,
                    "moment_type": clip.moment_type,
                    "original_duration": round(duration, 1),
                    "viral_score": clip.viral_score,
                    "start_time": clip.start_time,
                    "end_time": clip.end_time,
                })
                logger.debug(
                    f"[Validator] REJECTED {clip.moment_type} {clip.start_time:.0f}s "
                    f"({duration:.0f}s — extend failed)"
                )
            continue

        # ── CASE 3: PERFECT RANGE (60–180s) → PASS ───────────────────────────
        if SHORTS_MIN_DURATION <= duration <= SHORTS_MAX_DURATION:
            log.append({
                "action": "PASSED",
                "clip_title": title,
                "moment_type": clip.moment_type,
                "duration": round(duration, 1),
                "start_time": clip.start_time,
                "end_time": clip.end_time,
            })
            logger.debug(
                f"[Validator] PASSED {clip.moment_type} {clip.start_time:.0f}s ({duration:.0f}s)"
            )
            adjusted.append(clip)
            continue

        # ── CASE 4: TOO LONG (> 180s) → SPLIT ────────────────────────────────
        if duration > SHORTS_MAX_DURATION:
            splits = _try_split_clip(
                clip=clip,
                max_duration=SHORTS_MAX_DURATION,
                min_duration=SHORTS_MIN_DURATION,
                transcript_segments=transcript_segments,
            )
            for i, split_clip in enumerate(splits):
                split_dur = split_clip.end_time - split_clip.start_time
                log.append({
                    "action": f"SPLIT_{i + 1}_OF_{len(splits)}",
                    "reason": f"Original {duration:.0f}s -> part {i + 1} = {split_dur:.0f}s",
                    "clip_title": split_clip.titles[0] if split_clip.titles else "?",
                    "moment_type": split_clip.moment_type,
                    "original_duration": round(duration, 1),
                    "new_duration": round(split_dur, 1),
                    "start_time": split_clip.start_time,
                    "end_time": split_clip.end_time,
                })
                adjusted.append(split_clip)
            logger.info(
                f"[Validator] SPLIT {clip.moment_type} {clip.start_time:.0f}s "
                f"({duration:.0f}s -> {len(splits)} parts)"
            )

    # Summary log
    actions = [entry["action"] for entry in log]
    passed = actions.count("PASSED")
    extended = actions.count("EXTENDED")
    split = sum(1 for a in actions if a.startswith("SPLIT"))
    rejected = actions.count("REJECTED")
    logger.info(
        f"[Validator] {len(adjusted)} clips output | "
        f"PASSED={passed} EXTENDED={extended} SPLIT={split} REJECTED={rejected}"
    )

    return adjusted, log


def _try_extend_clip(
    clip: ClipSuggestion,
    target_duration: float,
    video_duration: float,
    buildup: float,
    resolution: float,
    transcript_segments: Optional[list] = None,
) -> Optional[ClipSuggestion]:
    """Extend a short clip by adding build-up and resolution context.

    Strategy:
    1. Add build-up at start (60% of needed)
    2. Add resolution at end (40% of needed)
    3. If still short, redistribute across both sides up to video bounds
    4. Snap to natural sentence boundary if transcript available
    5. Accept if >= 85% of target AND >= SHORTS_MIN_DURATION
    """
    current = clip.end_time - clip.start_time
    needed = max(0.0, target_duration - current)

    if needed <= 0:
        return clip  # already long enough

    extended = copy.deepcopy(clip)

    # Distribute: 60% build-up (tension before) + 40% resolution (reaction after)
    add_start = min(buildup, needed * 0.6)
    add_end = min(resolution, needed * 0.4)

    # If caps prevent reaching target, redistribute remainder evenly
    total_add = add_start + add_end
    if total_add < needed:
        remaining = needed - total_add
        add_start += remaining * 0.5
        add_end += remaining * 0.5

    new_start = max(0.0, extended.start_time - add_start)
    new_end = min(video_duration, extended.end_time + add_end)

    # If one side hit boundary, give leftover to the other
    actual_add_start = extended.start_time - new_start
    actual_add_end = new_end - extended.end_time
    if actual_add_start < add_start:
        shortfall = add_start - actual_add_start
        new_end = min(video_duration, new_end + shortfall)
    if actual_add_end < add_end:
        shortfall = add_end - actual_add_end
        new_start = max(0.0, new_start - shortfall)

    # Snap to sentence boundary if transcript available
    if transcript_segments:
        new_start = _snap_to_sentence_boundary(
            new_start, transcript_segments, direction="before"
        )
        new_end = _snap_to_sentence_boundary(
            new_end, transcript_segments, direction="after"
        )

    extended.start_time = new_start
    extended.end_time = new_end
    new_duration = new_end - new_start

    # Accept if >= 85% of target AND >= absolute minimum
    if new_duration >= target_duration * 0.85 and new_duration >= SHORTS_MIN_DURATION:
        return extended

    return None


def _try_split_clip(
    clip: ClipSuggestion,
    max_duration: float,
    min_duration: float,
    transcript_segments: Optional[list] = None,
) -> List[ClipSuggestion]:
    """Split a long clip (>180s) into 2+ valid Shorts clips.

    Each part gets a " (Part N)" suffix on titles.
    Viral score decreases slightly for subsequent parts.
    """
    duration = clip.end_time - clip.start_time

    if duration <= max_duration:
        return [clip]

    # How many parts do we need?
    num_parts = max(2, int(duration // max_duration) + (
        1 if duration % max_duration >= min_duration else 0
    ))
    part_duration = duration / num_parts

    # Ensure each part is at least min_duration
    if part_duration < min_duration:
        num_parts = max(2, int(duration // min_duration))
        part_duration = duration / num_parts

    splits = []
    for i in range(num_parts):
        part_start = clip.start_time + (i * part_duration)
        part_end = clip.start_time + ((i + 1) * part_duration)
        part_end = min(part_end, clip.end_time)
        part_dur = part_end - part_start

        # Remaining segment too short → merge into last part
        if part_dur < min_duration and splits:
            splits[-1].end_time = clip.end_time
            continue

        # Snap end to sentence boundary
        if transcript_segments:
            part_end = _snap_to_sentence_boundary(
                part_end, transcript_segments, direction="after"
            )
            part_end = min(part_end, clip.end_time)

        split_clip = copy.deepcopy(clip)
        split_clip.start_time = part_start
        split_clip.end_time = part_end
        split_clip.titles = [f"{t} (Part {i + 1})" for t in clip.titles]
        # Slightly lower score for subsequent parts
        if i > 0:
            split_clip.viral_score = max(40, clip.viral_score - (i * 5))

        splits.append(split_clip)

    return splits if splits else [clip]


def _snap_to_sentence_boundary(
    timestamp: float,
    segments: list,
    direction: str = "after",
    search_window: float = 5.0,
) -> float:
    """Find the nearest sentence end/start within search_window of timestamp.

    direction="before" → find segment.start closest BEFORE timestamp
    direction="after"  → find segment.end closest AFTER timestamp

    Prevents clips from starting/ending mid-sentence.
    """
    best = timestamp

    for seg in segments:
        if direction == "after":
            if seg.end >= timestamp and seg.end <= timestamp + search_window:
                if abs(seg.end - timestamp) < abs(best - timestamp):
                    best = seg.end
        elif direction == "before":
            if seg.start <= timestamp and seg.start >= timestamp - search_window:
                if abs(seg.start - timestamp) < abs(best - timestamp):
                    best = seg.start

    return best
