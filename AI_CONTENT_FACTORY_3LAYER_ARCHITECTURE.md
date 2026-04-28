# 🎯 AI CONTENT FACTORY — 3-Layer Moment Detection Architecture
> **Arsitektur lengkap** untuk memastikan TIDAK ADA momen viral yang hilang
> dari LIVE recording gaming (Battlefield 6, Valorant, KCD2, Arc Raiders)
> 
> Reference: Seego GG · OBS 2560x1440 @60fps · RTX 4070
> YouTube Shorts target: 60-180 detik per clip

---

## 🧠 FILOSOFI ARSITEKTUR

```
PRINSIP UTAMA:
Lebih baik 20 momen terdeteksi dan 5 di-reject oleh QC,
daripada hanya 10 momen terdeteksi dan kehilangan 10 momen epic.

MOMEN YANG HILANG DI LAYER 1 = HILANG SELAMANYA.
MOMEN YANG LOLOS KE LAYER 2 = MASIH BISA DISELAMATKAN.
```

**Analogi:**
- Layer 1 (AI Brain) = **MATA** — lihat semua yang bergerak, jangan kedip
- Layer 2 (Pipeline) = **TANGAN** — potong, extend, rapikan ke format yang benar
- Layer 3 (QC) = **QUALITY INSPECTOR** — tolak yang cacat, loloskan yang bagus

```
LIVE Recording 3 jam
        ↓
 ┌──────────────────────────────────────────┐
 │ LAYER 1 — AI BRAIN (GREEDY)             │
 │ "Tangkap SEMUA momen menarik"           │
 │ Output: 15-25 raw moments               │
 │ Durasi: TIDAK difilter                  │
 │ Viral score min: 40 (jaring lebar)      │
 └──────────────┬───────────────────────────┘
                ↓ semua momen, berapapun durasinya
 ┌──────────────────────────────────────────┐
 │ LAYER 2 — PIPELINE VALIDATOR (SMART)    │
 │ "Sesuaikan ke format YouTube Shorts"    │
 │ < 60s  → EXTEND (build-up + resolusi)   │
 │ 60-180s → PASS langsung                 │
 │ > 180s → SPLIT jadi 2 clip             │
 │ < 20s & unsalvageable → REJECT + log   │
 └──────────────┬───────────────────────────┘
                ↓ semua clip sudah 60-180s
 ┌──────────────────────────────────────────┐
 │ LAYER 3 — QC (STRICT)                   │
 │ "Jamin kualitas final"                  │
 │ Cek: silence, blur, audio clip, durasi  │
 │ Status: passed / failed / manual_review │
 └──────────────┬───────────────────────────┘
                ↓ clip bersih, siap review
 ┌──────────────────────────────────────────┐
 │ REVIEW QUEUE → Approve/Reject manual    │
 └──────────────────────────────────────────┘
```

---

## 📐 YOUTUBE SHORTS HARD LIMITS (Global Constants)

```python
# Importable dari mana saja: from app.constants import SHORTS_*
SHORTS_MIN_DURATION = 60    # detik — minimum
SHORTS_MAX_DURATION = 180   # detik — maximum (3 menit)

# Duration rules per moment type
# Semua min = 60, semua max ≤ 180
MOMENT_DURATION_RULES = {
    "clutch":      {"min": 60, "ideal_min": 75,  "ideal_max": 120, "max": 180},
    "funny":       {"min": 60, "ideal_min": 60,  "ideal_max": 90,  "max": 150},
    "achievement": {"min": 60, "ideal_min": 90,  "ideal_max": 150, "max": 180},
    "rage":        {"min": 60, "ideal_min": 70,  "ideal_max": 110, "max": 150},
    "epic":        {"min": 60, "ideal_min": 90,  "ideal_max": 140, "max": 180},
    "fail":        {"min": 60, "ideal_min": 60,  "ideal_max": 90,  "max": 150},
    "tutorial":    {"min": 60, "ideal_min": 90,  "ideal_max": 150, "max": 180},
}
```

---

## 🔍 LAYER 1 — AI BRAIN SERVICE (GREEDY DETECTION)

### Prinsip

```
TUGAS: Mendeteksi SEMUA momen menarik. Tidak memfilter. Tidak menolak.
INPUT: Transcript + timestamps dari Whisper
OUTPUT: 15-25 raw moment suggestions TANPA durasi filtering

AI Brain TIDAK BOLEH:
❌ Reject momen karena terlalu pendek
❌ Reject momen karena terlalu panjang
❌ Skip momen karena viral score "kurang tinggi"
❌ Membatasi jumlah output (lebih banyak = lebih baik)

AI Brain HARUS:
✅ Deteksi setiap perubahan emosi streamer
✅ Deteksi setiap gaming event (kill, achievement, fail, dll)
✅ Kasih viral_score seakurat mungkin
✅ Tentukan moment_type yang tepat
✅ Generate 3 judul + hashtags + description per momen
✅ Kasih start_time dan end_time yang NATURAL (bukan dipaksakan 60s)
```

### File: `backend/app/services/ai_brain.py`

