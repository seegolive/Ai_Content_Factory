"""Enhancement Celery task — runs Real-ESRGAN 2× upscale on a single clip."""

import asyncio
import os
import time
import uuid

from celery.exceptions import MaxRetriesExceededError
from loguru import logger

from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.workers.tasks.enhancement_task.enhance_clip",
    queue="enhancement",
)
def enhance_clip(self, clip_id: str):
    """Enhance a single clip to 1440p. Resumable: skips if already completed."""

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.pool import NullPool
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.models.clip import Clip

        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with Session() as db:
                result = await db.execute(select(Clip).where(Clip.id == uuid.UUID(clip_id)))
                clip = result.scalar_one_or_none()

                if not clip:
                    logger.error(f"[Enhancement] Clip {clip_id} not found")
                    return

                if clip.enhanced_status == "completed" and clip.enhanced_path:
                    logger.info(f"[Enhancement] Clip {clip_id} already enhanced, skipping")
                    return

                if not clip.clip_path or not os.path.exists(clip.clip_path):
                    raise FileNotFoundError(f"Source clip not found: {clip.clip_path}")

                # Build output path alongside original
                source_dir = os.path.dirname(clip.clip_path)
                output_path = os.path.join(source_dir, f"{clip.id}_enhanced_1440p.mp4")

                # Mark as processing
                clip.enhanced_status = "processing"
                clip.enhanced_progress = 0
                await db.commit()

                clip_id_str = str(clip.id)

                def _progress_cb(pct: int):
                    """Write progress to DB every 2s (throttled)."""
                    try:
                        import psycopg2
                        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE clips SET enhanced_progress=%s WHERE id=%s",
                            (pct, clip_id_str),
                        )
                        conn.commit()
                        cur.close()
                        conn.close()
                    except Exception:
                        pass

                # Run enhancement
                from app.services.video_enhancer import VideoEnhancerService
                enhancer = VideoEnhancerService()
                meta = await enhancer.enhance(clip.clip_path, output_path, _progress_cb)

                # Basic QC: file exists and has expected resolution
                if not os.path.exists(output_path):
                    raise RuntimeError("Enhanced file not created")
                if meta["width"] != 1440 or meta["height"] != 2560:
                    logger.warning(
                        f"[Enhancement] Unexpected resolution {meta['width']}×{meta['height']}"
                    )

                from datetime import datetime, timezone
                clip.enhanced_path = output_path
                clip.enhanced_status = "completed"
                clip.enhanced_progress = 100
                clip.enhanced_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    f"[Enhancement] ✓ Clip {clip_id} enhanced → "
                    f"{meta['width']}×{meta['height']} {meta['file_size_mb']}MB"
                )

        except Exception as e:
            logger.exception(f"[Enhancement] Failed for clip {clip_id}: {e}")
            # Write failed status
            try:
                async with Session() as db2:
                    r = await db2.execute(select(Clip).where(Clip.id == uuid.UUID(clip_id)))
                    clip2 = r.scalar_one_or_none()
                    if clip2:
                        clip2.enhanced_status = "failed"
                        await db2.commit()
            except Exception:
                pass
            raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error(f"[Enhancement] Max retries exceeded for clip {clip_id}")
