# 📊 AI CONTENT FACTORY — Enhanced Analytics Module Prompt
> **Addon prompt** untuk dijalankan setelah MVP base selesai
> Fokus: YouTube Analytics Dashboard + Content DNA Engine dari data real channel
> Reference channel: **Seego GG** (Gaming / LIVE Recording niche)

---

## 🧠 SYSTEM CONTEXT

Kamu adalah **Senior Fullstack Architect + Data Engineer** yang membangun modul **Enhanced Analytics** untuk AI Content Factory.

Konteks channel yang sudah terkoneksi:
- **Channel:** Seego GG (UCZtV_QayiN8qJeTGWA8YSrw)
- **Niche:** Gaming Indonesia — LIVE Recordings (Battlefield 6, Kingdom Come Deliverance II, Arc Raiders)
- **Stats:** 2.5K subscribers, 82.2K total views, 272 videos, avg 302 views/video
- **Problem:** Semua konten LIVE recording 2–5 jam, views masih rendah, judul belum teroptimasi
- **Opportunity:** 1 LIVE 3 jam → bisa generate 15–25 clips viral dengan AI

**Scope modul ini:**
1. Enhanced YouTube Analytics Dashboard (frontend)
2. Analytics Data Service (backend — fetch + store + process)
3. Content DNA Engine (AI yang belajar dari historis channel)
4. Insight Report Generator (weekly AI-generated report)
5. Viral Pattern Database untuk gaming niche

**OAuth Scopes yang dibutuhkan:**
```
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/yt-analytics.readonly        ← KRUSIAL untuk retention/watch time
https://www.googleapis.com/auth/yt-analytics-monetary.readonly ← Opsional untuk monetisasi
```

---

## 🗄️ STEP A — Database Schema Tambahan

```
Gunakan skill senior-architect dan senior-backend.

Tambahkan tabel-tabel berikut ke Alembic migration baru:
nama file: 002_analytics_schema.py

TABEL: video_analytics
Simpan snapshot performa per video, di-pull secara berkala.

Kolom:
- id: UUID PK
- video_id: UUID FK → videos (cascade delete)
- youtube_video_id: String(50) NOT NULL  ← ID di YouTube
- channel_id: String(255) NOT NULL
- snapshot_date: Date NOT NULL           ← Tanggal data di-pull
- views: Integer default 0
- likes: Integer default 0
- comments: Integer default 0
- shares: Integer default 0
- watch_time_minutes: Float default 0    ← Total menit ditonton (yt-analytics)
- avg_view_duration_seconds: Float       ← Rata-rata durasi tonton per viewer
- avg_view_percentage: Float             ← % video yang ditonton rata-rata
- impressions: Integer default 0         ← Berapa kali thumbnail muncul
- impression_ctr: Float                  ← Click-through rate dari impression
- subscribers_gained: Integer default 0
- subscribers_lost: Integer default 0
- revenue_usd: Float                     ← Opsional jika monetized
- traffic_sources: JSONB                 ← {search: %, suggested: %, direct: %}
- device_types: JSONB                    ← {mobile: %, desktop: %, tablet: %}
- top_geographies: JSONB                 ← [{country: 'ID', views: 80}, ...]
- pulled_at: Timestamp with timezone
- created_at: Timestamp with timezone
- UNIQUE constraint: (video_id, snapshot_date)
- INDEX: (channel_id, snapshot_date)
- INDEX: (youtube_video_id)

TABEL: video_retention_curves
Simpan retention curve per video — data paling berharga untuk tau mana bagian terbaik.

Kolom:
- id: UUID PK
- video_id: UUID FK → videos
- youtube_video_id: String(50) NOT NULL
- data_points: JSONB NOT NULL
  Format: [
    {"elapsed_ratio": 0.0, "retention_ratio": 1.0},
    {"elapsed_ratio": 0.1, "retention_ratio": 0.72},
    {"elapsed_ratio": 0.2, "retention_ratio": 0.58},
    ... per 5% atau 10% interval
  ]
- peak_moments: JSONB
  Format: [{"time_ratio": 0.35, "retention": 0.91, "timestamp_seconds": 3150}]
  ← Momen di mana retention naik kembali = potential viral moment
- drop_off_points: JSONB
  Format: [{"time_ratio": 0.05, "drop_pct": 0.28, "timestamp_seconds": 270}]
  ← Momen di mana banyak yang stop = content problem
- pulled_at: Timestamp with timezone
- UNIQUE constraint: (video_id)

TABEL: channel_analytics_daily
Aggregate performa channel per hari.

Kolom:
- id: UUID PK
- youtube_account_id: UUID FK → youtube_accounts
- channel_id: String(255) NOT NULL
- date: Date NOT NULL
- total_views: Integer default 0
- total_watch_time_minutes: Float default 0
- subscribers_net: Integer default 0    ← gained - lost
- revenue_usd: Float default 0
- top_videos: JSONB                      ← [{video_id, views, title}] top 5
- UNIQUE constraint: (channel_id, date)
- INDEX: (channel_id, date DESC)

TABEL: content_dna_models
Simpan learned model per channel — ini yang membuat AI makin pintar.

Kolom:
- id: UUID PK
- youtube_account_id: UUID FK → youtube_accounts
- channel_id: String(255) UNIQUE NOT NULL
- niche: String(100)                     ← 'gaming', 'education', 'gym', dll
- sub_niches: JSONB                      ← ['fps', 'rpg', 'survival'] untuk gaming
- viral_score_weights: JSONB
  Format: {
    "emotional_impact": 0.25,
    "hook_strength": 0.30,      ← Weight di-adjust berdasarkan data channel
    "info_density": 0.15,
    "relatability": 0.20,
    "cta_potential": 0.10
  }
- top_performing_patterns: JSONB
  Format: {
    "title_patterns": ["AKHIRNYA...", "MOMENT PALING...", "INI GILAA"],
    "hook_durations": {"optimal_seconds": 8},
    "best_clip_duration": {"min": 45, "max": 180, "optimal": 90},
    "best_upload_days": ["tuesday", "thursday", "saturday"],
    "best_upload_hours": [18, 19, 20, 21]
  }
- game_performance: JSONB
  Format: {
    "Battlefield 6": {"avg_views": 45, "avg_ctr": 0.062, "sample_size": 12},
    "Kingdom Come Deliverance II": {"avg_views": 31, "avg_ctr": 0.041, "sample_size": 18}
  }
- underperforming_patterns: JSONB        ← Pola yang harus dihindari
- confidence_score: Float default 0.0    ← 0-1, makin banyak data makin tinggi
- videos_analyzed: Integer default 0
- last_updated: Timestamp with timezone
- created_at: Timestamp with timezone

TABEL: weekly_insight_reports
AI-generated weekly report per channel.

Kolom:
- id: UUID PK
- youtube_account_id: UUID FK → youtube_accounts
- channel_id: String(255) NOT NULL
- week_start: Date NOT NULL
- week_end: Date NOT NULL
- summary_text: Text                     ← AI-generated narrative
- key_wins: JSONB                        ← List of good things this week
- key_issues: JSONB                      ← List of problems
- recommendations: JSONB                 ← Actionable AI recommendations
- top_clip_type: String(100)             ← Jenis clip terbaik minggu ini
- views_change_pct: Float
- subscribers_change: Integer
- estimated_viral_potential: JSONB       ← Videos yang belum diclip tapi potensial
- raw_data_snapshot: JSONB               ← Raw stats untuk referensi
- generated_at: Timestamp with timezone
- UNIQUE constraint: (channel_id, week_start)
```