```
Gunakan skill senior-backend dan senior-prompt-engineer.

═══════════════════════════════════════════════════════
PERUBAHAN DARI VERSI LAMA
═══════════════════════════════════════════════════════

1. SYSTEM PROMPT — ubah dari "defensive" ke "greedy"

HAPUS semua instruksi ini dari system prompt:
- "Semua clip MINIMUM 60 detik"
- "PERINGATAN KERAS: Kamu DILARANG menghasilkan clip yang durasinya kurang dari 60 detik"
- "Clip di bawah 60 detik otomatis DITOLAK"
- "HARD LIMIT YOUTUBE SHORTS: 60 detik MINIMUM"
- Contoh "BENAR" dan "SALAH" berdasarkan durasi

GANTI dengan instruksi ini:
"""
ATURAN DURASI — LAYER 1 (DETECTION MODE):
- Kamu sedang di mode DETEKSI, bukan mode filter.
- Tugas kamu adalah MENEMUKAN semua momen menarik.
- Kasih start_time dan end_time yang NATURAL sesuai momennya.
- Momen 25 detik? TETAP output. Pipeline akan extend nanti.
- Momen 5 menit? TETAP output. Pipeline akan split nanti.
- JANGAN manipulasi durasi. Kasih timestamp asli momen tersebut.
- Yang penting: start saat momen mulai menarik, end saat reaksi selesai.

TIPS MENENTUKAN START & END:
- start_time = saat situasi/tension MULAI terasa
- end_time = saat reaksi streamer SELESAI (kalimat terakhir selesai)
- Jangan paksa extend ke 60 detik jika momennya memang 30 detik natural
- Pipeline layer berikutnya akan handle extend/trim/split
"""

2. VIRAL SCORE THRESHOLD — turunkan dari 50 ke 40

GANTI:
"Minimum viral_score untuk diinclude: 50"
MENJADI:
"Minimum viral_score untuk diinclude: 40. Lebih baik 20 clip skor 40-80
daripada 5 clip skor 80+. Pipeline akan filter, tugas kamu deteksi."

3. GAMING EVENTS CHECKLIST — tambahkan section eksplisit

Tambahkan di system prompt:
"""
GAMING EVENTS YANG WAJIB JADI CLIP (jangan pernah skip):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FPS (Battlefield 6, Valorant):
✅ Kill streak / multikill / ace
✅ Clutch (1v2, 1v3, 1v4, 1v5)
✅ Last second win/defuse
✅ Headshot impressive / no-scope / collateral
✅ Vehicle/tank kill atau kena tank
✅ Squad wipe (menang atau kalah dramatis)
✅ Kena tembak dari arah tidak terduga
✅ Spawn kill (lucu atau kesal)

RPG (Kingdom Come Deliverance II):
✅ Boss fight defeat (terutama first attempt)
✅ Quest completion setelah struggle
✅ Dialog NPC yang aneh/lucu
✅ Combat yang tidak terduga
✅ Lockpick/steal yang menegangkan
✅ Discovery area/item baru

Survival (Arc Raiders):
✅ First encounter enemy baru
✅ Survival momen intense (hampir mati)
✅ Loot epic/rare drop
✅ Base building milestone
✅ PvE/PvP fight unexpected

Universal (semua game):
✅ Glitch / bug lucu
✅ Random funny moment
✅ Reaksi "first time" pada konten baru
✅ Streamer ngomong langsung ke kamera (personal moment)
✅ Diskusi/cerita menarik saat gameplay santai
"""

4. EXCLAMATION DETECTION HINTS

Tambahkan di system prompt:
"""
KATA-KATA KUNCI UNTUK DETEKSI MOMEN VIRAL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reaksi shock/kaget (= momen unexpected):
  "anjir", "anjay", "njir", "wuih", "buset", "gila", "edan", "wtf", "what"

Reaksi menang/berhasil (= clutch/achievement):
  "yes!", "yesss!", "akhirnya!", "berhasil!", "mantap!", "gg", "ez"

Reaksi kesal/rage (= rage moment):
  "kampret", "anjing", "tai", "bangsat", "kok bisa?!", "curang", "cheater"

Reaksi panik/takut (= survival/tension moment):
  "aduh", "mati gue", "habis gue", "bahaya!", "lari lari!", "kabur"

Reaksi tidak percaya (= unexpected moment):
  "dari mana?!", "kok bisa?!", "serius?!", "gak nyangka", "beneran?!"

Reaksi ketawa/lucu (= funny moment):
  "wkwk", "wkwkwk", "haha", "hahaha", "kocak", "ngakak", "lucu banget"

Intensitas sinyal:
- 1 exclamation = menarik tapi belum tentu viral
- 2-3 exclamation dalam 10 detik = KEMUNGKINAN BESAR viral
- 4+ exclamation rapid-fire = PASTI viral, jangan skip
"""

5. HASHTAG STRATEGY

Tambahkan di system prompt:
"""
HASHTAG STRATEGY (10-15 tags, TANPA simbol #):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lapisan 1 — Game specific (3-4): battlefield6, bf6, valorant, kcd2, arcraiders
Lapisan 2 — Gaming Indonesia (3-4): gamingindonesia, streamerindonesia, gamingid
Lapisan 3 — Moment specific (2-3):
  clutch → clutchmoment, 1v4, epicmoment
  funny → funnygaming, ngakak, kocak, wtfmoment
  achievement → akhirnya, firsttime, achievement
  rage → ragemoment, ragequit, rage
  fail → fail, gamingfail, lucu
  epic → epicgameplay, highlight, bestmoment
  tutorial → tips, tutorial, cara
Lapisan 4 — General reach (2-3): shorts, youtubeshorts, viral, fyp
"""

6. TITLE GENERATION GUIDE per moment_type

Tambahkan di system prompt:
"""
GAYA JUDUL PER MOMENT TYPE:
━━━━━━━━━━━━━━━━━━━━━━━━━

clutch:
  "1 LAWAN 4 DI [GAME] — BISA MENANG GAK NIH?"
  "DETIK TERAKHIR CLUTCH DI [GAME] INDONESIA!!"

funny:
  "DARI MANA?! [SITUASI] DI [GAME] WKWKWK"
  "[SITUASI] PALING KOCAK DI [GAME]"

achievement:
  "AKHIRNYA GUE [ACHIEVEMENT] DI [GAME]!"
  "SETELAH [X] KALI GAGAL... BERHASIL JUGA!!"

rage:
  "INI GAME CURANG!!! [SITUASI] DI [GAME]"
  "RAGE QUIT MOMENT DI [GAME] INDONESIA"

epic:
  "MOMEN PALING GILA GUE DI [GAME]!!"
  "INI BARU NAMANYA [GAME]!! [SITUASI]"

fail:
  "GUE KIRA BISA... TERNYATA [FAIL] WKWK"
  "JANGAN KAYAK GUE DI [GAME] 😂"

tutorial:
  "CARA [AKSI] DI [GAME] — TIPS YANG JARANG ORANG TAU"
  "[GAME] TUTORIAL: [TIPS] BIAR GAK NOOB"

PRINSIP:
- 1 emoji maksimal (jangan spam)
- CAPS untuk emphasis ("GILA", "AKHIRNYA")
- Bahasa Indonesia natural, campur English istilah gaming OK
- Jangan spoiler hasil untuk clutch moment
- titles WAJIB tepat 3 varian per clip
"""

7. _call_provider — CONDITIONAL response_format

UBAH:
json={
    "model": provider["model"],
    "messages": messages,
    "max_tokens": max_tokens,
    "response_format": {"type": "json_object"},
}

MENJADI:
payload = {
    "model": provider["model"],
    "messages": messages,
    "max_tokens": max_tokens,
    "temperature": 0.7,
}
# Hanya provider yang support JSON mode
if provider.get("supports_json_mode", False):
    payload["response_format"] = {"type": "json_object"}

Dan tambahkan field ke provider chain:
{
    "name": "Groq",
    ...
    "supports_json_mode": True,
},
{
    "name": "OpenRouter Gemini Flash",
    ...
    "supports_json_mode": False,  # Gemini via OpenRouter tidak konsisten
},
{
    "name": "OpenRouter GPT-4o-mini",
    ...
    "supports_json_mode": True,
},

8. _call_with_fallback — FIX error handling

UBAH:
if status not in (413, 429, 500, 502, 503, 504):
    break

MENJADI:
# 401/403 = auth error di provider INI → coba provider lain
# Jangan break seluruh chain hanya karena 1 key expired
SKIP_TO_NEXT = {401, 403, 413, 429, 500, 502, 503, 504}
if status not in SKIP_TO_NEXT:
    break

9. analyze_transcript — SMART CHUNK SAMPLING

HAPUS uniform sampling:
step = max(1, total // 800)
sampled = all_segments_lines[::step]

GANTI dengan chunk-based sampling:
def _smart_sample_segments(self, segments, max_chars=70_000) -> str:
    """
    Bagi video jadi 30 chunks waktu, sample dari setiap chunk.
    TIDAK skip segment secara uniform — preserves burst moments
    (kill streak, clutch) yang terjadi dalam waktu singkat.
    """
    all_lines = [f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}" for seg in segments]
    full = "\n".join(all_lines)
    if len(full) <= max_chars:
        return full

    # Bagi jadi 30 chunk berdasarkan timestamp
    total_dur = segments[-1].end if segments else 0
    chunk_dur = total_dur / 30
    chunks = [[] for _ in range(30)]

    for seg, line in zip(segments, all_lines):
        idx = min(int(seg.start / chunk_dur), 29)
        chunks[idx].append(line)

    # Budget char per chunk
    budget = max_chars // 30
    sampled = []
    for chunk_lines in chunks:
        chunk_text = "\n".join(chunk_lines)
        if len(chunk_text) <= budget:
            sampled.append(chunk_text)
        else:
            step = max(1, len(chunk_lines) // (budget // 80))
            sampled.append("\n".join(chunk_lines[::step]))

    note = f"[transcript sampled per {chunk_dur/60:.1f}min chunk dari video {total_dur/60:.0f} menit]"
    result = note + "\n" + "\n---\n".join(sampled)
    return result[:max_chars]

10. analyze_transcript — ADAPTIVE max_tokens

HAPUS:
await self._call_with_fallback(messages, max_tokens=4000)

GANTI:
def _calc_max_tokens(self, duration_sec: float) -> int:
    """Scale max_tokens berdasarkan durasi video."""
    minutes = duration_sec / 60
    clips_est = min(25, max(5, int(minutes / 10)))
    return min(8000, max(3000, clips_est * 350 + 1000))

max_tokens = self._calc_max_tokens(transcript.duration)

11. analyze_transcript — HAPUS full_text duplicate

HAPUS:
Full text:
{transcript.full_text[:5000]}

Ini duplicate dari segments_text — buang token sia-sia.

12. _parse_clip_suggestions — VALIDATION + NO DURATION FILTER

_parse_clip_suggestions TIDAK boleh reject berdasarkan durasi.
Hanya validasi data quality:

def _parse_clip_suggestions(self, data: dict) -> List[ClipSuggestion]:
    VALID_TYPES = {"clutch","funny","achievement","rage","epic","fail","tutorial"}
    clips = []
    for item in data.get("clips", []):
        try:
            # Validate moment_type
            mt = item.get("moment_type", "epic")
            if mt not in VALID_TYPES:
                mt = "epic"

            # Ensure 3 titles
            titles = item.get("titles", [item.get("title", "Untitled")])
            if not isinstance(titles, list): titles = [str(titles)]
            while len(titles) < 3: titles.append(titles[0])
            titles = titles[:3]

            # Clean hashtags
            tags = [h.lstrip("#").strip().lower() for h in item.get("hashtags",[]) if h]

            # Clamp viral_score
            score = max(0, min(100, int(item.get("viral_score", 50))))

            clips.append(ClipSuggestion(
                start_time=float(item["start_time"]),
                end_time=float(item["end_time"]),
                viral_score=score,
                moment_type=mt,
                titles=titles,
                hook_text=item.get("hook_text","")[:200],
                description=item.get("description","")[:1000],
                hashtags=tags[:15],
                thumbnail_prompt=item.get("thumbnail_prompt",""),
                reason=item.get("reason","")[:300],
            ))
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed clip: {e}")

    # TIDAK ADA duration filter di sini — itu tugas Layer 2
    return sorted(clips, key=lambda c: c.viral_score, reverse=True)

13. Timeout — naikkan

UBAH:
timeout=90.0

MENJADI:
timeout=120.0  # video panjang butuh waktu analisis lebih
```

