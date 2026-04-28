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
        },
        {
            "name": "OpenRouter Gemini Flash",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_MODEL,
        },
        {
            "name": "OpenRouter GPT-4o-mini",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_FALLBACK_MODEL,
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
            timeout=90.0,
        ) as client:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": provider["model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
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
                # 413 = payload too large → try next provider (may have higher limit)
                # 4xx auth/not-found errors (except 413/429) → stop immediately
                if status not in (413, 429, 500, 502, 503, 504):
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

        # Build segments text — cap at ~70k chars to stay within provider context limits.
        # For very long videos (streams, etc.) sample across the full duration instead of truncating.
        MAX_SEGMENTS_CHARS = 70_000
        all_segments_lines = [
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in transcript.segments
        ]
        segments_text = "\n".join(all_segments_lines)
        if len(segments_text) > MAX_SEGMENTS_CHARS:
            # Sample uniformly across segments to preserve context from whole video
            total = len(all_segments_lines)
            step = max(1, total // 800)  # keep ~800 lines
            sampled = all_segments_lines[::step]
            segments_text = "[NOTE: transcript sampled uniformly due to length]\n" + "\n".join(sampled)
            # Final safety truncate
            segments_text = segments_text[:MAX_SEGMENTS_CHARS]

        context_parts = []
        if game_title:
            context_parts.append(f"Game: {game_title}")
        if channel_name:
            context_parts.append(f"Channel: {channel_name}")
        if channel_info:
            context_parts.append(f"Channel info: {json.dumps(channel_info)}")

        context_block = "\n".join(context_parts)

        user_message = f"""Analisis transcript video gaming ini dan identifikasi momen-momen viral.

Video duration: {transcript.duration:.1f} detik
Language: {transcript.language}
Word count: {transcript.word_count}
{context_block}

TRANSCRIPT:
{segments_text}

Full text:
{transcript.full_text[:5000]}
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
        ) = await self._call_with_fallback(messages, max_tokens=4000)

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
            ) = await self._call_with_fallback(messages, max_tokens=4000)
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

        Layer 2 validation: reject clips outside YouTube Shorts duration range.
        """
        clips = []
        too_long = 0
        too_short_warn = 0
        for item in data.get("clips", []):
            try:
                start = float(item["start_time"])
                end = float(item["end_time"])
                duration = end - start
                # Hard reject only clips > 180s (YouTube Shorts hard limit).
                # Clips < 60s are passed through — pipeline._validate_clip_durations
                # will extend them before the final cut. Only truly unsalvageable
                # clips (< 20s) are rejected here to avoid wasting pipeline time.
                if duration > SHORTS_MAX_DURATION:
                    too_long += 1
                    logger.debug(
                        f"Clip rejected: too long ({duration:.1f}s > {SHORTS_MAX_DURATION}s)"
                    )
                    continue
                if duration < 20:
                    too_short_warn += 1
                    logger.debug(
                        f"Clip rejected: too short to salvage ({duration:.1f}s)"
                    )
                    continue
                if duration < SHORTS_MIN_DURATION:
                    logger.debug(
                        f"Clip under-duration ({duration:.1f}s) — passing to pipeline for extension"
                    )
                clips.append(
                    ClipSuggestion(
                        start_time=start,
                        end_time=end,
                        viral_score=int(item.get("viral_score", 50)),
                        moment_type=item.get("moment_type", "epic"),
                        titles=item.get("titles", [item.get("title", "Untitled")]),
                        hook_text=item.get("hook_text", ""),
                        description=item.get("description", ""),
                        hashtags=item.get("hashtags", []),
                        thumbnail_prompt=item.get("thumbnail_prompt", ""),
                        reason=item.get("reason", ""),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed clip item: {e}")
        skipped = too_long + too_short_warn
        if skipped:
            logger.info(
                f"Duration filter: {too_short_warn} unsalvageable (<20s), "
                f"{too_long} too long (>{SHORTS_MAX_DURATION}s) — total skipped: {skipped}"
            )
        return sorted(clips, key=lambda c: c.viral_score, reverse=True)
