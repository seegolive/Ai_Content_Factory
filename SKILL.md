---
name: ai-factory-dashboard-redesign
description: |
  Rebuild halaman Dashboard utama AI Factory (gaming content creator tool) menjadi versi production-grade dengan layout bento grid yang memanfaatkan seluruh viewport. Trigger skill ini kapanpun user meminta: redesign dashboard, perbaiki tampilan dashboard, implementasi mockup dashboard ke kode React, atau menambahkan komponen seperti Hero Strip, Pending Review primary KPI, AI Activity feed, atau Pipeline Status visualization. Gunakan skill ini bahkan jika user hanya bilang "bikin dashboard yang bagus" — karena skill ini punya struktur lengkap dari hero, KPI cards, channel card, recent videos, review queue, performance chart, AI activity, sampai pipeline status, semua sudah didefinisikan dengan tepat.
---

# AI Factory Dashboard Redesign Skill

Skill untuk merebuild halaman Dashboard utama AI Factory dengan layout bento grid 12-column yang mengisi penuh viewport. Skill ini diasumsikan berjalan pada **codebase yang sudah ada** (Next.js + React + TypeScript) dengan backend dan API yang sudah tersedia — fokus utama adalah **layer UI/presentasi**.

---

## Konteks Aplikasi

**AI Factory** adalah tool untuk content creator gaming (YouTube). Workflow utamanya:

1. Creator upload video panjang (live stream, gameplay)
2. AI generate clips pendek otomatis (Clutch, Funny, Fail, Rage moments)
3. Creator review clips di Review Queue
4. Approved clips di-publish ke YouTube/social media

**Halaman Dashboard** adalah landing page setelah login — harus memberikan:
- Glance overview pipeline state hari ini
- Primary CTA ke aksi paling urgent (Review pending clips)
- Quick access ke recent videos & queue
- Performance trend & AI activity log

---

## Trigger Behavior

Trigger skill ini saat user mengatakan:
- "redesign dashboard"
- "implementasi mockup dashboard"
- "perbaiki tampilan dashboard yang ada dead space"
- "buat dashboard utama yang lebih bagus"
- "dashboard saya kosong di kanan, bikinkan layout yang full"
- "implement bento grid dashboard"
- Semua frasa serupa yang menyangkut **halaman utama/landing/dashboard**

Jika user ragu apa yang harus diubah, sarankan: bento grid layout dengan 9 cards (lihat Section "Komponen Wajib").

---

## Prinsip Desain Non-Negotiable

Skill ini menerapkan prinsip-prinsip berikut tanpa kompromi:

### 1. Manfaatkan Viewport Penuh
Layout **wajib** mengisi seluruh lebar layar. Hindari `max-width: 1200px; margin: auto` yang menyebabkan dead space di kanan. Gunakan padding kontainer yang konsisten (24px) dan biarkan grid mengisi `1fr`.

### 2. Hierarki Visual Tegas
Tidak semua KPI sama pentingnya. **Pending Review** adalah primary metric → cardnya 2x lebih besar, warna amber prominent, ada CTA "Review Now". KPI sekunder (Total Videos, Clips, Published, Avg Score) lebih kecil dan kompak dengan sparkline.

### 3. Personalisasi & Action-Oriented
Hero strip bukan sekedar "Good Evening" — sertakan nama user dan **konteks aksi**: "Hi {name}, kamu punya {n} clips menunggu review". Hero punya 1 primary CTA (Review Sekarang) + 1 secondary (Sync Channel).

### 4. Setiap Card Harus Punya Tujuan
- Card tanpa data → ganti dengan empty state yang actionable, bukan kosong
- Card dengan data minimal → tampilkan trend, sparkline, atau context tambahan
- Tidak ada card "filler" hanya untuk mengisi grid

### 5. Live Data Indicators
Pipeline yang sedang berjalan punya indicator visual (pulse animation, progress bar shimmer). User harus tahu sistem aktif tanpa refresh.

---

## Komponen Wajib (9 Cards)

Berikut struktur grid 12-column dengan 9 cards yang **harus ada** di dashboard:

