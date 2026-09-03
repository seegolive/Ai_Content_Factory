"""AI Brain service — multi-model fallback (Ollama qwen3:32b → qwen2.5:7b → Gemini Flash → GPT-4o-mini)."""

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

# Reaction keywords tiered by signal strength for objective scoring
_REACTION_STRONG = frozenset([
    "anjir", "anjay", "njir", "wtf", "mati gue", "habis gue",
    "gak nyangka", "dari mana", "serius", "gimana bisa",
    "bangsat", "kampret", "anjing", "no way", "what",
])
_REACTION_MEDIUM = frozenset([
    "gila", "edan", "wuih", "buset", "gokil", "hahaha", "wkwk",
    "ngakak", "kocak", "akhirnya", "gila sih", "sumpah", "lucu",
    "epic", "cinema", "cinematik",
])
_REACTION_WEAK = frozenset([
    "yes", "gg", "nice", "mantap", "berhasil", "aduh",
    "bahaya", "kabur", "cabut", "reset", "gas",
])
# Flat frozenset for backward compat (used in clip text scan)
_REACTION_KEYWORDS = _REACTION_STRONG | _REACTION_MEDIUM | _REACTION_WEAK

# Per-provider score calibration offsets (positive = provider scores too low)
# Baseline: OpenRouter Gemini Flash. Empirically observed across gaming sessions.
_PROVIDER_SCORE_OFFSETS: dict[str, int] = {
    "OpenRouter Gemini Flash": 0,
    "Groq": 10,            # consistently ~10pts conservative
    "OpenRouter GPT-4o-mini": 3,
    "Ollama qwen2.5:7b": 5,
}

