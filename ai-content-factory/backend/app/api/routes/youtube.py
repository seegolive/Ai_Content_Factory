"""YouTube analytics routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.video import YoutubeAccount
from app.services.youtube_service import YouTubeService

router = APIRouter()
yt_service = YouTubeService()


@router.get("/youtube/stats")
async def get_youtube_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return connected YouTube channel stats for the current user."""
    result = await db.execute(
        select(YoutubeAccount).where(YoutubeAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()

    if not accounts:
        return {"connected": False, "accounts": []}

    stats = []
    for account in accounts:
        if not account.access_token:
            stats.append({
                "channel_id": account.channel_id,
                "channel_name": account.channel_name,
                "connected": True,
                "error": "No access token stored",
            })
            continue

        try:
            # Try with stored access token first
            info = await yt_service.get_channel_info(account.access_token)
            stats.append({
                "channel_id": info.channel_id,
                "channel_name": info.channel_name,
                "subscriber_count": info.subscriber_count,
                "thumbnail_url": info.thumbnail_url,
                "connected": True,
            })
        except Exception:
            # Try refreshing the token
            if account.refresh_token:
                try:
                    new_token = await yt_service.refresh_access_token(account.refresh_token)
                    account.access_token = new_token
                    await db.commit()
                    info = await yt_service.get_channel_info(new_token)
                    stats.append({
                        "channel_id": info.channel_id,
                        "channel_name": info.channel_name,
                        "subscriber_count": info.subscriber_count,
                        "thumbnail_url": info.thumbnail_url,
                        "connected": True,
                    })
                except Exception as e:
                    logger.warning(f"Could not refresh YouTube token for account {account.channel_id}: {e}")
                    stats.append({
                        "channel_id": account.channel_id,
                        "channel_name": account.channel_name,
                        "connected": True,
                        "error": "Token expired — please reconnect",
                    })
            else:
                stats.append({
                    "channel_id": account.channel_id,
                    "channel_name": account.channel_name,
                    "connected": True,
                    "error": "Token expired — please reconnect",
                })

    return {"connected": True, "accounts": stats}


def _get_token_for_account(account: YoutubeAccount) -> str | None:
    """Return the best available token for an account, or None."""
    return account.access_token or None


@router.get("/youtube/analytics")
async def get_youtube_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return detailed channel analytics (KPIs + per-video stats) for the first connected account."""
    result = await db.execute(
        select(YoutubeAccount).where(YoutubeAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()

    if not accounts:
        return {"connected": False, "analytics": None}

    # Use the first account that has a token
    account = None
    for acc in accounts:
        if acc.access_token or acc.refresh_token:
            account = acc
            break

    if not account:
        return {"connected": False, "analytics": None}

    access_token = account.access_token

    # Try to refresh token if needed
    async def _get_analytics_with_refresh(token: str):
        try:
            return await yt_service.get_channel_analytics(token, max_videos=20)
        except Exception:
            if account.refresh_token:
                try:
                    new_token = await yt_service.refresh_access_token(account.refresh_token)
                    account.access_token = new_token
                    await db.commit()
                    return await yt_service.get_channel_analytics(new_token, max_videos=20)
                except Exception as e:
                    logger.warning(f"Analytics fetch failed even after refresh: {e}")
                    raise
            raise

    try:
        analytics = await _get_analytics_with_refresh(access_token)
    except Exception as e:
        logger.error(f"YouTube analytics error for user {current_user.id}: {e}")
        return {
            "connected": True,
            "analytics": None,
            "error": "Could not fetch analytics — token may be expired. Please reconnect in Settings.",
        }

    def _video_stat_to_dict(v):
        return {
            "video_id": v.video_id,
            "title": v.title,
            "published_at": v.published_at,
            "thumbnail_url": v.thumbnail_url,
            "views": v.views,
            "likes": v.likes,
            "comments": v.comments,
            "duration_seconds": v.duration_seconds,
        }

    return {
        "connected": True,
        "error": None,
        "analytics": {
            "channel_id": analytics.channel_id,
            "channel_name": analytics.channel_name,
            "thumbnail_url": analytics.thumbnail_url,
            "subscriber_count": analytics.subscriber_count,
            "total_views": analytics.total_views,
            "total_videos": analytics.total_videos,
            "recent_videos": [_video_stat_to_dict(v) for v in analytics.recent_videos],
            "top_videos": [_video_stat_to_dict(v) for v in analytics.top_videos],
        },
    }
