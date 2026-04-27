"""Analytics API routes — 9 endpoints.

All endpoints require authentication. Channel-scoped data is
automatically filtered to the authenticated user's channels.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _require_channel_ownership(
    channel_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    """Verify the channel belongs to the current user and return account row."""
    result = await db.execute(
        text(
            "SELECT * FROM youtube_accounts WHERE channel_id = :cid AND user_id = :uid"
        ),
        {"cid": channel_id, "uid": str(current_user.id)},
    )
    account = result.fetchone()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found or not owned by current user",
        )
    return dict(account._mapping)


# ── Endpoint 1: Channel Overview ──────────────────────────────────────────────

@router.get("/channel/{channel_id}/overview")
async def get_channel_overview(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregated channel overview stats."""
    account = await _require_channel_ownership(channel_id, current_user, db)

    thirty_days_ago = date.today() - timedelta(days=30)
    sixty_days_ago = date.today() - timedelta(days=60)

    # Totals
    total_result = await db.execute(
        text(
            """
            SELECT
                COALESCE(SUM(va.views), 0) AS total_views,
                COUNT(DISTINCT va.video_id) AS total_videos_with_data,
                COALESCE(AVG(va.impression_ctr), 0) AS avg_ctr,
                COALESCE(AVG(va.avg_view_duration_seconds), 0) AS avg_view_duration,
                COALESCE(SUM(va.watch_time_minutes), 0) AS watch_time_minutes
            FROM video_analytics va
            JOIN videos v ON v.id = va.video_id
            JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            WHERE ya.channel_id = :cid
            """
        ),
        {"cid": channel_id},
    )
    totals = dict((total_result.fetchone() or {})._mapping or {})

    # Last 30 days
    recent_result = await db.execute(
        text(
            """
            SELECT
                COALESCE(SUM(total_views), 0) AS views_30d,
                COALESCE(SUM(subscribers_net), 0) AS subs_30d
            FROM channel_analytics_daily
            WHERE channel_id = :cid AND date >= :start
            """
        ),
        {"cid": channel_id, "start": thirty_days_ago},
    )
    recent = dict((recent_result.fetchone() or {})._mapping or {})

    # Prev 30 days for trend
    prev_result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(total_views), 0) AS prev_views
            FROM channel_analytics_daily
            WHERE channel_id = :cid AND date >= :start AND date < :end
            """
        ),
        {"cid": channel_id, "start": sixty_days_ago, "end": thirty_days_ago},
    )
    prev = dict((prev_result.fetchone() or {})._mapping or {})

    prev_views = int(prev.get("prev_views", 0))
    curr_views = int(recent.get("views_30d", 0))
    trend_pct = None
    if prev_views > 0:
        trend_pct = round((curr_views - prev_views) / prev_views * 100, 1)

    # Content DNA confidence
    dna_result = await db.execute(
        text("SELECT confidence_score, last_updated FROM content_dna_models WHERE channel_id = :cid"),
        {"cid": channel_id},
    )
    dna_row = dna_result.fetchone()

    # Last sync
    sync_result = await db.execute(
        text("SELECT MAX(pulled_at) FROM video_analytics va JOIN videos v ON v.id = va.video_id JOIN youtube_accounts ya ON ya.id = v.youtube_account_id WHERE ya.channel_id = :cid"),
        {"cid": channel_id},
    )
    last_synced = sync_result.scalar()

    return {
        "channel_id": channel_id,
        "channel_name": account.get("channel_name", ""),
        "total_views": int(totals.get("total_views", 0)),
        "total_videos": int(totals.get("total_videos_with_data", 0)),
        "avg_ctr": round(float(totals.get("avg_ctr", 0)), 4),
        "avg_view_duration_seconds": round(float(totals.get("avg_view_duration", 0)), 1),
        "watch_time_hours": round(float(totals.get("watch_time_minutes", 0)) / 60, 1),
        "views_last_30d": curr_views,
        "subscribers_last_30d": int(recent.get("subs_30d", 0)),
        "views_trend_pct": trend_pct,
        "content_dna_confidence": float(dna_row._mapping["confidence_score"]) if dna_row else 0.0,
        "last_synced": last_synced.isoformat() if last_synced else None,
    }


# ── Endpoint 2: Videos with analytics ────────────────────────────────────────

@router.get("/channel/{channel_id}/videos")
async def list_videos_with_analytics(
    channel_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("views", regex="^(views|ctr|watch_time|published_at)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    sort_map = {
        "views": "total_views DESC",
        "ctr": "avg_ctr DESC",
        "watch_time": "total_watch_time DESC",
        "published_at": "v.created_at DESC",
    }
    order = sort_map.get(sort_by, "total_views DESC")

    result = await db.execute(
        text(
            f"""
            SELECT
                v.id,
                v.title,
                v.duration_seconds,
                v.created_at AS published_at,
                COALESCE(SUM(va.views), 0) AS total_views,
                COALESCE(AVG(va.impression_ctr), 0) AS avg_ctr,
                COALESCE(SUM(va.watch_time_minutes), 0) AS total_watch_time,
                COALESCE(AVG(va.avg_view_duration_seconds), 0) AS avg_view_duration_seconds,
                COALESCE(AVG(va.avg_view_percentage), 0) AS avg_view_percentage,
                COUNT(c.id) AS clips_generated,
                COUNT(vrc.id) > 0 AS has_retention_data,
                MAX(va.youtube_video_id) AS youtube_video_id
            FROM videos v
            JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            LEFT JOIN video_analytics va ON va.video_id = v.id
            LEFT JOIN clips c ON c.video_id = v.id
            LEFT JOIN video_retention_curves vrc ON vrc.video_id = v.id
            WHERE ya.channel_id = :cid
            GROUP BY v.id
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
            """
        ),
        {"cid": channel_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    # Total count
    count_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT v.id) FROM videos v
            JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            WHERE ya.channel_id = :cid
            """
        ),
        {"cid": channel_id},
    )
    total = count_result.scalar() or 0

    items = []
    for row in rows:
        r = dict(row._mapping)
        duration = r.get("duration_seconds") or 0
        clippable = duration > 600 and r.get("clips_generated", 0) == 0
        items.append(
            {
                "video_id": str(r["id"]),
                "youtube_video_id": r.get("youtube_video_id") or "",
                "title": r.get("title", ""),
                "published_at": r["published_at"].isoformat() if r.get("published_at") else None,
                "duration_seconds": duration,
                "views": int(r.get("total_views", 0)),
                "avg_ctr": round(float(r.get("avg_ctr", 0)), 4),
                "watch_time_minutes": round(float(r.get("total_watch_time", 0)), 1),
                "avg_view_duration_seconds": round(float(r.get("avg_view_duration_seconds", 0)), 1),
                "avg_view_percentage": round(float(r.get("avg_view_percentage", 0)), 1),
                "clips_generated": int(r.get("clips_generated", 0)),
                "has_retention_data": bool(r.get("has_retention_data", False)),
                "clippable": clippable,
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ── Endpoint 3: Retention Curve ───────────────────────────────────────────────

@router.get("/videos/{youtube_video_id}/retention")
async def get_retention_curve(
    youtube_video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Verify user owns a video with this youtube ID
    result = await db.execute(
        text(
            """
            SELECT vrc.*, v.duration_seconds
            FROM video_retention_curves vrc
            JOIN videos v ON v.id = vrc.video_id
            WHERE vrc.youtube_video_id = :yt_id AND v.user_id = :uid
            LIMIT 1
            """
        ),
        {"yt_id": youtube_video_id, "uid": str(current_user.id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention curve not found. Video needs minimum views for this data.",
        )
    r = dict(row._mapping)
    data_points = r.get("data_points") or []
    peak_moments = r.get("peak_moments") or []
    drop_off_points = r.get("drop_off_points") or []
    duration = r.get("duration_seconds") or 0

    # Build optimal clip windows from peaks
    optimal_windows = []
    for peak in (peak_moments if isinstance(peak_moments, list) else []):
        ts = peak.get("timestamp_seconds", 0)
        window_start = max(0, ts - 60)
        window_end = min(duration, ts + 120)
        optimal_windows.append(
            {
                "start": window_start,
                "end": window_end,
                "score": round(peak.get("retention_ratio", 0.5) * 100, 1),
                "reason": "Retention naik kembali — potential re-watch moment",
            }
        )

    return {
        "youtube_video_id": youtube_video_id,
        "duration_seconds": duration,
        "data_points": data_points,
        "peak_moments": [
            {**p, "label": "Peak moment — potensial clip"}
            for p in (peak_moments if isinstance(peak_moments, list) else [])
        ],
        "drop_off_points": [
            {**d, "label": f"Drop-off {d.get('drop_pct', 0):.0f}% — hook bermasalah"}
            for d in (drop_off_points if isinstance(drop_off_points, list) else [])
        ],
        "optimal_clip_windows": optimal_windows[:5],
    }


# ── Endpoint 4: Content DNA ───────────────────────────────────────────────────

@router.get("/channel/{channel_id}/content-dna")
async def get_content_dna(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    result = await db.execute(
        text("SELECT * FROM content_dna_models WHERE channel_id = :cid"),
        {"cid": channel_id},
    )
    row = result.fetchone()
    if not row:
        # Return empty model with progress indicator
        count_result = await db.execute(
            text(
                """
                SELECT COUNT(DISTINCT va.video_id) FROM video_analytics va
                JOIN videos v ON v.id = va.video_id
                JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
                WHERE ya.channel_id = :cid
                """
            ),
            {"cid": channel_id},
        )
        current_count = count_result.scalar() or 0
        remaining = max(0, 10 - current_count)
        return {
            "channel_id": channel_id,
            "niche": "gaming",
            "confidence_score": 0.0,
            "videos_analyzed": current_count,
            "status": "building",
            "message": f"Content DNA: Butuh {remaining} video lagi untuk analisis pertama",
            "viral_score_weights": {},
            "top_performing_patterns": {},
            "game_performance": {},
        }

    r = dict(row._mapping)
    return {
        "channel_id": channel_id,
        "niche": r.get("niche"),
        "sub_niches": r.get("sub_niches", []),
        "confidence_score": float(r.get("confidence_score", 0)),
        "videos_analyzed": int(r.get("videos_analyzed", 0)),
        "status": "ready",
        "viral_score_weights": r.get("viral_score_weights", {}),
        "top_performing_patterns": r.get("top_performing_patterns", {}),
        "game_performance": r.get("game_performance", {}),
        "underperforming_patterns": r.get("underperforming_patterns", {}),
        "last_updated": r["last_updated"].isoformat() if r.get("last_updated") else None,
    }


# ── Endpoint 5: Opportunities ─────────────────────────────────────────────────

@router.get("/channel/{channel_id}/opportunities")
async def get_opportunities(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    from app.services.analytics.content_dna_builder import ContentDNABuilder

    builder = ContentDNABuilder(db)
    opportunities = await builder.identify_unclipped_viral_potential(channel_id)

    return {
        "items": [
            {
                "video_id": o.video_id,
                "title": o.title,
                "duration_seconds": o.duration_seconds,
                "published_at": o.published_at.isoformat() if o.published_at else None,
                "game_name": o.game_name,
                "viral_potential_score": o.viral_potential_score,
                "estimated_clips": o.estimated_clips,
                "peak_moments_count": o.peak_moments_count,
                "has_retention_data": o.has_retention_data,
                "recommendation": o.recommendation,
            }
            for o in opportunities
        ]
    }


# ── Endpoint 6: Weekly Report ─────────────────────────────────────────────────

@router.get("/channel/{channel_id}/weekly-report/latest")
async def get_latest_weekly_report(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    result = await db.execute(
        text(
            """
            SELECT * FROM weekly_insight_reports
            WHERE channel_id = :cid
            ORDER BY week_start DESC LIMIT 1
            """
        ),
        {"cid": channel_id},
    )
    row = result.fetchone()
    if not row:
        return {
            "available": False,
            "message": "Laporan pertama akan tersedia Senin depan",
        }
    r = dict(row._mapping)
    return {
        "available": True,
        "week_start": r["week_start"].isoformat(),
        "week_end": r["week_end"].isoformat(),
        "summary": r.get("summary_text", ""),
        "wins": r.get("key_wins", []),
        "issues": r.get("key_issues", []),
        "recommendations": r.get("recommendations", []),
        "top_clip_type": r.get("top_clip_type"),
        "views_change_pct": r.get("views_change_pct"),
        "subscribers_change": r.get("subscribers_change"),
        "generated_at": r["generated_at"].isoformat() if r.get("generated_at") else None,
    }


# ── Endpoint 7: Daily Stats (time-series) ────────────────────────────────────

@router.get("/channel/{channel_id}/daily-stats")
async def get_daily_stats(
    channel_id: str,
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    start = date.today() - timedelta(days=days)
    result = await db.execute(
        text(
            """
            SELECT date, total_views, total_watch_time_minutes, subscribers_net
            FROM channel_analytics_daily
            WHERE channel_id = :cid AND date >= :start
            ORDER BY date ASC
            """
        ),
        {"cid": channel_id, "start": start},
    )
    rows = result.fetchall()

    dates, views, watch_time, subscribers_net = [], [], [], []
    for row in rows:
        r = dict(row._mapping)
        dates.append(r["date"].isoformat())
        views.append(int(r.get("total_views", 0)))
        watch_time.append(round(float(r.get("total_watch_time_minutes", 0)), 1))
        subscribers_net.append(int(r.get("subscribers_net", 0)))

    return {
        "dates": dates,
        "views": views,
        "watch_time_minutes": watch_time,
        "subscribers_net": subscribers_net,
    }


# ── Endpoint 8: Trigger Manual Sync ──────────────────────────────────────────

@router.post("/channel/{channel_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    account = await _require_channel_ownership(channel_id, current_user, db)

    # Rate limit: check last sync
    result = await db.execute(
        text(
            """
            SELECT MAX(pulled_at) FROM video_analytics va
            JOIN videos v ON v.id = va.video_id
            JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            WHERE ya.channel_id = :cid
            """
        ),
        {"cid": channel_id},
    )
    last_sync = result.scalar()
    if last_sync:
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        hours_since = (now - last_sync.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if hours_since < 6:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Sync dilakukan terlalu sering. Coba lagi dalam {int(6 - hours_since)} jam.",
            )

    from app.workers.tasks.analytics import sync_channel_analytics
    task = sync_channel_analytics.delay(str(account["id"]))
    logger.info(f"[analytics] Manual sync triggered for {channel_id}, task={task.id}")

    return {"task_id": task.id, "message": "Sync analytics dimulai..."}


# ── Endpoint 9: Game Performance ─────────────────────────────────────────────

@router.get("/channel/{channel_id}/game-performance")
async def get_game_performance(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_channel_ownership(channel_id, current_user, db)

    result = await db.execute(
        text("SELECT game_performance FROM content_dna_models WHERE channel_id = :cid"),
        {"cid": channel_id},
    )
    row = result.fetchone()
    game_perf: dict = dict(row._mapping)["game_performance"] if row else {}

    if not game_perf:
        return {"games": [], "message": "Sync analytics untuk mendapatkan data performa game"}

    games = []
    all_views = [v["avg_views"] for v in game_perf.values() if v.get("avg_views")]
    max_views = max(all_views) if all_views else 1

    for game_name, stats in sorted(game_perf.items(), key=lambda x: x[1].get("avg_views", 0), reverse=True):
        avg_views = stats.get("avg_views", 0)
        avg_ctr = stats.get("avg_ctr", 0)
        trend = "up" if avg_views >= max_views * 0.7 else "stable"
        recommendation = (
            "Prioritaskan konten ini"
            if avg_views >= max_views * 0.7
            else "Optimasi judul dan thumbnail"
        )
        games.append(
            {
                "name": game_name,
                "video_count": stats.get("sample_size", 0),
                "avg_views": round(avg_views, 1),
                "avg_ctr": round(avg_ctr, 4),
                "trend": trend,
                "recommendation": recommendation,
            }
        )

    return {"games": games}
