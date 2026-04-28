"""AI Brain service — multi-model fallback (Groq → Gemini Flash → GPT-4o-mini)."""

import json
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx
from loguru import logger

from app.core.config import settings
from app.services.transcription import TranscriptResult


# ── YouTube Shorts hard limits (importable by QC service & frontend) ────────
SHORTS_MIN_DURATION = 60   # seconds
SHORTS_MAX_DURATION = 180  # seconds (YouTube Shorts official limit)

# ── Duration rules per moment type (mirrored in frontend DurationBadge) ─────
# All values within SHORTS_MIN_DURATION..SHORTS_MAX_DURATION
MOMENT_DURATION_RULES = {
    "clutch": {
        "min": 60,
        "ideal_min": 75,
        "ideal_max": 120,
        "max": 180,
        "buildup": 15,
        "resolution": 15,
    },
    "funny": {
        "min": 60,
        "ideal_min": 60,
        "ideal_max": 90,
        "max": 150,
        "buildup": 12,
        "resolution": 12,
    },
    "achievement": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 150,
        "max": 180,
        "buildup": 15,
        "resolution": 15,
    },
    "rage": {
        "min": 60,
        "ideal_min": 70,
        "ideal_max": 110,
        "max": 150,
        "buildup": 12,
        "resolution": 12,
    },
    "epic": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 140,
        "max": 180,
        "buildup": 15,
        "resolution": 15,
    },
    "fail": {
        "min": 60,
        "ideal_min": 60,
        "ideal_max": 90,
        "max": 150,
        "buildup": 12,
        "resolution": 12,
    },
    "tutorial": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 150,
        "max": 180,
        "buildup": 10,
        "resolution": 12,
    },
}
FALLBACK_DURATION_RULE = {
    "min": 60,
    "ideal_min": 75,
    "ideal_max": 120,
    "max": 180,
    "buildup": 12,
    "resolution": 12,
}


@dataclass
class ClipSuggestion:
    start_time: float
    end_time: float
    viral_score: int
    titles: List[str]  # 3 A/B variants
    hook_text: str
    description: str
    hashtags: List[str]
    thumbnail_prompt: str
    reason: str
    moment_type: str = "epic"  # clutch|funny|achievement|rage|epic|fail|tutorial


@dataclass
class AIAnalysisResult:
    clips: List[ClipSuggestion]
    processing_time: float
    model_used: str
    tokens_used: int
    provider_used: str = ""
    summary: str = ""


# ── Provider chain: tried in order, first success wins ──────────────────────
def _build_provider_chain() -> list:
    return [
        {
            "name": "Groq",
            "base_url": settings.GROQ_BASE_URL,
            "api_key": settings.GROQ_API_KEY,
            "model": settings.GROQ_MODEL,
            "supports_json_mode": True,
        },
        {
            "name": "OpenRouter Gemini Flash",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_MODEL,
            "supports_json_mode": False,  # Gemini via OpenRouter tidak konsisten
        },
        {
            "name": "OpenRouter GPT-4o-mini",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_FALLBACK_MODEL,
            "supports_json_mode": True,
        },
    ]


