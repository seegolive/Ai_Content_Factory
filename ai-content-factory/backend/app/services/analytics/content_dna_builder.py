"""Content DNA Builder.

Analyzes historical channel performance to build a learning model
(Content DNA) that makes viral scoring more accurate for this specific channel.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.models import VideoOpportunity


# ── Game title extraction helpers ────────────────────────────────────────────

KNOWN_GAMES = [
    "Battlefield 6",
    "Battlefield",
    "Kingdom Come Deliverance II",
    "Kingdom Come",
    "Arc Raiders",
    "Warzone",
    "PUBG",
    "Valorant",
    "CS2",
    "Minecraft",
    "GTA",
    "Fortnite",
    "Apex Legends",
    "Free Fire",
    "Mobile Legends",
]


def _extract_game_from_title(title: str) -> Optional[str]:
    """Try to extract game name from video title."""
    title_lower = title.lower()
    for game in KNOWN_GAMES:
        if game.lower() in title_lower:
            return game
    return None


def _calculate_confidence(videos_analyzed: int) -> float:
    """Confidence score: 0.3 at 10 videos, 0.7 at 50, 0.9 at 100+."""
    if videos_analyzed < 10:
        return 0.0
    if videos_analyzed >= 100:
        return 0.9
    if videos_analyzed >= 50:
        return 0.5 + (videos_analyzed - 50) / 50 * 0.4
    return 0.2 + (videos_analyzed - 10) / 40 * 0.3


# ── Main builder ─────────────────────────────────────────────────────────────


class ContentDNABuilder:
    """Builds and updates Content DNA models from historical analytics data."""

    MIN_VIDEOS_FOR_ANALYSIS = 10

    def __init__(self, db: AsyncSession, ai_generator: Any = None):
        self._db = db
        self._ai = ai_generator  # Optional AIInsightGenerator

    async def analyze_channel_performance(self, channel_id: str) -> dict[str, Any]:
        """
        Full analysis pipeline. Returns the DNA dict to be stored in DB.
        Raises ValueError if insufficient data.
        """
        from app.models.video import Video  # local import to avoid circular
        from sqlalchemy.dialects.postgresql import JSONB

        # ── Load analytics data ──────────────────────────────────────────────
        analytics_rows = await self._load_analytics(channel_id)
        if len(analytics_rows) < self.MIN_VIDEOS_FOR_ANALYSIS:
            raise ValueError(
                f"Insufficient data: need {self.MIN_VIDEOS_FOR_ANALYSIS} videos, "
                f"got {len(analytics_rows)}"
            )

        # ── Compute views_per_day for each video ─────────────────────────────
        now = datetime.now(tz=timezone.utc)
        enriched = []
        for row in analytics_rows:
            published_at = row["published_at"]
            if published_at and hasattr(published_at, "tzinfo") and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            days_live = max(1, (now - published_at).days) if published_at else 30
            vpd = row["total_views"] / days_live
            enriched.append({**row, "views_per_day": vpd})

        enriched.sort(key=lambda x: x["views_per_day"], reverse=True)
        top_quartile = enriched[: max(1, len(enriched) // 4)]
        bottom_quartile = enriched[-(max(1, len(enriched) // 4)) :]

        # ── Title pattern analysis ───────────────────────────────────────────
        title_patterns = self._analyze_titles(top_quartile, bottom_quartile)

        # ── Upload timing analysis ───────────────────────────────────────────
        timing = self._analyze_timing(enriched)

        # ── Game performance ─────────────────────────────────────────────────
        game_performance = self._analyze_game_performance(enriched)

        # ── Optimal clip duration from avg view duration ─────────────────────
        avg_durations = [
            r["avg_view_duration_seconds"]
            for r in top_quartile
            if r.get("avg_view_duration_seconds")
        ]
        optimal_clip_seconds = int(sum(avg_durations) / len(avg_durations)) if avg_durations else 90

        patterns: dict[str, Any] = {
            "title_patterns": title_patterns["winning"],
            "avoid_patterns": title_patterns["losing"],
            "hook_durations": {"optimal_seconds": min(optimal_clip_seconds // 3, 15)},
            "best_clip_duration": {
                "min": max(30, optimal_clip_seconds - 30),
                "max": optimal_clip_seconds + 60,
                "optimal": optimal_clip_seconds,
            },
            "best_upload_days": timing["best_days"],
            "best_upload_hours": timing["best_hours"],
        }

        # ── AI Enhancement ───────────────────────────────────────────────────
        ai_insights: dict[str, Any] = {}
        if self._ai:
            try:
                stats_summary = self._build_stats_summary(top_quartile, bottom_quartile)
                ai_insights = await self._ai.analyze_content_dna(channel_id, stats_summary)
                logger.info(f"[ContentDNA] AI insights generated for {channel_id}")
            except Exception as exc:
                logger.warning(f"[ContentDNA] AI enhancement failed: {exc}")

        confidence = _calculate_confidence(len(enriched))

        return {
            "niche": "gaming",
            "sub_niches": list(game_performance.keys())[:5],
            "viral_score_weights": self._calibrate_weights(top_quartile),
            "top_performing_patterns": {**patterns, **(ai_insights.get("clip_strategy", {}))},
            "game_performance": game_performance,
            "underperforming_patterns": {
                "titles": title_patterns["losing"],
                "ai_avoid": ai_insights.get("title_patterns", {}).get("losing", []),
            },
            "confidence_score": confidence,
            "videos_analyzed": len(enriched),
        }

    async def _load_analytics(self, channel_id: str) -> list[dict[str, Any]]:
        """Load aggregated analytics per video for this channel."""
        sql = text(
            """
            SELECT
                v.id AS video_id,
                v.title,
                v.duration_seconds,
                v.created_at AS published_at,
                COALESCE(SUM(va.views), 0) AS total_views,
                COALESCE(AVG(va.avg_view_duration_seconds), 0) AS avg_view_duration_seconds,
                COALESCE(AVG(va.impression_ctr), 0) AS avg_ctr,
                COALESCE(SUM(va.watch_time_minutes), 0) AS total_watch_time,
                MAX(va.snapshot_date) AS last_snapshot
            FROM videos v
            LEFT JOIN video_analytics va ON va.video_id = v.id
            LEFT JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            WHERE ya.channel_id = :channel_id
            GROUP BY v.id
            HAVING COALESCE(SUM(va.views), 0) > 0
            ORDER BY total_views DESC
            """
        )
        result = await self._db.execute(sql, {"channel_id": channel_id})
        return [dict(r._mapping) for r in result.fetchall()]

    def _analyze_titles(
        self,
        top: list[dict],
        bottom: list[dict],
    ) -> dict[str, list[str]]:
        """Extract winning vs losing title patterns."""
        top_words = Counter()
        bottom_words = Counter()

        for item in top:
            words = re.findall(r"\b[A-Z]{2,}\b|[A-Za-z]{4,}", item.get("title", ""))
            top_words.update(w.upper() for w in words)

        for item in bottom:
            words = re.findall(r"\b[A-Z]{2,}\b|[A-Za-z]{4,}", item.get("title", ""))
            bottom_words.update(w.upper() for w in words)

        # Words that appear in top but not in bottom
        winning = [
            w for w, c in top_words.most_common(20)
            if c >= 2 and bottom_words.get(w, 0) < c
        ]
        losing = [
            w for w, c in bottom_words.most_common(10)
            if c >= 2 and top_words.get(w, 0) < c
        ]
        return {"winning": winning[:10], "losing": losing[:5]}

    def _analyze_timing(self, videos: list[dict]) -> dict[str, Any]:
        """Correlate publish day/hour with performance."""
        day_scores: defaultdict[str, list[float]] = defaultdict(list)
        hour_scores: defaultdict[int, list[float]] = defaultdict(list)

        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        for v in videos:
            pub = v.get("published_at")
            if not pub:
                continue
            vpd = v.get("views_per_day", 0)
            day_scores[day_names[pub.weekday()]].append(vpd)
            hour_scores[pub.hour].append(vpd)

        best_days = sorted(
            day_scores.keys(),
            key=lambda d: sum(day_scores[d]) / len(day_scores[d]) if day_scores[d] else 0,
            reverse=True,
        )[:3]

        best_hours = sorted(
            hour_scores.keys(),
            key=lambda h: sum(hour_scores[h]) / len(hour_scores[h]) if hour_scores[h] else 0,
            reverse=True,
        )[:4]

        return {"best_days": best_days, "best_hours": best_hours}

    def _analyze_game_performance(self, videos: list[dict]) -> dict[str, Any]:
        """Group videos by game and compute avg stats."""
        game_data: defaultdict[str, list[dict]] = defaultdict(list)
        for v in videos:
            game = _extract_game_from_title(v.get("title", ""))
            if game:
                game_data[game].append(v)

        result: dict[str, Any] = {}
        for game, items in game_data.items():
            if len(items) < 2:
                continue
            avg_views = sum(i["total_views"] for i in items) / len(items)
            avg_ctr = sum(i["avg_ctr"] for i in items) / len(items)
            result[game] = {
                "avg_views": round(avg_views, 1),
                "avg_ctr": round(avg_ctr, 4),
                "sample_size": len(items),
            }
        return result

    def _calibrate_weights(self, top_videos: list[dict]) -> dict[str, float]:
        """Adjust viral score weights for this channel's niche (gaming).
        Gaming channels generally perform better on hook_strength + emotional_impact.
        """
        # For gaming Indonesia, hook and emotional weight more
        return {
            "emotional_impact": 0.28,
            "hook_strength": 0.32,
            "info_density": 0.12,
            "relatability": 0.18,
            "cta_potential": 0.10,
        }

    def _build_stats_summary(
        self, top: list[dict], bottom: list[dict]
    ) -> str:
        """Build a compact stats summary string for AI prompts."""
        lines = [
            f"Top performers ({len(top)} videos):",
            *[f"  - '{v['title'][:60]}' | {v['total_views']} views | {v['views_per_day']:.1f} vpd" for v in top[:5]],
            f"\nUnderperformers ({len(bottom)} videos):",
            *[f"  - '{v['title'][:60]}' | {v['total_views']} views | {v['views_per_day']:.1f} vpd" for v in bottom[:5]],
        ]
        return "\n".join(lines)

    async def calculate_viral_score_weights(self, channel_id: str) -> dict[str, float]:
        """Return calibrated viral score weights for this channel."""
        rows = await self._load_analytics(channel_id)
        if not rows:
            return {
                "emotional_impact": 0.25,
                "hook_strength": 0.25,
                "info_density": 0.20,
                "relatability": 0.20,
                "cta_potential": 0.10,
            }
        top = sorted(rows, key=lambda r: r["total_views"], reverse=True)[: len(rows) // 4 or 1]
        return self._calibrate_weights(top)

    async def identify_unclipped_viral_potential(
        self, channel_id: str
    ) -> list[VideoOpportunity]:
        """Find videos with high potential that haven't been clipped yet."""
        sql = text(
            """
            SELECT
                v.id,
                v.title,
                v.duration_seconds,
                v.created_at,
                COALESCE(SUM(va.views), 0) AS total_views,
                COUNT(c.id) AS clip_count,
                COUNT(vrc.id) AS has_retention,
                COALESCE(json_agg(vrc.peak_moments) FILTER (WHERE vrc.peak_moments IS NOT NULL), '[]') AS all_peaks
            FROM videos v
            LEFT JOIN youtube_accounts ya ON ya.id = v.youtube_account_id
            LEFT JOIN video_analytics va ON va.video_id = v.id
            LEFT JOIN clips c ON c.video_id = v.id
            LEFT JOIN video_retention_curves vrc ON vrc.video_id = v.id
            WHERE ya.channel_id = :channel_id
              AND v.duration_seconds > 600
              AND v.status = 'done'
            GROUP BY v.id
            HAVING COUNT(c.id) = 0
            ORDER BY total_views DESC
            LIMIT 20
            """
        )
        result = await self._db.execute(sql, {"channel_id": channel_id})
        rows = result.fetchall()

        opportunities: list[VideoOpportunity] = []
        for row in rows:
            r = dict(row._mapping)
            game = _extract_game_from_title(r.get("title", ""))
            duration = r.get("duration_seconds", 0) or 0
            views = r.get("total_views", 0) or 0
            has_retention = bool(r.get("has_retention", 0))

            # Scoring heuristic
            score = min(100, views / 10 + (duration / 60) * 0.5 + (20 if has_retention else 0))

            estimated_clips = max(3, int(duration / 300))  # ~1 clip per 5 min
            peak_count = len(r.get("all_peaks", []) or [])

            opportunities.append(
                VideoOpportunity(
                    video_id=str(r["id"]),
                    youtube_video_id="",  # filled by caller if needed
                    title=r.get("title", ""),
                    duration_seconds=duration,
                    published_at=r.get("created_at", datetime.now(tz=timezone.utc)),
                    game_name=game,
                    viral_potential_score=round(score, 1),
                    estimated_clips=estimated_clips,
                    peak_moments_count=peak_count,
                    has_retention_data=has_retention,
                    recommendation=(
                        f"Game {game} perform tinggi di channel ini"
                        if game
                        else "Video panjang dengan potential clips tinggi"
                    ),
                )
            )

        return sorted(opportunities, key=lambda o: o.viral_potential_score, reverse=True)