---

## ⚙️ LAYER 2 — PIPELINE DURATION VALIDATOR (SMART)

### Prinsip

```
TUGAS: Menerima raw moments dari AI Brain, sesuaikan durasi ke YouTube Shorts format.
INPUT: List[ClipSuggestion] dari AI Brain (durasi bervariasi, mungkin 15s atau 300s)
OUTPUT: List[ClipSuggestion] yang SEMUA durasinya 60-180 detik

EMPAT OPERASI:
1. EXTEND — clip terlalu pendek, tambah context di awal/akhir
2. PASS   — clip sudah 60-180s, langsung lolos
3. SPLIT  — clip terlalu panjang, belah jadi 2
4. REJECT — clip < 20s dan tidak bisa di-extend → log + notify
```

### File: `backend/app/workers/tasks/pipeline_validator.py`

```
Gunakan skill senior-backend dan senior-architect.

Buat file baru: backend/app/workers/tasks/pipeline_validator.py

from app.services.ai_brain import (
    SHORTS_MIN_DURATION,    # 60
    SHORTS_MAX_DURATION,    # 180
    MOMENT_DURATION_RULES,
    FALLBACK_DURATION_RULE,
    ClipSuggestion,
)

# Batas minimum absolut — di bawah ini momen memang bukan clip material
UNSALVAGEABLE_THRESHOLD = 15  # detik


def validate_and_adjust_clips(
    clips: List[ClipSuggestion],
    video_duration: float,
    transcript_segments: List = None,
) -> Tuple[List[ClipSuggestion], List[dict]]:
    """
    Layer 2: Adjust semua clip ke YouTube Shorts format (60-180s).
    
    Return: (adjusted_clips, action_log)
    action_log berisi record setiap keputusan untuk debugging/analytics.
    """
    adjusted = []
    log = []

    for clip in clips:
        duration = clip.end_time - clip.start_time
        rule = MOMENT_DURATION_RULES.get(clip.moment_type, FALLBACK_DURATION_RULE)
        
        # ─── CASE 1: UNSALVAGEABLE (< 15 detik) ───
        if duration < UNSALVAGEABLE_THRESHOLD:
            log.append({
                "action": "REJECTED",
                "reason": f"Terlalu pendek ({duration:.0f}s) — tidak bisa di-extend natural",
                "clip_title": clip.titles[0] if clip.titles else "?",
                "moment_type": clip.moment_type,
                "original_duration": duration,
                "viral_score": clip.viral_score,
            })
            continue
        
        # ─── CASE 2: TERLALU PENDEK (15-59s) → EXTEND ───
        if duration < SHORTS_MIN_DURATION:
            extended = _try_extend_clip(
                clip=clip,
                target_duration=rule["ideal_min"],
                video_duration=video_duration,
                buildup=rule.get("buildup", 12),
                resolution=rule.get("resolution", 12),
                transcript_segments=transcript_segments,
            )
            if extended:
                new_dur = extended.end_time - extended.start_time
                log.append({
                    "action": "EXTENDED",
                    "reason": f"{duration:.0f}s → {new_dur:.0f}s",
                    "clip_title": clip.titles[0],
                    "moment_type": clip.moment_type,
                    "original_duration": duration,
                    "new_duration": new_dur,
                })
                adjusted.append(extended)
            else:
                log.append({
                    "action": "REJECTED",
                    "reason": f"Tidak bisa extend ke {SHORTS_MIN_DURATION}s (original {duration:.0f}s)",
                    "clip_title": clip.titles[0],
                    "moment_type": clip.moment_type,
                    "original_duration": duration,
                    "viral_score": clip.viral_score,
                })
            continue
        
        # ─── CASE 3: PERFECT RANGE (60-180s) → PASS ───
        if SHORTS_MIN_DURATION <= duration <= SHORTS_MAX_DURATION:
            log.append({
                "action": "PASSED",
                "clip_title": clip.titles[0],
                "moment_type": clip.moment_type,
                "duration": duration,
            })
            adjusted.append(clip)
            continue
        
        # ─── CASE 4: TERLALU PANJANG (> 180s) → SPLIT ───
        if duration > SHORTS_MAX_DURATION:
            splits = _try_split_clip(
                clip=clip,
                max_duration=SHORTS_MAX_DURATION,
                min_duration=SHORTS_MIN_DURATION,
                transcript_segments=transcript_segments,
            )
            for i, split_clip in enumerate(splits):
                split_dur = split_clip.end_time - split_clip.start_time
                log.append({
                    "action": f"SPLIT_{i+1}_OF_{len(splits)}",
                    "reason": f"Original {duration:.0f}s → split {split_dur:.0f}s",
                    "clip_title": split_clip.titles[0],
                    "moment_type": split_clip.moment_type,
                    "duration": split_dur,
                })
                adjusted.append(split_clip)

    # Log summary
    actions = [l["action"] for l in log]
    logger.info(
        f"Pipeline validator: {len(adjusted)} clips output | "
        f"PASSED: {actions.count('PASSED')}, "
        f"EXTENDED: {actions.count('EXTENDED')}, "
        f"SPLIT: {sum(1 for a in actions if a.startswith('SPLIT'))}, "
        f"REJECTED: {actions.count('REJECTED')}"
    )

    return adjusted, log


def _try_extend_clip(
    clip: ClipSuggestion,
    target_duration: float,
    video_duration: float,
    buildup: float,
    resolution: float,
    transcript_segments: List = None,
) -> Optional[ClipSuggestion]:
    """
    Extend clip pendek dengan menambah build-up dan resolusi.

    Strategi smart:
    1. Tambah build-up di awal (60% dari kebutuhan)
    2. Tambah resolusi di akhir (40% dari kebutuhan)
    3. Jika ada transcript_segments, cari natural break point
       (akhir kalimat) untuk start/end yang lebih natural

    JANGAN extend melewati:
    - 0 detik (awal video)
    - video_duration (akhir video)
    - Clip lain yang overlap (cek di caller)
    """
    current = clip.end_time - clip.start_time
    needed = max(0, target_duration - current)

    if needed <= 0:
        return clip  # sudah cukup

    # Distribusi: prioritas build-up (tension di awal lebih penting)
    add_start = min(buildup, needed * 0.6)
    add_end = min(resolution, needed * 0.4)

    # Jika masih kurang, redistribute
    total_add = add_start + add_end
    if total_add < needed:
        remaining = needed - total_add
        add_start += remaining * 0.5
        add_end += remaining * 0.5

    new_start = max(0.0, clip.start_time - add_start)
    new_end = min(video_duration, clip.end_time + add_end)
    new_duration = new_end - new_start

    # Snap ke natural break jika transcript tersedia
    if transcript_segments:
        new_start = _snap_to_sentence_boundary(
            timestamp=new_start,
            segments=transcript_segments,
            direction="before",
        )
        new_end = _snap_to_sentence_boundary(
            timestamp=new_end,
            segments=transcript_segments,
            direction="after",
        )
        new_duration = new_end - new_start

    # Toleransi 85% — jika sangat dekat target, terima
    if new_duration >= target_duration * 0.85 and new_duration >= SHORTS_MIN_DURATION:
        clip.start_time = new_start
        clip.end_time = new_end
        return clip

    return None


def _try_split_clip(
    clip: ClipSuggestion,
    max_duration: float,
    min_duration: float,
    transcript_segments: List = None,
) -> List[ClipSuggestion]:
    """
    Split clip panjang (> 180s) jadi 2 atau lebih clip yang valid.

    Strategi:
    1. Cari natural break point di tengah (silence, akhir kalimat)
    2. Jika ada transcript_segments, split di boundary kalimat
    3. Jika tidak ada, split merata tapi pastikan setiap bagian >= 60s
    4. Copy viral_score dan metadata ke kedua bagian
    5. Append " (Part 1)", " (Part 2)" ke titles
    """
    duration = clip.end_time - clip.start_time

    if duration <= max_duration:
        return [clip]  # tidak perlu split

    # Hitung berapa bagian
    num_parts = int(duration // max_duration) + (1 if duration % max_duration >= min_duration else 0)
    num_parts = max(2, num_parts)
    part_duration = duration / num_parts

    # Pastikan setiap part >= min_duration
    if part_duration < min_duration:
        num_parts = max(2, int(duration // min_duration))
        part_duration = duration / num_parts

    splits = []
    for i in range(num_parts):
        part_start = clip.start_time + (i * part_duration)
        part_end = clip.start_time + ((i + 1) * part_duration)

        # Jangan melebihi clip asli
        part_end = min(part_end, clip.end_time)
        part_dur = part_end - part_start

        if part_dur < min_duration:
            # Sisa terlalu pendek → merge dengan part terakhir
            if splits:
                splits[-1].end_time = clip.end_time
            continue

        # Snap ke sentence boundary jika ada transcript
        if transcript_segments:
            part_end = _snap_to_sentence_boundary(
                timestamp=part_end,
                segments=transcript_segments,
                direction="after",
            )

        # Buat clip baru dengan metadata ter-copy
        import copy
        split_clip = copy.deepcopy(clip)
        split_clip.start_time = part_start
        split_clip.end_time = min(part_end, clip.end_time)

        # Update titles dengan part number
        split_clip.titles = [f"{t} (Part {i+1})" for t in clip.titles]

        # Viral score sedikit turun untuk part 2+
        if i > 0:
            split_clip.viral_score = max(40, clip.viral_score - (i * 5))

        splits.append(split_clip)

    return splits


def _snap_to_sentence_boundary(
    timestamp: float,
    segments: list,
    direction: str = "after",
    search_window: float = 5.0,
) -> float:
    """
    Cari akhir kalimat terdekat dari timestamp.
    direction="before" → cari boundary SEBELUM timestamp
    direction="after"  → cari boundary SETELAH timestamp

    Tujuan: clip tidak mulai/berakhir di tengah kalimat.
    """
    best = timestamp

    for seg in segments:
        if direction == "after":
            # Cari segment.end yang paling dekat SETELAH timestamp
            if seg.end >= timestamp and seg.end <= timestamp + search_window:
                if abs(seg.end - timestamp) < abs(best - timestamp):
                    best = seg.end
        elif direction == "before":
            # Cari segment.start yang paling dekat SEBELUM timestamp
            if seg.start <= timestamp and seg.start >= timestamp - search_window:
                if abs(seg.start - timestamp) < abs(best - timestamp):
                    best = seg.start

    return best
```

