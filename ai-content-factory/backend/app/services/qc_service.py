"""QC orchestration — delegates to VideoProcessorService, with moment-type duration awareness."""

from typing import Optional

from app.services.ai_brain import FALLBACK_DURATION_RULE, MOMENT_DURATION_RULES
from app.services.video_processor import QCIssue, QCResult, VideoProcessorService

_processor = VideoProcessorService()


async def run_qc(
    clip_path: str,
    moment_type: Optional[str] = None,
    clip_duration: Optional[float] = None,
) -> QCResult:
    """
    Run QC on a clip, with optional moment-type-aware duration validation.

    Args:
        clip_path: Path to the clip file.
        moment_type: Moment type for duration rule lookup (e.g. 'clutch', 'funny').
        clip_duration: Clip duration in seconds (start_time - end_time). Calculated
                       from ffprobe if not provided.
    """
    result = await _processor.run_qc_check(clip_path)

    # Append duration-awareness check if moment_type provided
    if moment_type:
        rule = MOMENT_DURATION_RULES.get(moment_type, FALLBACK_DURATION_RULE)
        duration = clip_duration
        if duration is None:
            # Try to infer from ffprobe via metrics (run_qc_check always probes duration)
            duration = result.metrics.get("duration_seconds")

        if duration is not None:
            if duration < rule["min"]:
                result.issues.append(
                    QCIssue(
                        type="duration_too_short",
                        description=(
                            f"{moment_type} clip is {duration:.1f}s — "
                            f"minimum is {rule['min']}s (ideal {rule['ideal_min']}–{rule['ideal_max']}s)"
                        ),
                        severity="error",
                    )
                )
                result.passed = False
            elif duration > rule["max"]:
                result.issues.append(
                    QCIssue(
                        type="duration_too_long",
                        description=(
                            f"{moment_type} clip is {duration:.1f}s — "
                            f"maximum is {rule['max']}s (ideal {rule['ideal_min']}–{rule['ideal_max']}s)"
                        ),
                        severity="warning",
                    )
                )
            elif duration < rule["ideal_min"] or duration > rule["ideal_max"]:
                result.issues.append(
                    QCIssue(
                        type="duration_suboptimal",
                        description=(
                            f"{moment_type} clip is {duration:.1f}s — "
                            f"ideal range is {rule['ideal_min']}–{rule['ideal_max']}s"
                        ),
                        severity="warning",
                    )
                )

    return result
