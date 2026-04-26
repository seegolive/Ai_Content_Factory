"""Whisper-based local transcription service using faster-whisper."""
import asyncio
from dataclasses import dataclass, field
from functools import partial
from typing import List, Optional

from loguru import logger

from app.core.config import settings


@dataclass
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    confidence: float


@dataclass
class TranscriptResult:
    full_text: str
    segments: List[TranscriptSegment]
    language: str
    duration: float
    word_count: int


class WhisperTranscriptionService:
    """Load faster-whisper once, reuse for all transcription tasks."""

    _model = None  # Class-level singleton

    def __init__(self):
        self._ensure_model()

    def _ensure_model(self):
        if WhisperTranscriptionService._model is None:
            self._load_model()

    def _load_model(self):
        """Load model — called once at startup."""
        try:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading Whisper model '{settings.WHISPER_MODEL}' "
                f"on {settings.WHISPER_DEVICE} ({settings.WHISPER_COMPUTE_TYPE})"
            )
            WhisperTranscriptionService._model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
            logger.info("Whisper model loaded successfully.")
        except RuntimeError as e:
            if "CUDA" in str(e) or "cuda" in str(e):
                logger.warning(f"CUDA unavailable ({e}), falling back to CPU with medium model")
                from faster_whisper import WhisperModel
                WhisperTranscriptionService._model = WhisperModel(
                    "medium",
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise

    def _transcribe_sync(self, video_path: str, language: Optional[str]) -> TranscriptResult:
        """Run synchronous transcription (called in thread pool)."""
        model = WhisperTranscriptionService._model
        if model is None:
            raise RuntimeError("Whisper model not loaded")

        segments_iter, info = model.transcribe(
            video_path,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
        )

        segments: List[TranscriptSegment] = []
        full_texts: List[str] = []

        for i, seg in enumerate(segments_iter):
            confidence = float(getattr(seg, "avg_logprob", 0.0))
            segments.append(
                TranscriptSegment(
                    id=i,
                    start=float(seg.start),
                    end=float(seg.end),
                    text=seg.text.strip(),
                    confidence=confidence,
                )
            )
            full_texts.append(seg.text.strip())

        full_text = " ".join(full_texts)

        return TranscriptResult(
            full_text=full_text,
            segments=segments,
            language=info.language,
            duration=float(info.duration),
            word_count=len(full_text.split()),
        )

    async def transcribe(self, video_path: str, language: Optional[str] = None) -> TranscriptResult:
        """Non-blocking transcription using thread pool executor."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, partial(self._transcribe_sync, video_path, language)
            )
            logger.info(
                f"Transcription complete: {result.word_count} words, "
                f"language={result.language}, duration={result.duration:.1f}s"
            )
            return result
        except MemoryError:
            logger.error("Out of memory during transcription — falling back to CPU")
            # Reload with smaller model on CPU
            from faster_whisper import WhisperModel
            WhisperTranscriptionService._model = WhisperModel("medium", device="cpu", compute_type="int8")
            return await self.transcribe(video_path, language)
        except FileNotFoundError:
            raise FileNotFoundError(f"Video file not found: {video_path}")
        except Exception as e:
            logger.exception(f"Transcription failed for {video_path}: {e}")
            raise