```
┌──────────────────── HERO STRIP (full width) ────────────────────┐
│ Greeting + nama + context aksi + 2 buttons                       │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────┬────────────────────────────────────┐
│  PENDING REVIEW (4×2) 🟠    │  CONNECTED CHANNEL (4×2)           │
│  Primary KPI                │  Channel info + 3 stats            │
│  Big number + CTA           │                                    │
├──────────┬──────────┬───────┴──────────┬─────────────────────────┤
│ Videos   │  Clips   │  Published       │  Avg Score              │
│ (2×1)    │  (2×1)   │  (2×1)           │  (2×1)                  │
│ +sparkln │ +sparkln │  +sparkln        │  +sparkln               │
├──────────┴──────────┴──────────────────┴─────────────────────────┤
│  RECENT VIDEOS (7×3)             │  REVIEW QUEUE (5×3)           │
│  5 video items dengan thumbnail  │  6 clip items dengan score    │
│  + status badge                  │  + tag pills                  │
├──────────────────┬───────────────┴───────────┬───────────────────┤
│ PERFORMANCE      │  AI ACTIVITY (4×2)        │ PIPELINE (4×2)    │
│ TREND (4×2)      │  Timeline 4 entries       │ 5 stages visual   │
│ Dual-line chart  │  + dots severity          │ + progress bar    │
└──────────────────┴───────────────────────────┴───────────────────┘
```

### Card 1: Hero Strip (full width)
**Lokasi:** Di atas bento grid
**Struktur:**
- Greeting kontekstual: `Good {morning|afternoon|evening} · {date}`
- Title: `Hi {name}, kamu punya {n} clips menunggu review`
- Subtitle: kalimat actionable yang menjelaskan kenapa user harus action sekarang
- 2 buttons: `[Sync Channel]` (secondary) + `[Review Sekarang →]` (primary, gradient amber)

**Data dari API:**
- `user.name`
- `pending_review_count`
- `last_video_processed_at`

### Card 2: Pending Review (Primary KPI, 4×2)
**Visual:** Background gradient amber subtle, border amber, primary card paling menonjol.
**Data:** Big number (font-size 64px), label "clips siap di-review & publish", CTA "Review now →" (button amber solid).
**Meta:** Bottom-right showing "Last clip 2h ago · Est. 4 min review"

### Card 3: Connected Channel (4×2)
**Layout:** Horizontal — avatar (44px gradient) + nama + handle + platform badge (YouTube merah).
**Stats grid 3 kolom:** Subscribers, Total Views, 30D Growth (% dengan warna green/red).
**Action:** Link "Manage →" di header.

### Cards 4-7: Secondary KPIs (4 cards × 2×1 each)
Setiap card punya:
- Icon kecil (24px) berwarna sesuai accent
- Card title (uppercase mono 11px)
- Trend badge di kanan atas (↑ +X / ↓ -X)
- Big value (28px mono)
- Label kecil
- Sparkline 7-day di bawah

**Mapping warna:**
| KPI | Accent Color |
|---|---|
| Videos | Purple `#a78bfa` |
| Clips | Green `#00e5a0` |
| Published | Red `#ff4d6d` (jika 0) atau Green |
| Avg Score | Blue `#4d9fff` |

### Card 8: Recent Videos (7×3)
**Layout:** List 5 video items, masing-masing punya:
- Thumbnail 90×50px (background gradient + emoji icon + duration overlay)
- Live badge (jika streaming, pulse animation)
- Title (truncate dengan ellipsis)
- Meta row: time ago · clips count · score avg
- Status badge: `Review` (amber) / `Published` (green) / `Processing` (blue)

### Card 9: Review Queue (5×3)
**Layout:** List 6 clip items, masing-masing punya:
- Thumbnail 70×40px + emoji
- Score badge circular (22px) di pojok kanan-bawah thumbnail (warna by score: ≥80 hijau, 70-79 amber, <70 merah)
- Title truncate
- Tag pill (Clutch=purple, Funny=amber, Fail=blue, Rage=red)
- Duration small text

### Card 10: Performance Trend (4×2)
**Chart:** SVG dual-line area chart
- Line 1 (solid): Views (blue)
- Line 2 (dashed): Clips Generated (green)
- Grid lines horizontal dashed
- Last data point dengan dot + halo

**Tabs:** 7D / 30D / 90D di header
**Stats footer:** 3 cells (Views, Clips, Watch Time) dengan trend %

