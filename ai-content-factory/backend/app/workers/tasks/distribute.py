"""Distribution task — upload approved clips to platforms."""
import uuid
from typing import List, Optional

from loguru import logger

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, name="app.workers.tasks.distribute.distribute_clip")
def distribute_clip(self, clip_id: str, platforms: List[str], youtube_account_id: Optional[str]):
    """Upload a clip to the requested platforms."""
    import asyncio

    async def _run():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.clip import Clip
        from app.models.video import YoutubeAccount

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Clip).where(Clip.id == uuid.UUID(clip_id)))
            clip = result.scalar_one_or_none()
            if not clip:
                logger.error(f"[Distribute] Clip {clip_id} not found")
                return

            status_updates = {}

            for platform in platforms:
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

                        youtube_id = await yt_service.upload_video(
                            clip_path=clip.clip_path,
                            title=clip.title or "Untitled Clip",
                            description=clip.description or "",
                            tags=clip.hashtags or [],
                            access_token=access_token,
                            privacy="unlisted",
                        )
                        status_updates[platform] = {"status": "published", "video_id": youtube_id}
                        logger.info(f"[Distribute] Clip {clip_id} published to YouTube: {youtube_id}")

                    except Exception as e:
                        logger.error(f"[Distribute] YouTube upload failed for {clip_id}: {e}")
                        status_updates[platform] = {"status": "failed", "error": str(e)}

            clip.platform_status = {**clip.platform_status, **status_updates}
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_run())
