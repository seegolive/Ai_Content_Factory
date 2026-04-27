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
        from sqlalchemy.pool import NullPool
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.models.user import User
        from app.models.video import Video, YoutubeAccount

        # Use NullPool to avoid event-loop conflicts in Celery forked workers
        _engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        _SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

        async with _SessionLocal() as db:
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

            # Clear stale error from previous failed attempts
            if video.error_message:
                video.error_message = None
                await db.commit()

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
                            provider_used=video.ai_provider_used or "",
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
            finally:
                await _engine.dispose()

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

    # ── Download YouTube URL if no local file ────────────────────────────────
    if not video.file_path and video.original_url:
        logger.info(f"[Pipeline] Downloading YouTube video: {video.original_url}")
        await _download_youtube_video(video, db)

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


async def _download_youtube_video(video, db):
    """Download a YouTube video using yt-dlp and update video.file_path + title."""
    import yt_dlp

    storage_dir = os.path.join("storage", "videos")
    os.makedirs(storage_dir, exist_ok=True)
    output_path = os.path.join(storage_dir, f"{video.id}.%(ext)s")

    # Use cookies file if available (needed to bypass YouTube bot detection in Docker)
    cookies_path = os.path.join("storage", "youtube_cookies.txt")

    # Map quality_preference to yt-dlp format string
    quality = getattr(video, "quality_preference", "1440p") or "1440p"
    quality_format_map = {
        "1080p":  "bestvideo[height>=1080]+bestaudio/bestvideo+bestaudio/best",
        "1440p":  "bestvideo[height>=1440]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo+bestaudio/best",
        "2160p":  "bestvideo[height>=2160]+bestaudio/bestvideo[height>=1440]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo+bestaudio/best",
        "best":   "bestvideo+bestaudio/best",
    }
    fmt = quality_format_map.get(quality, quality_format_map["1440p"])

    # Progress hook — writes download_progress (0-100) directly to DB via sync psycopg
    video_id_str = str(video.id)

    def _progress_hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and total > 0:
                pct = int(downloaded * 100 / total)
                # Use a sync raw SQL UPDATE to avoid async event loop issues in executor thread
                try:
                    import psycopg2
                    from app.core.config import settings
                    sync_url = settings.DATABASE_URL_SYNC
                    conn = psycopg2.connect(sync_url)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE videos SET download_progress = %s WHERE id = %s",
                        (pct, video_id_str)
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception:
                    pass  # Non-critical — progress display only

    # Use android_vr player client: provides 1080p/1440p/4K without JS challenge solving.
    # The web/ios clients require EJS challenge solver or PO Token (often unavailable in Docker).
    # android_vr bypasses both requirements and reliably returns high-quality formats.
    ydl_opts = {
        "format": fmt,
        "outtmpl": output_path,
        "quiet": False,
        "no_warnings": False,
        "merge_output_format": "mp4",
        "noprogress": False,
        "nopart": True,
        "overwrites": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr", "android", "web"]}},
        "progress_hooks": [_progress_hook],
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path
        logger.info(f"[Pipeline] Using cookies from {cookies_path}")
    else:
        logger.warning(
            "[Pipeline] No cookies file found at storage/youtube_cookies.txt — "
            "YouTube may block download. Export cookies from browser and save there."
        )

    loop = asyncio.get_event_loop()

    def _do_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video.original_url, download=True)
            return info

    info = await loop.run_in_executor(None, _do_download)

    # Warn if resolution below 1080p (Deno not working or source quality low)
    downloaded_height = info.get("height", 0) if info else 0
    if downloaded_height and downloaded_height < 1080:
        logger.warning(
            f"[Pipeline] ⚠️ Downloaded at {downloaded_height}p (below 1080p minimum). "
            "Check Deno is on PATH or video source quality is low."
        )
    else:
        logger.info(f"[Pipeline] ✅ Download quality: {downloaded_height}p")

    # Locate the downloaded file
    downloaded_path = os.path.join(storage_dir, f"{video.id}.mp4")
    if not os.path.exists(downloaded_path):
        # try to find it
        for f in os.listdir(storage_dir):
            if f.startswith(str(video.id)):
                downloaded_path = os.path.join(storage_dir, f)
                break

    if not os.path.exists(downloaded_path):
        raise FileNotFoundError(f"yt-dlp download failed: file not found for video {video.id}")

    # Update video record
    file_size_bytes = os.path.getsize(downloaded_path)
    video.file_path = downloaded_path
    video.file_size_mb = file_size_bytes / (1024 * 1024)
    video.download_progress = 100
    if info.get("title"):
        video.title = info["title"]
    if info.get("duration"):
        video.duration_seconds = float(info["duration"])
    if info.get("thumbnail"):
        video.thumbnail_url = info["thumbnail"]

    await db.commit()
    logger.info(f"[Pipeline] Downloaded: {video.title!r} ({video.file_size_mb:.1f} MB) → {downloaded_path}")


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
    from app.services.ai_brain import AIBrainService, MOMENT_DURATION_RULES, FALLBACK_DURATION_RULE
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

    # Validate and filter clips by duration rules
    valid_clips, rejected_clips = _validate_clip_durations(
        analysis.clips, video.duration_seconds or 0
    )
    if rejected_clips:
        logger.warning(
            f"[Pipeline] {len(rejected_clips)} clips rejected by duration validation: "
            + ", ".join(f"{c.moment_type}({c.end_time - c.start_time:.0f}s)" for c in rejected_clips)
        )

    # Store valid clip suggestions in DB
    from app.models.clip import Clip

    for suggestion in valid_clips:
        clip = Clip(
            video_id=video.id,
            user_id=video.user_id,
            title=suggestion.titles[0] if suggestion.titles else None,
            description=suggestion.description,
            start_time=suggestion.start_time,
            end_time=suggestion.end_time,
            duration=suggestion.end_time - suggestion.start_time,
            viral_score=suggestion.viral_score,
            moment_type=suggestion.moment_type,
            hook_text=suggestion.hook_text,
            hashtags=suggestion.hashtags,
            qc_status="pending",
            review_status="pending",
            ai_provider_used=analysis.provider_used,
        )
        db.add(clip)

    video.checkpoint = "ai_done"
    video.ai_provider_used = analysis.provider_used
    logger.info(
        f"AI analysis done via {analysis.provider_used} "
        f"({len(valid_clips)} valid clips, {len(rejected_clips)} rejected, "
        f"{analysis.tokens_used} tokens)"
    )
    await db.commit()


