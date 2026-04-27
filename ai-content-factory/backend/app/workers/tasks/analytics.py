"""Analytics Celery tasks.

Scheduled tasks for syncing YouTube analytics, updating Content DNA,
and generating weekly insight reports.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from celery import shared_task
from loguru import logger

from app.workers.celery_app import celery_app


def _run_async(coro):
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, name="app.workers.tasks.analytics.sync_channel_analytics")
def sync_channel_analytics(self, youtube_account_id: str) -> dict[str, Any]:
    """
    Fetch analytics for all recent videos in a channel.
    Runs daily at 06:00 WIB (23:00 UTC previous day).

    Idempotent: uses UPSERT on (video_id, snapshot_date).
    """
    return _run_async(_sync_channel_analytics_async(youtube_account_id))


@celery_app.task(bind=True, max_retries=3, name="app.workers.tasks.analytics.update_content_dna")
def update_content_dna(self, youtube_account_id: str) -> dict[str, Any]:
    """
    Rebuild Content DNA model after analytics sync.
    Only runs if 5+ new videos have been analyzed since last update.
    """
    return _run_async(_update_content_dna_async(youtube_account_id))


@celery_app.task(bind=True, max_retries=2, name="app.workers.tasks.analytics.generate_weekly_insight_report")
def generate_weekly_insight_report(self, youtube_account_id: str) -> dict[str, Any]:
    """
    Generate AI-powered weekly insight report.
    Runs every Monday at 07:00 WIB.
    """
    return _run_async(_generate_weekly_report_async(youtube_account_id))


# ── Async implementations ────────────────────────────────────────────────────


async def _sync_channel_analytics_async(youtube_account_id: str) -> dict[str, Any]:
    from app.core.database import AsyncSessionLocal
    from app.services.analytics.youtube_analytics_fetcher import (
        YouTubeAnalyticsFetcher,
        detect_drop_offs,
        detect_peak_moments,
    )

    async with AsyncSessionLocal() as db:
        # Load youtube account
        from sqlalchemy import select, text

        result = await db.execute(
            text("SELECT * FROM youtube_accounts WHERE id = :id"),
            {"id": youtube_account_id},
        )
        account = result.fetchone()
        if not account:
            logger.error(f"[sync_analytics] youtube_account {youtube_account_id} not found")
            return {"status": "error", "message": "Account not found"}

        account_dict = dict(account._mapping)
        channel_id: str = account_dict["channel_id"]

        logger.info(f"[sync_analytics] Starting sync for channel {channel_id}")

        fetcher = YouTubeAnalyticsFetcher(
            access_token=account_dict.get("access_token", ""),
            refresh_token=account_dict.get("refresh_token", ""),
            channel_id=channel_id,
        )

        # 1. Fetch latest 50 videos
        videos = await fetcher.fetch_channel_videos(max_results=50)
        logger.info(f"[sync_analytics] Fetched {len(videos)} videos from YouTube")

        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        synced = 0
        for video_meta in videos:
            try:
                # Match to internal video via youtube_video_id in video_analytics
                # First upsert the analytics data
                analytics = await fetcher.fetch_video_analytics(
                    video_meta.youtube_id, start_date, end_date
                )
                if not analytics:
                    continue

                # Find matching internal video
                vid_result = await db.execute(
                    text(
                        """
                        SELECT v.id FROM videos v
                        JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
                        WHERE ya.channel_id = :channel_id
                          AND v.title ILIKE :title_pattern
                        LIMIT 1
                        """
                    ),
                    {"channel_id": channel_id, "title_pattern": f"%{video_meta.title[:30]}%"},
                )
                vid_row = vid_result.fetchone()
                if not vid_row:
                    continue

                video_id = str(vid_row[0])

                # Upsert analytics snapshot
                await db.execute(
                    text(
                        """
                        INSERT INTO video_analytics (
                            id, video_id, youtube_video_id, channel_id, snapshot_date,
                            views, likes, comments, shares, watch_time_minutes,
                            avg_view_duration_seconds, avg_view_percentage,
                            impressions, impression_ctr,
                            subscribers_gained, subscribers_lost,
                            traffic_sources, device_types, top_geographies, pulled_at
                        ) VALUES (
                            gen_random_uuid(), :video_id, :yt_id, :channel_id, :snapshot_date,
                            :views, :likes, :comments, :shares, :watch_time,
                            :avg_duration, :avg_pct,
                            :impressions, :ctr,
                            :subs_gained, :subs_lost,
                            :traffic::jsonb, :devices::jsonb, :geos::jsonb, now()
                        )
                        ON CONFLICT (video_id, snapshot_date) DO UPDATE SET
                            views = EXCLUDED.views,
                            likes = EXCLUDED.likes,
                            watch_time_minutes = EXCLUDED.watch_time_minutes,
                            pulled_at = now()
                        """
                    ),
                    {
                        "video_id": video_id,
                        "yt_id": video_meta.youtube_id,
                        "channel_id": channel_id,
                        "snapshot_date": end_date,
                        "views": analytics.views,
                        "likes": analytics.likes,
                        "comments": analytics.comments,
                        "shares": analytics.shares,
                        "watch_time": analytics.watch_time_minutes,
                        "avg_duration": analytics.avg_view_duration_seconds,
                        "avg_pct": analytics.avg_view_percentage,
                        "impressions": analytics.impressions,
                        "ctr": analytics.impression_ctr,
                        "subs_gained": analytics.subscribers_gained,
                        "subs_lost": analytics.subscribers_lost,
                        "traffic": str(analytics.traffic_sources).replace("'", '"'),
                        "devices": str(analytics.device_types).replace("'", '"'),
                        "geos": "[]",
                    },
                )

                # Fetch retention curve if not yet stored
                existing_curve = await db.execute(
                    text("SELECT id FROM video_retention_curves WHERE video_id = :vid"),
                    {"vid": video_id},
                )
                if not existing_curve.fetchone():
                    curve_points = await fetcher.fetch_retention_curve(video_meta.youtube_id)
                    if curve_points:
                        import json
                        peaks = detect_peak_moments(curve_points)
                        drops = detect_drop_offs(curve_points)
                        points_json = json.dumps([
                            {"elapsed_ratio": p.elapsed_ratio, "retention_ratio": p.retention_ratio}
                            for p in curve_points
                        ])
                        await db.execute(
                            text(
                                """
                                INSERT INTO video_retention_curves
                                    (id, video_id, youtube_video_id, data_points, peak_moments, drop_off_points, pulled_at)
                                VALUES
                                    (gen_random_uuid(), :video_id, :yt_id, :points::jsonb, :peaks::jsonb, :drops::jsonb, now())
                                ON CONFLICT (video_id) DO NOTHING
                                """
                            ),
                            {
                                "video_id": video_id,
                                "yt_id": video_meta.youtube_id,
                                "points": points_json,
                                "peaks": json.dumps(peaks),
                                "drops": json.dumps(drops),
                            },
                        )

                synced += 1

            except Exception as exc:
                logger.warning(f"[sync_analytics] Failed for video {video_meta.youtube_id}: {exc}")
                continue

        # 3. Fetch channel daily stats for last 7 days
        daily_stats = await fetcher.fetch_channel_daily_stats(start_date, end_date)
        import json as _json
        for day in daily_stats:
            try:
                await db.execute(
                    text(
                        """
                        INSERT INTO channel_analytics_daily
                            (id, youtube_account_id, channel_id, date,
                             total_views, total_watch_time_minutes, subscribers_net, top_videos)
                        VALUES
                            (gen_random_uuid(), :account_id, :channel_id, :date,
                             :views, :watch_time, :subs_net, '[]'::jsonb)
                        ON CONFLICT (channel_id, date) DO UPDATE SET
                            total_views = EXCLUDED.total_views,
                            total_watch_time_minutes = EXCLUDED.total_watch_time_minutes,
                            subscribers_net = EXCLUDED.subscribers_net
                        """
                    ),
                    {
                        "account_id": youtube_account_id,
                        "channel_id": channel_id,
                        "date": day.date,
                        "views": day.views,
                        "watch_time": day.watch_time_minutes,
                        "subs_net": day.subscribers_net,
                    },
                )
            except Exception as exc:
                logger.warning(f"[sync_analytics] Daily stats insert failed for {day.date}: {exc}")

        await db.commit()
        logger.info(f"[sync_analytics] Done. Synced {synced} videos for {channel_id}")

        # 4. Trigger DNA update
        update_content_dna.delay(youtube_account_id)

        # 5. Check if weekly report needed (Monday)
        if date.today().weekday() == 0:
            generate_weekly_insight_report.delay(youtube_account_id)

        return {"status": "ok", "synced_videos": synced}


async def _update_content_dna_async(youtube_account_id: str) -> dict[str, Any]:
    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal
    from app.services.analytics.ai_insight_generator import AIInsightGenerator
    from app.services.analytics.content_dna_builder import ContentDNABuilder

    async with AsyncSessionLocal() as db:
        # Load account
        result = await db.execute(
            text("SELECT * FROM youtube_accounts WHERE id = :id"),
            {"id": youtube_account_id},
        )
        account = result.fetchone()
        if not account:
            return {"status": "error"}

        channel_id: str = account._mapping["channel_id"]

        # Load existing DNA
        existing_result = await db.execute(
            text("SELECT * FROM content_dna_models WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        existing = existing_result.fetchone()

        # Count current analyzed videos
        count_result = await db.execute(
            text(
                """
                SELECT COUNT(DISTINCT va.video_id)
                FROM video_analytics va
                JOIN videos v ON v.id = va.video_id
                JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
                WHERE ya.channel_id = :cid
                """
            ),
            {"cid": channel_id},
        )
        current_count = count_result.scalar() or 0

        # Only update if 5+ new videos since last run
        last_analyzed = existing._mapping["videos_analyzed"] if existing else 0
        if current_count - last_analyzed < 5 and existing is not None:
            logger.info(f"[update_dna] Skip: only {current_count - last_analyzed} new videos")
            return {"status": "skip"}

        ai = AIInsightGenerator()
        builder = ContentDNABuilder(db, ai_generator=ai)

        try:
            dna = await builder.analyze_channel_performance(channel_id)
        except ValueError as exc:
            logger.info(f"[update_dna] Insufficient data: {exc}")
            return {"status": "insufficient_data", "message": str(exc)}

        import json

        if existing:
            await db.execute(
                text(
                    """
                    UPDATE content_dna_models SET
                        viral_score_weights = :weights::jsonb,
                        top_performing_patterns = :patterns::jsonb,
                        game_performance = :games::jsonb,
                        underperforming_patterns = :under::jsonb,
                        confidence_score = :confidence,
                        videos_analyzed = :count,
                        last_updated = now()
                    WHERE channel_id = :channel_id
                    """
                ),
                {
                    "weights": json.dumps(dna["viral_score_weights"]),
                    "patterns": json.dumps(dna["top_performing_patterns"]),
                    "games": json.dumps(dna["game_performance"]),
                    "under": json.dumps(dna["underperforming_patterns"]),
                    "confidence": dna["confidence_score"],
                    "count": dna["videos_analyzed"],
                    "channel_id": channel_id,
                },
            )
        else:
            await db.execute(
                text(
                    """
                    INSERT INTO content_dna_models
                        (id, youtube_account_id, channel_id, niche, sub_niches,
                         viral_score_weights, top_performing_patterns, game_performance,
                         underperforming_patterns, confidence_score, videos_analyzed, last_updated)
                    VALUES
                        (gen_random_uuid(), :account_id, :channel_id, :niche, :sub_niches::jsonb,
                         :weights::jsonb, :patterns::jsonb, :games::jsonb,
                         :under::jsonb, :confidence, :count, now())
                    """
                ),
                {
                    "account_id": youtube_account_id,
                    "channel_id": channel_id,
                    "niche": dna.get("niche", "gaming"),
                    "sub_niches": json.dumps(dna.get("sub_niches", [])),
                    "weights": json.dumps(dna["viral_score_weights"]),
                    "patterns": json.dumps(dna["top_performing_patterns"]),
                    "games": json.dumps(dna["game_performance"]),
                    "under": json.dumps(dna["underperforming_patterns"]),
                    "confidence": dna["confidence_score"],
                    "count": dna["videos_analyzed"],
                },
            )

        await db.commit()
        logger.info(f"[update_dna] Updated for {channel_id}, confidence={dna['confidence_score']:.2f}")
        return {"status": "ok", "confidence": dna["confidence_score"]}


async def _generate_weekly_report_async(youtube_account_id: str) -> dict[str, Any]:
    import json
    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal
    from app.services.analytics.ai_insight_generator import AIInsightGenerator
    from app.services.notification import NotificationService

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT ya.*, u.email, u.name FROM youtube_accounts ya JOIN users u ON u.id = ya.user_id WHERE ya.id = :id"),
            {"id": youtube_account_id},
        )
        account = result.fetchone()
        if not account:
            return {"status": "error"}

        account_dict = dict(account._mapping)
        channel_id = account_dict["channel_id"]
        channel_name = account_dict.get("channel_name", "Your Channel")

        today = date.today()
        week_start = today - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        # Week stats
        week_result = await db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(total_views), 0) AS views,
                    COALESCE(SUM(total_watch_time_minutes), 0) AS watch_time,
                    COALESCE(SUM(subscribers_net), 0) AS subs_net
                FROM channel_analytics_daily
                WHERE channel_id = :cid AND date >= :start AND date <= :end
                """
            ),
            {"cid": channel_id, "start": week_start, "end": today},
        )
        week_row = week_result.fetchone()
        week_stats = dict(week_row._mapping) if week_row else {}

        prev_result = await db.execute(
            text(
                """
                SELECT COALESCE(SUM(total_views), 0) AS views
                FROM channel_analytics_daily
                WHERE channel_id = :cid AND date >= :start AND date < :end
                """
            ),
            {"cid": channel_id, "start": prev_week_start, "end": week_start},
        )
        prev_row = prev_result.fetchone()
        prev_stats = dict(prev_row._mapping) if prev_row else {"views": 0}

        # Unclipped potential
        unclipped_result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM videos v
                JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
                LEFT JOIN clips c ON c.video_id = v.id
                WHERE ya.channel_id = :cid AND v.duration_seconds > 600
                GROUP BY v.id HAVING COUNT(c.id) = 0
                """
            ),
            {"cid": channel_id},
        )
        unclipped_count = len(unclipped_result.fetchall())

        ai = AIInsightGenerator()
        report_data = await ai.generate_weekly_report(
            channel_name=channel_name,
            week_stats={"views": int(week_stats.get("views", 0)), "watch_time_minutes": float(week_stats.get("watch_time", 0)), "subscribers_net": int(week_stats.get("subs_net", 0))},
            prev_week_stats={"views": int(prev_stats.get("views", 0))},
            top_videos=[],
            unclipped_count=unclipped_count,
        )

        views_change_pct = None
        prev_views = int(prev_stats.get("views", 0))
        curr_views = int(week_stats.get("views", 0))
        if prev_views > 0:
            views_change_pct = round((curr_views - prev_views) / prev_views * 100, 1)

        # Upsert report
        await db.execute(
            text(
                """
                INSERT INTO weekly_insight_reports
                    (id, youtube_account_id, channel_id, week_start, week_end,
                     summary_text, key_wins, key_issues, recommendations,
                     top_clip_type, views_change_pct, subscribers_change,
                     estimated_viral_potential, raw_data_snapshot, generated_at)
                VALUES
                    (gen_random_uuid(), :account_id, :channel_id, :week_start, :week_end,
                     :summary, :wins::jsonb, :issues::jsonb, :recs::jsonb,
                     :clip_type, :views_pct, :subs_change,
                     '{}'::jsonb, :raw::jsonb, now())
                ON CONFLICT (channel_id, week_start) DO UPDATE SET
                    summary_text = EXCLUDED.summary_text,
                    key_wins = EXCLUDED.key_wins,
                    key_issues = EXCLUDED.key_issues,
                    recommendations = EXCLUDED.recommendations,
                    generated_at = now()
                """
            ),
            {
                "account_id": youtube_account_id,
                "channel_id": channel_id,
                "week_start": week_start,
                "week_end": today,
                "summary": report_data.get("summary", ""),
                "wins": json.dumps(report_data.get("wins", [])),
                "issues": json.dumps(report_data.get("issues", [])),
                "recs": json.dumps(report_data.get("recommendations", [])),
                "clip_type": report_data.get("best_performing_content", ""),
                "views_pct": views_change_pct,
                "subs_change": int(week_stats.get("subs_net", 0)),
                "raw": json.dumps({"week_stats": week_stats, "prev_week_stats": prev_stats}),
            },
        )
        await db.commit()
        logger.info(f"[weekly_report] Generated for {channel_id}")

        # Notify
        try:
            notifier = NotificationService()
            summary = report_data.get("summary", "")
            await notifier.send_telegram(
                f"📋 <b>Laporan Mingguan {channel_name}</b>\n\n{summary}\n\n"
                f"👉 Buka dashboard untuk detail lengkap."
            )
        except Exception as exc:
            logger.warning(f"[weekly_report] Notification failed: {exc}")

        return {"status": "ok"}
