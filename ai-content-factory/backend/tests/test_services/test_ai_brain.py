"""Tests for AIBrainService — multi-model fallback (Groq → Gemini Flash → GPT-4o-mini)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ai_brain import AIBrainService, AIAnalysisResult, ClipSuggestion
from app.services.transcription import TranscriptResult, TranscriptSegment


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_transcript(lang: str = "id") -> TranscriptResult:
    segments = [
        TranscriptSegment(
            id=i, start=float(i * 10), end=float(i * 10 + 9),
            text=f"Wah gila segment {i}, ez gg!", confidence=-0.3,
        )
        for i in range(5)
    ]
    return TranscriptResult(
        full_text=" ".join(s.text for s in segments),
        segments=segments,
        language=lang,
        duration=50.0,
        word_count=20,
    )


def make_valid_response_json(viral_score: int = 85, moment_type: str = "clutch") -> str:
    return json.dumps({
        "clips": [
            {
                "start_time": 0.0,
                "end_time": 45.0,
                "viral_score": viral_score,
                "moment_type": moment_type,
                "titles": ["Judul A", "Judul B", "Judul C"],
                "hook_text": "Gak nyangka bisa survive...",
                "description": "Momen clutch terbaik di Battlefield 6",
                "hashtags": ["gaming", "battlefield6", "indonesia"],
                "thumbnail_prompt": "gamer shocked face",
                "reason": "Reaksi ekspresif + momen langka",
            }
        ],
        "summary": "Stream Battlefield 6 penuh momen epic",
    })


def _make_httpx_response(content: str, status: int = 200, model: str = "llama-3.3-70b-versatile") -> MagicMock:
    """Build a mock httpx.Response for a chat/completions call."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "model": model,
        "usage": {"total_tokens": 512},
    }
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ── Unit: _parse_clip_suggestions ────────────────────────────────────────────

def test_parse_valid_response_sorted_desc():
    """_parse_clip_suggestions returns ClipSuggestion list sorted by viral_score DESC."""
    service = AIBrainService.__new__(AIBrainService)
    data = {
        "clips": [
            {"start_time": 0.0, "end_time": 45.0, "viral_score": 70, "moment_type": "funny",
             "titles": ["T1"], "hook_text": "Hook", "description": "Desc",
             "hashtags": ["tag"], "thumbnail_prompt": "", "reason": ""},
            {"start_time": 10.0, "end_time": 40.0, "viral_score": 90, "moment_type": "clutch",
             "titles": ["T2"], "hook_text": "Hook2", "description": "Desc2",
             "hashtags": ["tag2"], "thumbnail_prompt": "", "reason": ""},
        ]
    }
    clips = service._parse_clip_suggestions(data)
    assert len(clips) == 2
    assert clips[0].viral_score == 90
    assert clips[0].moment_type == "clutch"
    assert clips[1].viral_score == 70


def test_parse_empty_clips():
    service = AIBrainService.__new__(AIBrainService)
    clips = service._parse_clip_suggestions({"clips": []})
    assert clips == []


def test_parse_malformed_item_skipped():
    """Items missing required fields should be skipped without raising."""
    service = AIBrainService.__new__(AIBrainService)
    data = {
        "clips": [
            {"start_time": "bad", "end_time": 45.0, "viral_score": 80},  # bad start_time
            {"start_time": 0.0, "end_time": 30.0, "viral_score": 75, "moment_type": "epic",
             "titles": ["T"], "hook_text": "", "description": "", "hashtags": [], "thumbnail_prompt": "", "reason": ""},
        ]
    }
    clips = service._parse_clip_suggestions(data)
    assert len(clips) == 1
    assert clips[0].viral_score == 75


def test_try_parse_strips_markdown_fences():
    service = AIBrainService.__new__(AIBrainService)
    content = '```json\n{"clips": []}\n```'
    result = service._try_parse_clips(content)
    assert result == {"clips": []}


def test_try_parse_invalid_json_returns_none():
    service = AIBrainService.__new__(AIBrainService)
    assert service._try_parse_clips("not json {{{") is None