### Integrasi di Pipeline

```
File: backend/app/workers/tasks/pipeline.py

Di stage antara ai_done dan clips_done, panggil validator:

# Setelah AI Brain menghasilkan clips
from app.workers.tasks.pipeline_validator import validate_and_adjust_clips

raw_clips = ai_result.clips
logger.info(f"AI Brain detected {len(raw_clips)} raw moments")

# Layer 2: validate & adjust
adjusted_clips, action_log = validate_and_adjust_clips(
    clips=raw_clips,
    video_duration=video.duration_seconds,
    transcript_segments=transcript.segments,
)

logger.info(f"After validation: {len(adjusted_clips)} clips ready for processing")

# Simpan action_log ke video.metadata untuk analytics
video.processing_log = {
    "raw_moments_detected": len(raw_clips),
    "clips_after_validation": len(adjusted_clips),
    "actions": action_log,
}

# Lanjut ke FFmpeg processing dengan adjusted_clips
```

---

## ✅ LAYER 3 — QC SERVICE (STRICT QUALITY)

### Prinsip

```
TUGAS: Validasi kualitas AKHIR clip setelah video di-cut oleh FFmpeg.
INPUT: File video clip yang sudah di-cut
OUTPUT: QCResult (passed / failed / manual_review)

Layer 3 HANYA cek kualitas TEKNIS:
- Silence detection (> 3 detik berturut-turut)
- Audio clipping (peak > -1dB)
- Blur frame detection (laplacian variance)
- Black frame detection
- Durasi FINAL (hard reject < 60s atau > 180s)
- Duration warning per moment_type (dari MOMENT_DURATION_RULES)

Layer 3 TIDAK menilai konten — itu tugas AI Brain dan user review.
```

