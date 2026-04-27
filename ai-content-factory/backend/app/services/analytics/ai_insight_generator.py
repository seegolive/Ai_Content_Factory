"""AI Insight Generator for analytics.

Generates structured insights using OpenRouter (Claude Sonnet primary,
GPT-4o-mini fallback). All outputs are in Bahasa Indonesia.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


_WEEKLY_REPORT_SYSTEM = """
Kamu adalah analis konten YouTube berpengalaman yang mengkhususkan diri
pada channel gaming Indonesia. Tugasmu adalah menganalisis data performa
minggu ini dan menghasilkan laporan yang actionable untuk creator.

ATURAN OUTPUT:
- Bahasa: Indonesia yang natural, bukan terjemahan kaku
- Tone: Seperti konsultan yang supportive, jujur, dan to-the-point
- Hindari jargon teknis yang tidak perlu
- Setiap rekomendasi harus spesifik dan actionable (bukan "optimalkan konten")
- PENTING: Jika `is_new_channel` = true atau `total_videos` = 0, jangan analisis
  seolah channel lama yang drop. Berikan laporan "channel baru" yang encouraging.
  Fokus pada langkah-langkah setup dan ekspektasi awal yang realistis.
- Output HANYA JSON, tidak ada teks di luar JSON

JSON Schema yang harus diikuti PERSIS:
{
  "summary": "string (1-2 kalimat TL;DR)",
  "wins": ["string"],
  "issues": ["string"],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "action": "string",
      "reason": "string",
      "expected_impact": "string"
    }
  ],
  "best_performing_content": "string",
  "focus_game_next_week": "string",
  "clip_opportunity_summary": "string"
}
""".strip()

_CONTENT_DNA_SYSTEM = """
Kamu adalah AI yang menganalisis pola konten untuk channel gaming Indonesia.
Berdasarkan data performa historis, identifikasi pola yang membuat video
perform baik vs buruk untuk channel spesifik ini.

Data yang diberikan: statistik agregat dari semua video channel.
Tugasmu: temukan pattern, bukan hanya deskripsi angka.

Output HANYA JSON:
{
  "title_patterns": {
    "winning": ["pattern yang bekerja"],
    "losing": ["pattern yang harus dihindari"],
    "recommended_format": "format judul yang direkomendasikan"
  },
  "hook_insights": {
    "optimal_duration_seconds": 0,
    "effective_patterns": ["pola hook yang efektif"],
    "avoid": ["apa yang harus dihindari di hook"]
  },
  "clip_strategy": {
    "optimal_duration_seconds": {"min": 0, "max": 0, "sweet_spot": 0},
    "best_moment_types": ["jenis momen yang perform"],
    "gaming_specific_tips": ["tips spesifik untuk gaming content"]
  },
  "audience_insights": {
    "peak_activity_time": "deskripsi waktu aktif audiens",
    "content_preference": "deskripsi preferensi audiens channel ini"
  },
  "confidence_note": "string"
}
""".strip()

_TITLE_OPTIMIZER_SYSTEM = """
Kamu adalah copywriter viral untuk konten gaming Indonesia.
Kamu memiliki akses ke Content DNA channel ini yang menunjukkan
pola judul yang terbukti perform.

Berdasarkan: konten clip, game yang dimainkan, momen spesifik, dan
pola historis channel, generate judul yang optimal.

Prinsip judul gaming Indonesia yang viral:
- Gunakan bahasa sehari-hari Indonesia (bukan formal)
- Boleh campur Indonesia-Inggris jika natural
- Emotional trigger: terkejut, bangga, lucu, epic, kesal
- Angka spesifik lebih baik dari yang umum
- Pertanyaan atau cliffhanger bekerja untuk gaming

Output HANYA JSON:
{
  "titles": [
    {
      "text": "judul utama",
      "style": "emotional|curiosity|how-to|epic|funny",
      "predicted_ctr_boost": "low|medium|high",
      "reasoning": "kenapa judul ini efektif"
    }
  ],
  "recommended": 0,
  "hashtags": ["tag1"],
  "hook_suggestion": "saran teks untuk 5 detik pertama clip"
}
""".strip()


_DEFAULT_WEEKLY_REPORT: dict[str, Any] = {
    "summary": "Laporan mingguan tidak tersedia saat ini.",
    "wins": [],
    "issues": [],
    "recommendations": [],
    "best_performing_content": "Data belum tersedia",
    "focus_game_next_week": "Belum ditentukan",
    "clip_opportunity_summary": "Data belum tersedia",
}

_DEFAULT_DNA: dict[str, Any] = {
    "title_patterns": {"winning": [], "losing": [], "recommended_format": ""},
    "hook_insights": {"optimal_duration_seconds": 8, "effective_patterns": [], "avoid": []},
    "clip_strategy": {
        "optimal_duration_seconds": {"min": 45, "max": 180, "sweet_spot": 90},
        "best_moment_types": [],
        "gaming_specific_tips": [],
    },
    "audience_insights": {"peak_activity_time": "", "content_preference": ""},
    "confidence_note": "Data terlalu sedikit untuk analisis yang akurat.",
}


class AIInsightGenerator:
    """OpenRouter-based insight generator for analytics module."""

    def __init__(self) -> None:
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_MODEL
        self._fallback = settings.OPENROUTER_FALLBACK_MODEL

    async def generate_weekly_report(
        self,
        channel_name: str,
        week_stats: dict[str, Any],
        prev_week_stats: dict[str, Any],
        top_videos: list[dict],
        unclipped_count: int,
        total_videos: int = 0,
        is_new_channel: bool = False,
    ) -> dict[str, Any]:
        """Generate AI weekly report in Bahasa Indonesia."""
        user_msg = f"""