# ── System prompt: Indonesian gaming content specialist ──────────────────────
GAMING_SYSTEM_PROMPT = """Kamu adalah analis konten gaming Indonesia yang ahli mendeteksi momen viral dari transcript stream/video gaming.

Kamu memahami konteks gaming Indonesia:
- Kata-kata exclamation gamer: "wah gila", "aduh", "anjir", "yes!", "dari mana tuh", "ez", "gg", "noob", "pro banget"
- Tipe momen: clutch (1vX, menang tipis), rage (frustrasi), funny (lucu/fail), achievement (capai sesuatu), epic (momen luar biasa), fail (kesalahan lucu), tutorial (tips/cara)
- Preferensi audiens gaming Indonesia: reaksi ekspresif, momen tidak terduga, comeback dramatis, humor gaming

Viral scoring untuk gaming content (total 100 poin):
- Reaksi ekspresif streamer (0-30): teriak, exclamation, shock, tawa
- Kelangkaan momen (0-25): clutch 1v4, first achievement, never-seen-before
- Hook strength 5 detik pertama (0-25): langsung action atau tension tinggi
- Relatability & shareability (0-20): "ini gue banget", "tag temen lo"

═══════════════════════════════════════════════════════
ATURAN DURASI CLIP — BERBEDA PER TIPE MOMEN (WAJIB DIIKUTI)
═══════════════════════════════════════════════════════

PERINGATAN KERAS: Kamu DILARANG menghasilkan clip yang durasinya kurang dari 60 detik.
Jangan pernah output start_time dan end_time yang selisihnya kurang dari 60 detik.
Ini adalah ATURAN ABSOLUT, bukan saran.

LANGKAH WAJIB: Tentukan moment_type DULU, baru tentukan durasi.
Semua clip MINIMUM 60 detik — sesuai standar YouTube Shorts yang optimal.

CONTOH BENAR:
{‘start_time’: 120.0, ‘end_time’: 185.0}  ← durasi 65s ✓
{‘start_time’: 500.0, ‘end_time’: 590.0}  ← durasi 90s ✓

CONTOH SALAH (JANGAN LAKUKAN):
{‘start_time’: 120.0, ‘end_time’: 140.0}  ← durasi 20s ✗ DITOLAK
{‘start_time’: 500.0, ‘end_time’: 527.0}  ← durasi 27s ✗ DITOLAK

┌─────────────┬────────┬─────────────┬────────┬─────────────────────────────────────────────────────┐
│ moment_type │  min   │    ideal    │  max   │ kenapa                                              │
├─────────────┼────────┼─────────────┼────────┼─────────────────────────────────────────────────────┤
│ clutch      │  60s   │  75–120s    │ 180s   │ tension butuh ruang penuh                           │
│ funny       │  60s   │  60–90s     │ 150s   │ joke jangan dragged, energi cepat habis             │
│ achievement │  60s   │  90–150s    │ 180s   │ butuh story arc + context kenapa susah              │
│ rage        │  60s   │  70–110s    │ 150s   │ rage cepat habis energi, jangan dipanjang           │
│ epic        │  60s   │  90–140s    │ 180s   │ grandeur full, butuh ruang naratif                  │
│ fail        │  60s   │  60–90s     │ 150s   │ punchy + reaksi, jangan panjang                     │
│ tutorial    │  60s   │  90–150s    │ 180s   │ step-by-step + verifikasi hasil butuh waktu         │
└─────────────┴────────┴─────────────┴────────┴─────────────────────────────────────────────────────┘

HARD LIMIT YOUTUBE SHORTS: 60 detik MINIMUM, 180 detik MAKSIMUM.
Clip di luar range ini OTOMATIS DITOLAK — tidak ada pengecualian.

STRUKTUR SETIAP CLIP (WAJIB ADA KETIGA BAGIAN):
1. BUILD-UP: context sebelum momen utama (clutch:15s, funny:12s, achievement:15s, rage:12s, epic:15s, fail:12s, tutorial:10s)
2. MOMEN UTAMA: inti yang viral — jangan dipotong sama sekali
3. RESOLUSI: reaksi + aftermath (clutch:15s, funny:12s, achievement:15s, rage:12s, epic:15s, fail:12s, tutorial:12s)

ATURAN POTONG — JANGAN PERNAH DILANGGAR:
❌ Jangan potong di tengah kalimat streamer
❌ Jangan potong saat reaksi emosional belum selesai
❌ Jangan potong saat aksi gameplay masih berlangsung
❌ Jangan mulai dari loading screen atau transisi
✅ Mulai saat ada audio (suara gameplay atau streamer bicara)
✅ Akhiri saat ada natural pause atau kalimat selesai

PENANGANAN MOMEN DI BAWAH 60 DETIK:
Jika momen secara natural < 60 detik:
1. WAJIB extend ke build-up sebelumnya yang relevan sampai mencapai 60s
2. Gabungkan 2 momen yang berdekatan (jeda < 15 detik) menjadi satu clip
3. Extend ke aftermath/reaksi setelahnya jika masih kurang
4. Jika setelah semua langkah di atas tetap tidak bisa mencapai 60s: SKIP

Untuk setiap clip, generate:
1. start_time dan end_time (dalam detik) — WAJIB dalam range ideal untuk moment_type-nya
2. viral_score (0-100)
3. moment_type: salah satu dari "clutch", "funny", "achievement", "rage", "epic", "fail", "tutorial"
4. titles: TEPAT 3 varian (emosional, curiosity gap, achievement-style) — dalam Bahasa Indonesia
5. hook_text: kalimat pembuka <10 kata yang langsung menarik perhatian
6. description: 2-3 kalimat deskripsi SEO YouTube Bahasa Indonesia dengan keywords
7. hashtags: 10-15 hashtag relevan TANPA simbol #
8. thumbnail_prompt: deskripsi gambar SDXL untuk thumbnail ideal
9. reason: 1-2 kalimat kenapa segmen ini viral

Output HANYA JSON valid. TIDAK ADA teks di luar JSON. Schema:
{
  "clips": [
    {
      "start_time": 120.0,
      "end_time": 190.0,
      "viral_score": 87,
      "moment_type": "clutch",
      "titles": ["Judul 1", "Judul 2", "Judul 3"],
      "hook_text": "Gak nyangka bisa survive dari sini...",
      "description": "...",
      "hashtags": ["gaming", "battlefield6", "indonesia"],
      "thumbnail_prompt": "...",
      "reason": "..."
    }
  ],
  "summary": "Ringkasan singkat video/stream ini"
}

Identifikasi 5-20 clip terbaik — jangan lewatkan momen yang menarik hanya karena skornya tidak sempurna.
Minimum viral_score untuk diinclude: 50.
Urutkan clips dari viral_score tertinggi ke terendah.

PERINGATAN: Jangan terlalu selektif. Lebih baik 15 clip dengan skor 50–80 daripada hanya 5 clip dengan skor 80+.
Semua clip HARUS >= 60 detik. Clip di bawah 60 detik otomatis DITOLAK."""