---

## ⚙️ STEP B — Analytics Data Service (Backend)

### B.1 YouTube Analytics Fetcher

```
Gunakan skill senior-backend.

Buat backend/app/services/analytics/youtube_analytics_fetcher.py:

Class YouTubeAnalyticsFetcher:

DEPENDENCY: google-api-python-client, google-auth

- __init__(youtube_account: YoutubeAccount):
  - Build YouTube Data API v3 client
  - Build YouTube Analytics API client
  - Handle token refresh otomatis

- async fetch_channel_videos(max_results=50) → List[VideoMetadata]:
  """Fetch list video terbaru dari channel"""
  - YouTube Data API: search.list + videos.list
  - Fields: id, title, publishedAt, duration, statistics (views, likes, comments)
  - Parse ISO 8601 duration ke seconds
  - Return list VideoMetadata dataclass

- async fetch_video_analytics(youtube_video_id: str, start_date: date, end_date: date) → VideoAnalyticsData:
  """Fetch analytics detail per video dari YouTube Analytics API"""
  - Endpoint: youtubeAnalytics.reports.query
  - Dimensions: video
  - Metrics yang di-fetch:
    views, likes, comments, shares,
    estimatedMinutesWatched, averageViewDuration, averageViewPercentage,
    annotationImpressions, cardImpressions, cardClickRate,
    subscribersGained, subscribersLost
  - Traffic source breakdown: trafficSourceType dimension
  - Device type breakdown: deviceType dimension
  - Geography breakdown: country dimension (top 5)

- async fetch_retention_curve(youtube_video_id: str) → List[RetentionDataPoint]:
  """Fetch audience retention curve — PALING BERHARGA"""
  - Endpoint: youtubeAnalytics.reports.query
  - Dimensions: elapsedVideoTimeRatio
  - Metrics: audienceWatchRatio, relativeRetentionPerformance
  - Return list of {elapsed_ratio, retention_ratio, relative_performance}
  - Detect peak moments: titik di mana retention_ratio naik (re-watch / seek)
  - Detect drop-off points: titik di mana ada penurunan > 15% dalam 1 interval

- async fetch_channel_daily_stats(start_date: date, end_date: date) → List[DailyStats]:
  """Channel-level aggregate per hari"""
  - Metrics: views, estimatedMinutesWatched, subscribersGained, subscribersLost
  - Optional: estimatedRevenue jika monetized

- async batch_fetch_all_videos_analytics(video_ids: List[str]) → Dict[str, VideoAnalyticsData]:
  """Batch fetch untuk efisiensi — hindari quota exhaustion"""
  - YouTube Analytics API: max 200 metrics per request
  - Implement chunking: 10 video per batch
  - Rate limiting: 1 request per 100ms
  - Progress callback untuk UI feedback

QUOTA MANAGEMENT:
YouTube Analytics API quota: 10.000 units/day (lebih longgar dari Data API)
- reports.query = 1 unit per request
- Implementasikan quota tracker di Redis
- Key: f"yt_analytics_quota:{channel_id}:{date}"
- Alert jika mendekati 8.000 units/day

DataClasses yang dibutuhkan (buat di analytics/models.py):
- VideoMetadata: id, youtube_id, title, published_at, duration_seconds, views, likes, comments
- VideoAnalyticsData: semua fields dari analytics
- RetentionDataPoint: elapsed_ratio, retention_ratio, relative_performance, timestamp_seconds
- DailyStats: date, views, watch_time_minutes, subscribers_net
```