Channel: {channel_name}
Total video dengan analytics: {total_videos}
Channel baru (belum banyak data): {is_new_channel}

Statistik minggu ini:
{json.dumps(week_stats, indent=2, ensure_ascii=False)}

Statistik minggu lalu:
{json.dumps(prev_week_stats, indent=2, ensure_ascii=False)}

Top video minggu ini:
{json.dumps(top_videos[:5], indent=2, ensure_ascii=False)}

Video belum diclip (berpotensi): {unclipped_count} video
"""
        result = await self._call_openrouter(
            system=_WEEKLY_REPORT_SYSTEM,
            user=user_msg.strip(),
        )
        if result is None:
            logger.warning("[AIInsightGenerator] weekly report generation failed, using default")
            return _DEFAULT_WEEKLY_REPORT
        return result

    async def analyze_content_dna(
        self,
        channel_id: str,
        stats_summary: str,
    ) -> dict[str, Any]:
        """Analyze content DNA patterns from historical data."""
        user_msg = f"""
Channel ID: {channel_id}

Data historis:
{stats_summary}

Identifikasi pola konten yang efektif untuk channel gaming Indonesia ini.
"""
        result = await self._call_openrouter(
            system=_CONTENT_DNA_SYSTEM,
            user=user_msg.strip(),
        )
        if result is None:
            return _DEFAULT_DNA
        return result

    async def optimize_clip_titles(
        self,
        game: str,
        moment_description: str,
        content_dna: dict[str, Any],
        transcript_excerpt: str = "",
    ) -> dict[str, Any]:
        """Generate optimized titles for a clip using Content DNA."""
        user_msg = f"""
Game: {game}
Momen: {moment_description}
Transcript (excerpt): {transcript_excerpt[:500] if transcript_excerpt else 'tidak tersedia'}

Content DNA channel:
Pola judul yang berhasil: {content_dna.get('top_performing_patterns', {}).get('title_patterns', [])}
Pola yang harus dihindari: {content_dna.get('underperforming_patterns', {}).get('titles', [])}
"""
        result = await self._call_openrouter(
            system=_TITLE_OPTIMIZER_SYSTEM,
            user=user_msg.strip(),
        )
        if result is None:
            return {
                "titles": [{"text": f"Moment Epik {game}!", "style": "epic", "predicted_ctr_boost": "medium", "reasoning": "Default fallback"}],
                "recommended": 0,
                "hashtags": [game.replace(" ", ""), "gaming", "Indonesia"],
                "hook_suggestion": "Mulai dengan momen paling menarik langsung",
            }
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=False,
    )
    async def _call_openrouter(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any] | None:
        """Call OpenRouter API and parse JSON response."""
        target_model = model or self._model
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-content-factory.local",
            "X-Title": "AI Content Factory Analytics",
        }
        payload = {
            "model": target_model,
            "temperature": 0.3,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            raw = data["choices"][0]["message"]["content"]
            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

            return json.loads(raw.strip())

        except json.JSONDecodeError as exc:
            logger.warning(f"[AIInsightGenerator] JSON parse failed ({exc}), retrying with explicit instruction")
            # On retry, explicitly remind to output only JSON
            raise ValueError("JSON parse failed — retry with explicit instruction") from exc

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("[AIInsightGenerator] Rate limited by OpenRouter")
                raise  # tenacity will retry
            # Try fallback model on 5xx
            if exc.response.status_code >= 500 and target_model != self._fallback:
                logger.warning(f"[AIInsightGenerator] Model {target_model} failed, trying fallback")
                return await self._call_openrouter(system, user, model=self._fallback)
            logger.error(f"[AIInsightGenerator] HTTP error: {exc}")
            return None

        except Exception as exc:
            logger.error(f"[AIInsightGenerator] Unexpected error: {exc}")
            return None