class AIBrainService:
    async def _call_provider(
        self,
        provider: dict,
        messages: list,
        max_tokens: int,
    ) -> dict:
        """Call a single provider. Raises on any error."""
        async with httpx.AsyncClient(
            base_url=provider["base_url"],
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "HTTP-Referer": "https://ai-content-factory.app",
                "X-Title": "AI Content Factory",
            },
            timeout=120.0,
        ) as client:
            payload: dict = {
                "model": provider["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            # Only add response_format for providers that reliably support it
            if provider.get("supports_json_mode", False):
                payload["response_format"] = {"type": "json_object"}
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", provider["model"]),
                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                "provider_name": provider["name"],
            }

    async def _call_with_fallback(
        self,
        messages: list,
        max_tokens: int = 4000,
    ) -> Tuple[str, str, str, int]:
        """Try providers in order. Return (content, provider_name, model, tokens_used)."""
        chain = _build_provider_chain()
        last_error: Optional[Exception] = None

        for provider in chain:
            if not provider["api_key"]:
                logger.warning(f"Skipping {provider['name']} — no API key configured")
                continue
            try:
                logger.info(
                    f"Trying provider: {provider['name']} / {provider['model']}"
                )
                result = await self._call_provider(provider, messages, max_tokens)
                logger.info(
                    f"Success: {provider['name']} ({result['tokens_used']} tokens)"
                )
                return (
                    result["content"],
                    result["provider_name"],
                    result["model"],
                    result["tokens_used"],
                )
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning(
                    f"{provider['name']} HTTP {status} — trying next provider"
                )
                last_error = e
                # 401/403 = auth error for this provider → try next (key may be expired)
                # 413 = payload too large → try next (other provider may have higher limit)
                # 429 = rate limit → try next
                # 5xx = server errors → try next
                SKIP_TO_NEXT = {401, 403, 413, 429, 500, 502, 503, 504}
                if status not in SKIP_TO_NEXT:
                    break
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(
                    f"{provider['name']} connection error: {e} — trying next provider"
                )
                last_error = e

        raise RuntimeError(f"All AI providers failed. Last error: {last_error}")

    async def analyze_transcript(
        self,
        transcript: TranscriptResult,
        channel_info: Optional[dict] = None,
        game_title: str = "",
        channel_name: str = "",
    ) -> AIAnalysisResult:
        """Analyze transcript and return viral clip suggestions."""
        start = time.perf_counter()

        # Build segments text — smart chunk sampling to preserve burst moments.
        MAX_SEGMENTS_CHARS = 70_000
        segments_text = self._smart_sample_segments(
            transcript.segments, MAX_SEGMENTS_CHARS
        )

        context_parts = []
        if game_title:
            context_parts.append(f"Game: {game_title}")
        if channel_name:
            context_parts.append(f"Channel: {channel_name}")
        if channel_info:
            context_parts.append(f"Channel info: {json.dumps(channel_info)}")

        context_block = "\n".join(context_parts)

        max_tokens = self._calc_max_tokens(transcript.duration)

        user_message = f"""Analisis transcript video gaming ini dan identifikasi momen-momen viral.

Video duration: {transcript.duration:.1f} detik ({transcript.duration/60:.1f} menit)
Language: {transcript.language}
Word count: {transcript.word_count}
{context_block}

TRANSCRIPT:
{segments_text}
"""

        messages = [
            {"role": "system", "content": GAMING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        (
            content,
            provider_name,
            model_used,
            tokens_used,
        ) = await self._call_with_fallback(messages, max_tokens=max_tokens)

        # If JSON is malformed, retry once with explicit instruction
        clips_data = self._try_parse_clips(content)
        if clips_data is None:
            logger.warning(
                "First parse failed, retrying with explicit JSON instruction"
            )
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": "Output di atas bukan JSON valid. Coba lagi — output HANYA JSON valid, tidak ada teks lain.",
                }
            )
            (
                content,
                provider_name,
                model_used,
                tokens_used,
            ) = await self._call_with_fallback(messages, max_tokens=max_tokens)
            clips_data = self._try_parse_clips(content)

        elapsed = time.perf_counter() - start
        raw = clips_data or {}
        clips = self._parse_clip_suggestions(raw)

        return AIAnalysisResult(
            clips=clips,
            processing_time=elapsed,
            model_used=model_used,
            tokens_used=tokens_used,
            provider_used=provider_name,
            summary=raw.get("summary", ""),
        )

    async def generate_titles(
        self,
        clip_info: dict,
        game_title: str = "",
    ) -> List[str]:
        """Generate 3 viral title variants for a clip (Indonesian gaming style)."""
        game_ctx = f" untuk game {game_title}" if game_title else ""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Generate 3 judul YouTube viral{game_ctx} dalam Bahasa Indonesia. "
                    "Style: emosional, curiosity gap, achievement. "
                    "Return JSON array of strings ONLY.\n\n"
                    f"Clip info: {json.dumps(clip_info)}"
                ),
            }
        ]
        try:
            content, _, _, _ = await self._call_with_fallback(messages, max_tokens=300)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, RuntimeError) as e:
            logger.warning(f"generate_titles failed: {e}")
            return [clip_info.get("title", "Untitled")]

    def _smart_sample_segments(self, segments: list, max_chars: int = 70_000) -> str:
        """Chunk-based sampling: divide video into 30 time chunks, sample from each.

        Unlike uniform step sampling, this preserves burst moments (kill streaks,
        clutch plays) that happen in short windows of time.
        """
        all_lines = [
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in segments
        ]
        full = "\n".join(all_lines)
        if len(full) <= max_chars:
            return full

        # Divide into 30 time-based chunks
        total_dur = segments[-1].end if segments else 1
        num_chunks = 30
        chunk_dur = total_dur / num_chunks
        chunks: list = [[] for _ in range(num_chunks)]

        for seg, line in zip(segments, all_lines):
            idx = min(int(seg.start / chunk_dur), num_chunks - 1)
            chunks[idx].append(line)

        budget = max_chars // num_chunks
        sampled = []
        for chunk_lines in chunks:
            chunk_text = "\n".join(chunk_lines)
            if len(chunk_text) <= budget:
                sampled.append(chunk_text)
            else:
                step = max(1, len(chunk_lines) // max(1, budget // 80))
                sampled.append("\n".join(chunk_lines[::step]))

        note = (
            f"[transcript sampled per {chunk_dur/60:.1f}min chunk "
            f"dari video {total_dur/60:.0f} menit]\n"
        )
        result = note + "\n---\n".join(sampled)
        return result[:max_chars]

    def _calc_max_tokens(self, duration_sec: float) -> int:
        """Scale max_tokens based on video duration to fit more clips for longer videos."""
        minutes = duration_sec / 60
        clips_est = min(25, max(5, int(minutes / 10)))
        return min(8000, max(3000, clips_est * 350 + 1000))

    def _try_parse_clips(self, content: str) -> Optional[dict]:
        """Try to parse JSON from response. Returns dict or None."""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None

    def _parse_clip_suggestions(self, data: dict) -> List[ClipSuggestion]:
        """Parse dict into ClipSuggestion objects, sorted by viral_score desc.

        Layer 1 parser — NO duration filtering here.
        All clips passed through to Layer 2 (pipeline_validator) which handles
        extend/pass/split/reject based on YouTube Shorts requirements.
        Only rejects malformed items (missing fields, invalid types).
        """
        VALID_TYPES = {"clutch", "funny", "achievement", "rage", "epic", "fail", "tutorial"}
        clips = []
        skipped = 0
        for item in data.get("clips", []):
            try:
                start = float(item["start_time"])
                end = float(item["end_time"])
                if end <= start:
                    logger.warning(f"Skipping clip: end <= start ({start}-{end})")
                    skipped += 1
                    continue

                # Normalize moment_type
                mt = item.get("moment_type", "epic")
                if mt not in VALID_TYPES:
                    mt = "epic"

                # Ensure exactly 3 titles
                titles = item.get("titles", [item.get("title", "Untitled")])
                if not isinstance(titles, list):
                    titles = [str(titles)]
                while len(titles) < 3:
                    titles.append(titles[0])
                titles = titles[:3]

                # Clean hashtags
                tags = [
                    h.lstrip("#").strip().lower()
                    for h in item.get("hashtags", [])
                    if h and isinstance(h, str)
                ]

                # Clamp viral_score
                score = max(0, min(100, int(item.get("viral_score", 50))))

                duration = end - start
                logger.debug(
                    f"Layer1 clip: {mt} {start:.0f}s-{end:.0f}s ({duration:.0f}s) score={score}"
                )

                clips.append(
                    ClipSuggestion(
                        start_time=start,
                        end_time=end,
                        viral_score=score,
                        moment_type=mt,
                        titles=titles,
                        hook_text=item.get("hook_text", "")[:200],
                        description=item.get("description", "")[:1000],
                        hashtags=tags[:15],
                        thumbnail_prompt=item.get("thumbnail_prompt", ""),
                        reason=item.get("reason", "")[:300],
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed clip item: {e}")
                skipped += 1

        logger.info(
            f"Layer 1 parsed: {len(clips)} raw moments detected, {skipped} malformed skipped"
        )
        return sorted(clips, key=lambda c: c.viral_score, reverse=True)