### File: `backend/app/services/qc_service.py`

```
Gunakan skill senior-backend.

from app.services.ai_brain import (
    SHORTS_MIN_DURATION,
    SHORTS_MAX_DURATION,
    MOMENT_DURATION_RULES,
    FALLBACK_DURATION_RULE,
)

@dataclass
class QCIssue:
    type: str          # silence, audio_clip, blur, black_frame, duration
    severity: str      # error | warning | info
    message: str
    timestamp: float = 0.0    # di momen mana issue terjadi
    suggestion: str = ""

@dataclass
class QCResult:
    status: str        # passed | failed | manual_review
    issues: List[QCIssue]
    metrics: dict      # silence_total, peak_db, blur_score, etc.


class QCService:

    async def run_full_qc(
        self,
        clip_path: str,
        moment_type: str,
        expected_duration: float,
    ) -> QCResult:
        """
        Full QC check pada clip yang sudah di-cut oleh FFmpeg.
        Ini LAYER TERAKHIR sebelum clip masuk review queue.
        """
        issues = []

        # 1. Durasi hard limit
        actual_duration = await self._get_duration(clip_path)
        duration_issues = self._check_duration(
            actual_duration, moment_type
        )
        issues.extend(duration_issues)

        # 2. Silence detection
        silence_issues = await self._check_silence(clip_path)
        issues.extend(silence_issues)

        # 3. Audio clipping
        audio_issues = await self._check_audio_quality(clip_path)
        issues.extend(audio_issues)

        # 4. Blur detection
        blur_issues = await self._check_blur(clip_path)
        issues.extend(blur_issues)

        # 5. Black frame detection
        black_issues = await self._check_black_frames(clip_path)
        issues.extend(black_issues)

        # Determine overall status
        has_errors = any(i.severity == "error" for i in issues)
        has_warnings = any(i.severity == "warning" for i in issues)

        if has_errors:
            status = "failed"
        elif has_warnings:
            status = "manual_review"
        else:
            status = "passed"

        return QCResult(
            status=status,
            issues=issues,
            metrics={
                "duration": actual_duration,
                "moment_type": moment_type,
                "issue_count": len(issues),
            },
        )

    def _check_duration(
        self,
        duration: float,
        moment_type: str,
    ) -> List[QCIssue]:
        """
        Layer 3 duration check — FINAL GATE.
        Ini catch untuk clip yang entah kenapa lolos Layer 2
        tapi durasinya masih di luar range.
        """
        issues = []
        rule = MOMENT_DURATION_RULES.get(moment_type, FALLBACK_DURATION_RULE)

        # Hard reject — tidak boleh ada pengecualian
        if duration < SHORTS_MIN_DURATION:
            issues.append(QCIssue(
                type="duration_hard_fail",
                severity="error",
                message=f"Durasi {duration:.0f}s di bawah minimum Shorts ({SHORTS_MIN_DURATION}s)",
                suggestion="Clip ini seharusnya sudah di-extend oleh pipeline",
            ))
        elif duration > SHORTS_MAX_DURATION:
            issues.append(QCIssue(
                type="duration_hard_fail",
                severity="error",
                message=f"Durasi {duration:.0f}s melebihi maximum Shorts ({SHORTS_MAX_DURATION}s)",
                suggestion="Clip ini seharusnya sudah di-split oleh pipeline",
            ))

        # Soft warning — durasi valid tapi tidak ideal
        elif duration < rule["ideal_min"]:
            issues.append(QCIssue(
                type="duration_below_ideal",
                severity="info",
                message=f"[{moment_type}] Durasi {duration:.0f}s — idealnya {rule['ideal_min']}–{rule['ideal_max']}s",
                suggestion="Pertimbangkan extend sedikit untuk engagement optimal",
            ))
        elif duration > rule["max"]:
            issues.append(QCIssue(
                type="duration_above_type_max",
                severity="warning",
                message=f"[{moment_type}] Durasi {duration:.0f}s melebihi max untuk tipe ini ({rule['max']}s)",
                suggestion=f"{moment_type} content biasanya lebih efektif di bawah {rule['max']}s",
            ))

        return issues

    async def _check_silence(self, clip_path: str) -> List[QCIssue]:
        """Deteksi silence > 3 detik menggunakan FFmpeg silencedetect."""
        # ffmpeg -i clip.mp4 -af silencedetect=n=-45dB:d=3 -f null -
        # Parse output untuk silence_start, silence_end, silence_duration
        # Flag sebagai warning jika total silence > 5 detik
        # Flag sebagai error jika silence di 5 detik pertama (hook mati)
        ...

    async def _check_audio_quality(self, clip_path: str) -> List[QCIssue]:
        """Deteksi audio clipping menggunakan FFmpeg loudnorm."""
        # ffmpeg -i clip.mp4 -af loudnorm=print_format=json -f null -
        # Flag jika peak > -1dB (audio clip)
        # Flag jika average loudness < -30dB (terlalu pelan)
        ...

    async def _check_blur(self, clip_path: str) -> List[QCIssue]:
        """Sampling frame setiap 2 detik, hitung laplacian variance."""
        # Jika rata-rata variance < threshold → blur warning
        # Jika > 50% frame blur → error
        ...

    async def _check_black_frames(self, clip_path: str) -> List[QCIssue]:
        """Deteksi black frame > 2 detik menggunakan FFmpeg blackdetect."""
        # ffmpeg -i clip.mp4 -vf blackdetect=d=2:pix_th=0.10 -f null -
        # Flag sebagai warning
        ...
```

