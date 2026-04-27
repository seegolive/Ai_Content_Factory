"""AI Brain service — multi-model fallback (Groq → Gemini Flash → GPT-4o-mini)."""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import httpx
from loguru import logger

from app.core.config import settings
from app.services.transcription import TranscriptResult


# ── Duration rules per moment type (mirrored in frontend DurationBadge) ─────
MOMENT_DURATION_RULES = {
    "clutch":      {"min": 45, "ideal_min": 55, "ideal_max": 75,  "max": 90,  "buildup": 10, "resolution": 12},
    "funny":       {"min": 20, "ideal_min": 25, "ideal_max": 45,  "max": 60,  "buildup": 5,  "resolution": 8},
    "achievement": {"min": 60, "ideal_min": 70, "ideal_max": 90,  "max": 120, "buildup": 15, "resolution": 15},
    "rage":        {"min": 30, "ideal_min": 40, "ideal_max": 60,  "max": 75,  "buildup": 8,  "resolution": 10},
    "epic":        {"min": 45, "ideal_min": 60, "ideal_max": 90,  "max": 100, "buildup": 12, "resolution": 12},
    "fail":        {"min": 20, "ideal_min": 30, "ideal_max": 50,  "max": 60,  "buildup": 8,  "resolution": 8},
    "tutorial":    {"min": 45, "ideal_min": 60, "ideal_max": 90,  "max": 120, "buildup": 5,  "resolution": 10},
}
FALLBACK_DURATION_RULE = {"min": 30, "ideal_min": 45, "ideal_max": 75, "max": 90, "buildup": 8, "resolution": 8}


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

LANGKAH WAJIB: Tentukan moment_type DULU, baru tentukan durasi.

┌─────────────┬────────┬────────────┬────────┬──────────────────────────────────────────┐
│ moment_type │  min   │   ideal    │  max   │ kenapa                                   │
├─────────────┼────────┼────────────┼────────┼──────────────────────────────────────────┤
│ clutch      │  45s   │  55–75s    │  90s   │ tension + fight + reaksi kelegaan        │
│ funny       │  20s   │  25–45s    │  60s   │ joke harus landing cepat                 │
│ achievement │  60s   │  70–90s    │ 120s   │ penonton butuh context kenapa susah      │
│ rage        │  30s   │  40–60s    │  75s   │ energy rage cepat turun                  │
│ epic        │  45s   │  60–90s    │ 100s   │ butuh grandeur, jangan buru-buru         │
│ fail        │  20s   │  30–50s    │  60s   │ singkat + reaksi = cukup                 │
│ tutorial    │  45s   │  60–90s    │ 120s   │ step by step + verifikasi hasil          │
└─────────────┴────────┴────────────┴────────┴──────────────────────────────────────────┘

STRUKTUR SETIAP CLIP (WAJIB ADA KETIGA BAGIAN):
1. BUILD-UP: context sebelum momen utama (clutch:10s, funny:5s, achievement:15s, rage:8s, epic:12s, fail:8s, tutorial:5s)
2. MOMEN UTAMA: inti yang viral — jangan dipotong sama sekali
3. RESOLUSI: reaksi + aftermath (clutch:12s, funny:8s, achievement:15s, rage:10s, epic:12s, fail:8s, tutorial:10s)

ATURAN POTONG — JANGAN PERNAH DILANGGAR:
❌ Jangan potong di tengah kalimat streamer
❌ Jangan potong saat reaksi emosional belum selesai
❌ Jangan potong saat aksi gameplay masih berlangsung
❌ Jangan mulai dari loading screen atau transisi
✅ Mulai saat ada audio (suara gameplay atau streamer bicara)
✅ Akhiri saat ada natural pause atau kalimat selesai

PENANGANAN MOMEN TERLALU PENDEK:
Jika momen secara natural < minimum untuk tipenya:
1. Extend ke build-up sebelumnya yang relevan
2. Gabungkan 2 momen sejenis yang berdekatan (< 10 detik jeda)
3. Jika tetap tidak bisa: SKIP — jangan dipaksakan

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
      "start_time": 12.5,
      "end_time": 75.2,
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

Identifikasi 5-15 clip terbaik. Minimum viral_score untuk diinclude: 60.
Urutkan clips dari viral_score tertinggi ke terendah."""


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
                logger.info(f"Trying provider: {provider['name']} / {provider['model']}")
                result = await self._call_provider(provider, messages, max_tokens)
                logger.info(f"Success: {provider['name']} ({result['tokens_used']} tokens)")
                return (
                    result["content"],
                    result["provider_name"],
                    result["model"],
                    result["tokens_used"],
                )
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning(f"{provider['name']} HTTP {status} — trying next provider")
                last_error = e
                if status not in (429, 500, 502, 503, 504):
                    # Don't fall through for unexpected auth / not-found errors
                    break
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"{provider['name']} connection error: {e} — trying next provider")
                last_error = e

        raise RuntimeError(
            f"All AI providers failed. Last error: {last_error}"
        )

    async def analyze_transcript(
        self,
        transcript: TranscriptResult,
        channel_info: Optional[dict] = None,
        game_title: str = "",
        channel_name: str = "",
    ) -> AIAnalysisResult:
        """Analyze transcript and return viral clip suggestions."""
        start = time.perf_counter()

        segments_text = "\n".join(
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in transcript.segments
        )

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

        content, provider_name, model_used, tokens_used = await self._call_with_fallback(
            messages, max_tokens=4000
        )

        # If JSON is malformed, retry once with explicit instruction
        clips_data = self._try_parse_clips(content)
        if clips_data is None:
            logger.warning("First parse failed, retrying with explicit JSON instruction")
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "Output di atas bukan JSON valid. Coba lagi — output HANYA JSON valid, tidak ada teks lain.",
            })
            content, provider_name, model_used, tokens_used = await self._call_with_fallback(
                messages, max_tokens=4000
            )
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
        """Parse dict into ClipSuggestion objects, sorted by viral_score desc."""
        clips = []
        for item in data.get("clips", []):
            try:
                clips.append(
                    ClipSuggestion(
                        start_time=float(item["start_time"]),
                        end_time=float(item["end_time"]),
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
        return sorted(clips, key=lambda c: c.viral_score, reverse=True)