def _validate_clip_durations(clips, video_duration: float):
    """
    Validate each clip's duration against MOMENT_DURATION_RULES.
    Returns (valid_clips, rejected_clips).
    Attempts to extend short clips before rejecting.
    """
    from app.services.ai_brain import MOMENT_DURATION_RULES, FALLBACK_DURATION_RULE

    valid = []
    rejected = []

    for clip in clips:
        rule = MOMENT_DURATION_RULES.get(clip.moment_type, FALLBACK_DURATION_RULE)
        duration = clip.end_time - clip.start_time

        if duration < rule["min"]:
            # Try to extend the clip
            extended = _try_extend_clip(clip, rule, video_duration)
            ext_duration = extended.end_time - extended.start_time
            if ext_duration >= rule["min"]:
                logger.info(
                    f"[Validate] Extended {clip.moment_type} clip "
                    f"{duration:.0f}s → {ext_duration:.0f}s"
                )
                valid.append(extended)
            else:
                rejected.append(clip)
        elif duration > rule["max"]:
            # Trim from end (preserve buildup + action, trim resolution tail)
            from copy import copy
            trimmed = copy(clip)
            trimmed.end_time = clip.start_time + rule["max"]
            valid.append(trimmed)
        else:
            valid.append(clip)

    return valid, rejected


def _try_extend_clip(clip, rule: dict, video_duration: float):
    """
    Try to extend a clip to meet minimum duration by pulling start earlier
    (adding buildup context) and/or extending end (adding resolution).
    Returns modified clip copy.
    """
    from copy import copy
    extended = copy(clip)
    duration = extended.end_time - extended.start_time
    deficit = rule["min"] - duration

    # First: extend start backwards to add build-up
    buildup_add = min(rule.get("buildup", 8), deficit)
    new_start = max(0.0, extended.start_time - buildup_add)
    extended.start_time = new_start
    duration = extended.end_time - extended.start_time

    # Second: extend end forwards to add resolution
    if duration < rule["min"]:
        still_short = rule["min"] - duration
        resolution_add = min(rule.get("resolution", 8), still_short)
        new_end = min(video_duration, extended.end_time + resolution_add)
        extended.end_time = new_end

    return extended


async def _stage_qc_filtering(video, db):
    """QC is run per-clip after video processing; mark checkpoint here."""
    video.checkpoint = "qc_done"
    await db.commit()