---

## 📊 MONITORING & ANALYTICS

### Processing Log Schema

```
Setiap video yang diproses menyimpan log lengkap di video.processing_log (JSONB):

{
    "pipeline_version": "1.0",
    "processed_at": "2026-04-28T14:30:00Z",
    "total_duration_seconds": 7374,

    "layer1_ai_brain": {
        "provider_used": "Groq",
        "model": "llama-3.3-70b-versatile",
        "processing_time_seconds": 12.5,
        "tokens_used": 4200,
        "raw_moments_detected": 18,
        "viral_score_distribution": {
            "40-59": 5,
            "60-79": 8,
            "80-100": 5
        }
    },

    "layer2_validator": {
        "input_clips": 18,
        "output_clips": 15,
        "actions": {
            "PASSED": 10,
            "EXTENDED": 3,
            "SPLIT": 1,    
            "REJECTED": 4   
        },
        "rejected_details": [
            {
                "title": "Loading screen moment",
                "reason": "Terlalu pendek (8s) — unsalvageable",
                "viral_score": 42
            }
        ]
    },

    "layer3_qc": {
        "input_clips": 15,
        "passed": 12,
        "manual_review": 2,
        "failed": 1,
        "common_issues": ["silence_beginning", "blur_detected"]
    },

    "final_output": {
        "clips_ready_for_review": 14,
        "avg_viral_score": 68.5,
        "avg_duration_seconds": 95,
        "moment_type_distribution": {
            "clutch": 3,
            "funny": 5,
            "epic": 2,
            "achievement": 2,
            "rage": 1,
            "fail": 1
        }
    }
}

Manfaat log ini:
1. Debug: kenapa momen tertentu hilang? → cek action_log
2. Analytics: seberapa efektif AI Brain? → cek viral_score_distribution
3. Optimasi: AI terlalu banyak reject? → turunkan threshold
4. Monitoring: provider mana yang paling sering dipakai? → cek provider_used
5. Weekly insight: rata-rata berapa clips per video? → aggregate dari log
```

