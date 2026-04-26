"""
Main pipeline orchestrator with checkpoint-based resumability.

STAGES (in order):
  input_validated → transcript_done → ai_done → qc_done → clips_done → review_ready

If a stage fails, the pipeline saves the error and notifies the user.
On retry, completed stages are skipped — idempotent execution.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from celery import states
from celery.exceptions import MaxRetriesExceededError
from loguru import logger

from app.workers.celery_app import celery_app

CHECKPOINT_ORDER = [
    "input_validated",
    "transcript_done",
    "ai_done",
    "qc_done",
    "clips_done",
    "review_ready",
]


def _checkpoint_index(checkpoint: Optional[str]) -> int:
    if checkpoint is None:
        return -1
    try:
        return CHECKPOINT_ORDER.index(checkpoint)
    except ValueError:
        return -1


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3, name="app.workers.tasks.pipeline.process_video_pipeline")
def process_video_pipeline(self, video_id: str):
    """
    Process a video through all pipeline stages.
    Resumes from last successful checkpoint on retry.
    """
    logger.info(f"[Pipeline] Starting for video_id={video_id}")

    async def _run():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.user import User
        from app.models.video import Video

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Video).where(Video.id == uuid.UUID(video_id)))
            video = result.scalar_one_or_none()
            if not video:
                logger.error(f"[Pipeline] Video {video_id} not found")
                return

            # Load user for notifications
            user_result = await db.execute(select(User).where(User.id == video.user_id))
            user = user_result.scalar_one_or_none()

            current_idx = _checkpoint_index(video.checkpoint)
            logger.info(f"[Pipeline] Resuming from checkpoint: {video.checkpoint!r} (idx={current_idx})")

            # Skip if already fully completed
            if video.checkpoint == "review_ready":
                logger.info(f"[Pipeline] Video {video_id} already completed, skipping.")
                return

            try:
                video.status = "processing"
                await db.commit()

                # ── STAGE 1: Input Validation ────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("input_validated"):
                    logger.info("[Pipeline] Stage 1: Input validation")
                    await _stage_input_validation(video, db)

                # ── STAGE 2: Transcription ───────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("transcript_done"):
                    logger.info("[Pipeline] Stage 2: Transcription")
                    await _stage_transcription(video, db)

                # ── STAGE 3: AI Analysis ─────────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("ai_done"):
                    logger.info("[Pipeline] Stage 3: AI Analysis")
                    await _stage_ai_analysis(video, db)

                # ── STAGE 4: QC Filtering ────────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("qc_done"):
                    logger.info("[Pipeline] Stage 4: QC Filtering")
                    await _stage_qc_filtering(video, db)

                # ── STAGE 5: Video Processing ────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("clips_done"):
                    logger.info("[Pipeline] Stage 5: Video processing")
                    await _stage_video_processing(video, db)

                # ── STAGE 6: Review Ready ────────────────────────────────────
                if current_idx < CHECKPOINT_ORDER.index("review_ready"):
                    logger.info("[Pipeline] Stage 6: Mark review ready")
                    video.status = "review"
                    video.checkpoint = "review_ready"
                    await db.commit()

                    # Count clips
                    from sqlalchemy import func
                    from app.models.clip import Clip
                    count_result = await db.execute(
                        select(func.count(Clip.id)).where(Clip.video_id == video.id)
                    )
                    clips_count = count_result.scalar_one()

                    if user:
                        from app.services.notification import NotificationService
                        notifier = NotificationService()
                        await notifier.notify_job_complete(
                            video_title=video.title or str(video.id),
                            clips_count=clips_count,
                            user_email=user.email,
                        )

                logger.info(f"[Pipeline] Completed for video_id={video_id}")

            except Exception as e:
                logger.exception(f"[Pipeline] Error in pipeline for {video_id}: {e}")
                video.status = "error"
                video.error_message = str(e)[:1000]
                await db.commit()

                if user:
                    from app.services.notification import NotificationService
                    notifier = NotificationService()
                    await notifier.notify_job_error(
                        video_title=video.title or str(video.id),
                        error=str(e),
                        user_email=user.email,
                    )
                raise

    try:
        _run_async(_run())
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error(f"[Pipeline] Max retries exceeded for video {video_id}")


# ── Stage implementations ────────────────────────────────────────────────────

async def _stage_input_validation(video, db):
    from app.services.copyright_check import CopyrightCheckService

    # Validate file exists (for uploads) or URL is accessible
    if video.file_path and not os.path.exists(video.file_path):
        raise FileNotFoundError(f"Video file missing: {video.file_path}")

    # Copyright pre-check
    if video.file_path:
        checker = CopyrightCheckService()
        result = await checker.check_audio(video.file_path)
        video.copyright_status = result.status
        if result.is_flagged:
            logger.warning(f"[Pipeline] Copyright flag on {video.id}: {result.matched_music}")

    video.checkpoint = "input_validated"
    await db.commit()


async def _stage_transcription(video, db):
    from app.services.transcription import WhisperTranscriptionService

    if not video.file_path or not os.path.exists(video.file_path):
        raise FileNotFoundError(f"Cannot transcribe: file missing {video.file_path}")

    service = WhisperTranscriptionService()
    result = await service.transcribe(video.file_path)

    video.transcript = result.full_text
    video.transcript_segments = [
        {
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "confidence": seg.confidence,
        }
        for seg in result.segments
    ]
    if not video.duration_seconds:
        video.duration_seconds = result.duration

    video.checkpoint = "transcript_done"
    await db.commit()


async def _stage_ai_analysis(video, db):
    from app.services.ai_brain import AIBrainService
    from app.services.transcription import TranscriptResult, TranscriptSegment

    if not video.transcript:
        raise ValueError("Cannot run AI analysis: transcript missing")

    # Reconstruct TranscriptResult from stored data
    segments = [
        TranscriptSegment(
            id=seg["id"],
            start=seg["start"],
            end=seg["end"],
            text=seg["text"],
            confidence=seg.get("confidence", 0.0),
        )
        for seg in (video.transcript_segments or [])
    ]
    transcript = TranscriptResult(
        full_text=video.transcript,
        segments=segments,
        language="auto",
        duration=video.duration_seconds or 0,
        word_count=len(video.transcript.split()),
    )

    brain = AIBrainService()
    analysis = await brain.analyze_transcript(transcript)

    # Store clip suggestions in DB
    from app.models.clip import Clip

    for suggestion in analysis.clips:
        clip = Clip(
            video_id=video.id,
            user_id=video.user_id,
            title=suggestion.titles[0] if suggestion.titles else None,
            description=suggestion.description,
            start_time=suggestion.start_time,
            end_time=suggestion.end_time,
            duration=suggestion.end_time - suggestion.start_time,
            viral_score=suggestion.viral_score,
            hook_text=suggestion.hook_text,
            hashtags=suggestion.hashtags,
            qc_status="pending",
            review_status="pending",
        )
        db.add(clip)

    video.checkpoint = "ai_done"
    await db.commit()
    await brain.close()


async def _stage_qc_filtering(video, db):
    """QC is run per-clip after video processing; mark checkpoint here."""
    video.checkpoint = "qc_done"
    await db.commit()


async def _stage_video_processing(video, db):
    from sqlalchemy import select
    from app.models.clip import Clip
    from app.services.video_processor import VideoProcessorService

    result = await db.execute(select(Clip).where(Clip.video_id == video.id))
    clips = result.scalars().all()

    processor = VideoProcessorService()
    clips_dir = os.path.join("storage", "clips", str(video.id))
    os.makedirs(clips_dir, exist_ok=True)

    for clip in clips:
        try:
            clip_filename = f"{clip.id}.mp4"
            clip_path = os.path.join(clips_dir, clip_filename)

            await processor.cut_clip(
                input_path=video.file_path,
                output_path=clip_path,
                start_time=clip.start_time,
                end_time=clip.end_time,
            )

            # QC check
            qc_result = await processor.run_qc_check(clip_path)
            clip.clip_path = clip_path
            clip.qc_status = "passed" if qc_result.passed else "failed"
            clip.qc_issues = [
                {"type": i.type, "description": i.description, "severity": i.severity}
                for i in qc_result.issues
            ]

        except Exception as e:
            logger.error(f"[Pipeline] Failed to process clip {clip.id}: {e}")
            clip.qc_status = "failed"
            clip.qc_issues = [{"type": "processing_error", "description": str(e), "severity": "error"}]

    video.checkpoint = "clips_done"
    await db.commit()