### Card 11: AI Activity (4×2)
**Layout:** Vertical timeline dengan vertical line di kiri.
**Setiap item:**
- Dot 22px (success=green check, info=blue chart, warn=amber triangle)
- Title dengan keyword strong (warna accent)
- Time ago + source ("Gemini Flash · 41s avg")

**Min 4 entries** (mock jika data kurang).

### Card 12: Pipeline Status (4×2)
**5 stages horizontal:** Upload → Transcribe → Analyze → Review → Publish
- Done stage: hijau filled dengan ✓
- Active stage: blue dengan pulse animation
- Pending stage: grey dengan angka
- Connecting line antar stages (hijau jika done)

**Bottom:**
- Progress bar dengan shimmer animation
- "Stage X of 5 · {description}" + "ETA: ~X min"
- Live badge "● Active" di header

---

## Aturan Eksekusi (untuk Sonnet 4.6)

Saat skill ini dipicu, ikuti urutan ini:

### Step 1: Baca Existing Code
Sebelum menulis kode baru, baca terlebih dahulu:
- File page Dashboard yang ada (biasanya `app/dashboard/page.tsx` atau `pages/index.tsx`)
- File CSS global / theme variables yang sudah dipakai
- Komponen yang sudah ada dan mungkin reusable (`KPICard`, `Sidebar`, `Topbar`)
- Hook untuk data fetching (`useDashboardOverview`, `useYoutubeStats`, dll)

**Jangan reinvent the wheel.** Kalau sudah ada `<Sidebar />` yang dipakai di halaman lain, gunakan komponen itu juga di Dashboard baru.

### Step 2: Identifikasi Data Source
Petakan setiap card ke API/hook yang sudah ada. Catat di komentar kode:

```tsx
// PENDING REVIEW card
// Data: useReviewQueue() → { pending_count, last_processed_at }
```

Jika data belum tersedia di backend, tandai dengan `// TODO: Backend endpoint needed: GET /api/dashboard/...` dan **tetap implementasi UI dengan mock data** sehingga user bisa lihat hasil visual sambil menunggu backend.

### Step 3: Implementasi Bottom-Up
Buat komponen dari yang paling kecil ke paling besar:
1. **Atom components**: `<KPICard>`, `<VideoItem>`, `<QueueItem>`, `<ActivityItem>`, `<PipelineStage>`
2. **Composite cards**: `<PendingReviewCard>`, `<RecentVideosCard>`, `<ReviewQueueCard>`, dst
3. **Layout**: `<DashboardBentoGrid>` yang assemble semua cards
4. **Page**: `<DashboardPage>` yang wrap dengan layout shell

### Step 4: Styling — Pakai Pattern yang Konsisten
- **CSS Module** atau **Tailwind** atau **styled-components** — sesuaikan dengan codebase yang ada
- Jangan campur 3 sistem styling sekaligus
- CSS Variables untuk semua warna (lihat `references/design-tokens.md`)
- Font family: ikuti yang sudah dipakai di codebase. Jika belum ada font display, sarankan **Syne + DM Mono**.

### Step 5: Animations & Interactions
Wajib include:
- Staggered fadeIn cards saat mount (delay 0.04s per index)
- Live pulse pada indicator (live badge, pipeline active)
- Hover state pada setiap clickable item (translate, border color change)
- Sparkline animation pada KPI saat load
- Counter-up animation pada primary KPI value

Hindari:
- Heavy animation library kalau hanya butuh CSS transitions
- Animasi yang memicu layout shift

### Step 6: Empty States & Loading
**Setiap card** harus handle 3 state:
1. **Loading** — skeleton placeholder dengan shape yang sama
2. **Empty** — message + icon + CTA (kalau bisa)
3. **Error** — message singkat + retry button

Loading skeleton dilihat di `references/loading-states.md`.

### Step 7: Responsive
Skill ini fokus desktop (≥1280px), tapi:
- Tablet (768-1279px): bento grid jadi 6 kolom, beberapa card span lebih besar
- Mobile (<768px): single column stack, KPIs jadi 2 kolom, sidebar collapse

---

## Integrasi dengan Backend yang Sudah Ada

**Asumsi:** User sudah punya backend dengan beberapa endpoint. Skill ini tidak membuat backend baru, hanya UI yang konsumsi data.

