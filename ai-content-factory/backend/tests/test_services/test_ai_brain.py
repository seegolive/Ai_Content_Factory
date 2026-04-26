"""Tests for AIBrainService."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import AIBrainService, ClipSuggestion
from app.services.transcription import TranscriptResult, TranscriptSegment


def make_transcript() -> TranscriptResult:
    segments = [
        TranscriptSegment(id=i, start=float(i * 10), end=float(i * 10 + 9), text=f"Segment {i} text", confidence=-0.3)
        for i in range(5)
    ]
    return TranscriptResult(
        full_text=" ".join(s.text for s in segments),
        segments=segments,
        language="en",
        duration=50.0,
        word_count=20,
    )


@pytest.mark.asyncio
async def test_parse_valid_response():
    """_parse_clip_suggestions should return sorted ClipSuggestion list."""
    service = AIBrainService.__new__(AIBrainService)

    mock_json = json.dumps({
        "clips": [
            {
                "start_time": 0.0,
                "end_time": 45.0,
                "viral_score": 75,
                "titles": ["Title A", "Title B", "Title C"],
                "hook_text": "You won't believe this",
                "description": "Great content here",
                "hashtags": ["viral", "tips"],
                "thumbnail_prompt": "person looking shocked",
                "reason": "Strong hook",
            },
            {
                "start_time": 10.0,
                "end_time": 40.0,
                "viral_score": 90,
                "titles": ["High score clip"],
                "hook_text": "This changes everything",
                "description": "Must watch",
                "hashtags": ["trending"],
                "thumbnail_prompt": "energetic person",
                "reason": "Very high virality",
            },
        ]
    })

    clips = service._parse_clip_suggestions(mock_json)
    assert len(clips) == 2
    # Sorted by viral_score descending
    assert clips[0].viral_score == 90
    assert clips[1].viral_score == 75


@pytest.mark.asyncio
async def test_parse_invalid_json_returns_empty():
    """Malformed JSON should return empty list, not raise."""
    service = AIBrainService.__new__(AIBrainService)
    clips = service._parse_clip_suggestions("not valid json {{{")
    assert clips == []


@pytest.mark.asyncio
@patch("app.services.ai_brain.AIBrainService._call_openrouter")
async def test_analyze_transcript_calls_openrouter(mock_call):
    """analyze_transcript should call OpenRouter and return AIAnalysisResult."""
    mock_call.return_value = {
        "content": json.dumps({"clips": []}),
        "model": "anthropic/claude-sonnet-4-5",
        "tokens_used": 500,
    }

    service = AIBrainService.__new__(AIBrainService)
    import httpx
    service._client = AsyncMock()

    transcript = make_transcript()
    result = await service.analyze_transcript(transcript)

    assert result.clips == []
    assert result.model_used == "anthropic/claude-sonnet-4-5"
    assert result.tokens_used == 500
    mock_call.assert_called_once()
