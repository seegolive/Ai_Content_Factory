"""
Main pipeline orchestrator with checkpoint-based resumability.

STAGES (in order):
  input_validated → transcript_done → ai_done → qc_done → clips_done → review_ready

If a stage fails, the pipeline saves the error and notifies the user.
On retry, completed stages are skipped — idempotent execution.
"""

import asyncio
import json
import os
import statistics
import subprocess
import time
import uuid
from typing import Optional

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


@celery_app.task(
    bind=True, max_retries=3, name="app.workers.tasks.pipeline.process_video_pipeline"
)
def process_video_pipeline(self, video_id: str):
    """
    Process a video through all pipeline stages.
    Resumes from last successful checkpoint on retry.
    """
    logger.info(f"[Pipeline] Starting for video_id={video_id}")

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.pool import NullPool
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )
        from app.core.config import settings
        from app.models.user import User
        from app.models.video import Video

        # Use NullPool to avoid event-loop conflicts in Celery forked workers
        _engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        _SessionLocal = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )

        async with _SessionLocal() as db:
            result = await db.execute(
                select(Video).where(Video.id == uuid.UUID(video_id))
            )
            video = result.scalar_one_or_none()
            if not video:
                logger.error(f"[Pipeline] Video {video_id} not found")
                return

            # Load user for notifications
            user_result = await db.execute(select(User).where(User.id == video.user_id))
            user = user_result.scalar_one_or_none()

            current_idx = _checkpoint_index(video.checkpoint)
            logger.info(
                f"[Pipeline] Resuming from checkpoint: {video.checkpoint!r} (idx={current_idx})"
            )

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