**Pattern integration:**

```tsx
// hooks/useDashboardData.ts (assumed exists or to be created)
export function useDashboardData() {
  const { data: overview } = useDashboardOverview();      // existing
  const { data: pending } = useReviewQueue();             // existing
  const { data: channel } = useYoutubeStats();            // existing
  const { data: recent } = useRecentVideos({ limit: 5 }); // existing
  const { data: queue } = useQueueClips({ limit: 6 });    // existing
  const { data: activity } = useAIActivity({ limit: 4 }); // may need new endpoint
  const { data: pipeline } = usePipelineStatus();         // may need new endpoint

  return { overview, pending, channel, recent, queue, activity, pipeline };
}
```

**TODO list yang dilaporkan ke user di akhir:**
- Backend endpoints yang perlu ditambah (jika ada)
- Data shapes yang diasumsikan (dengan TypeScript interface)
- Fitur yang masih mock data

---

## Bundled References

Skill ini didukung file referensi yang dibaca sesuai kebutuhan:

- **`examples/dashboard-final.html`** — Mockup HTML lengkap, single file. Baca file ini untuk melihat:
  - Struktur layout final
  - CSS variables & design tokens
  - Animation keyframes
  - Component markup pattern

- **`references/design-tokens.md`** — Lengkap CSS variables (colors, spacing, radius, typography, shadows)

- **`references/component-specs.md`** — Detail spec per komponen: props, states, edge cases, accessibility

- **`references/data-contracts.md`** — TypeScript interfaces untuk semua data shapes yang dikonsumsi dashboard

- **`references/integration-checklist.md`** — Checklist untuk integrasi ke codebase existing (cek import path, theme system, routing)

**Cara baca file:** Gunakan `view` tool pada path yang tersedia di skill folder. Baca minimal `examples/dashboard-final.html` sebelum mulai coding agar gaya output konsisten.

---

## Output Akhir yang Diharapkan

Setelah skill ini dieksekusi, user akan menerima:

1. **File komponen React** terstruktur (atom → composite → page)
2. **CSS/Tailwind** sesuai sistem styling existing
3. **Hook data fetching** yang menggabungkan multiple existing hooks
4. **TypeScript types** untuk data contracts
5. **Daftar TODO** untuk backend endpoint yang perlu ditambah (jika ada)
6. **Catatan integrasi** — apa yang perlu di-import, di-update di routing, di-tambahkan di theme

---

## Checklist Quality Sebelum Selesai

Sebelum bilang ke user "selesai", verifikasi:

- [ ] Layout mengisi viewport penuh (tidak ada dead space ≥30%)
- [ ] Pending Review card visually dominant (2x size + amber + CTA)
- [ ] Hero strip personalisasi (nama user + context number)
- [ ] Setiap KPI punya trend indicator atau sparkline
- [ ] Recent Videos & Review Queue masing-masing tampil minimal 5-6 items
- [ ] Performance chart ada (mock ok kalau backend belum siap)
- [ ] AI Activity timeline ada (mock ok)
- [ ] Pipeline 5-stages ada dengan live indicator
- [ ] Loading states konsisten di semua cards
- [ ] Empty states actionable, bukan kosong
- [ ] Animasi load staggered (tidak semua muncul bersamaan)
- [ ] Hover states di semua clickable elements
- [ ] CSS variables digunakan, bukan hardcode
- [ ] Tidak ada console error
- [ ] Mobile responsive minimal tidak crash (single column stack)

---

## Anti-Patterns yang Harus Dihindari

❌ **Jangan** pakai `max-width: 1200px; margin: 0 auto` di main content
❌ **Jangan** buat semua KPI cards seukuran (boring + tidak ada hierarki)
❌ **Jangan** tampilkan greeting generik tanpa nama/context
❌ **Jangan** biarkan card kosong tanpa empty state
❌ **Jangan** import semua komponen sebagai default (gunakan named exports untuk discoverability)
❌ **Jangan** pakai inline style untuk styling utama — pakai CSS Variables / Tailwind / CSS Module
❌ **Jangan** hardcode warna seperti `color: "#00e5a0"` — pakai `var(--accent-green)` atau token Tailwind
❌ **Jangan** lupa loading states (frustrating user kalau lihat layout meledak saat data load)