# ── Integration: _call_with_fallback ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_groq_success_no_other_provider_tried():
    """If Groq succeeds, other providers should NOT be called."""
    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]

    call_log: list[str] = []

    async def mock_call(provider, msgs, max_tokens):
        call_log.append(provider["name"])
        if provider["name"] == "Groq":
            return {
                "content": '{"ok": true}',
                "model": "llama-3.3-70b-versatile",
                "tokens_used": 100,
                "provider_name": "Groq",
            }
        raise AssertionError("Should not reach other providers")

    with patch.object(service, "_call_provider", side_effect=mock_call):
        content, provider_name, model, tokens = await service._call_with_fallback(messages)

    assert provider_name == "Groq"
    assert call_log == ["Groq"]


@pytest.mark.asyncio
async def test_fallback_groq_429_falls_to_gemini():
    """If Groq returns 429, should fall through to OpenRouter Gemini Flash."""
    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]

    async def mock_call(provider, msgs, max_tokens):
        if provider["name"] == "Groq":
            resp = MagicMock()
            resp.status_code = 429
            raise httpx.HTTPStatusError("429", request=MagicMock(), response=resp)
        if "Gemini" in provider["name"]:
            return {
                "content": '{"ok": true}',
                "model": "google/gemini-2.0-flash-001",
                "tokens_used": 200,
                "provider_name": provider["name"],
            }
        raise AssertionError("Should not reach GPT-4o-mini")

    with patch.object(service, "_call_provider", side_effect=mock_call):
        content, provider_name, model, tokens = await service._call_with_fallback(messages)

    assert "Gemini" in provider_name
    assert tokens == 200


@pytest.mark.asyncio
async def test_fallback_groq_and_gemini_fail_falls_to_gpt4o_mini():
    """If Groq and Gemini both fail, should use GPT-4o-mini as last resort."""
    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]

    async def mock_call(provider, msgs, max_tokens):
        if "GPT-4o-mini" in provider["name"]:
            return {
                "content": '{"ok": true}',
                "model": "openai/gpt-4o-mini",
                "tokens_used": 300,
                "provider_name": provider["name"],
            }
        resp = MagicMock()
        resp.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)

    with patch.object(service, "_call_provider", side_effect=mock_call):
        content, provider_name, model, tokens = await service._call_with_fallback(messages)

    assert "GPT-4o-mini" in provider_name


@pytest.mark.asyncio
async def test_fallback_all_providers_fail_raises():
    """If ALL providers fail, should raise RuntimeError."""
    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]

    async def mock_call(provider, msgs, max_tokens):
        resp = MagicMock()
        resp.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)

    with patch.object(service, "_call_provider", side_effect=mock_call):
        with pytest.raises(RuntimeError, match="All AI providers failed"):
            await service._call_with_fallback(messages)


