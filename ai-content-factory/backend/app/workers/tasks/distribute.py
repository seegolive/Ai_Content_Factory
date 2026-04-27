"""Distribution task — upload approved clips to platforms."""
import uuid
from typing import List, Optional

from loguru import logger

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, name="app.workers.tasks.distribute.distribute_clip")
def distribute_clip(self, clip_id: str, platforms: List[str], youtube_account_id: Optional[str], privacy: str = "unlisted"):
    """Upload a clip to the requested platforms."""
    import asyncio

    async def _run():
        # Create a fresh engine scoped to this event loop to avoid
        # "Future attached to a different loop" errors with asyncpg.
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import select
        from app.core.config import settings
        from app.models.clip import Clip
        from app.models.video import YoutubeAccount

        task_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        TaskSession = async_sessionmaker(bind=task_engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with TaskSession() as db:
                result = await db.execute(select(Clip).where(Clip.id == uuid.UUID(clip_id)))
                clip = result.scalar_one_or_none()
                if not clip:
                    logger.error(f"[Distribute] Clip {clip_id} not found")
                    return

                # Resolve privacy from publish_settings if present, fall back to task arg
                resolved_privacy = clip.publish_settings.get("privacy", privacy) if clip.publish_settings else privacy

                status_updates: dict = {}

                # Mark platforms as "uploading" immediately
                for platform in platforms:
                    existing = clip.platform_status.get(platform, {})
                    if existing.get("status") == "published":
                        logger.info(f"[Distribute] Clip {clip_id} already published to {platform}, skipping")
                        continue
                    status_updates[platform] = {"status": "uploading"}

                if status_updates:
                    clip.platform_status = {**clip.platform_status, **status_updates}
                    await db.commit()

                final_updates: dict = {}

                for platform in platforms:
                    existing = clip.platform_status.get(platform, {})
                    if existing.get("status") == "published":
                        continue

                    if platform == "youtube" and youtube_account_id:
                        try:
                            from app.services.youtube_service import YouTubeService

                            yt_result = await db.execute(
                                select(YoutubeAccount).where(
                                    YoutubeAccount.id == uuid.UUID(youtube_account_id)
                                )
                            )
                            yt_account = yt_result.scalar_one_or_none()
                            if not yt_account:
                                raise ValueError("YouTube account not found")

                            yt_service = YouTubeService()

                            # Refresh token if needed
                            access_token = yt_account.access_token
                            if yt_account.refresh_token:
                                try:
                                    access_token = await yt_service.refresh_access_token(yt_account.refresh_token)
                                    yt_account.access_token = access_token
                                except Exception as e:
                                    logger.warning(f"Token refresh failed: {e}")

                            # Use publish_settings overrides if available
                            ps = clip.publish_settings or {}
                            upload_title = ps.get("title") or clip.title or "Untitled Clip"
                            upload_description = ps.get("description") or clip.description or ""
                            upload_tags = ps.get("hashtags") or clip.hashtags or []
                            upload_privacy = resolved_privacy

                            # Prefer vertical (9:16) for YouTube Shorts upload
                            upload_path = clip.clip_path_vertical or clip.clip_path

                            youtube_id = await yt_service.upload_video(
                                clip_path=upload_path,
                                title=upload_title,
                                description=upload_description,
                                tags=upload_tags,
                                access_token=access_token,
                                privacy=upload_privacy,
                            )
                            final_updates[platform] = {"status": "published", "video_id": youtube_id}
                            logger.info(f"[Distribute] Clip {clip_id} published to YouTube: {youtube_id} (privacy={upload_privacy})")

                        except Exception as e:
                            logger.error(f"[Distribute] YouTube upload failed for {clip_id}: {e}")
                            final_updates[platform] = {"status": "failed", "error": str(e)}

                    elif platform == "youtube":
                        logger.warning(f"[Distribute] No youtube_account_id for clip {clip_id}, skipping YouTube")
                        final_updates[platform] = {"status": "pending", "error": "No YouTube account linked"}

                clip.platform_status = {**clip.platform_status, **final_updates}
                await db.commit()
        finally:
            await task_engine.dispose()

    asyncio.run(_run())