### B.2 Analytics Processor & Content DNA Builder

```
Gunakan skill senior-backend dan senior-prompt-engineer.

Buat backend/app/services/analytics/content_dna_builder.py:

Class ContentDNABuilder:

- async analyze_channel_performance(channel_id: str) → ContentDNAModel:
  """
  Analisis historis channel untuk membangun Content DNA.
  Jalankan setelah ada minimal 10 video dengan analytics data.
  """
  
  STEP 1 — Load & Aggregate Data:
  - Query semua video_analytics untuk channel ini
  - Query retention_curves yang tersedia
  - Hitung stats per video: views_per_day = views / days_since_publish

  STEP 2 — Identify Top Performers vs Underperformers:
  - Top 25%: video dengan views_per_day tertinggi
  - Bottom 25%: video dengan views_per_day terendah
  - Extract pattern dari judul, durasi, game title
  
  STEP 3 — Title Pattern Analysis (gunakan regex + NLP sederhana):
  - Kata-kata yang muncul di top performers
  - Format judul yang perform (LIVE prefix, game name position, episode number)
  - Uppercase words yang konsisten di top performers
  
  STEP 4 — Retention Curve Analysis:
  - Cari rata-rata "peak moments" across top performers
  - Identifikasi optimal clip duration dari average_view_duration
  - Flag: menit ke berapa viewers paling sering drop off (= hindari hook di sana)
  
  STEP 5 — Upload Timing Analysis:
  - Dari published_at dan views_per_day, cari korelasi hari/jam upload vs performa
  - Group by: day_of_week, hour_of_day
  - Output: best_upload_days, best_upload_hours
  
  STEP 6 — Game Performance Ranking (gaming-specific):
  - Group videos by game title (extract dari judul)
  - Hitung avg_views, avg_ctr per game
  - Output: game_performance dict
  
  STEP 7 — AI Enhancement (OpenRouter):
  Kirim summary statistik ke AI untuk generate insights:
  
  System prompt:
  """
  Kamu adalah Content DNA Analyst untuk channel gaming Indonesia.
  Berdasarkan data performa historis berikut, identifikasi:
  1. Pola judul yang paling efektif untuk channel ini
  2. Jenis momen gaming yang paling viral (kill, rage, achievement, funny)
  3. Rekomendasi hook pattern spesifik untuk niche gaming Indonesia
  4. Kata-kata yang harus DIHINDARI berdasarkan underperformer
  5. Optimal clip duration berdasarkan audience retention
  
  Output HARUS dalam format JSON dengan struktur yang ditentukan.
  Bahasa analisis: Indonesia.
  """
  
  STEP 8 — Simpan ke content_dna_models:
  - Update confidence_score berdasarkan jumlah data (min 10 video = 0.3, 50 video = 0.7, 100+ = 0.9)
  - Update videos_analyzed
  - Simpan semua pattern ke JSONB fields

- async calculate_viral_score_weights(channel_id: str) → Dict[str, float]:
  """
  Kalibrasi ulang viral score weights berdasarkan data channel ini.
  Default weights di PRD: emotional=0.25, hook=0.25, info=0.20, etc.
  Channel gaming mungkin: hook=0.35, emotional=0.30, info=0.15, ...
  """
  - Analisis: feature mana yang paling berkorelasi dengan high views?
  - Gunakan simple correlation analysis (scipy.stats jika tersedia)
  - Return adjusted weights yang dijumlahkan = 1.0

- async identify_unclipped_viral_potential(channel_id: str) → List[VideoOpportunity]:
  """
  Dari video yang belum diclip, mana yang paling berpotensi?
  Prioritaskan berdasarkan: retention peaks + game popularity + video length
  """
  - Query videos yang status='done' tapi belum punya clips
  - Score tiap video: game_score + retention_peak_count + duration_bonus
  - Return sorted list dengan estimated_clips_potential per video
```

### B.3 Analytics Celery Tasks

