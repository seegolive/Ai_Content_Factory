"""Tests for WhisperTranscriptionService."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services.transcription import TranscriptResult, WhisperTranscriptionService


def test_transcript_result_word_count():
    from app.services.transcription import TranscriptSegment, TranscriptResult

    result = TranscriptResult(
        full_text="hello world this is a test",
        segments=[],
        language="en",
        duration=10.0,
        word_count=6,
    )
    assert result.word_count == 6


@pytest.mark.asyncio
async def test_transcribe_missing_file():
    """transcribe() on a non-existent file should raise FileNotFoundError."""
    with patch.object(WhisperTranscriptionService, "_load_model"):
        service = WhisperTranscriptionService.__new__(WhisperTranscriptionService)
        WhisperTranscriptionService._model = None

        with patch.object(service, "_transcribe_sync", side_effect=FileNotFoundError("not found")):
            with pytest.raises(FileNotFoundError):
                await service.transcribe("/nonexistent/path/video.mp4")


@pytest.mark.asyncio
async def test_transcribe_returns_result():
    """transcribe() should return a TranscriptResult when model succeeds."""
    from app.services.transcription import TranscriptSegment

    mock_result = TranscriptResult(
        full_text="Hello world",
        segments=[TranscriptSegment(id=0, start=0.0, end=5.0, text="Hello world", confidence=-0.2)],
        language="en",
        duration=5.0,
        word_count=2,
    )

    with patch.object(WhisperTranscriptionService, "_load_model"):
        service = WhisperTranscriptionService.__new__(WhisperTranscriptionService)
        WhisperTranscriptionService._model = MagicMock()

        with patch.object(service, "_transcribe_sync", return_value=mock_result):
            result = await service.transcribe("/fake/video.mp4")

    assert result.full_text == "Hello world"
    assert result.language == "en"
    assert len(result.segments) == 1