---

## 🧪 TESTING STRATEGY

```
Gunakan skill code-reviewer.

Test Layer 1 (AI Brain):
- [ ] Input video 30 menit → output minimal 5 raw moments
- [ ] Input video 3 jam → output 15-25 raw moments
- [ ] Clip < 60s TETAP ada di output (tidak di-reject oleh AI)
- [ ] Clip > 180s TETAP ada di output (tidak di-reject oleh AI)
- [ ] Viral score range 40-100 (bukan hanya 80+)
- [ ] Setiap clip punya 3 titles, hashtags, moment_type valid

Test Layer 2 (Pipeline Validator):
- [ ] Clip 35 detik → di-extend ke 60-75s
- [ ] Clip 45 detik → di-extend ke 60s minimal
- [ ] Clip 90 detik → PASS langsung
- [ ] Clip 250 detik → SPLIT jadi 2 clip (masing-masing 60-180s)
- [ ] Clip 10 detik → REJECT (unsalvageable)
- [ ] Clip di dekat awal video (start 0.0) → extend hanya ke depan
- [ ] Clip di dekat akhir video → extend hanya ke belakang
- [ ] Sentence boundary snapping berfungsi
- [ ] action_log ter-record dengan benar

Test Layer 3 (QC):
- [ ] Clip 59s → error (hard fail)
- [ ] Clip 181s → error (hard fail)
- [ ] Clip 70s funny → info (below ideal_min)
- [ ] Clip dengan 5 detik silence → warning
- [ ] Clip dengan silence di detik pertama → error (hook mati)
- [ ] Semua metrics ter-record di QCResult

Integration Test:
- [ ] Upload video Battlefield 6 2 jam → pipeline end-to-end
- [ ] Hitung: berapa momen yang terdeteksi, berapa yang lolos
- [ ] Bandingkan: manual clip vs AI clip → AI tidak boleh miss yang kamu clip manual
- [ ] Cek processing_log di DB → semua data lengkap
```