# ── Duration rules per moment type (mirrored in frontend DurationBadge) ─────
# All values within SHORTS_MIN_DURATION..SHORTS_MAX_DURATION
MOMENT_DURATION_RULES = {
    "clutch": {
        "min": 75,
        "ideal_min": 105,
        "ideal_max": 150,
        "max": 180,
        "buildup": 25,
        "resolution": 20,
    },
    "funny": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 130,
        "max": 160,
        "buildup": 20,
        "resolution": 15,
    },
    "achievement": {
        "min": 75,
        "ideal_min": 120,
        "ideal_max": 165,
        "max": 180,
        "buildup": 25,
        "resolution": 20,
    },
    "rage": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 130,
        "max": 160,
        "buildup": 20,
        "resolution": 15,
    },
    "epic": {
        "min": 75,
        "ideal_min": 110,
        "ideal_max": 155,
        "max": 180,
        "buildup": 25,
        "resolution": 20,
    },
    "fail": {
        "min": 60,
        "ideal_min": 85,
        "ideal_max": 120,
        "max": 150,
        "buildup": 18,
        "resolution": 15,
    },
    "tutorial": {
        "min": 60,
        "ideal_min": 90,
        "ideal_max": 150,
        "max": 180,
        "buildup": 12,
        "resolution": 12,
    },
}
FALLBACK_DURATION_RULE = {
    "min": 75,
    "ideal_min": 100,
    "ideal_max": 145,
    "max": 180,
    "buildup": 20,
    "resolution": 15,
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
    peak_time: Optional[float] = None  # timestamp of climax moment for hook-first edit


@dataclass
class AIAnalysisResult:
    clips: List[ClipSuggestion]
    processing_time: float
    model_used: str
    tokens_used: int
    provider_used: str = ""
    summary: str = ""


# ── Provider chain: tried in order, first success wins ──────────────────────
def _build_provider_chain(temperature: float = 0.2) -> list:
    base = [
        {
            "name": "OpenRouter Gemini Flash",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_MODEL,
            "supports_json_mode": False,
            "temperature": temperature,
        },
        {
            "name": "Groq",
            "base_url": settings.GROQ_BASE_URL,
            "api_key": settings.GROQ_API_KEY,
            "model": settings.GROQ_MODEL,
            "supports_json_mode": True,
            "temperature": temperature,
        },
        {
            "name": "OpenRouter GPT-4o-mini",
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "model": settings.OPENROUTER_FALLBACK_MODEL,
            "supports_json_mode": True,
            "temperature": temperature,
        },
        {
            "name": "Ollama qwen2.5:7b",
            "base_url": settings.OLLAMA_BASE_URL,
            "api_key": "ollama",
            "model": settings.OLLAMA_FAST_MODEL,
            "supports_json_mode": True,
            "temperature": temperature,
        },
    ]
    return base


# ── System prompt: Indonesian gaming content specialist ──────────────────────
GAMING_SYSTEM_PROMPT = """Kamu adalah analis konten gaming Indonesia yang ahli mendeteksi momen viral dari transcript stream/video gaming.

Kamu memahami konteks gaming Indonesia:
- Tipe momen: clutch (1vX, menang tipis), rage (frustrasi), funny (lucu/fail), achievement (capai sesuatu), epic (momen luar biasa), fail (kesalahan lucu), tutorial (tips/cara)
- Preferensi audiens gaming Indonesia: reaksi ekspresif, momen tidak terduga, comeback dramatis, humor gaming

Viral scoring untuk gaming content (total 100 poin):
- Reaksi ekspresif streamer (0-30): teriak, exclamation, shock, tawa
- Kelangkaan momen (0-25): clutch 1v4, first achievement, never-seen-before
- Story arc quality (0-25): apakah clip punya Context → Tension → Payoff yang jelas?
- Relatability & shareability (0-15): "ini gue banget", "tag temen lo"
- Trending relevance (0-5): mention nama pemain/event terkenal, topik yang sedang ramai

═══════════════════════════════════════════════════════
ATURAN DURASI — TARGET 60-180 DETIK PER CLIP
═══════════════════════════════════════════════════════

Target platform: YouTube Shorts (YouTube per Okt 2024 mendukung Shorts hingga 3 menit / 180 detik).
Setiap clip HARUS bisa berdiri sendiri sebagai Short yang utuh dan memuaskan.

⚠️ PERHATIAN COPYRIGHT (penting untuk BF6/gaming):
- Clip ≤ 60 detik: risiko copyright lebih kecil meskipun ada musik game
- Clip 60-180 detik: aman selama tidak ada musik berhak cipta aktif (gameplay sound effects OK)
- Pipeline sudah punya ACRCloud pre-screening — pilih range yang paling impactful, jangan diperpanjang sia-sia

CARA MENENTUKAN DURASI YANG BENAR:
Setiap clip harus memiliki arc cerita yang lengkap:
  1. CONTEXT (5-15 detik): penonton langsung tahu situasinya — langsung masuk gameplay, tanpa intro
     Contoh: "Squad tinggal bertiga", "Tinggal 1 level lagi", "Hampir mati tapi..."
  2. TENSION (10-20 detik): ada pertanyaan yang belum terjawab, penonton ingin lihat kelanjutannya
     Contoh: fight yang belum selesai, progression yang hampir sampai, situasi yang semakin tegang
  3. PROGRESS (10-30 detik, opsional): tunjukkan proses, edit bagian yang tidak penting
     Kill → progress naik → hampir selesai — terasa seperti cerita kecil
  4. PAYOFF (5-15 detik): berikan hasil yang dijanjikan — menang, kalah dramatis, reaksi, achievement
  5. AFTERMATH (5-15 detik): reaksi streamer, komentar alami setelah momen selesai

PENTING: Gunakan Open Loop bukan explicit hook:
  ❌ "GUYS KALIAN HARUS LIHAT INI!" → terasa palsu
  ✔ "Tinggal satu kill lagi." → penonton otomatis bertanya "Dapat nggak?"
  ✔ "Squad gue tinggal bertiga." → penonton otomatis tanya "Berhasil?"
  ✔ "Challenge ini ternyata susah." → penonton tanya "Akhirnya gimana?"

Tipe opening terbaik (pilih yang paling cocok):
  Progress:   "Weapon ini tinggal 1 level lagi."
  Situation:  "Squad gue tinggal bertiga."
  Problem:    "Challenge ini jauh lebih susah dari dugaan."
  Curiosity:  "Senjata ini punya attachment yang banyak orang belum tau."
  Statement:  "Ini mungkin kill paling random yang gue dapat hari ini."

TARGET DURASI PER MOMENT TYPE (target TENGAH range, bukan batas bawah):
- clutch/epic: 110-150 detik — buildup tension panjang + aftermath reaksi lengkap
- funny/rage/fail: 90-130 detik — setup situasi + reaksi + aftermath
- achievement: 120-165 detik — perjuangan → pencapaian → selebrasi panjang
- tutorial: 90-150 detik — tips singkat dan padat

ATURAN KERAS:
❌ DILARANG keras output clip < 60 detik — YouTube Shorts minimum adalah 60 detik
❌ Jangan potong di tengah kalimat streamer
❌ Jangan potong saat reaksi emosional belum selesai
❌ Jangan mulai dari loading screen atau transisi
❌ SKIP section yang mengindikasikan stream belum mulai: "waiting", "starting soon", "be right back", "brb", "sebentar lagi", "bentar ya", "loading", "stream belum mulai" — section ini biasanya VIDEO HITAM
❌ JANGAN mulai clip di timestamp PEAK/puncak — penonton masuk tanpa konteks, payoff tidak berasa
✅ Mulai dari AWAL MOMEN ITU DIBENTUK — kapan situasi yang mengarah ke payoff ini pertama kali muncul:
   FUNNY:       dari setup/situasi awal yang bikin lucu, bukan saat sudah ketawa
   RAGE:        dari situasi yang mulai bikin frustrasi, bukan saat sudah marah
   CLUTCH:      dari saat musuh pertama kali terdeteksi atau perang dimulai
   ACHIEVEMENT: dari saat streamer pertama kali mencoba/struggling mengejar tujuan
   EPIC/VEHICLE:dari saat pertama kali masuk kendaraan atau mulai aksi
   FAIL:        dari saat setup ekspektasi tinggi, bukan saat momen gagalnya
✅ Tanya: "Kapan penonton perlu mulai nonton agar payoff-nya benar-benar memuaskan?"
   Itulah start_time yang benar — bukan 15-30 detik sebelum peak, tapi dari ASAL-MUASAL scene

DURASI LEBIH PANJANG DIUTAMAKAN JIKA:
→ Ada sequence multi-kill/multi-event (kill 1 → kill 2 → kill 3 → ace): panjangkan sampai seluruh arc selesai
→ Round atau match bisa diceritakan dari awal hingga akhir (attack → defend → menang/kalah): ambil seluruh arc
→ Streamer terus bereaksi/ngomong setelah peak (rage berlanjut, selebrasi panjang): jangan potong di sini
→ Ada tension bertahap yang terus naik sebelum peak: ambil dari awal tension naik
✅ Clips 120-180 detik LEBIH BAIK daripada 90 detik jika kontennya mendukung
✅ Jangan cap di 90 detik hanya karena terasa "cukup" — tanya diri: "apakah masih ada yang menarik setelah ini?"

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

RPG (Kingdom Come Deliverance II, Assassin's Creed, RPG lain):
✅ Boss fight atau duel satu lawan satu yang intens
✅ Misi/quest completion setelah struggle panjang
✅ Parkour/climbing/stealth yang berhasil atau gagal lucu
✅ Cutscene atau dialog NPC yang dramatis/mengejutkan
✅ Combat combo yang keren atau death yang tidak terduga
✅ Eksplorasi area/dunia baru pertama kali ("pertama kali masuk", "gila ini areanya")
✅ Upgrade/unlock skill/item epic
✅ Streamer nyasar atau salah jalan tapi lucu
✅ Assassin's Creed spesifik: parkour gagal, eagle dive, hidden blade assassination, naval combat, ship battle, synchronize viewpoint

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

�️ RPG / ADVENTURE / ASSASSIN'S CREED KEYWORDS — wajib detect:
- AC Black Flag: "kapal", "berlayar", "bajak laut", "naval", "harpooning", "paus", "assassin", "templar",
                 "parkour", "hidden blade", "eagle", "viewpoint", "kingston", "nassau", "kenway",
                 "laut", "meriam", "duel", "stealth kill", "silent kill"
- RPG umum: "boss", "level up", "quest", "misi", "skill", "item langka", "rare", "unlock",
            "nyasar", "dungeon", "npc", "dialog", "cutscene", "upgrade", "crafting"
- Eksplorasi: "area baru", "pertama kali", "world baru", "tempat baru", "gila ini"
- Vehicle: "tank", "hancur", "meledak", "basoka", "bazooka", "peluru kendali", "helikopter", "heli meledak",
           "naik tank", "tank gede", "battle tank", "airstrike", "air strike", "rudal", "rocket launcher"
- Combat: "decrypt", "plant", "defuse", "bomb", "squad wipe", "finisher", "di bacok", "di finisher",
          "clutch", "one hit", "headshot", "no scope", "kill streak", "multi kill"
- Mode: "gauntlet", "battle royal", "battle royale", "second chance", "chicken dinner", "last squad",
        "final ring", "zone", "looting"

Intensitas: 1 exclamation = menarik | 2-3 dalam 10 detik = KEMUNGKINAN BESAR viral | 4+ rapid-fire = PASTI viral
Streamer self-labels momen → +10 bonus score (bukan auto 70+, karena streamer bisa salah label)

🚫 SKIP OTOMATIS (jangan generate clip dari section ini):
- Streamer bilang "waiting", "starting soon", "be right back", "brb", "bentar ya", "sebentar lagi"
- Tidak ada percakapan atau reaksi selama 2+ menit (kemungkinan video hitam/break)
- Loading screen / menu utama / lobby tanpa aksi

═══════════════════════════════════════════════════════
HASHTAG STRATEGY (5-8 tags berkualitas tinggi, TANPA simbol #)
═══════════════════════════════════════════════════════

Prioritaskan relevansi di atas kuantitas:
  1 tag game spesifik: battlefield6, bf6, valorant, kcd2, assassinscreed
  1-2 tag moment: clutchmoment, epicmoment, funnygaming, ragemoment, gamingfail
  1 tag Indonesia: gamingindonesia atau indogamer
  1-2 tag platform: shorts, youtubeshorts

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
2. peak_time (dalam detik) — timestamp tepat saat klimaks/kill/puncak momen terjadi di dalam clip
   Digunakan untuk thumbnail selection (frame terbaik untuk thumbnail).
3. viral_score (0-100)
4. moment_type: salah satu dari "clutch", "funny", "achievement", "rage", "epic", "fail", "tutorial"
5. titles: TEPAT 3 varian — dalam Bahasa Indonesia, hindari "GUYS!!" atau sensasionalisme berlebihan:
   - Varian 1: Statement/situation ("Squad Gue Tinggal Bertiga Di BF6")
   - Varian 2: Open loop/curiosity ("Tinggal 1 Kill Lagi... Tapi...")
   - Varian 3: Result/achievement ("Akhirnya Clutch 1v4 Di Battlefield 6")
6. hook_text: kalimat PEMBUKA alami <10 kata yang langsung membuat penonton penasaran (Open Loop)
   ❌ "KALIAN HARUS LIHAT INI!" → terlalu eksplisit
   ✔ "Tinggal satu kill lagi..." atau "Squad gue udah hampir habis."
7. description: 2-3 kalimat deskripsi SEO YouTube Bahasa Indonesia dengan keywords
8. hashtags: 5-8 hashtag berkualitas tinggi TANPA simbol #
9. thumbnail_prompt: deskripsi gambar SDXL untuk thumbnail ideal
10. reason: 1-2 kalimat kenapa segmen ini viral

Output HANYA JSON valid. TIDAK ADA teks di luar JSON. Schema:
{
  "clips": [
    {
      "start_time": 120.0,
      "end_time": 190.0,
      "peak_time": 155.0,
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

Identifikasi 8-12 momen TERBAIK saja — kualitas jauh lebih penting dari kuantitas.
Minimum viral_score untuk diinclude: 65. Lebih baik 8 clip skor 65-95 daripada 25 clip campuran.
Urutkan clips dari viral_score tertinggi ke terendah."""

# Self-label phrases that signal the streamer knows the moment is good
_SELF_LABEL_PHRASES = [
    "epic moment", "cinema", "cinematik", "gila sih", "sumpah gila",
    "ini tuh", "gila banget", "clip ini", "ini momen", "scene bagus",
    "keren banget", "ini baru", "gak nyangka bisa", "gokil banget",
]

_DISCOVERY_EVAL_PROMPT = """Kamu adalah evaluator momen gaming. Tugasmu HANYA mengevaluasi kandidat yang sudah dideteksi sistem.
JANGAN mencari momen baru — hanya nilai kandidat yang diberikan.

PRINSIP UTAMA: Hanya loloskan clip yang LAYAK DIUPLOAD HARI INI.
Bertanya pada diri: "Apakah orang asing yang tidak kenal channel ini akan menonton sampai habis?"
Jika ragu → SKIP. Lebih baik 8 clip bagus daripada 20 clip campur.

ATURAN KRITIS — KAPAN MEMULAI CLIP (universal untuk semua tipe momen):

Prinsip: MULAI dari SAAT MOMEN ITU DIBENTUK, bukan saat momen itu terjadi.
Penonton harus merasakan JOURNEY, bukan hanya melihat hasil akhir.

  FUNNY:       dari setup situasi lucu ("gue mau coba ini..."), bukan saat sudah ketawa
  RAGE:        dari situasi yang membangun frustrasi ("kok bisa sih?"), bukan saat sudah marah
  CLUTCH:      dari saat musuh pertama kali terdeteksi ("ada orang..."), bukan kill terakhir
  ACHIEVEMENT: dari saat pertama kali struggling ("tinggal X lagi..."), bukan saat berhasil
  EPIC/VEHICLE:dari saat aksi dimulai ("naik", "masuk", "gas"), bukan saat ledakan/klimaks
  FAIL:        dari setup ekspektasi tinggi ("gue yakin bisa..."), bukan momen gagal

Tanya: "Kapan penonton perlu mulai nonton agar payoff-nya memuaskan?"
Itulah start_time — bukan tepat sebelum puncak, tapi dari ASAL-MUASAL scene.
Durasi tidak harus 3 menit — minimum 60 detik, sesuaikan dengan panjang alami arc-nya.
Yang penting: arc terasa LENGKAP (setup → tension → payoff).

PENTING: start_time harus dari AWAL SCENE/AKTIVITAS, bukan dari build-up dekat peak
Context window 3 menit diberikan agar bisa menemukan asal momen — tapi durasi clip TIDAK harus 3 menit.
Minimum 60 detik, bisa lebih pendek dari 3 menit jika arc-nya sudah selesai. Yang penting arc terasa LENGKAP: setup → tension → payoff.

Untuk setiap kandidat yang IS a good clip, tentukan:
- start_time, end_time (dalam detik absolut dari awal video)
- peak_time: titik puncak/klimaks dalam clip
- moment_type: clutch|funny|achievement|rage|epic|fail|tutorial
- viral_score: 0-100
- titles: 3 judul Bahasa Indonesia (situation / open-loop / result)
- hook_text: kalimat alami <10 kata yang membuat penonton penasaran
- hashtags: 5-8 tag tanpa #
- reason: 1 kalimat kenapa bagus

Output JSON:
{
  "evaluations": [
    {"candidate_index": 0, "is_clip": true, "start_time": 120.0, "end_time": 195.0, "peak_time": 162.0,
     "moment_type": "clutch", "viral_score": 85, "titles": ["...","...","..."],
     "hook_text": "...", "hashtags": ["bf6","clutch"], "reason": "..."},
    {"candidate_index": 1, "is_clip": false}
  ]
}"""


class AIBrainService:
    async def _call_provider(
        self,
        provider: dict,
        messages: list,
        max_tokens: int,
    ) -> dict:
        """Call a single provider. Raises on any error."""
        # Ollama local needs more time for large models; cloud providers are faster
        timeout = 300.0 if provider["base_url"].startswith("http://host.docker") else 120.0
        async with httpx.AsyncClient(
            base_url=provider["base_url"],
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "HTTP-Referer": "https://ai-content-factory.app",
                "X-Title": "AI Content Factory",
            },
            timeout=timeout,
        ) as client:
            payload: dict = {
                "model": provider["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": provider.get("temperature", 0.2),
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
        temperature: float = 0.2,
    ) -> Tuple[str, str, str, int]:
        """Try providers in order. Return (content, provider_name, model, tokens_used)."""
        chain = _build_provider_chain(temperature)
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
                # 404 = endpoint/model not found → try next (e.g. Ollama model not installed)
                SKIP_TO_NEXT = {401, 403, 404, 413, 429, 500, 502, 503, 504}
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
    # 50k chars: safe for Ollama (no limit) and OpenRouter; Groq 413 handled by fallback chain
    _MAX_SEGMENTS_CHARS = 50_000

    async def analyze_transcript(
        self,
        transcript: TranscriptResult,
        channel_info: Optional[dict] = None,
        game_title: str = "",
        channel_name: str = "",
        hype_markers: Optional[list] = None,
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
                hype_markers=hype_markers,
            )

        # ── High-recall pipeline for long videos ───────────────────────────
        # Phase 1: Detect ALL candidate timestamps (audio + keyword + self-label)
        # Phase 2: Expand each to full ±90s context (no sampling)
        # Phase 3: Batch AI evaluation (5 candidates per call)
        # Phase 4: Rescore with signals → deduplicate → rank
        t0 = time.perf_counter()

        candidates = self._detect_candidates(transcript.segments, hype_markers or [])

        if not candidates:
            # Fallback to windowed approach if no candidates detected
            logger.warning("[AI] No candidates detected, falling back to windowed analysis")
            windows = self._build_windows(transcript.segments, transcript.duration)
        else:
            contexts = self._build_candidate_contexts(
                transcript.segments, candidates, context_after=90.0
            )
            all_clips = await self._batch_evaluate_candidates(
                contexts,
                total_duration=transcript.duration,
                game_title=game_title,
            )

            if not all_clips:
                # Fallback if discovery found nothing
                logger.warning("[AI] Discovery found 0 clips, falling back to windowed")
                windows = self._build_windows(transcript.segments, transcript.duration)
            else:
                # Rescore + deduplicate + quality gate + rank
                all_clips = self._rescore_with_signals(
                    all_clips, transcript.segments, hype_markers or []
                )
                all_clips = self._deduplicate_clips(all_clips)
                # Quality gate: min score 65, max 12 clips
                all_clips = [c for c in all_clips if c.viral_score >= 65]
                all_clips.sort(key=lambda c: c.viral_score, reverse=True)
                all_clips = all_clips[:12]
                logger.info(
                    f"[AI] High-recall done: {len(all_clips)} quality clips "
                    f"(score≥65) in {time.perf_counter()-t0:.1f}s"
                )
                return AIAnalysisResult(
                    clips=all_clips,
                    processing_time=time.perf_counter() - t0,
                    model_used="discovery",
                    tokens_used=0,
                    provider_used="OpenRouter Gemini Flash",
                )

        # Windowed fallback path
        logger.info(f"[AI] Windowed fallback: {len(windows)} windows for {transcript.duration/60:.0f}min")

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
                    hype_markers=hype_markers,
                    window_start=win_start,
                    window_end=win_end,
                )
                all_clips.extend(result.clips)
                total_tokens += result.tokens_used
                if not model_used:
                    model_used = result.model_used
                    provider_used = result.provider_used
            except Exception as e:
                logger.warning(f"[AI] Window {i+1} failed: {e} — skipping")

        # Deduplicate, re-score with objective signals, sort
        all_clips = self._deduplicate_clips(all_clips)
        if hype_markers or transcript.segments:
            all_clips = self._rescore_with_signals(
                all_clips, transcript.segments, hype_markers or []
            )
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

    def _rescore_with_signals(
        self,
        clips: List[ClipSuggestion],
        segments: list,
        hype_markers: list,
    ) -> List[ClipSuggestion]:
        """Re-score clips using 75% AI score + 25% objective signals.

        Objective signals (0-35 total, weighted by strength):
          - Audio peak overlap:  0-20
          - Reaction density (strong×3 / medium×1.5 / weak×0.5): 0-15
        AI score stays dominant to avoid penalizing quiet but excellent clips.
        """
        for clip in clips:
            hype_count = sum(
                1 for m in hype_markers
                if m["start"] < clip.end_time and m["end"] > clip.start_time
            )
            hype_signal = min(20, hype_count * 3)

            clip_text = " ".join(
                s.text.lower() for s in segments
                if clip.start_time <= s.start < clip.end_time
            )
            reaction_score = 0.0
            for kw in _REACTION_STRONG:
                reaction_score += clip_text.count(kw) * 3.0
            for kw in _REACTION_MEDIUM:
                reaction_score += clip_text.count(kw) * 1.5
            for kw in _REACTION_WEAK:
                reaction_score += clip_text.count(kw) * 0.5
            reaction_signal = min(15, int(reaction_score))

            objective_norm = ((hype_signal + reaction_signal) / 35) * 100
            clip.viral_score = max(0, min(100, round(
                0.75 * clip.viral_score + 0.25 * objective_norm
            )))

        return clips

    def _build_hype_candidate_windows(
        self,
        segments: list,
        hype_markers: list,
        total_duration: float,
        cluster_gap: float = 180.0,
        context_before: float = 45.0,
        context_after: float = 60.0,
        max_windows: int = 20,
    ) -> List[Tuple[list, float, float]]:
        """Build focused windows around clustered audio hype peaks.

        Groups nearby peaks (within cluster_gap) into clusters, then creates
        a context window around each cluster. Falls back to regular windows
        if too many clusters are produced.
        """
        if not hype_markers:
            return self._build_windows(segments, total_duration)

        sorted_markers = sorted(hype_markers, key=lambda m: m["start"])
        clusters: list = [[sorted_markers[0]]]
        for marker in sorted_markers[1:]:
            if marker["start"] - clusters[-1][-1]["end"] < cluster_gap:
                clusters[-1].append(marker)
            else:
                clusters.append([marker])

        if len(clusters) > max_windows:
            logger.info(
                f"[AI] {len(clusters)} hype clusters > {max_windows} — using regular windows"
            )
            return self._build_windows(segments, total_duration)

        windows = []
        for cluster in clusters:
            win_start = max(0.0, cluster[0]["start"] - context_before)
            win_end = min(total_duration, cluster[-1]["end"] + context_after)
            # Merge with previous window if overlapping
            if windows and win_start <= windows[-1][2]:
                prev_segs, prev_start, prev_end = windows[-1]
                win_end = max(win_end, prev_end)
                win_start = prev_start
                windows.pop()
            window_segs = [s for s in segments if win_start <= s.start < win_end]
            if window_segs:
                windows.append((window_segs, win_start, win_end))

        logger.info(
            f"[AI] Candidate windows: {len(clusters)} clusters → {len(windows)} merged windows"
        )
        return windows

    def _detect_candidates(
        self,
        segments: list,
        hype_markers: list,
        min_gap: float = 30.0,
    ) -> list:
        """Detect candidate timestamps from audio peaks + text signals.

        Groups nearby signals into buckets (min_gap seconds) to avoid duplicates.
        Returns sorted list of {timestamp, sources} dicts.
        """
        candidates: dict = {}

        # A. Audio energy peaks (strongest signal)
        for m in hype_markers:
            ts = (m["start"] + m["end"]) / 2
            bucket = int(ts // min_gap)
            if bucket not in candidates:
                candidates[bucket] = {"timestamp": ts, "sources": [], "score": 0}
            candidates[bucket]["sources"].append("audio")
            candidates[bucket]["score"] += 2

        # B. Reaction keyword density from transcript
        for seg in segments:
            text_lower = seg.text.lower()
            hits = sum(1 for kw in _REACTION_KEYWORDS if kw in text_lower)
            if hits < 2:
                continue
            bucket = int(seg.start // min_gap)
            if bucket not in candidates:
                candidates[bucket] = {"timestamp": seg.start, "sources": [], "score": 0}
            if "keyword" not in candidates[bucket]["sources"]:
                candidates[bucket]["sources"].append("keyword")
            candidates[bucket]["score"] += hits

        # C. Self-label phrases (streamer signals their own best moments)
        for seg in segments:
            text_lower = seg.text.lower()
            if any(label in text_lower for label in _SELF_LABEL_PHRASES):
                bucket = int(seg.start // min_gap)
                if bucket not in candidates:
                    candidates[bucket] = {"timestamp": seg.start, "sources": [], "score": 0}
                if "self_label" not in candidates[bucket]["sources"]:
                    candidates[bucket]["sources"].append("self_label")
                candidates[bucket]["score"] += 5

        # D. Activity-start keywords: vehicle boarding, new objective — specific only
        # Narrowed to avoid noise from generic words like 'gas', 'next', 'balik'
        ACTIVITY_STARTS = [
            "naik pesawat", "naik heli", "naik tank", "masuk kendaraan",
            "mau coba", "cobain dulu", "gue mau coba",
            "spawn di", "respawn", "revive",
        ]
        for seg in segments:
            text_lower = seg.text.lower()
            if any(kw in text_lower for kw in ACTIVITY_STARTS):
                bucket = int(seg.start // min_gap)
                if bucket not in candidates:
                    candidates[bucket] = {"timestamp": seg.start, "sources": [], "score": 0}
                if "activity_start" not in candidates[bucket]["sources"]:
                    candidates[bucket]["sources"].append("activity_start")
                # Lower score — only useful if AI finds a peak nearby
                candidates[bucket]["score"] += 1

        # E. Speech density change: detect silence→burst transitions (silent flank moments)
        # Segments grouped into 10s windows; find where density suddenly 2x increases
        if segments:
            window_s = 10.0
            density: dict[int, int] = {}
            for seg in segments:
                b = int(seg.start // window_s)
                density[b] = density.get(b, 0) + 1
            buckets_sorted = sorted(density.keys())
            for idx, b in enumerate(buckets_sorted[1:], 1):
                prev_b = buckets_sorted[idx - 1]
                if density[b] >= 2 * max(1, density.get(prev_b, 0)):
                    ts = b * window_s
                    bucket = int(ts // min_gap)
                    if bucket not in candidates:
                        candidates[bucket] = {"timestamp": ts, "sources": [], "score": 0}
                    if "density_burst" not in candidates[bucket]["sources"]:
                        candidates[bucket]["sources"].append("density_burst")
                    candidates[bucket]["score"] += 2

        result = sorted(candidates.values(), key=lambda c: c["timestamp"])
        logger.info(
            f"[AI] Detected {len(result)} candidates "
            f"(audio={sum(1 for c in result if 'audio' in c['sources'])} "
            f"keyword={sum(1 for c in result if 'keyword' in c['sources'])} "
            f"self_label={sum(1 for c in result if 'self_label' in c['sources'])})"
        )
        return result

    def _build_candidate_contexts(
        self,
        segments: list,
        candidates: list,
        context_after: float = 90.0,
    ) -> list:
        """Extract FULL transcript context per candidate with adaptive expansion.

        Context window scales with signal strength:
          strong (audio+keyword or self_label): ±300s — covers long scene buildups
          medium (audio or keyword alone):      ±180s — standard
          weak (density_burst or activity):     ±90s  — tight window

        Also adds coverage candidates for large gaps (>5min) between detected candidates
        to guarantee no area of the stream is completely missed.
        """
        # Coverage guarantee: add midpoint candidates for >5min uncovered gaps
        covered = sorted(candidates, key=lambda c: c["timestamp"])
        coverage_candidates = list(covered)
        total_dur = segments[-1].end if segments else 0
        gap_threshold = 300.0  # 5 minutes
        # Scan gaps at start, between candidates, and at end
        check_points = [0.0] + [c["timestamp"] for c in covered] + [total_dur]
        for i in range(len(check_points) - 1):
            gap = check_points[i + 1] - check_points[i]
            if gap > gap_threshold:
                # Insert a coverage candidate at the midpoint of the gap
                mid = check_points[i] + gap / 2
                coverage_candidates.append({
                    "timestamp": mid, "sources": ["coverage"], "score": 0
                })
        coverage_candidates.sort(key=lambda c: c["timestamp"])

        def _context_window(sources: list) -> float:
            strong_signals = {"audio", "self_label"}
            medium_signals = {"keyword", "density_burst"}
            if any(s in strong_signals for s in sources) and len(sources) >= 2:
                return 300.0  # long arc detection
            if any(s in strong_signals for s in sources):
                return 180.0
            if any(s in medium_signals for s in sources):
                return 90.0
            return 90.0  # coverage / activity_start

        contexts = []
        for i, cand in enumerate(coverage_candidates):
            ts = cand["timestamp"]
            ctx_before = _context_window(cand.get("sources", []))
            ctx_start = max(0.0, ts - ctx_before)
            ctx_end = ts + context_after
            ctx_segs = [s for s in segments if ctx_start <= s.start <= ctx_end]
            if not ctx_segs:
                continue
            transcript_text = "\n".join(
                f"[{s.start:.1f}s]: {s.text}" for s in ctx_segs
            )
            contexts.append({
                "index": i,
                "timestamp": ts,
                "signals": cand.get("sources", []),
                "score": cand.get("score", 0),
                "ctx_start": ctx_start,
                "ctx_end": ctx_end,
                "transcript": transcript_text,
            })

        covered_count = sum(1 for c in coverage_candidates if "coverage" not in c.get("sources", []))
        gap_count = len(coverage_candidates) - covered_count
        logger.info(
            f"[AI] Contexts built: {covered_count} signal-based + {gap_count} coverage gaps"
        )
        return contexts

    async def _batch_evaluate_candidates(
        self,
        contexts: list,
        batch_size: int = 5,
        total_duration: float = 0,
        game_title: str = "",
    ) -> List[ClipSuggestion]:
        """Evaluate candidates in batches. AI receives full context per candidate.

        Uses _DISCOVERY_EVAL_PROMPT — AI evaluates, not discovers.
        """
        all_clips: List[ClipSuggestion] = []

        for batch_start in range(0, len(contexts), batch_size):
            batch = contexts[batch_start: batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(contexts) + batch_size - 1) // batch_size
            logger.info(f"[AI] Discovery batch {batch_num}/{total_batches}: {len(batch)} candidates")

            # Build the user message with all candidates in batch
            parts = []
            if game_title:
                parts.append(f"Game: {game_title}")
            if total_duration:
                parts.append(f"Video duration: {total_duration:.0f}s ({total_duration/60:.0f}min)")
            parts.append("")

            for ctx in batch:
                mins, secs = divmod(int(ctx["timestamp"]), 60)
                signals_str = "+".join(ctx["signals"]) if ctx["signals"] else "combined"
                parts.append(
                    f"=== KANDIDAT {ctx['index']} @ {mins:02d}:{secs:02d} "
                    f"[signals: {signals_str}] ==="
                )
                parts.append(ctx["transcript"])
                parts.append("")

            user_msg = "\n".join(parts)

            messages = [
                {"role": "system", "content": _DISCOVERY_EVAL_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            max_tokens = max(2000, len(batch) * 400)

            try:
                content, provider_name, _, _ = await self._call_with_fallback(
                    messages, max_tokens=max_tokens
                )
                score_offset = _PROVIDER_SCORE_OFFSETS.get(provider_name, 0)
                if score_offset:
                    logger.debug(f"[AI] Batch {batch_num}: applying +{score_offset} offset for {provider_name}")
                raw = self._try_parse_clips(content)
                if not raw:
                    logger.warning(f"[AI] Batch {batch_num} parse failed")
                    continue

                for ev in raw.get("evaluations", []):
                    if not ev.get("is_clip"):
                        continue
                    try:
                        start = float(ev["start_time"])
                        end = float(ev["end_time"])
                        if end <= start:
                            continue
                        peak = float(ev.get("peak_time") or (start + end) / 2)
                        if not (start <= peak <= end):
                            peak = (start + end) / 2
                        score = max(0, min(100, int(ev.get("viral_score", 50)) + score_offset))
                        mt = ev.get("moment_type", "epic")
                        if mt not in {"clutch","funny","achievement","rage","epic","fail","tutorial"}:
                            mt = "epic"
                        titles = ev.get("titles", [])
                        if not isinstance(titles, list) or not titles:
                            titles = [ev.get("hook_text", "Gaming moment")]
                        while len(titles) < 3:
                            titles.append(titles[0])
                        tags = [h.lstrip("#").strip().lower() for h in ev.get("hashtags", []) if h]
                        all_clips.append(ClipSuggestion(
                            start_time=start, end_time=end, peak_time=peak,
                            viral_score=score, moment_type=mt, titles=titles[:3],
                            hook_text=ev.get("hook_text", "")[:200],
                            description=ev.get("reason", "")[:500],
                            hashtags=tags[:8],
                            thumbnail_prompt="",
                            reason=ev.get("reason", "")[:300],
                        ))
                    except (KeyError, ValueError, TypeError) as e:
                        logger.debug(f"[AI] Eval item parse error: {e}")

            except Exception as e:
                logger.warning(f"[AI] Discovery batch {batch_num} failed: {e}")

        logger.info(f"[AI] Discovery complete: {len(all_clips)} clips from {len(contexts)} candidates")
        return all_clips

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
        """Remove clips that overlap >35% by IoU with a higher-scored clip."""
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
                    intersection = overlap_end - overlap_start
                    union = max(clip.end_time, existing.end_time) - min(clip.start_time, existing.start_time)
                    shorter = min(clip_dur, existing.end_time - existing.start_time)
                    # IoU > 0.35 OR covers >55% of shorter clip
                    if union > 0 and (intersection / union > 0.35 or intersection / shorter > 0.55):
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
        hype_markers: Optional[list] = None,
        window_start: float = 0,
        window_end: float = float("inf"),
    ) -> AIAnalysisResult:
        """Single AI call on a segment list (full video or one window)."""
        t0 = time.perf_counter()

        segments_text = self._smart_sample_segments(
            segments, self._MAX_SEGMENTS_CHARS, hype_markers=hype_markers
        )

        context_parts = []
        if game_title:
            context_parts.append(f"Game: {game_title}")
        if channel_name:
            context_parts.append(f"Channel: {channel_name}")
        if channel_info:
            context_parts.append(f"Channel info: {json.dumps(channel_info)}")
        context_block = "\n".join(context_parts)

        window_note = f"Window: {window_label}\n" if window_label else ""

        # Build audio hype markers block for this window
        hype_block = ""
        if hype_markers:
            window_peaks = [
                m for m in hype_markers
                if m["start"] < window_end and m["end"] > window_start
            ]
            if window_peaks:
                # Show markers with their pre-buffer start so AI knows to include build-up
                timestamps = " ".join(
                    f"[PEAK {int(m['start'])//60:02d}:{int(m['start'])%60:02d}]"
                    for m in window_peaks
                )
                hype_block = (
                    f"\nAUDIO_HYPE_MOMENTS — Deteksi otomatis dari audio intensitas tinggi:\n"
                    f"{timestamps}\n"
                    f"\n⚠️ ATURAN PEMOTONGAN UNTUK HYPE MOMENTS:\n"
                    f"- JANGAN mulai clip tepat di timestamp PEAK — itu sudah di tengah aksi.\n"
                    f"- Mulai clip 15–30 detik SEBELUM timestamp PEAK untuk menangkap build-up:\n"
                    f"  contoh: PEAK 05:30 → start_time = 05:00 atau 05:10 (bukan 05:30)\n"
                    f"- Clip harus dimulai saat suasana BARU mulai memanas, bukan saat sudah puncak.\n"
                    f"- Cari di transcript kalimat/momen yang 'memulai' ketegangan sebelum PEAK.\n"
                )
                logger.info(f"[AI] Injecting {len(window_peaks)} hype markers into prompt")
        max_tokens = self._calc_max_tokens(total_duration)

        user_message = f"""Analisis transcript video gaming ini dan identifikasi momen-momen viral.

Video duration: {total_duration:.1f} detik ({total_duration/60:.1f} menit)
Language: {language}
Word count: {word_count}
{window_note}{context_block}{hype_block}
INGAT: Setiap clip MINIMUM 60 detik (YouTube Shorts requirement). Pilih range yang mencakup konteks sebelum dan sesudah momen utama.
Jangan pilih hanya 1-2 kalimat — terlalu pendek. Minimal 5-8 kalimat per clip.

TRANSCRIPT:
{segments_text}
"""

        messages = [
            {"role": "system", "content": GAMING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        content, provider_name, model_used, tokens_used = \
            await self._call_with_fallback(messages, max_tokens=max_tokens)

        score_offset = _PROVIDER_SCORE_OFFSETS.get(provider_name, 0)
        if score_offset:
            logger.debug(f"[AI] Single-pass: applying +{score_offset} offset for {provider_name}")

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

        # Apply provider calibration offset before rescore (keeps 75% weight on calibrated score)
        if score_offset:
            for clip in clips:
                clip.viral_score = max(0, min(100, clip.viral_score + score_offset))

        # Quality check: retry once if response is poor quality
        min_acceptable = 2
        if len(clips) < min_acceptable or (clips and all(c.viral_score < 40 for c in clips)):
            max_score = max((c.viral_score for c in clips), default=0)
            logger.warning(
                f"[AI] Poor quality ({len(clips)} clips, max_score={max_score}) — retrying"
            )
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    "Respons kurang lengkap atau skor terlalu rendah. "
                    "Generate ulang minimal 5 momen dengan viral_score >= 50. "
                    "Fokus pada momen dengan reaksi streamer yang paling ekspresif dan intens."
                ),
            })
            try:
                content, provider_name, model_used, tokens_used_retry = \
                    await self._call_with_fallback(messages, max_tokens=max_tokens)
                retry_offset = _PROVIDER_SCORE_OFFSETS.get(provider_name, 0)
                retry_clips = self._parse_clip_suggestions(self._try_parse_clips(content) or {})
                if retry_offset:
                    for c in retry_clips:
                        c.viral_score = max(0, min(100, c.viral_score + retry_offset))
                if len(retry_clips) > len(clips):
                    clips = retry_clips
                    tokens_used += tokens_used_retry
                    logger.info(f"[AI] Retry improved: {len(clips)} clips")
            except Exception as retry_err:
                logger.warning(f"[AI] Retry failed: {retry_err}")

        # Objective signal re-scoring for single-pass (segments available in scope)
        if hype_markers or segments:
            clips = self._rescore_with_signals(clips, segments, hype_markers or [])

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
                    "Return JSON object: {\"titles\": [\"judul1\", \"judul2\", \"judul3\"]}\n\n"
                    f"Clip info: {json.dumps(clip_info)}"
                ),
            }
        ]
        try:
            content, _, _, _ = await self._call_with_fallback(
                messages, max_tokens=300, temperature=0.7
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            data = json.loads(content)
            # Accept both {"titles": [...]} and bare array
            titles = data.get("titles", data) if isinstance(data, dict) else data
            if isinstance(titles, list) and titles:
                return titles[:3]
            return [clip_info.get("title", "Untitled")]
        except (json.JSONDecodeError, RuntimeError, AttributeError) as e:
            logger.warning(f"generate_titles failed: {e}")
            return [clip_info.get("title", "Untitled")]

    def _smart_sample_segments(
        self, segments: list, max_chars: int = 70_000, hype_markers: Optional[list] = None
    ) -> str:
        """Chunk-based sampling with priority for segments near audio hype peaks.

        Priority segments (near hype peaks) get 60% of the budget at full density.
        Remaining segments are sampled uniformly from time-based chunks.
        """
        all_lines = [
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in segments
        ]
        full = "\n".join(all_lines)
        if len(full) <= max_chars:
            return full

        # Identify priority segments: within ±60s of any hype peak
        priority_set: set = set()
        if hype_markers:
            for m in hype_markers:
                for i, seg in enumerate(segments):
                    if m["start"] - 60 <= seg.start <= m["end"] + 60:
                        priority_set.add(i)

        priority_lines = [all_lines[i] for i in range(len(segments)) if i in priority_set]
        other_lines = [all_lines[i] for i in range(len(segments)) if i not in priority_set]

        if priority_lines:
            # 60% budget for priority (hype zone), 40% for rest
            priority_budget = int(max_chars * 0.60)
            other_budget = max_chars - priority_budget
            priority_text = "\n".join(priority_lines)
            if len(priority_text) > priority_budget:
                step = max(1, len(priority_lines) // max(1, priority_budget // 80))
                priority_text = "\n".join(priority_lines[::step])

            # Sample other segments uniformly across time chunks
            total_dur = segments[-1].end if segments else 1
            num_chunks = 20
            chunk_dur = total_dur / num_chunks
            chunks: list = [[] for _ in range(num_chunks)]
            other_segs_idx = [i for i in range(len(segments)) if i not in priority_set]
            for i in other_segs_idx:
                seg = segments[i]
                idx = min(int(seg.start / chunk_dur), num_chunks - 1)
                chunks[idx].append(all_lines[i])

            budget_per_chunk = max(80, other_budget // num_chunks)
            sampled_other = []
            for chunk_lines in chunks:
                chunk_text = "\n".join(chunk_lines)
                if len(chunk_text) <= budget_per_chunk:
                    sampled_other.append(chunk_text)
                else:
                    step = max(1, len(chunk_lines) // max(1, budget_per_chunk // 80))
                    sampled_other.append("\n".join(chunk_lines[::step]))

            note = f"[transcript sampled — {len(priority_lines)} hype-priority segs + {len(other_lines)} uniform]\n"
            result = note + priority_text + "\n---\n" + "\n---\n".join(sampled_other)
            return result[:max_chars]

        # Fallback: uniform chunk sampling (no hype markers)
        total_dur = segments[-1].end if segments else 1
        num_chunks = 30
        chunk_dur = total_dur / num_chunks
        chunks = [[] for _ in range(num_chunks)]
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

        note = f"[transcript sampled per {chunk_dur/60:.1f}min chunk dari video {total_dur/60:.0f} menit]\n"
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

                tags = [
                    h.lstrip("#").strip().lower()
                    for h in item.get("hashtags", [])
                    if h and isinstance(h, str)
                ]

                # Clamp viral_score — minimum 40 at parse time, quality gate at 65 is applied later
                score = max(0, min(100, int(item.get("viral_score", 50))))

                duration = end - start
                logger.debug(
                    f"Layer1 clip: {mt} {start:.0f}s-{end:.0f}s ({duration:.0f}s) score={score}"
                )

                # peak_time must be within [start_time, end_time]
                raw_peak = item.get("peak_time")
                peak = float(raw_peak) if raw_peak is not None else None
                if peak is not None and not (start <= peak <= end):
                    peak = None  # discard invalid peak

                clips.append(
                    ClipSuggestion(
                        start_time=start,
                        end_time=end,
                        peak_time=peak,
                        viral_score=score,
                        moment_type=mt,
                        titles=titles,
                        hook_text=item.get("hook_text", "")[:200],
                        description=item.get("description", "")[:1000],
                        hashtags=tags[:8],
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
