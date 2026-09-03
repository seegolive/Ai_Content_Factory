"""QC orchestration — delegates to VideoProcessorService, with moment-type duration awareness."""

from typing import Optional

from loguru import logger

from app.services.ai_brain import FALLBACK_DURATION_RULE, MOMENT_DURATION_RULES
from app.services.video_processor import QCIssue, QCResult, VideoProcessorService

_processor = VideoProcessorService()

_VALID_MOMENT_TYPES = frozenset(MOMENT_DURATION_RULES.keys())


async def run_qc(
    clip_path: str,
    moment_type: Optional[str] = None,
    clip_duration: Optional[float] = None,
) -> QCResult:
    """Run QC on a clip with moment-type-aware duration validation.

    ffprobe-measured duration is authoritative; clip_duration from caller is
    only used when ffprobe data is unavailable (e.g. pre-cut validation).
    """
    result = await _processor.run_qc_check(clip_path)

    if not moment_type:
        return result

    # Validate moment_type; log if unknown so AI typos are visible in logs
    if moment_type not in _VALID_MOMENT_TYPES:
        logger.warning(
            f"[QC] Unknown moment_type '{moment_type}' — using fallback duration rule"
        )
        result.issues.append(
            QCIssue(
                type="invalid_moment_type",
                description=f"Unknown moment_type '{moment_type}'; fallback duration rule applied.",
                severity="warning",
            )
        )
    rule = MOMENT_DURATION_RULES.get(moment_type, FALLBACK_DURATION_RULE)

    # ffprobe duration is authoritative; caller-supplied is fallback only
    ffprobe_dur: Optional[float] = result.metrics.get("duration_seconds")
    if ffprobe_dur is not None:
        if clip_duration is not None and abs(ffprobe_dur - clip_duration) > 1.0:
            logger.warning(
                f"[QC] Duration mismatch — caller said {clip_duration:.1f}s, "
                f"ffprobe measured {ffprobe_dur:.1f}s; using ffprobe value"
            )
        duration = ffprobe_dur
    else:
        duration = clip_duration

    if duration is None:
        return result

    if duration < rule["min"]:
        deficit = rule["min"] - duration
        result.issues.append(
            QCIssue(
                type="duration_too_short",
                description=(
                    f"{moment_type} clip is {duration:.1f}s — "
                    f"minimum is {rule['min']}s "
                    f"(ideal {rule['ideal_min']}–{rule['ideal_max']}s, deficit {deficit:.1f}s)"
                ),
                severity="error",
                recommendation=f"expand_before:{rule['buildup']:.0f}s,expand_after:{rule['resolution']:.0f}s",
            )
        )
        result.passed = False

    elif duration > rule["max"]:
        excess = duration - rule["max"]
        result.issues.append(
            QCIssue(
                type="duration_too_long",
                description=(
                    f"{moment_type} clip is {duration:.1f}s — "
                    f"maximum is {rule['max']}s "
                    f"(ideal {rule['ideal_min']}–{rule['ideal_max']}s, excess {excess:.1f}s)"
                ),
                severity="error",
                recommendation=f"trim_after:{excess:.0f}s",
            )
        )
        result.passed = False

    elif duration < rule["ideal_min"] or duration > rule["ideal_max"]:
        result.issues.append(
            QCIssue(
                type="duration_suboptimal",
                description=(
                    f"{moment_type} clip is {duration:.1f}s — "
                    f"ideal range is {rule['ideal_min']}–{rule['ideal_max']}s"
                ),
                severity="warning",
                recommendation="editorial_review",
            )
        )

    return result