async def _stage_video_processing(video, db):
    from sqlalchemy import select
    from app.models.clip import Clip
    from app.models.channel_config import ChannelCropConfig, GameCropProfile
    from app.services.video_processor import VideoProcessorService
    from app.services.game_detector import GameDetector
    from app.services.facecam_detector import FacecamDetector

    result = await db.execute(select(Clip).where(Clip.video_id == video.id))
    clips = result.scalars().all()

    processor = VideoProcessorService()
    clips_dir = os.path.join("storage", "clips", str(video.id))
    os.makedirs(clips_dir, exist_ok=True)

    # ── Load crop config for this channel ──────────────────────────────
    channel_config = None
    default_game_profile = None

    # Resolve which YouTube account to use for crop config.
    # If the video was not tagged with an account, fall back to the user's first connected account.
    yt_account_id_for_config = video.youtube_account_id
    if not yt_account_id_for_config:
        yt_fb = await db.execute(
            select(YoutubeAccount).where(YoutubeAccount.user_id == video.user_id).limit(1)
        )
        yt_fb_row = yt_fb.scalars().first()
        if yt_fb_row:
            yt_account_id_for_config = yt_fb_row.id
            logger.info(f"[Pipeline] No yt_account on video, using fallback account {yt_account_id_for_config}")

    if yt_account_id_for_config:
        # Load channel config
        cfg_result = await db.execute(
            select(ChannelCropConfig).where(
                ChannelCropConfig.youtube_account_id == yt_account_id_for_config
            )
        )
        channel_config = cfg_result.scalars().first()

        if not channel_config:
            # Auto-detect and create config
            detector = FacecamDetector()
            region = detector.detect_facecam_region(video.file_path) if video.file_path else None
            if region:
                suggested = detector.suggest_crop_config(region)
                from app.models.channel_config import seed_default_game_profiles
                channel_config = ChannelCropConfig(
                    youtube_account_id=video.youtube_account_id,
                    channel_id=str(video.youtube_account_id),  # fallback key
                    default_vertical_crop_mode=suggested["vertical_crop_mode"],
                    default_facecam_position=suggested["facecam_position"],
                    default_crop_x_offset=suggested.get("crop_x_offset", 0),
                    default_crop_anchor=suggested.get("crop_anchor", "left"),
                )
                db.add(channel_config)
                await db.flush()
                for p in seed_default_game_profiles(channel_config):
                    db.add(p)
                logger.info(f"[Pipeline] Auto-created crop config: {suggested['vertical_crop_mode']}")
            else:
                # Use in-memory default (blur_pillarbox)
                channel_config = ChannelCropConfig(
                    youtube_account_id=video.youtube_account_id,
                    channel_id=str(video.youtube_account_id),
                )

    # ── Detect game and resolve game profile ───────────────────────────
    game_detector = GameDetector()
    game_name = game_detector.detect_from_title(video.title or "")
    if game_name == "_default" and video.transcript:
        game_name = game_detector.detect_from_transcript(video.transcript)

    logger.info(f"[Pipeline] Detected game: {game_name}")

    if channel_config and channel_config.id:
        default_game_profile = await game_detector.get_game_profile(
            game_name, channel_config.channel_id, db
        )

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

            # Generate vertical 9:16 version using smart crop
            vertical_path = os.path.join(clips_dir, f"{clip.id}_vertical.mp4")
            try:
                await processor.resize_to_vertical_smart(
                    input_path=clip_path,
                    output_path=vertical_path,
                    game_profile=default_game_profile,
                    channel_config=channel_config,
                )
                clip.clip_path_vertical = vertical_path
                logger.info(f"[Pipeline] Vertical crop done for clip {clip.id}")
            except Exception as crop_err:
                logger.warning(f"[Pipeline] Vertical crop failed for clip {clip.id}: {crop_err}")

            # QC check — pass moment_type for duration-aware validation
            qc_result = await processor.run_qc_check(clip_path)
            # Also run moment-type duration check via qc_service
            from app.services.qc_service import run_qc as run_moment_qc
            duration_qc = await run_moment_qc(
                clip_path,
                moment_type=clip.moment_type,
                clip_duration=clip.end_time - clip.start_time,
            )
            # Merge issues from both checks
            combined_issues = qc_result.issues + [
                i for i in duration_qc.issues if i.type not in {qi.type for qi in qc_result.issues}
            ]
            passed = qc_result.passed and duration_qc.passed
            clip.clip_path = clip_path
            clip.qc_status = "passed" if passed else "failed"
            clip.qc_issues = [
                {"type": i.type, "description": i.description, "severity": i.severity}
                for i in combined_issues
            ]

        except Exception as e:
            logger.error(f"[Pipeline] Failed to process clip {clip.id}: {e}")
            clip.qc_status = "failed"
            clip.qc_issues = [{"type": "processing_error", "description": str(e), "severity": "error"}]

    video.checkpoint = "clips_done"
    await db.commit()