async def _extract_audio_energy_peaks(file_path: str, video_id: str) -> list:
    """Extract audio hype moments via FFmpeg ebur128 loudness analysis.
    Returns list of {start, end, level} dicts for windows above the energy threshold.
    """
    energy_file = os.path.join("storage", "videos", f"{video_id}_energy.json")
    if os.path.exists(energy_file):
        with open(energy_file) as f:
            return json.load(f)

    def _run():
        result = subprocess.run(
            ["ffmpeg", "-i", file_path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600,
        )
        return result.stderr

    loop = asyncio.get_running_loop()
    stderr = await loop.run_in_executor(None, _run)

    # Parse: "t:  3.2 M: -18.5 S: ..." → (time_s, momentary_lufs)
    momentary: list[tuple[float, float]] = []
    for line in stderr.splitlines():
        if "M:" in line and "t:" in line:
            try:
                t_val = float(line.split("t:")[1].split()[0])
                m_val = float(line.split("M:")[1].split()[0])
                if m_val > -70:  # skip silence frames
                    momentary.append((t_val, m_val))
            except (ValueError, IndexError):
                continue

    if len(momentary) < 10:
        logger.warning("[Pipeline] Audio energy: not enough data, skipping")
        return []

    # Aggregate to 5-second windows
    window_sec = 5
    windows: dict[int, list[float]] = {}
    for t, m in momentary:
        bucket = int(t // window_sec)
        windows.setdefault(bucket, []).append(m)

    window_avgs = sorted(
        [(bucket * window_sec, sum(v) / len(v)) for bucket, v in windows.items()]
    )
    loudness_vals = [lv for _, lv in window_avgs]
    mean_l = statistics.mean(loudness_vals)
    std_l = statistics.stdev(loudness_vals) if len(loudness_vals) > 1 else 1.0
    # 0.7 std catches top ~24% of windows — aggressive enough for gaming
    threshold = mean_l + 0.7 * std_l

    peaks = [
        {"start": int(t), "end": int(t + window_sec), "level": round(lv, 1)}
        for t, lv in window_avgs
        if lv > threshold
    ]

    # Merge consecutive / overlapping peaks into longer hype segments
    merged: list[dict] = []
    for p in peaks:
        if merged and p["start"] <= merged[-1]["end"] + window_sec:
            merged[-1]["end"] = p["end"]
            merged[-1]["level"] = max(merged[-1]["level"], p["level"])
        else:
            merged.append(dict(p))

    with open(energy_file, "w") as f:
        json.dump(merged, f)

    logger.info(f"[Pipeline] Audio energy: {len(merged)} hype segments detected")
    return merged


async def _stage_input_validation(video, db):

    # ── Download YouTube URL if no local file ────────────────────────────────
    if not video.file_path and video.original_url:
        logger.info(f"[Pipeline] Downloading YouTube video: {video.original_url}")
        await _download_youtube_video(video, db)

    # Validate file exists (for uploads) or URL is accessible
    if video.file_path and not os.path.exists(video.file_path):
        raise FileNotFoundError(f"Video file missing: {video.file_path}")

    # Copyright pre-check
    if video.file_path:
        from app.services.copyright_check import CopyrightCheckService
        checker = CopyrightCheckService()
        result = await checker.check_audio(video.file_path)
        video.copyright_status = result.status
        if result.is_flagged:
            logger.warning(
                f"[Pipeline] Copyright flag on {video.id}: {result.matched_music}"
            )

    # Extract audio energy peaks (non-blocking, best-effort)
    if video.file_path:
        try:
            await _extract_audio_energy_peaks(video.file_path, str(video.id))
        except Exception as e:
            logger.warning(f"[Pipeline] Audio energy extraction failed (non-fatal): {e}")

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

    # Map quality_preference to yt-dlp format string.
    # bestvideo*+bestaudio* = any container (wildcard) ensures final fallback never fails.
    quality = getattr(video, "quality_preference", "1440p") or "1440p"
    quality_format_map = {
        "1080p": "bestvideo[height>=1080]+bestaudio/bestvideo*[height>=1080]+bestaudio*/bestvideo*+bestaudio*/best",
        "1440p": "bestvideo[height>=1440]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo*+bestaudio*/best",
        "2160p": "bestvideo[height>=2160]+bestaudio/bestvideo[height>=1440]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo*+bestaudio*/best",
        "best": "bestvideo*+bestaudio*/best",
    }
    fmt = quality_format_map.get(quality, quality_format_map["1440p"])

    # Progress hook — writes download_progress (0-100) directly to DB via sync psycopg
    video_id_str = str(video.id)

    _last_dl_update = [0.0]  # mutable closure for throttle
    def _progress_hook(d):
        if d.get("status") == "downloading":
            now = time.time()
            if now - _last_dl_update[0] < 2.0:
                return
            _last_dl_update[0] = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and total > 0:
                pct = int(downloaded * 100 / total)
                try:
                    import psycopg2
                    from app.core.config import settings

                    sync_url = settings.DATABASE_URL_SYNC
                    conn = psycopg2.connect(sync_url)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE videos SET download_progress = %s WHERE id = %s",
                        (pct, video_id_str),
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception:
                    pass  # Non-critical — progress display only

    # visionos client: returns high-quality https formats without PO Token or SABR restrictions.
    # android_vr/android/mweb now require GVS PO Token and are blocked by SABR experiment.
    ydl_opts = {
        "format": fmt,
        "outtmpl": output_path,
        "quiet": False,
        "no_warnings": False,
        "merge_output_format": "mp4",
        "noprogress": False,
        "nopart": True,
        "overwrites": True,
        "extractor_args": {
            "youtube": {"player_client": ["visionos", "web"]}
        },
        "progress_hooks": [_progress_hook],
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path
        logger.info(f"[Pipeline] Using cookies from {cookies_path}")
    else:
        logger.warning(
            "[Pipeline] No cookies file found at storage/youtube_cookies.txt — "
            "YouTube may block download. Export cookies from browser and save there."
        )

    loop = asyncio.get_running_loop()

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
        raise FileNotFoundError(
            f"yt-dlp download failed: file not found for video {video.id}"
        )

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
    logger.info(
        f"[Pipeline] Downloaded: {video.title!r} ({video.file_size_mb:.1f} MB) → {downloaded_path}"
    )


async def _stage_transcription(video, db):
    from app.services.transcription import WhisperTranscriptionService

    if not video.file_path or not os.path.exists(video.file_path):
        raise FileNotFoundError(f"Cannot transcribe: file missing {video.file_path}")

    # Reset download_progress so it starts from 0 (not leftover 100 from yt-dlp)
    video.download_progress = 0
    await db.commit()

    # Write transcription sub-progress to download_progress column (reused for display).
    # Transcription maps to pipeline 15–35%; we write whisper progress (0-100) here
    # so the frontend can show live progress rather than a stuck bar.
    video_id_str = str(video.id)

    _last_tx_update = [0.0]  # mutable closure for throttle
    def _transcription_progress(whisper_pct: int):
        now = time.time()
        if now - _last_tx_update[0] < 2.0:
            return
        _last_tx_update[0] = now
        try:
            import psycopg2
            from app.core.config import settings
            conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
            cur = conn.cursor()
            cur.execute(
                "UPDATE videos SET download_progress = %s WHERE id = %s",
                (whisper_pct, video_id_str),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass  # non-critical

    service = WhisperTranscriptionService()
    result = await service.transcribe(video.file_path, progress_callback=_transcription_progress)

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

    # Load audio energy peaks if available
    energy_file = os.path.join("storage", "videos", f"{video.id}_energy.json")
    hype_markers = []
    if os.path.exists(energy_file):
        try:
            with open(energy_file) as f:
                hype_markers = json.load(f)
            logger.info(f"[Pipeline] Loaded {len(hype_markers)} audio hype markers")
        except Exception:
            pass

    # Detect game for AI context (text-based; crop profile loading stays in Stage 5)
    from app.services.game_detector import GameDetector as _GameDetector
    _gd = _GameDetector()
    _game_name = _gd.detect_from_title(video.title or "")
    if _game_name == "_default" and video.transcript:
        _game_name = _gd.detect_from_transcript(video.transcript)
    game_title_for_ai = _game_name if _game_name != "_default" else ""
    if game_title_for_ai:
        logger.info(f"[Pipeline] AI context: game={game_title_for_ai}")

    analysis = await brain.analyze_transcript(
        transcript,
        game_title=game_title_for_ai,
        hype_markers=hype_markers,
    )

    # Layer 2: Validate and adjust clips (extend/pass/split/reject)
    from app.workers.tasks.pipeline_validator import validate_and_adjust_clips

    valid_clips, action_log = validate_and_adjust_clips(
        clips=analysis.clips,
        video_duration=video.duration_seconds or 0,
        transcript_segments=segments,
    )

    rejected_count = sum(1 for e in action_log if e.get("action") == "REJECTED")
    if rejected_count:
        logger.warning(
            f"[Pipeline] {rejected_count} clips rejected by Layer 2 validator"
        )

    # Store action_log in video.processing_log if column exists
    if hasattr(video, "processing_log"):
        import json as _json

        existing_log = video.processing_log or {}
        if isinstance(existing_log, str):
            try:
                existing_log = _json.loads(existing_log)
            except Exception:
                existing_log = {}
        existing_log["layer2_validation"] = action_log
        video.processing_log = existing_log

    # Store valid clip suggestions in DB
    from app.models.clip import Clip
    from sqlalchemy import delete as sql_delete

    # Idempotency: delete clips from any previous partial run before re-inserting
    await db.execute(sql_delete(Clip).where(Clip.video_id == video.id))
    await db.flush()

    for suggestion in valid_clips:
        clip = Clip(
            video_id=video.id,
            user_id=video.user_id,
            title=suggestion.titles[0] if suggestion.titles else None,
            description=suggestion.description,
            start_time=suggestion.start_time,
            end_time=suggestion.end_time,
            peak_time=suggestion.peak_time,
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
        f"({len(valid_clips)} valid clips, {rejected_count} rejected, "
        f"{analysis.tokens_used} tokens)"
    )
    await db.commit()


async def _sample_brightness(file_path: str, timestamp: float) -> float:
    """Return mean grayscale brightness (0–255) for one frame. Returns 255 on error."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-ss", str(timestamp), "-i", file_path,
            "-vframes", "1", "-vf", "scale=32:18,format=gray",
            "-f", "rawvideo", "pipe:",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return sum(stdout) / len(stdout) if stdout else 255.0
    except Exception:
        return 255.0  # assume non-black on error


async def _stage_qc_filtering(video, db):
    """Pre-cut QC: reject clips that are mostly black (loading screens / waiting screens).

    Samples 5 frames at 10/25/50/75/90% of clip duration in parallel.
    Rejects if ≥60% of samples are dark (brightness < 20/255).
    """
    from sqlalchemy import select
    from app.models.clip import Clip

    result = await db.execute(
        select(Clip).where(Clip.video_id == video.id, Clip.clip_path.is_(None))
    )
    clips = result.scalars().all()

    _SAMPLE_PCTS = [0.10, 0.25, 0.50, 0.75, 0.90]
    rejected = 0
    if video.file_path and clips:
        for clip in clips:
            try:
                clip_dur = clip.end_time - clip.start_time
                timestamps = [clip.start_time + clip_dur * p for p in _SAMPLE_PCTS]
                brightnesses = await asyncio.gather(
                    *[_sample_brightness(video.file_path, ts) for ts in timestamps]
                )
                black_count = sum(1 for b in brightnesses if b < 20)
                black_ratio = black_count / len(brightnesses)

                if black_ratio >= 0.6:  # 3+ of 5 frames black → reject
                    clip.qc_status = "failed"
                    clip.qc_issues = [{
                        "type": "black_frame", "severity": "error",
                        "description": (
                            f"Clip {clip.start_time:.0f}s is mostly black "
                            f"({black_count}/{len(_SAMPLE_PCTS)} sampled frames, "
                            f"min brightness={min(brightnesses):.1f})"
                        ),
                        "recommendation": "skip_or_shift_start",
                    }]
                    rejected += 1
                    logger.debug(
                        f"[QC] Rejected black clip {clip.id} "
                        f"({black_count}/{len(_SAMPLE_PCTS)} black frames)"
                    )
            except Exception as e:
                logger.warning(f"[QC] Brightness check failed for clip {clip.id}: {e}")

    if rejected:
        logger.info(f"[QC] Pre-cut blackframe filter: rejected {rejected}/{len(clips)} clips")

    video.checkpoint = "qc_done"
    await db.commit()


async def _stage_video_processing(video, db):
    from sqlalchemy import select
    from app.models.clip import Clip
    from app.models.channel_config import ChannelCropConfig
    from app.models.video import YoutubeAccount
    from app.services.video_processor import VideoProcessorService
    from app.services.game_detector import GameDetector
    from app.services.facecam_detector import FacecamDetector

    result = await db.execute(
        select(Clip).where(
            Clip.video_id == video.id,
            Clip.clip_path.is_(None),
            Clip.qc_status != "failed",  # skip pre-rejected black frames
        )
    )
    clips = result.scalars().all()
    if not clips:
        logger.info(f"[Pipeline] All clips already processed for video {video.id}, skipping cut stage")
        video.checkpoint = "clips_done"
        await db.commit()
        return

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
            select(YoutubeAccount)
            .where(YoutubeAccount.user_id == video.user_id)
            .limit(1)
        )
        yt_fb_row = yt_fb.scalars().first()
        if yt_fb_row:
            yt_account_id_for_config = yt_fb_row.id
            logger.info(
                f"[Pipeline] No yt_account on video, using fallback account {yt_account_id_for_config}"
            )

    if yt_account_id_for_config:
        # Load channel config saved by the user from /settings/crop-config
        cfg_result = await db.execute(
            select(ChannelCropConfig).where(
                ChannelCropConfig.youtube_account_id == yt_account_id_for_config
            )
        )
        channel_config = cfg_result.scalars().first()

        if channel_config:
            logger.info(
                f"[Pipeline] Loaded user crop config: channel={channel_config.channel_id} "
                f"mode={channel_config.default_vertical_crop_mode} "
                f"canvas={channel_config.obs_canvas_width}x{channel_config.obs_canvas_height}"
            )
        else:
            logger.warning(
                f"[Pipeline] No saved crop config found for yt_account={yt_account_id_for_config} "
                "— running facecam auto-detect"
            )
            # Auto-detect and create config
            detector = FacecamDetector()
            region = (
                detector.detect_facecam_region(video.file_path)
                if video.file_path
                else None
            )
            if region:
                suggested = detector.suggest_crop_config(region)
                from app.models.channel_config import seed_default_game_profiles

                channel_config = ChannelCropConfig(
                    youtube_account_id=yt_account_id_for_config,
                    channel_id=str(yt_account_id_for_config),  # fallback key
                    default_vertical_crop_mode=suggested["vertical_crop_mode"],
                    default_facecam_position=suggested["facecam_position"],
                    default_crop_x_offset=suggested.get("crop_x_offset", 0),
                    default_crop_anchor=suggested.get("crop_anchor", "left"),
                )
                db.add(channel_config)
                await db.flush()
                for p in seed_default_game_profiles(channel_config):
                    db.add(p)
                logger.info(
                    f"[Pipeline] Auto-created crop config: {suggested['vertical_crop_mode']}"
                )
            else:
                # Use in-memory default (blur_pillarbox) — NOT saved to DB
                logger.warning(
                    "[Pipeline] Facecam not detected — using in-memory blur_pillarbox default"
                )
                channel_config = ChannelCropConfig(
                    youtube_account_id=yt_account_id_for_config,
                    channel_id=str(yt_account_id_for_config),
                )
    else:
        logger.warning(
            "[Pipeline] No YouTube account linked to this video or user — "
            "crop config cannot be loaded, using blur_pillarbox default"
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
            vertical_path = os.path.join(clips_dir, f"{clip.id}_vertical.mp4")

            # Linear cut + vertical crop (hook-first formula removed — causes jarring jump)
            await processor.resize_to_vertical_smart(
                input_path=video.file_path,
                output_path=vertical_path,
                game_profile=default_game_profile,
                channel_config=channel_config,
                start_time=clip.start_time,
                end_time=clip.end_time,
            )
            logger.info(f"[Pipeline] Cut+crop done for clip {clip.id}")

            # Burn captions from transcript (Montserrat Bold, y=h*0.74)
            cap_path = os.path.join(clips_dir, f"{clip.id}_captioned.mp4")
            hook_dur = 0.0  # hook-first formula removed
            try:
                # Only include segments within the clip's time range (+ small buffer)
                cap_segments = [
                    {"start": s["start"], "end": s["end"], "text": s.get("text", "")}
                    for s in (video.transcript_segments or [])
                    if clip.start_time - 2 <= s["start"] <= clip.end_time + 2
                ]
                captioned = await processor.burn_captions(
                    input_path=vertical_path,
                    output_path=cap_path,
                    segments=cap_segments,
                    clip_start=clip.start_time,
                    clip_end=clip.end_time,
                    hook_duration=hook_dur,
                    peak_time=clip.peak_time if hook_dur > 0 else None,
                )
                if captioned == cap_path and os.path.exists(cap_path):
                    os.replace(cap_path, vertical_path)
                    logger.info(f"[Pipeline] Captions burned for clip {clip.id}")
            except Exception as e:
                logger.warning(f"[Pipeline] Caption burn failed (non-fatal): {e}")
                try:
                    os.remove(cap_path)
                except OSError:
                    pass

            # Single ffprobe: pass base QCResult into run_qc to skip second probe
            from app.services.qc_service import run_qc as run_moment_qc
            qc_base = await processor.run_qc_check(vertical_path)
            duration_qc = await run_moment_qc(
                vertical_path,
                moment_type=clip.moment_type,
                existing_result=qc_base,
            )
            passed = duration_qc.passed
            clip.clip_path = vertical_path
            clip.clip_path_vertical = vertical_path
            clip.qc_status = "passed" if passed else "failed"
            clip.qc_issues = [
                {
                    "type": i.type,
                    "description": i.description,
                    "severity": i.severity,
                    "recommendation": i.recommendation,
                }
                for i in duration_qc.issues
            ]

        except Exception as e:
            logger.error(f"[Pipeline] Failed to process clip {clip.id}: {e}")
            clip.qc_status = "failed"
            clip.qc_issues = [
                {"type": "processing_error", "description": str(e), "severity": "error", "recommendation": ""}
            ]

        # Commit each clip immediately so progress is saved if pipeline crashes
        await db.commit()

    video.checkpoint = "clips_done"
    await db.commit()
