"""AI Brain service — multi-model fallback (Gemini Flash → Groq → GPT-4o-mini)."""

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
            "name": "OpenRouter Gemini Flash",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_MODEL,
            "supports_json_mode": False,  # Gemini via OpenRouter tidak konsisten
        },
        {
            "name": "Groq",
            "base_url": settings.GROQ_BASE_URL,
            "api_key": settings.GROQ_API_KEY,
            "model": settings.GROQ_MODEL,
            "supports_json_mode": True,
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
- Tipe momen: clutch (1vX, menang tipis), rage (frustrasi), funny (lucu/fail), achievement (capai sesuatu), epic (momen luar biasa), fail (kesalahan lucu), tutorial (tips/cara)
- Preferensi audiens gaming Indonesia: reaksi ekspresif, momen tidak terduga, comeback dramatis, humor gaming

Viral scoring untuk gaming content (total 100 poin):
- Reaksi ekspresif streamer (0-30): teriak, exclamation, shock, tawa
- Kelangkaan momen (0-25): clutch 1v4, first achievement, never-seen-before
- Hook strength 5 detik pertama (0-25): langsung action atau tension tinggi
- Relatability & shareability (0-20): "ini gue banget", "tag temen lo"

═══════════════════════════════════════════════════════
ATURAN DURASI — TARGET 60-180 DETIK PER CLIP
═══════════════════════════════════════════════════════

Target platform: YouTube Shorts (minimum 60 detik, maksimum 180 detik).
Setiap clip HARUS bisa berdiri sendiri sebagai Short yang utuh dan memuaskan.

CARA MENENTUKAN DURASI YANG BENAR:
Sebuah viral moment terdiri dari 3 bagian — SEMUANYA harus masuk:
  1. BUILDUP (10-25 detik): konteks sebelum momen, tension, atau setup
  2. PEAK (5-30 detik): momen inti yang viral (kill, reaksi, fail, dll)
  3. AFTERMATH (10-25 detik): reaksi streamer setelah momen selesai

Contoh benar:
  - Momen kill streak hanya 8 detik → start 15 detik SEBELUMNYA (saat streamer mulai engage), end 20 detik SETELAHNYA (reaksi selesai) → total ~43 detik minimum
  - Rage moment 5 detik → mulai saat situasi frustasi dimulai, akhiri saat streamer selesai bereaksi → total 60-90 detik

TARGET DURASI PER MOMENT TYPE:
- clutch/epic: 75-120 detik (butuh buildup tension yang cukup)
- funny/rage/fail: 60-90 detik (reaksi + aftermath)
- achievement: 90-150 detik (perjuangan + pencapaian + selebrasi)
- tutorial: 90-180 detik (penjelasan harus lengkap)

ATURAN KERAS:
❌ DILARANG keras output clip < 45 detik — tidak akan pernah layak jadi Short
❌ Jangan potong di tengah kalimat streamer
❌ Jangan potong saat reaksi emosional belum selesai
❌ Jangan mulai dari loading screen atau transisi
✅ Mulai 10-25 detik SEBELUM momen inti (untuk buildup)
✅ Akhiri 10-20 detik SETELAH momen inti (reaksi selesai + natural pause)
✅ Jika durasi di bawah 60 detik, WAJIB tambah buildup dan aftermath lebih banyak

═══════════════════════════════════════════════════════
GAMING EVENTS YANG WAJIB JADI CLIP (jangan pernah skip)
═══════════════════════════════════════════════════════

FPS (Battlefield 6, Valorant):
✅ Kill streak / multikill / ace
✅ Clutch (1v2, 1v3, 1v4, 1v5)
✅ Last second win/defuse/decrypt
✅ Headshot impressive / no-scope / collateral
✅ Vehicle combat: tank duel, basoka/bazooka hit, heli meledak, airstrike kena musuh
✅ Squad wipe (menang atau kalah dramatis)
✅ Kena tembak dari arah tidak terduga
✅ Spawn kill (lucu atau kesal)
✅ Near-death escape (tipis banget, hampir mati, cabut last second)
✅ Finisher move (di bacok, di finisher, executions)
✅ Cinematic moment yang streamer sendiri komentari ("cinema banget", "scene bagus", "epic moment")
✅ Object/bomb plant + defuse tension (defend/attack mode)
✅ Battle Royale: final squad, zone closing, last zone clutch, "chicken dinner"

RPG (Kingdom Come Deliverance II):
✅ Boss fight defeat (terutama first attempt)
✅ Quest completion setelah struggle
✅ Dialog NPC yang aneh/lucu
✅ Combat yang tidak terduga
✅ Lockpick/steal yang menegangkan

Survival (Arc Raiders):
✅ First encounter enemy baru
✅ Survival momen intense (hampir mati)
✅ Loot epic/rare drop
✅ PvE/PvP fight unexpected

Universal (semua game):
✅ Glitch / bug lucu
✅ Random funny moment
✅ Reaksi "first time" pada konten baru
✅ Streamer ngomong langsung ke kamera (personal moment)
✅ Diskusi/cerita menarik saat gameplay santai

═══════════════════════════════════════════════════════
KATA-KATA KUNCI UNTUK DETEKSI MOMEN VIRAL
═══════════════════════════════════════════════════════

Reaksi shock/kaget: "anjir", "anjay", "njir", "wuih", "buset", "gila", "edan", "wtf", "cuh", "cuy", "cok", "gokil"
Reaksi menang/berhasil: "yes!", "yesss!", "akhirnya!", "berhasil!", "mantap!", "gg", "ez", "nice", "gas gas gas", "let's go"
Reaksi kesal/rage: "kampret", "anjing", "tai", "bangsat", "kok bisa?!", "curang", "brengsek", "kagak", "elah"
Reaksi panik: "aduh", "mati gue", "habis gue", "bahaya!", "lari lari!", "kabur", "cabut cabut cabut", "reset reset"
Reaksi tidak percaya: "dari mana?!", "serius?!", "gak nyangka", "beneran?!", "gimana bisa", "kok"
Reaksi lucu: "wkwk", "wkwkwk", "hahaha", "kocak", "ngakak", "lucu banget"

🔥 SELF-LABELING MOMEN (streamer sendiri menyebut momennya) — PRIORITAS TERTINGGI:
"epic moment", "cinema banget", "cinematik", "scene nya bagus", "gila sih", "ini momen", "clip ini",
"keren banget", "gila banget sih", "ini baru namanya", "sumpah gila", "ini tuh"

🔫 BATTLEFIELD / FPS ACTION KEYWORDS — wajib detect:
- Vehicle: "tank", "hancur", "meledak", "basoka", "bazooka", "peluru kendali", "helikopter", "heli meledak",
           "naik tank", "tank gede", "battle tank", "airstrike", "air strike", "rudal", "rocket launcher"
- Combat: "decrypt", "plant", "defuse", "bomb", "squad wipe", "finisher", "di bacok", "di finisher",
          "clutch", "one hit", "headshot", "no scope", "kill streak", "multi kill"
- Mode: "gauntlet", "battle royal", "battle royale", "second chance", "chicken dinner", "last squad",
        "final ring", "zone", "looting"

Intensitas: 1 exclamation = menarik | 2-3 dalam 10 detik = KEMUNGKINAN BESAR viral | 4+ rapid-fire = PASTI viral
Streamer self-labels momen → langsung score 70+ (dia tahu momennya sendiri yang bagus)

═══════════════════════════════════════════════════════
HASHTAG STRATEGY (10-15 tags, TANPA simbol #)
═══════════════════════════════════════════════════════

Lapisan 1 — Game specific (3-4): battlefield6, bf6, valorant, kcd2, arcraiders
Lapisan 2 — Gaming Indonesia (3-4): gamingindonesia, streamerindonesia, gamingid
Lapisan 3 — Moment specific: clutch→clutchmoment,epicmoment | funny→funnygaming,ngakak | rage→ragemoment | fail→gamingfail
Lapisan 4 — General reach (2-3): shorts, youtubeshorts, viral, fyp

═══════════════════════════════════════════════════════
GAYA JUDUL PER MOMENT TYPE
═══════════════════════════════════════════════════════

clutch:      "1 LAWAN 4 DI [GAME] — BISA MENANG GAK NIH?" / "DETIK TERAKHIR CLUTCH!!"
funny:       "DARI MANA?! [SITUASI] DI [GAME] WKWKWK" / "[SITUASI] PALING KOCAK"
achievement: "AKHIRNYA GUE [ACHIEVEMENT] DI [GAME]!" / "SETELAH [X] KALI GAGAL..."
rage:        "INI GAME CURANG!!! [SITUASI]" / "RAGE QUIT MOMENT"
epic:        "MOMEN PALING GILA GUE DI [GAME]!!" / "INI BARU NAMANYA [GAME]!!"
fail:        "GUE KIRA BISA... TERNYATA [FAIL] WKWK" / "JANGAN KAYAK GUE 😂"
tutorial:    "CARA [AKSI] DI [GAME] — TIPS YANG JARANG ORANG TAU"

PRINSIP: 1 emoji maksimal, CAPS untuk emphasis, Bahasa Indonesia natural

Untuk setiap clip, generate:
1. start_time dan end_time (dalam detik) — NATURAL, tidak dipaksakan
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

Identifikasi 15-25 momen — lebih banyak lebih baik, pipeline yang akan filter.
Minimum viral_score untuk diinclude: 40. Lebih baik 20 clip skor 40-80 daripada 5 clip skor 80+.
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

    # ── Multi-pass windowed analysis constants ───────────────────────────────
    _WINDOW_DURATION_S = 1800    # 30-min windows
    _WINDOW_OVERLAP_S  = 300     # 5-min overlap between windows
    _MULTIPASS_THRESHOLD_S = 2400  # videos > 40 min use multi-pass
    _MAX_SEGMENTS_CHARS = 15_000   # per-window budget (safe for Groq)

    async def analyze_transcript(
        self,
        transcript: TranscriptResult,
        channel_info: Optional[dict] = None,
        game_title: str = "",
        channel_name: str = "",
    ) -> AIAnalysisResult:
        """Analyze transcript and return viral clip suggestions.

        Short videos (≤40 min): single AI call.
        Long videos (>40 min): multi-pass windowed — one AI call per 30-min window,
        results merged and deduplicated. This ensures full transcript coverage
        instead of sparse 12% sampling.
        """
        if transcript.duration <= self._MULTIPASS_THRESHOLD_S:
            return await self._analyze_single_pass(
                transcript.segments, transcript.duration, transcript.language,
                transcript.word_count, channel_info, game_title, channel_name,
            )

        # Multi-pass for long videos
        t0 = time.perf_counter()
        windows = self._build_windows(transcript.segments, transcript.duration)
        logger.info(
            f"[AI] Multi-pass: {len(windows)} windows × 30min "
            f"for {transcript.duration/60:.0f}min video"
        )

        all_clips: List[ClipSuggestion] = []
        total_tokens = 0
        model_used = ""
        provider_used = ""

        for i, (window_segs, win_start, win_end) in enumerate(windows):
            logger.info(
                f"[AI] Window {i+1}/{len(windows)}: "
                f"{win_start/60:.0f}–{win_end/60:.0f}min "
                f"({len(window_segs)} segments)"
            )
            try:
                result = await self._analyze_single_pass(
                    window_segs,
                    transcript.duration,
                    transcript.language,
                    transcript.word_count,
                    channel_info,
                    game_title,
                    channel_name,
                    window_label=f"[{win_start/60:.0f}–{win_end/60:.0f}min]",
                )
                all_clips.extend(result.clips)
                total_tokens += result.tokens_used
                if not model_used:
                    model_used = result.model_used
                    provider_used = result.provider_used
            except Exception as e:
                logger.warning(f"[AI] Window {i+1} failed: {e} — skipping")

        # Deduplicate overlapping clips, sort by viral_score
        all_clips = self._deduplicate_clips(all_clips)
        all_clips.sort(key=lambda c: c.viral_score, reverse=True)

        logger.info(
            f"[AI] Multi-pass done: {len(all_clips)} unique clips "
            f"from {len(windows)} windows ({total_tokens} tokens total)"
        )

        return AIAnalysisResult(
            clips=all_clips,
            processing_time=time.perf_counter() - t0,
            model_used=model_used,
            tokens_used=total_tokens,
            provider_used=provider_used,
        )

    def _build_windows(
        self, segments: list, total_duration: float
    ) -> List[Tuple[list, float, float]]:
        """Slice segments into overlapping 30-min windows."""
        step = self._WINDOW_DURATION_S - self._WINDOW_OVERLAP_S  # 1500s
        windows = []
        start = 0.0
        while start < total_duration:
            end = min(start + self._WINDOW_DURATION_S, total_duration)
            window_segs = [s for s in segments if start <= s.start < end]
            if window_segs:
                windows.append((window_segs, start, end))
            start += step
        return windows

    def _deduplicate_clips(self, clips: List[ClipSuggestion]) -> List[ClipSuggestion]:
        """Remove clips that overlap >50% with a higher-scored clip."""
        clips_sorted = sorted(clips, key=lambda c: c.viral_score, reverse=True)
        result: List[ClipSuggestion] = []
        for clip in clips_sorted:
            clip_dur = clip.end_time - clip.start_time
            if clip_dur <= 0:
                continue
            duplicate = False
            for existing in result:
                overlap_start = max(clip.start_time, existing.start_time)
                overlap_end = min(clip.end_time, existing.end_time)
                if overlap_end > overlap_start:
                    if (overlap_end - overlap_start) / clip_dur > 0.5:
                        duplicate = True
                        break
            if not duplicate:
                result.append(clip)
        return result

    async def _analyze_single_pass(
        self,
        segments: list,
        total_duration: float,
        language: str,
        word_count: int,
        channel_info: Optional[dict] = None,
        game_title: str = "",
        channel_name: str = "",
        window_label: str = "",
    ) -> AIAnalysisResult:
        """Single AI call on a segment list (full video or one window)."""
        t0 = time.perf_counter()

        segments_text = self._smart_sample_segments(segments, self._MAX_SEGMENTS_CHARS)

        context_parts = []
        if game_title:
            context_parts.append(f"Game: {game_title}")
        if channel_name:
            context_parts.append(f"Channel: {channel_name}")
        if channel_info:
            context_parts.append(f"Channel info: {json.dumps(channel_info)}")
        context_block = "\n".join(context_parts)

        window_note = f"Window: {window_label}\n" if window_label else ""
        max_tokens = self._calc_max_tokens(total_duration)

        user_message = f"""Analisis transcript video gaming ini dan identifikasi momen-momen viral.

Video duration: {total_duration:.1f} detik ({total_duration/60:.1f} menit)
Language: {language}
Word count: {word_count}
{window_note}{context_block}

INGAT: Setiap clip MINIMUM 15 detik. Pilih range yang mencakup konteks sebelum dan sesudah momen utama.
Jangan pilih hanya 1 kalimat — itu terlalu pendek. Minimal 3-5 kalimat per clip.

TRANSCRIPT:
{segments_text}
"""

        messages = [
            {"role": "system", "content": GAMING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        content, provider_name, model_used, tokens_used = \
            await self._call_with_fallback(messages, max_tokens=max_tokens)

        clips_data = self._try_parse_clips(content)
        if clips_data is None:
            logger.warning("First parse failed, retrying with explicit JSON instruction")
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "Output di atas bukan JSON valid. Coba lagi — output HANYA JSON valid, tidak ada teks lain.",
            })
            content, provider_name, model_used, tokens_used = \
                await self._call_with_fallback(messages, max_tokens=max_tokens)
            clips_data = self._try_parse_clips(content)

        raw = clips_data or {}
        clips = self._parse_clip_suggestions(raw)

        return AIAnalysisResult(
            clips=clips,
            processing_time=time.perf_counter() - t0,
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