```
Buat backend/app/workers/tasks/analytics.py:

@celery_app.task
def sync_channel_analytics(youtube_account_id: str):
  """
  Task ini dijalankan terjadwal (Celery Beat) setiap hari jam 06:00 WIB.
  Fetch analytics terbaru untuk semua video channel.
  """
  Flow:
  1. Load youtube_account dari DB
  2. Fetch list 50 video terbaru via YouTubeAnalyticsFetcher
  3. Untuk setiap video yang belum punya analytics hari ini:
     - fetch_video_analytics(start=7 hari lalu, end=hari ini)
     - Upsert ke video_analytics tabel
  4. Fetch retention curve untuk video yang belum punya (1x fetch, tidak perlu update)
  5. Fetch channel daily stats untuk 7 hari terakhir
  6. Trigger: update_content_dna.delay(youtube_account_id)
  7. Cek apakah perlu generate weekly report (setiap Senin)

@celery_app.task
def update_content_dna(youtube_account_id: str):
  """
  Update Content DNA model setelah analytics di-sync.
  Hanya jalankan jika ada minimal 5 video baru sejak update terakhir.
  """
  - Load content_dna_models untuk channel ini
  - Cek: videos_analyzed_now vs videos_analyzed_last_update
  - Jika delta >= 5: jalankan ContentDNABuilder.analyze_channel_performance()
  - Update model di DB

@celery_app.task
def generate_weekly_insight_report(youtube_account_id: str):
  """
  Generate AI insight report mingguan. Trigger setiap Senin pagi.
  """
  Flow:
  1. Aggregate data minggu lalu dari channel_analytics_daily
  2. Identifikasi top video minggu ini
  3. Bandingkan dengan minggu sebelumnya (% change)
  4. Identifikasi video yang belum diclip tapi punya potensi tinggi
  5. Call OpenRouter untuk generate narrative report dalam Bahasa Indonesia
  6. Simpan ke weekly_insight_reports
  7. Notify user via Telegram + Email

Celery Beat Schedule (tambahkan ke celery_app.py):
beat_schedule = {
  'sync-analytics-daily': {
    'task': 'app.workers.tasks.analytics.sync_channel_analytics',
    'schedule': crontab(hour=6, minute=0),  # 06:00 WIB = 23:00 UTC
  },
  'weekly-insight-monday': {
    'task': 'app.workers.tasks.analytics.generate_weekly_insight_report',
    'schedule': crontab(hour=7, minute=0, day_of_week=1),  # Senin 07:00 WIB
  }
}
```

### B.4 Analytics API Endpoints

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/analytics.py:

Semua endpoint membutuhkan authentication.

1. GET /analytics/channel/{channel_id}/overview
   Response:
   {
     "channel_id": "...",
     "channel_name": "Seego GG",
     "subscribers": 2500,
     "total_views": 82200,
     "total_videos": 272,
     "avg_views_per_video": 302,
     "avg_ctr": 0.045,
     "avg_view_duration_seconds": 420,
     "watch_time_hours": 1370,
     "subscribers_last_30d": +45,
     "views_last_30d": 1250,
     "views_trend_pct": +12.5,
     "content_dna_confidence": 0.65,
     "last_synced": "2026-04-27T06:00:00Z"
   }

2. GET /analytics/channel/{channel_id}/videos
   Query params: limit=20, offset=0, sort_by=views|ctr|watch_time|published_at
   Response: List video dengan analytics data tergabung
   Tiap item:
   {
     "video_id": "...",
     "youtube_video_id": "...",
     "title": "LIVE Gas Yang Mau Mabar...",
     "published_at": "2026-04-27",
     "duration_seconds": 7374,
     "views": 283,
     "likes": 3,
     "comments": 0,
     "watch_time_minutes": 420,
     "avg_view_duration_seconds": 89,
     "avg_view_percentage": 1.2,
     "impression_ctr": 0.041,
     "viral_potential_score": 72,    ← kalkulasi dari data analytics
     "has_retention_data": true,
     "clips_generated": 0,
     "clippable": true               ← belum diclip & durasi > 10 menit
   }

3. GET /analytics/videos/{youtube_video_id}/retention
   Response:
   {
     "youtube_video_id": "...",
     "duration_seconds": 7374,
     "data_points": [
       {"elapsed_ratio": 0.0, "retention_ratio": 1.0, "timestamp_seconds": 0},
       {"elapsed_ratio": 0.05, "retention_ratio": 0.72, "timestamp_seconds": 369},
       ...
     ],
     "peak_moments": [
       {"timestamp_seconds": 1820, "retention_ratio": 0.68, "label": "Peak moment — potensial clip"},
       ...
     ],
     "drop_off_points": [
       {"timestamp_seconds": 185, "drop_pct": 28, "label": "Early drop-off — hook bermasalah"},
       ...
     ],
     "optimal_clip_windows": [
       {"start": 1750, "end": 1960, "score": 85, "reason": "Retention naik kembali"},
       ...
     ]
   }

4. GET /analytics/channel/{channel_id}/content-dna
   Response: Full content DNA model untuk channel ini
   Termasuk: viral_score_weights, top_performing_patterns, game_performance,
             best_upload_days, optimal_clip_duration, confidence_score

5. GET /analytics/channel/{channel_id}/opportunities
   Response: List video yang potensial untuk di-clip tapi belum diproses
   Sorted by estimated viral potential DESC
   Include: estimated_clips_count, best_moments_preview

6. GET /analytics/channel/{channel_id}/weekly-report/latest
   Response: Latest weekly insight report dengan AI narrative

7. GET /analytics/channel/{channel_id}/daily-stats
   Query params: days=30 (default), days=7, days=90
   Response: Time series views, watch time, subscribers per hari
   Format untuk chart:
   {
     "dates": ["2026-04-01", ...],
     "views": [45, 32, 67, ...],
     "watch_time_minutes": [320, 210, 480, ...],
     "subscribers_net": [+2, 0, +5, ...]
   }

