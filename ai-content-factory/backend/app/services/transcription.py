"""Whisper-based local transcription service using faster-whisper."""

import asyncio
import os
import threading
from dataclasses import dataclass
from functools import partial
from typing import Callable, List, Optional

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
    _model_lock = threading.Lock()

    def __init__(self):
        self._ensure_model()

    def _ensure_model(self):
        with WhisperTranscriptionService._model_lock:
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
                logger.warning(
                    f"CUDA unavailable ({e}), falling back to CPU with medium model"
                )
                from faster_whisper import WhisperModel

                WhisperTranscriptionService._model = WhisperModel(
                    "medium",
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise

    # Split threshold: videos longer than one chunk get split before transcription
    CHUNK_SECONDS = 1800  # 30 minutes per chunk → ~800MB RAM per chunk, safe for VAD

    def _get_audio_duration(self, video_path: str) -> float:
        """Quick probe of audio duration without loading into RAM."""
        import json
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", video_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            return float(data["format"].get("duration", 0))
        except Exception:
            return 0.0

    def _split_audio_chunks(
        self, video_path: str, total_duration: float, tmp_dir: str
    ) -> List[tuple]:
        """
        Split video audio into 30-min WAV chunks via FFmpeg.
        Returns list of (chunk_path, time_offset_seconds).
        Each chunk is 16kHz mono — exactly what Whisper wants.
        """
        import subprocess

        chunks = []
        start = 0.0
        idx = 0
        while start < total_duration:
            chunk_path = os.path.join(tmp_dir, f"chunk_{idx:04d}.wav")
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-t", str(self.CHUNK_SECONDS),
                "-i", video_path,
                "-ar", "16000",
                "-ac", "1",
                "-vn",
                chunk_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg chunk split failed for chunk {idx}: "
                    f"{result.stderr.decode()[:300]}"
                )
            chunks.append((chunk_path, start))
            start += self.CHUNK_SECONDS
            idx += 1
        logger.info(f"Split audio into {len(chunks)} chunks of {self.CHUNK_SECONDS//60} min each")
        return chunks

    def _transcribe_chunk(
        self,
        chunk_path: str,
        time_offset: float,
        language: Optional[str],
        segment_id_start: int,
    ) -> tuple:
        """
        Transcribe a single audio chunk with large-v3 + VAD (full quality).
        Returns (segments, detected_language, chunk_duration).
        All segment timestamps are adjusted by time_offset.
        """
        model = WhisperTranscriptionService._model
        if model is None:
            raise RuntimeError("Whisper model not loaded")

        segments_iter, info = model.transcribe(
            chunk_path,
            language=language,
            beam_size=1,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            chunk_length=30,
        )

        segments: List[TranscriptSegment] = []
        full_texts: List[str] = []
        for i, seg in enumerate(segments_iter):
            confidence = float(getattr(seg, "avg_logprob", 0.0))
            segments.append(
                TranscriptSegment(
                    id=segment_id_start + i,
                    start=float(seg.start) + time_offset,
                    end=float(seg.end) + time_offset,
                    text=seg.text.strip(),
                    confidence=confidence,
                )
            )
            full_texts.append(seg.text.strip())

        return segments, full_texts, info.language, float(info.duration)

    def _transcribe_sync(
        self,
        video_path: str,
        language: Optional[str],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> TranscriptResult:
        """
        Transcribe video using large-v3 (full quality) for ALL video lengths.
        Videos longer than CHUNK_SECONDS are pre-split into 30-min WAV chunks
        via FFmpeg — each chunk is small enough for VAD without OOM.
        Chunks are processed sequentially, timestamps merged with correct offsets.
        """
        import tempfile
        import shutil

        total_duration = self._get_audio_duration(video_path)
        use_chunked = total_duration > self.CHUNK_SECONDS

        if use_chunked:
            n_chunks = int(total_duration // self.CHUNK_SECONDS) + 1
            logger.info(
                f"Long video detected ({total_duration/3600:.1f}h). "
                f"Splitting into {n_chunks} × {self.CHUNK_SECONDS//60}-min chunks "
                f"for full-quality large-v3 transcription."
            )

        all_segments: List[TranscriptSegment] = []
        all_texts: List[str] = []
        detected_language = language
        last_reported_pct = -1

        tmp_dir = None
        try:
            if use_chunked:
                tmp_dir = tempfile.mkdtemp(prefix="whisper_chunks_")
                chunks = self._split_audio_chunks(video_path, total_duration, tmp_dir)

                for chunk_idx, (chunk_path, time_offset) in enumerate(chunks):
                    logger.info(
                        f"Transcribing chunk {chunk_idx + 1}/{len(chunks)} "
                        f"(offset={time_offset/60:.1f}min)"
                    )
                    segs, texts, lang, _ = self._transcribe_chunk(
                        chunk_path,
                        time_offset,
                        language,
                        segment_id_start=len(all_segments),
                    )
                    all_segments.extend(segs)
                    all_texts.extend(texts)
                    if detected_language is None:
                        detected_language = lang

                    # Progress based on chunks completed
                    if progress_callback and total_duration > 0:
                        pct = min(int((chunk_idx + 1) / len(chunks) * 99), 99)
                        if pct >= last_reported_pct + 2:
                            last_reported_pct = pct
                            try:
                                progress_callback(pct)
                            except Exception:
                                pass
            else:
                # Short video: single-pass, full quality, no temp files needed
                model = WhisperTranscriptionService._model
                if model is None:
                    raise RuntimeError("Whisper model not loaded")

                segments_iter, info = model.transcribe(
                    video_path,
                    language=language,
                    beam_size=1,
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500},
                    chunk_length=30,
                )
                detected_language = info.language

                for i, seg in enumerate(segments_iter):
                    confidence = float(getattr(seg, "avg_logprob", 0.0))
                    all_segments.append(
                        TranscriptSegment(
                            id=i,
                            start=float(seg.start),
                            end=float(seg.end),
                            text=seg.text.strip(),
                            confidence=confidence,
                        )
                    )
                    all_texts.append(seg.text.strip())

                    if progress_callback and total_duration > 0:
                        pct = min(int(float(seg.end) / total_duration * 99), 99)
                        if pct >= last_reported_pct + 2:
                            last_reported_pct = pct
                            try:
                                progress_callback(pct)
                            except Exception:
                                pass

        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.info("Cleaned up temp chunk files")

        full_text = " ".join(all_texts)
        return TranscriptResult(
            full_text=full_text,
            segments=all_segments,
            language=detected_language or "id",
            duration=total_duration,
            word_count=len(full_text.split()),
        )

    async def transcribe(
        self,
        video_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        _is_retry: bool = False,
    ) -> TranscriptResult:
        """Non-blocking transcription using thread pool executor."""
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, partial(self._transcribe_sync, video_path, language, progress_callback)
            )
            logger.info(
                f"Transcription complete: {result.word_count} words, "
                f"language={result.language}, duration={result.duration:.1f}s"
            )
            return result
        except (MemoryError, RuntimeError) as e:
            if not _is_retry and (
                "out of memory" in str(e).lower() or "cuda" in str(e).lower()
            ):
                logger.error(
                    "GPU OOM during transcription — falling back to CPU medium model"
                )
                from faster_whisper import WhisperModel

                with WhisperTranscriptionService._model_lock:
                    WhisperTranscriptionService._model = WhisperModel(
                        "medium", device="cpu", compute_type="int8"
                    )
                return await self.transcribe(video_path, language, progress_callback, _is_retry=True)
            raise
        except FileNotFoundError:
            raise FileNotFoundError(f"Video file not found: {video_path}")
        except Exception as e:
            logger.exception(f"Transcription failed for {video_path}: {e}")
            raise
