"""
Tests for analytics services.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Retention / Peak Detection ────────────────────────────────────────────────

class TestPeakDetection:
    """Tests for detect_peak_moments() and detect_drop_offs()."""

    @pytest.fixture(autouse=True)
    def import_helpers(self):
        from app.services.analytics.youtube_analytics_fetcher import (
            detect_peak_moments,
            detect_drop_offs,
        )
        self.detect_peaks = detect_peak_moments
        self.detect_drops = detect_drop_offs

    def _make_point(self, elapsed: float, retention: float):
        from app.services.analytics.models import RetentionDataPoint
        return RetentionDataPoint(
            elapsed_ratio=elapsed,
            retention_ratio=retention,
            relative_performance=1.0,
            timestamp_seconds=int(elapsed * 600),
        )

    def _make_flat(self, n: int = 100, value: float = 0.5):
        """Flat retention curve — no peaks or drops."""
        return [self._make_point(i / n, value) for i in range(n + 1)]

    def test_flat_curve_no_peaks(self):
        data = self._make_flat()
        peaks = self.detect_peaks(data)
        assert isinstance(peaks, list)
        # Flat curve should have no significant peaks
        assert len(peaks) == 0

    def test_spike_detected_as_peak(self):
        from app.services.analytics.models import RetentionDataPoint
        data = self._make_flat()
        # Insert a clear spike at index 30
        data[30] = self._make_point(30 / 100, 0.85)
        data[31] = self._make_point(31 / 100, 0.82)
        data[32] = self._make_point(32 / 100, 0.80)
        peaks = self.detect_peaks(data)
        elapsed_ratios = [p["elapsed_ratio"] for p in peaks]
        # Spike at 30% should be detected
        assert any(abs(r - 0.30) < 0.05 for r in elapsed_ratios)

    def test_drop_detected(self):
        data = self._make_flat()
        # Sharp single-step drop > 15% threshold at index 50 (0.5 → 0.3 = 40% drop)
        data[50] = self._make_point(50 / 100, 0.5)
        data[51] = self._make_point(51 / 100, 0.3)
        drops = self.detect_drops(data)
        assert isinstance(drops, list)
        assert len(drops) > 0

    def test_empty_data_returns_empty(self):
        assert self.detect_peaks([]) == []
        assert self.detect_drops([]) == []

    def test_single_point_no_peaks(self):
        data = [self._make_point(0.5, 0.5)]
        assert self.detect_peaks(data) == []
        assert self.detect_drops(data) == []


# ── Content DNA Builder ───────────────────────────────────────────────────────

class TestContentDNABuilder:
    """Tests for ContentDNABuilder._extract_game_from_title() and _calculate_confidence()."""

    @pytest.fixture(autouse=True)
    def import_builder(self):
        from app.services.analytics.content_dna_builder import ContentDNABuilder
        self.ContentDNABuilder = ContentDNABuilder

    def test_extract_known_game(self):
        from app.services.analytics.content_dna_builder import _extract_game_from_title
        game = _extract_game_from_title("Tutorial PUBG Mobile terbaru 2024")
        # KNOWN_GAMES has "PUBG" — function returns first match
        assert game is not None
        assert "PUBG" in game

    def test_extract_another_known_game(self):
        from app.services.analytics.content_dna_builder import _extract_game_from_title
        game = _extract_game_from_title("Cara main Mobile Legends biar gak noob")
        assert game is not None
        assert "Mobile Legends" in game or "MLBB" in game or game.lower().replace(" ", "") in ["mobilelegends", "mlbb"]

    def test_unknown_game_returns_none(self):
        from app.services.analytics.content_dna_builder import _extract_game_from_title
        game = _extract_game_from_title("Video random tanpa nama game apapun xyz123")
        assert game is None

    def test_confidence_increases_with_videos(self):
        from app.services.analytics.content_dna_builder import _calculate_confidence
        conf_10 = _calculate_confidence(10)
        conf_30 = _calculate_confidence(30)
        conf_100 = _calculate_confidence(100)
        assert 0 <= conf_10 <= 100
        assert conf_10 < conf_30 < conf_100
        assert conf_100 <= 100

    def test_confidence_never_exceeds_100(self):
        from app.services.analytics.content_dna_builder import _calculate_confidence
        for n in [1, 10, 50, 100, 500, 1000]:
            assert _calculate_confidence(n) <= 100


# ── AI Insight Generator ──────────────────────────────────────────────────────

class TestAIInsightGenerator:
    """Tests for AIInsightGenerator JSON parsing and fallback logic."""

    @pytest.fixture(autouse=True)
    def import_generator(self):
        from app.services.analytics.ai_insight_generator import AIInsightGenerator
        self.AIInsightGenerator = AIInsightGenerator

    @pytest.mark.asyncio
    async def test_valid_weekly_report_json_parsed(self):
        """generate_weekly_report parses AI response and returns structured dict."""
        from unittest.mock import AsyncMock, patch
        generator = self.AIInsightGenerator()
        mock_result = {
            "summary": "Week was good",
            "wins": ["CTR naik"],
            "issues": ["Watch time turun"],
            "recommendations": [{"priority": "high", "action": "Upload", "reason": "", "expected_impact": ""}],
            "best_performing_content": "clip A",
            "focus_game_next_week": "BF6",
            "clip_opportunity_summary": "good",
        }
        with patch.object(generator, "_call_openrouter", new=AsyncMock(return_value=mock_result)):
            result = await generator.generate_weekly_report("Seego GG", {}, {}, [], 0)
        assert result["summary"] == "Week was good"
        assert len(result["wins"]) == 1
        assert len(result["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_malformed_response_returns_default(self):
        """If _call_openrouter returns None (parse failure), default dict is returned."""
        from unittest.mock import AsyncMock, patch
        from app.services.analytics.ai_insight_generator import _DEFAULT_WEEKLY_REPORT
        generator = self.AIInsightGenerator()
        with patch.object(generator, "_call_openrouter", new=AsyncMock(return_value=None)):
            result = await generator.generate_weekly_report("Seego GG", {}, {}, [], 0)
        assert isinstance(result, dict)
        assert "wins" in result
        assert result["wins"] == _DEFAULT_WEEKLY_REPORT["wins"]

    @pytest.mark.asyncio
    async def test_analyze_content_dna_returns_dict(self):
        """analyze_content_dna returns structured DNA dict."""
        from unittest.mock import AsyncMock, patch
        generator = self.AIInsightGenerator()
        mock_result = {"title_patterns": {}, "hook_insights": {}, "clip_strategy": {}, "audience_insights": {}}
        with patch.object(generator, "_call_openrouter", new=AsyncMock(return_value=mock_result)):
            result = await generator.analyze_content_dna("UCtest", "100 videos analyzed")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_analyze_content_dna_returns_default_on_failure(self):
        """If AI call fails, default DNA is returned."""
        from unittest.mock import AsyncMock, patch
        from app.services.analytics.ai_insight_generator import _DEFAULT_DNA
        generator = self.AIInsightGenerator()
        with patch.object(generator, "_call_openrouter", new=AsyncMock(return_value=None)):
            result = await generator.analyze_content_dna("UCtest", "")
        assert result == _DEFAULT_DNA


# ── YouTube Analytics Fetcher ─────────────────────────────────────────────────

class TestQuotaManagement:
    """Tests for Redis-based quota management in YouTubeAnalyticsFetcher."""

    @pytest.fixture
    def fetcher(self):
        from app.services.analytics.youtube_analytics_fetcher import YouTubeAnalyticsFetcher
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.incrby = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        return YouTubeAnalyticsFetcher(
            channel_id="UCtest123",
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            redis_client=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_quota_check_passes_when_below_limit(self, fetcher):
        """When quota used is 0, _check_quota should return True."""
        fetcher._redis.get = AsyncMock(return_value=b"0")
        result = await fetcher._check_quota(100)
        assert result is True

    @pytest.mark.asyncio
    async def test_quota_check_returns_false_when_exceeded(self, fetcher):
        """When quota would exceed daily limit, _check_quota returns False."""
        fetcher._redis.get = AsyncMock(return_value=b"9999")
        result = await fetcher._check_quota(100)
        assert result is False

    @pytest.mark.asyncio
    async def test_quota_increment_called(self, fetcher):
        """After passing quota check, redis.incrby should be called."""
        fetcher._redis.get = AsyncMock(return_value=b"100")
        await fetcher._check_quota(50)
        fetcher._redis.incrby.assert_called()


# ── Integration-style test for API route (mocked DB) ─────────────────────────

@pytest.mark.asyncio
class TestAnalyticsRouteHelpers:
    """Tests for _require_channel_ownership helper in analytics routes."""

    async def test_raises_404_when_channel_not_owned(self):
        from fastapi import HTTPException
        from app.api.routes.analytics import _require_channel_ownership

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # Not found
        mock_db.execute.return_value = mock_result

        mock_user = MagicMock()
        mock_user.id = "user-uuid-123"

        with pytest.raises(HTTPException) as exc_info:
            await _require_channel_ownership("nonexistent_channel", mock_user, mock_db)
        assert exc_info.value.status_code == 404

    async def test_returns_account_dict_when_owned(self):
        from app.api.routes.analytics import _require_channel_ownership

        mock_db = AsyncMock()
        mock_row = MagicMock()
        mock_row._mapping = {"channel_id": "UC123", "user_id": "user-uuid-123"}
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        mock_user = MagicMock()
        mock_user.id = "user-uuid-123"

        account = await _require_channel_ownership("UC123", mock_user, mock_db)
        assert account["channel_id"] == "UC123"