@pytest.mark.asyncio
async def test_fallback_skips_provider_with_no_api_key(monkeypatch):
    """Providers with empty api_key should be silently skipped."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]
    called_names: list[str] = []

    async def mock_call(provider, msgs, max_tokens):
        called_names.append(provider["name"])
        return {
            "content": '{"ok": true}',
            "model": provider["model"],
            "tokens_used": 50,
            "provider_name": provider["name"],
        }

    with patch.object(service, "_call_provider", side_effect=mock_call):
        await service._call_with_fallback(messages)

    assert "Groq" not in called_names  # Groq was skipped
    assert len(called_names) == 1  # Only one provider called (Gemini succeeds)


@pytest.mark.asyncio
async def test_fallback_timeout_falls_to_next_provider():
    """TimeoutException should also fall through to next provider."""
    service = AIBrainService()
    messages = [{"role": "user", "content": "test"}]

    async def mock_call(provider, msgs, max_tokens):
        if provider["name"] == "Groq":
            raise httpx.TimeoutException("timeout")
        return {
            "content": '{"ok": true}',
            "model": provider["model"],
            "tokens_used": 150,
            "provider_name": provider["name"],
        }

    with patch.object(service, "_call_provider", side_effect=mock_call):
        content, provider_name, model, tokens = await service._call_with_fallback(messages)

    assert "Groq" not in provider_name


# ── Integration: analyze_transcript ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_transcript_returns_analysis_result():
    """analyze_transcript should parse AI response and return AIAnalysisResult."""
    service = AIBrainService()
    transcript = make_transcript()

    async def mock_fallback(messages, max_tokens=4000):
        return (
            make_valid_response_json(viral_score=85, moment_type="clutch"),
            "Groq",
            "llama-3.3-70b-versatile",
            512,
        )

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        result = await service.analyze_transcript(transcript, game_title="Battlefield 6", channel_name="Seego GG")

    assert isinstance(result, AIAnalysisResult)
    assert len(result.clips) == 1
    assert result.clips[0].viral_score == 85
    assert result.clips[0].moment_type == "clutch"
    assert result.provider_used == "Groq"
    assert result.model_used == "llama-3.3-70b-versatile"
    assert result.tokens_used == 512
    assert result.summary == "Stream Battlefield 6 penuh momen epic"


@pytest.mark.asyncio
async def test_analyze_transcript_retries_on_malformed_json():
    """If first response is malformed JSON, analyze_transcript retries once."""
    service = AIBrainService()
    transcript = make_transcript()

    call_count = 0

    async def mock_fallback(messages, max_tokens=4000):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ("not valid json {{{", "Groq", "llama-3.3-70b-versatile", 100)
        return (
            make_valid_response_json(viral_score=78),
            "Groq",
            "llama-3.3-70b-versatile",
            200,
        )

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        result = await service.analyze_transcript(transcript)

    assert call_count == 2  # First call failed JSON parse, second succeeded
    assert len(result.clips) == 1


@pytest.mark.asyncio
async def test_analyze_transcript_gaming_context_in_prompt():
    """Game title and channel name should appear in the user message sent to AI."""
    service = AIBrainService()
    transcript = make_transcript()
    captured_messages = []

    async def mock_fallback(messages, max_tokens=4000):
        captured_messages.extend(messages)
        return (make_valid_response_json(), "Groq", "llama-3.3-70b-versatile", 100)

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        await service.analyze_transcript(
            transcript,
            game_title="Battlefield 6",
            channel_name="Seego GG",
        )

    user_msg = next(m for m in captured_messages if m["role"] == "user")
    assert "Battlefield 6" in user_msg["content"]
    assert "Seego GG" in user_msg["content"]


@pytest.mark.asyncio
async def test_analyze_transcript_gaming_system_prompt():
    """System prompt should contain Indonesian gaming keywords."""
    service = AIBrainService()
    transcript = make_transcript()
    captured_messages = []

    async def mock_fallback(messages, max_tokens=4000):
        captured_messages.extend(messages)
        return (make_valid_response_json(), "Groq", "llama-3.3-70b-versatile", 100)

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        await service.analyze_transcript(transcript)

    system_msg = next(m for m in captured_messages if m["role"] == "system")
    assert "clutch" in system_msg["content"]
    assert "moment_type" in system_msg["content"]
    assert "Indonesia" in system_msg["content"]


# ── Integration: generate_titles ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_titles_returns_list():
    service = AIBrainService()
    clip_info = {"title": "Epic clutch moment", "moment_type": "clutch"}

    async def mock_fallback(messages, max_tokens=300):
        return ('["Judul 1", "Judul 2", "Judul 3"]', "Groq", "llama-3.3-70b-versatile", 50)

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        titles = await service.generate_titles(clip_info, game_title="Battlefield 6")

    assert titles == ["Judul 1", "Judul 2", "Judul 3"]


@pytest.mark.asyncio
async def test_generate_titles_fallback_on_bad_json():
    """If AI returns non-JSON, generate_titles falls back to clip title."""
    service = AIBrainService()
    clip_info = {"title": "Epic moment", "moment_type": "epic"}

    async def mock_fallback(messages, max_tokens=300):
        return ("not json at all", "Groq", "llama-3.3-70b-versatile", 10)

    with patch.object(service, "_call_with_fallback", side_effect=mock_fallback):
        titles = await service.generate_titles(clip_info)

    assert titles == ["Epic moment"]