8. POST /analytics/channel/{channel_id}/sync
   Trigger manual sync analytics (rate limited: 1x per 6 jam)
   Response: { "task_id": "...", "message": "Sync dimulai..." }

9. GET /analytics/channel/{channel_id}/game-performance
   Gaming-specific endpoint:
   Response:
   {
     "games": [
       {
         "name": "Battlefield 6",
         "video_count": 12,
         "avg_views": 45,
         "avg_ctr": 0.062,
         "avg_watch_time_minutes": 8.5,
         "trend": "up",
         "recommendation": "Prioritaskan konten ini"
       },
       {
         "name": "Kingdom Come Deliverance II",
         "video_count": 18,
         "avg_views": 31,
         "avg_ctr": 0.041,
         "avg_watch_time_minutes": 5.2,
         "trend": "stable",
         "recommendation": "Optimasi judul dan thumbnail"
       }
     ]
   }
```

---

## 🎨 STEP C — Enhanced Analytics Dashboard (Frontend)

### C.1 Analytics Page Layout

```
Gunakan skill senior-frontend, frontend-design, ui-ux-pro-max, ui-design-system.

Buat frontend/src/app/analytics/page.tsx

Design direction: 
- Dark theme dengan data-forward aesthetic
- Terinspirasi dari YouTube Studio + Linear + Vercel Analytics
- Warna aksen: Electric violet (#6C63FF) untuk positive trends
- Coral (#FF6B6B) untuk alerts dan drops
- Cyber teal (#00D4AA) untuk highlights dan peaks
- Font display: 'DM Mono' untuk angka/metrics, 'Space Grotesk' untuk label
- Chart library: Recharts (sudah tersedia di stack)
- Animasi: angka counter dari 0 ke nilai aktual (framer-motion atau CSS)

Layout keseluruhan:
┌─────────────────────────────────────────────────────┐
│ Header: Channel Selector + Last Synced + Sync Button│
├─────────────────────────────────────────────────────┤
│ Channel Profile Card (avatar, name, stats summary)  │
├──────────┬──────────┬──────────┬────────────────────┤
│ KPI Card │ KPI Card │ KPI Card │ KPI Card           │
│ Views    │ Watch Hr │ CTR Avg  │ Sub Net            │
├──────────┴──────────┴──────────┴────────────────────┤
│ Views Trend Chart (30 hari) — Area Chart             │
├─────────────────────┬───────────────────────────────┤
│ Game Performance    │ Content DNA Insights           │
│ (Bar Chart)         │ (AI-generated insight card)    │
├─────────────────────┴───────────────────────────────┤
│ Video Table dengan analytics per video              │
│ (sortable, filterable, pagination)                  │
├─────────────────────────────────────────────────────┤
│ 🎯 Opportunities — "Video ini belum diclip!"        │
│ Card list dengan CTA "Proses Sekarang"              │
└─────────────────────────────────────────────────────┘
```

### C.2 KPI Cards Component

```
Buat frontend/src/components/analytics/KPICard.tsx:

Props:
- label: string
- value: number | string
- unit?: string ('views', 'jam', '%', 'subs')
- trend?: { value: number, direction: 'up' | 'down' | 'neutral', period: string }
- icon: ReactNode
- accentColor?: string

Design:
- Glassmorphism card: bg-white/5 backdrop-blur-sm border border-white/10
- Label: uppercase, letter-spacing wide, text-xs, muted color
- Value: large font (text-4xl), DM Mono, white/90
- Trend badge: pill shape, green untuk up, red untuk down, neutral abu
- Animated counter: angka naik dari 0 saat pertama load (useCountUp hook)
- Subtle gradient glow di belakang angka sesuai trend direction

Buat 4 instance:
1. Total Views (periode 30 hari) — ikon: Eye
2. Watch Hours — ikon: Clock  
3. Avg CTR % — ikon: MousePointerClick, accentColor teal
4. Subscribers Net — ikon: Users, color based on positive/negative
```

### C.3 Views Trend Chart

```
Buat frontend/src/components/analytics/ViewsTrendChart.tsx:

Library: Recharts (AreaChart)

Design:
- Background transparan (sesuai dashboard)
- Area gradient: dari #6C63FF40 di bawah ke transparan
- Line: #6C63FF solid, strokeWidth 2
- Dots: hidden by default, muncul saat hover
- Grid: horizontal only, sangat subtle (opacity 0.1)
- Tooltip custom: dark glassmorphism, tampilkan tanggal + views + watch time
- X-axis: tanggal format "Apr 1", "Apr 7", etc. — responsive, skip labels jika penuh
- Y-axis: hidden, angka ada di tooltip saja

Period selector tabs: 7D | 30D | 90D
- Saat toggle, animasi transisi smooth (fade + slide)
- Data di-fetch ulang dari API dengan period berbeda

Tambahkan secondary line (optional toggle):
- Subscribers net: warna teal, y-axis kanan
- Watch time: warna coral

Responsive: chart menyesuaikan container width dengan aspect ratio 16:5
```

### C.4 Game Performance Chart

```
Buat frontend/src/components/analytics/GamePerformanceChart.tsx:

Library: Recharts (BarChart horizontal)

Data: dari endpoint /analytics/channel/{id}/game-performance

Design:
- Horizontal bar chart (lebih mudah baca nama game panjang)
- Bar color: gradient dari violet ke teal berdasarkan ranking
- Label value di ujung bar: avg views dengan font mono
- Hover: highlight bar + tooltip dengan detail lengkap
  (video count, avg CTR, avg watch time, trend)
- Badge kecil di sebelah nama game:
  - "🔥 Top" untuk game dengan avg views tertinggi
  - "📈 Trending" jika trend naik
  - "⚠️ Optimize" jika CTR rendah

Di bawah chart:
- AI Recommendation text per game (dari content DNA)
- Format: italic, warna muted, font-size sm
- Contoh: "Konten Battlefield 6 konsisten perform 45% lebih tinggi. Prioritaskan game ini."
```

### C.5 Retention Curve Viewer

```
Buat frontend/src/components/analytics/RetentionCurveViewer.tsx:

Ini komponen PALING CANGGIH di analytics — tampilkan sebagai feature premium.

Design:
- Header: "Audience Retention Analysis" dengan badge "AI-Powered"
- Video selector: dropdown pilih video yang punya retention data

Chart: Recharts LineChart
- X-axis: 0% → 100% (progress video), tampilkan timestamp di hover
- Y-axis: 0% → 100% retention
- Line utama: retention curve, tebal, warna teal
- Reference line horizontal: rata-rata YouTube (benchmark ~40%)
- Annotation markers di chart:
  ▲ Peak Moments: marker icon hijau ↑ "Potensi Clip"
  ▼ Drop-off Points: marker icon merah ↓ "Hook Bermasalah"

Di bawah chart:
- "Optimal Clip Windows" section:
  - Card per window dengan: timestamp range, retention score, reason
  - CTA button: "Buat Clip dari Momen Ini →"
  - Click → redirect ke video upload/processing dengan pre-filled timestamps

- Drop-off Analysis:
  - Alert card untuk early drop (< 30 detik): "28% penonton pergi di detik ke-185"
  - Rekomendasi: "Perkuat hook di 30 detik pertama untuk game Battlefield"

State: pilih video → loading skeleton → render curve dengan animasi draw
```

### C.6 Video Performance Table

```
Buat frontend/src/components/analytics/VideoPerformanceTable.tsx:

Design: Dark table dengan hover highlight

Columns (bisa toggle show/hide):
1. Thumbnail (48x36, rounded) + Judul (truncated, tooltip full)
2. Published At (relative: "2 hari lalu")
3. Views (dengan mini bar chart inline — relative ke max views)
4. CTR % (color-coded: merah <3%, kuning 3-6%, hijau >6%)
5. Avg Watch Duration (format mm:ss)
6. Watch % (% video yang ditonton rata-rata)
7. Viral Potential Score (0-100, badge color)
8. Clips (jumlah clips yang sudah dibuat, atau "—")
9. Action: "Lihat Retention" | "Buat Clips"

Fitur:
- Sort by setiap kolom (click header)
- Filter: "Belum Diclip" toggle, "CTR Rendah" toggle, game filter dropdown
- Pagination: 20 per halaman
- Bulk select: checkbox per row + "Proses Semua yang Dipilih" action bar
- Row expand: klik row → expand tampilkan mini stats + traffic sources donut

Loading state: skeleton rows yang animated
Empty state: ilustrasi simple + "Sync analytics untuk melihat data"
```

### C.7 Opportunities Section

```
Buat frontend/src/components/analytics/OpportunitiesSection.tsx:

Header: "🎯 Video Berpotensi Tinggi — Belum Diclip"
Sub: "AI menemukan X video dengan momen viral yang belum diekstrak"

Card per opportunity:
┌─────────────────────────────────────────────────────┐
│ [Thumbnail] LIVE Gas Yang Mau Mabar | Battlefield 6 │
│             Apr 27, 2026 · 2 jam 2 menit            │
├─────────────────────────────────────────────────────┤
│ 🔥 Viral Potential: 78/100                          │
│ 📊 3 peak moments terdeteksi di retention curve     │
│ ⏱️ Estimated: 8–12 clips bisa diekstrak             │
│ 🎮 Game: Battlefield 6 (top performer channel ini)  │
├─────────────────────────────────────────────────────┤
│ [Lihat Retention] [▶ Proses Sekarang]               │
└─────────────────────────────────────────────────────┘

Design:
- Card dengan left border accent warna berdasarkan score (hijau=tinggi, kuning=medium)
- Horizontal scroll jika banyak (carousel-like dengan scroll snap)
- Badge "🔥 HOT" untuk score > 75
- Tombol "Proses Sekarang" → trigger video processing pipeline langsung dari sini

Empty state: "Semua video sudah diproses! Upload video baru atau sync analytics."
```

### C.8 Weekly Insight Report Component

```
Buat frontend/src/components/analytics/WeeklyInsightReport.tsx:

Design: Report card yang terasa seperti AI-generated newsletter

Header: "📋 Laporan Mingguan" + tanggal range + "Generated by AI"

Sections dalam card:
1. TL;DR (1-2 kalimat summary dari AI)
   Style: italic, slightly larger font, border-left accent

2. Key Wins (green checkmarks)
   - Bullet list dari AI
   - Contoh: "✅ Battlefield 6 Part 2 mencapai 98 views — tertinggi bulan ini"

3. Issues & Warnings (coral/red)
   - Contoh: "⚠️ 3 video upload di hari yang sama — spread konten lebih merata"

4. AI Recommendations (violet accent)
   - Numbered list actionable
   - Contoh: "1. Fokus ke Battlefield 6 — avg views 45% lebih tinggi dari game lain"

5. Next Week Opportunities
   - Video yang sudah ada dan bisa diclip minggu ini

Footer: "Laporan berikutnya: Senin, 4 Mei 2026 07:00 WIB"
CTA: "Export PDF" | "Kirim ke Telegram"

Jika belum ada report: placeholder card dengan "Laporan pertama akan tersedia Senin depan"
```

### C.9 Analytics State Management

```
Gunakan skill senior-frontend.

Buat frontend/src/stores/analyticsStore.ts (Zustand):

State:
- selectedChannelId: string | null
- overviewData: ChannelOverview | null
- videosData: VideoWithAnalytics[]
- dailyStats: DailyStats[]
- contentDNA: ContentDNAModel | null
- opportunities: VideoOpportunity[]
- weeklyReport: WeeklyInsightReport | null
- isSyncing: boolean
- lastSynced: Date | null

Actions:
- setSelectedChannel(channelId)
- syncAnalytics(channelId) → trigger API POST + poll status
- refreshAll(channelId) → fetch semua data segar

Buat TanStack Query hooks di frontend/src/hooks/useAnalytics.ts:
- useChannelOverview(channelId)
- useVideosWithAnalytics(channelId, filters)
- useRetentionCurve(youtubeVideoId)
- useDailyStats(channelId, days)
- useContentDNA(channelId)
- useOpportunities(channelId)
- useWeeklyReport(channelId)
- useSyncAnalytics() mutation

Buat TypeScript types di frontend/src/types/analytics.ts:
- ChannelOverview, VideoWithAnalytics, RetentionCurve
- DailyStats, ContentDNAModel, VideoOpportunity
- WeeklyInsightReport, GamePerformance
- Semua interfaces harus strict typed, no 'any'
```

---

## 🤖 STEP D — AI Prompt Engineering untuk Analytics

```
Gunakan skill senior-prompt-engineer.

Buat backend/app/services/analytics/ai_insight_generator.py:

Class AIInsightGenerator:

Semua prompt harus dalam Bahasa Indonesia.
Output selalu JSON yang strict parseable.

PROMPT 1 — Weekly Report Generator:
System:
"""
Kamu adalah analis konten YouTube berpengalaman yang mengkhususkan diri
pada channel gaming Indonesia. Tugasmu adalah menganalisis data performa
minggu ini dan menghasilkan laporan yang actionable untuk creator.

ATURAN OUTPUT:
- Bahasa: Indonesia yang natural, bukan terjemahan kaku
- Tone: Seperti konsultan yang supportive, jujur, dan to-the-point
- Hindari jargon teknis yang tidak perlu
- Setiap rekomendasi harus spesifik dan actionable (bukan "optimalkan konten")
- Output HANYA JSON, tidak ada teks di luar JSON

JSON Schema yang harus diikuti PERSIS:
{
  "summary": "string (1-2 kalimat TL;DR)",
  "wins": ["string", ...] (3-5 hal positif),
  "issues": ["string", ...] (2-4 masalah),
  "recommendations": [
    {
      "priority": "high|medium|low",
      "action": "string (apa yang harus dilakukan)",
      "reason": "string (kenapa ini penting)",
      "expected_impact": "string (dampak yang diharapkan)"
    }
  ],
  "best_performing_content": "string (deskripsi jenis konten terbaik)",
  "focus_game_next_week": "string (game yang harus diprioritaskan)",
  "clip_opportunity_summary": "string (berapa banyak potential clips yang tersisa)"
}
"""

PROMPT 2 — Content DNA Pattern Analyzer:
System:
"""
Kamu adalah AI yang menganalisis pola konten untuk channel gaming Indonesia.
Berdasarkan data performa historis, identifikasi pola yang membuat video
perform baik vs buruk untuk channel spesifik ini.

Data yang diberikan: statistik agregat dari semua video channel.
Tugasmu: temukan pattern, bukan hanya deskripsi angka.

Output HANYA JSON:
{
  "title_patterns": {
    "winning": ["pattern yang bekerja", ...],
    "losing": ["pattern yang harus dihindari", ...],
    "recommended_format": "format judul yang direkomendasikan"
  },
  "hook_insights": {
    "optimal_duration_seconds": number,
    "effective_patterns": ["pola hook yang efektif", ...],
    "avoid": ["apa yang harus dihindari di hook", ...]
  },
  "clip_strategy": {
    "optimal_duration_seconds": {"min": number, "max": number, "sweet_spot": number},
    "best_moment_types": ["jenis momen yang perform", ...],
    "gaming_specific_tips": ["tips spesifik untuk gaming content", ...]
  },
  "audience_insights": {
    "peak_activity_time": "deskripsi waktu aktif audiens",
    "content_preference": "deskripsi preferensi audiens channel ini"
  },
  "confidence_note": "string (seberapa yakin AI dengan analisis ini)"
}
"""

PROMPT 3 — Clip Title Optimizer (dengan Content DNA):
System:
"""
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
  "hashtags": ["tag1", "tag2", ...] (10-15 hashtag mix ID+EN),
  "hook_suggestion": "saran teks untuk 5 detik pertama clip"
}
"""

Implementasikan retry dengan tenacity:
- 3 retries dengan exponential backoff
- Jika JSON parse gagal: retry dengan instruksi "output hanya JSON valid"
- Jika masih gagal setelah 3x: return default template, log error
```

---

## 📋 STEP E — Requirements Tambahan

```
Tambahkan ke backend/requirements.txt:

# Analytics
google-analytics-data==0.18.0   ← Google Analytics Data API (jika dibutuhkan)
scipy==1.14.0                    ← Untuk correlation analysis di Content DNA
numpy==2.1.0                     ← Array operations untuk retention analysis
pandas==2.2.0                    ← Data aggregation untuk analytics

# Scheduling (Celery Beat)
celery[redis,beat]==5.4.0        ← Update existing entry

# Export
reportlab==4.2.0                 ← PDF export weekly report
jinja2==3.1.4                    ← HTML template untuk email report

Tambahkan ke frontend/package.json:
"recharts": "^2.13.0"            ← Sudah ada, pastikan versi ini
"date-fns": "^4.1.0"            ← Date formatting untuk chart
"@tanstack/react-table": "^8.20.0" ← Untuk video performance table
```

---

## 🧪 STEP F — Testing Analytics Module

```
Gunakan skill code-reviewer dan senior-backend.

Buat tests/test_services/test_analytics.py:

1. Test YouTubeAnalyticsFetcher:
   - Mock Google API responses
   - Test retention curve parsing (peak detection algorithm)
   - Test drop-off point detection
   - Test quota management

2. Test ContentDNABuilder:
   - Test dengan sample dataset 20+ videos
   - Verify output schema selalu valid
   - Test confidence score calculation
   - Test game performance ranking

3. Test AI Insight Generator:
   - Mock OpenRouter responses
   - Test JSON parsing robustness (malformed → retry)
   - Test Bahasa Indonesia output (tidak ada English jargon)

4. Test Analytics API Endpoints:
   - Test semua 9 endpoints dengan authenticated requests
   - Test pagination, sorting, filtering
   - Test rate limiting pada POST /sync

Buat fixture: sample_channel_analytics_data.json
- 30 hari data harian
- 20 video dengan analytics lengkap
- 5 video dengan retention curve
- 1 content DNA model
```

---

## 🎯 EXECUTION ORDER — Analytics Module

```
[ ] STEP A   → Database schema (migration 002)
[ ] STEP B.1 → YouTube Analytics Fetcher
[ ] STEP B.2 → Content DNA Builder
[ ] STEP B.3 → Analytics Celery Tasks + Beat Schedule
[ ] STEP B.4 → Analytics API Endpoints (9 endpoints)
[ ] STEP C.1 → Analytics Page Layout
[ ] STEP C.2 → KPI Cards Component
[ ] STEP C.3 → Views Trend Chart
[ ] STEP C.4 → Game Performance Chart
[ ] STEP C.5 → Retention Curve Viewer ← PRIORITAS
[ ] STEP C.6 → Video Performance Table
[ ] STEP C.7 → Opportunities Section ← PRIORITAS
[ ] STEP C.8 → Weekly Insight Report Component
[ ] STEP C.9 → Analytics State + TanStack Query Hooks
[ ] STEP D   → AI Prompts (3 prompts)
[ ] STEP E   → Update requirements
[ ] STEP F   → Tests

DEPENDENCIES: Modul ini HARUS dijalankan setelah MVP base (STEP 1-10) selesai.
Minimal yang harus ada: Auth, YouTube OAuth, database migrations 001.
```

---

## ⚠️ CRITICAL NOTES untuk Claude Sonnet

1. **YouTube Analytics API quota sangat limited** — implementasikan quota tracker di Redis dengan hard stop di 8.000 units/hari. Jangan fetch data yang sama dua kali dalam satu hari.

2. **Retention curve adalah data premium** — tidak semua video punya data ini. Hanya video dengan minimal 1.000 views yang biasanya punya retention data di YouTube Analytics. Untuk channel Seego GG yang masih kecil, data ini mungkin sparse — handle gracefully dengan state "Data belum tersedia (perlu minimal views)".

3. **Content DNA butuh minimal data** — jangan run analisis jika < 10 video punya analytics. Tampilkan progress indicator: "Content DNA: Butuh 7 video lagi untuk analisis pertama".

4. **Gaming niche specific** — semua AI prompts harus aware bahwa ini gaming content Indonesia. Jangan generate insights yang generik untuk semua niche.

5. **Bahasa Indonesia di semua AI output** — weekly report, recommendations, dan insights harus dalam Bahasa Indonesia yang natural, bukan terjemahan kaku.

6. **Offline-first mindset** — sync analytics bisa gagal (quota exceeded, token expired, network). Selalu tampilkan data terakhir yang tersimpan di DB dengan label "Last synced: X jam lalu". Jangan pernah show empty state jika ada historical data.

---

*Analytics Module — AI Content Factory*
*Designed for: Seego GG channel · Gaming Indonesia niche*
*Goal: Turn 272 unoptimized LIVE recordings into viral short-form content*