---

## 🎯 EXECUTION ORDER

```
[ ] 1. Update ai_brain.py — hapus duration filtering dari Layer 1
[ ] 2. Update ai_brain.py — system prompt greedy + gaming events + exclamations
[ ] 3. Update ai_brain.py — response_format conditional + error handling
[ ] 4. Update ai_brain.py — smart chunk sampling + adaptive max_tokens
[ ] 5. Buat pipeline_validator.py — extend/pass/split/reject logic
[ ] 6. Buat _snap_to_sentence_boundary — natural cut points
[ ] 7. Update pipeline.py — integrasikan validator antara AI dan FFmpeg
[ ] 8. Update qc_service.py — duration check per moment_type
[ ] 9. Update video.processing_log schema — simpan action_log
[ ] 10. Buat test cases — semua 3 layer
[ ] 11. Test end-to-end — upload video Battlefield 6 2 jam
```

---

## ⚠️ CRITICAL RULES

1. **Layer 1 TIDAK BOLEH reject momen berdasarkan durasi** — biarkan pipeline handle
2. **Layer 2 HARUS try extend sebelum reject** — extend > reject
3. **Layer 3 HANYA cek teknis** — tidak menilai "apakah konten menarik"
4. **Sentence boundary snapping** — clip tidak boleh mulai/akhir di tengah kalimat
5. **Processing log wajib** — setiap keputusan harus traceable
6. **SHORTS_MIN_DURATION dan SHORTS_MAX_DURATION sebagai single source of truth** — import dari constants, jangan hardcode angka 60/180 di tempat lain
7. **Split harus menghasilkan clip yang masing-masing valid** — jangan split jadi 1 clip 170s dan 1 clip 30s
8. **Backward compatible** — perubahan tidak boleh break pipeline yang sudah running

---

*3-Layer Moment Detection Architecture — AI Content Factory*
*LAYER 1: Greedy Detection (miss nothing)*
*LAYER 2: Smart Adjustment (fit to Shorts format)*
*LAYER 3: Quality Gate (ensure production quality)*
*Target: 0% false negatives — setiap momen viral PASTI terdeteksi*
