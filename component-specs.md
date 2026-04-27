# Component Specs — Dashboard

Detail spec untuk setiap komponen Dashboard. Format: **Props**, **States**, **Edge Cases**, **A11y**.

---

## `<DashboardPage />`

**File:** `app/dashboard/page.tsx` (atau path setara di codebase)

**Tanggung jawab:**
- Memuat data via `useDashboardData()`
- Render shell (Topbar + Sidebar + Main)
- Render `<DashboardBentoGrid />` sebagai konten utama
- Handle global loading & error states

**Props:** None (page component, datanya dari hook).

**Loading state:** Tampilkan full-page skeleton sebelum data pertama datang. Setelah ada data, individual cards punya loading state masing-masing.

---

## `<DashboardHero />`

**Props:**
```typescript
{
  userName: string;
  pendingCount: number;
  greetingPeriod: 'morning' | 'afternoon' | 'evening';
  currentDate: string;
  lastProcessedRelative: string;
  onReviewClick: () => void;
  onSyncClick: () => void;
}
```

**Render:**
- Title interpolation: dynamic — kalau `pendingCount === 0`, ubah judul jadi "Hi {name}, semua clips sudah di-review! 🎉"
- Greeting prefix berdasarkan `greetingPeriod`
- Background radial gradient di kanan (amber)

**Edge cases:**
- `pendingCount === 0` → ganti CTA primary jadi "Upload Video Baru" dengan icon upload
- `pendingCount > 99` → tampilkan "99+ clips" untuk cegah overflow
- `userName` kosong → fallback ke "there"

**Loading skeleton:**
- Greeting line (180px wide × 14px tall)
- Title line (60% wide × 28px tall)
- Subtitle 2 lines

**A11y:**
- Title sebagai `<h1>` (page heading)
- Buttons punya `aria-label` lengkap
- CTA primary `autoFocus` saat halaman load (sehingga tekan Enter langsung ke action)

---

## `<KPICardPrimary />` (Pending Review)

**Props:**
```typescript
{
  value: number;
  label: string;
  ctaText: string;
  ctaHref: string;
  metaLines: string[];        // ["⌚ Last clip 2h ago", "Est. 4 min review"]
  loading?: boolean;
}
```

**Visual:**
- Background: `linear-gradient(135deg, rgba(255,179,71,.12), rgba(255,107,53,.04))`
- Border: `rgba(255,179,71,.25)`
- Inner glow di pojok kanan-bawah (radial amber)
- Big value: 64px font-mono, color amber, animasi countUp saat mount

**Loading skeleton:**
- Card layout sama, value diganti shimmer block 80×64px

**Edge case:**
- `value === 0` → ubah message jadi "Semua clips sudah di-review! 🎉" + ganti CTA jadi "Upload video baru"
- `value > 99` → display "99+"

**Click target:**
- Seluruh card harus clickable (linked ke ctaHref) — bukan hanya button

---

## `<KPICardSecondary />`

**Props:**
```typescript
{
  icon: ReactNode;
  label: string;             // "Videos"
  value: number;
  sublabel: string;          // "total uploaded"
  trendPct: number;          // +1, +6, 0, -2
  trendDirection: 'up' | 'down' | 'flat';
  sparklineData: number[];   // 7 values
  accent: 'purple' | 'green' | 'red' | 'blue';
  loading?: boolean;
}
```

**Render rules:**
- Trend badge color: `accent-green` jika up, `accent-red` jika down, muted jika flat
- Trend badge tampil "+X" / "-X" / "0" (tanpa %)
- Sparkline SVG: 100×28 viewBox, polyline tanpa fill
- Sparkline color = accent color, opacity 0.6 jika trend = down

**Edge cases:**
- `value === 0` & `trendDirection === 'down'` → tampil dengan opacity 0.7 (visual cue "no activity")
- Sparkline data < 7 → pad dengan 0 di awal

---

## `<ChannelCard />`

**Props:**
```typescript
{
  channel: ConnectedChannel;
  onManage: () => void;
  loading?: boolean;
}
```

**Render:**
- Avatar 44×44px, gradient pink/red (atau image jika ada)
- Avatar punya double ring: `box-shadow: 0 0 0 2px var(--bg-panel), 0 0 0 3px var(--border)`
- Platform badge: warna sesuai platform (YouTube = red, Twitch = purple, TikTok = white/black)
- Stats grid: 3 kolom (Subs, Views, Growth %)

**Edge cases:**
- `is_connected === false` → ganti seluruh card jadi empty state: ikon + "Hubungkan channel" + button
- `growth_30d_pct === 0` → tampil "0%" warna muted, bukan red atau green
- `subscribers > 1000000` → format "1.2M" alih-alih "1200K"

---

## `<RecentVideosCard />`

**Props:**
```typescript
{
  videos: RecentVideo[];      // max 5 items
  totalCount: number;
  onViewAll: () => void;
  onVideoClick: (id: string) => void;
  loading?: boolean;
}
```

**Render:**
- Header: title "Recent Videos" + link "All videos →"
- List of `<VideoItem />` components
- Empty state: ikon video + "Belum ada video" + CTA "Upload pertama"

**Edge cases:**
- `videos.length === 0` → empty state
- `videos.length < 5` → tetap render list, tidak perlu padding empty slots
- Video dengan `status === 'processing'` → tampilkan progress text "AI processing... 47%"

---

## `<VideoItem />`

**Props:**
```typescript
{
  video: RecentVideo;
  onClick: () => void;
}
```

**Layout:** Grid 90px / 1fr / auto

**Thumbnail:**
- 90×50px, gradient background fallback
- Emoji di tengah jika no thumbnail
- Live badge top-left (jika is_live, dengan pulse animation)
- Duration overlay bottom-right (font-mono, tiny)

**Status badge:** Pakai `<StatusBadge status={video.status} />` (lihat below)

---

## `<StatusBadge />`

**Props:**
```typescript
{
  status: 'review' | 'published' | 'processing' | 'queued';
}
```

**Mapping:**
| Status | Background | Color | Label |
|---|---|---|---|
| review | `rgba(255,179,71,.1)` | `--accent-amber` | "Review" |
| published | `rgba(0,229,160,.1)` | `--accent-green` | "Published" |
| processing | `rgba(77,159,255,.1)` | `--accent-blue` | "Processing" |
| queued | `rgba(167,139,250,.1)` | `--accent-purple` | "Queued" |

---

## `<ReviewQueueCard />`

**Props:**
```typescript
{
  clips: QueueClip[];         // max 6 items
  totalCount: number;
  onReviewAll: () => void;
  onClipClick: (id: string) => void;
  loading?: boolean;
}
```

**Render:**
- Header: "Review Queue · {totalCount}"
- List of `<QueueItem />`
- Hover state pada item: translate-x 2px + border amber

**Empty state:** "Semua clips sudah di-review 🎉" + ikon checkmark hijau besar

---

## `<QueueItem />`

**Props:**
```typescript
{
  clip: QueueClip;
  onClick: () => void;
}
```

**Score badge** (circular 22px) di pojok thumbnail:
- Position: `bottom: -3px; right: -3px`
- `box-shadow: inset 0 0 0 2px <color>` untuk ring effect
- Background `var(--bg-panel)` dengan border 2px sama warna sebagai outer ring
- Color by tier: high=green, mid=amber, low=red

**Tag pill:** Pakai `<TagPill type={clip.primary_tag} />`

---

## `<TagPill />`

**Props:**
```typescript
{
  type: 'clutch' | 'funny' | 'fail' | 'rage';
}
```

**Mapping:**
| Tag | Color | Background |
|---|---|---|
| clutch | `#a78bfa` | `rgba(167,139,250,.08)` |
| funny | `#ffb347` | `rgba(255,179,71,.08)` |
| fail | `#4d9fff` | `rgba(77,159,255,.08)` |
| rage | `#ff4d6d` | `rgba(255,77,109,.08)` |

Border `rgba(<color>,.3)`, padding `1.5px 5px`, font-mono 9px.

---

## `<PerformanceChart />`

**Props:**
```typescript
{
  trend: PerformanceTrend;
  onRangeChange: (range: '7d' | '30d' | '90d') => void;
  loading?: boolean;
}
```

**Chart implementation:**
- SVG manual (bukan Recharts/Chart.js untuk artifact ringan)
- Atau pakai library yang sudah ada di codebase (cek dulu)
- viewBox: `0 0 400 180`
- 2 lines:
  - Solid line: Views (color blue)
  - Dashed line: Clips (color green)
- Dashed grid lines horizontal (3 baris)
- Last data point dengan circle + halo

**Tabs:** 7D / 30D / 90D — controlled by parent state

**Footer stats:** 3 cells dengan label, value, trend %
- Trend % berwarna green jika positive, red jika negative

**Edge cases:**
- `data_points.length === 0` → empty state "Belum ada data trend"
- Single data point → render dot saja, tanpa line

---

## `<AIActivityFeed />`

**Props:**
```typescript
{
  activities: ActivityEntry[];   // 4-6 items
  onLogsClick: () => void;
  loading?: boolean;
}
```

**Layout:**
- Vertical timeline dengan vertical line connecting all dots
- Setiap entry: dot 22px + content

**Dot variants:**
| Type | Border | Background | Icon Color |
|---|---|---|---|
| success | `rgba(0,229,160,.4)` | `rgba(0,229,160,.08)` | green |
| info | `rgba(77,159,255,.4)` | `rgba(77,159,255,.08)` | blue |
| warn | `rgba(255,179,71,.4)` | `rgba(255,179,71,.08)` | amber |
| error | `rgba(255,77,109,.4)` | `rgba(255,77,109,.08)` | red |

**Title rendering:** Map `title_parts` array. Parts dengan `emphasis: true` di-render dengan `<strong>` warna accent.

**Edge cases:**
- `activities.length === 0` → empty state "AI belum melakukan aktivitas hari ini"
- Title terlalu panjang → truncate 2 lines max

---

## `<PipelineStatus />`

**Props:**
```typescript
{
  pipeline: PipelineStatus;
  loading?: boolean;
}
```

**Stages render:**
- 5 stages horizontal, equal width (flex: 1)
- Connecting line di antara stages (positioned absolute behind)
- Active stage punya pulse box-shadow animation

**Stage circle:**
- Done: bg `rgba(0,229,160,.12)`, border green, ✓ icon
- Active: bg `rgba(77,159,255,.12)`, border blue, ◉ icon, pulse
- Pending: bg card, border default, angka

**Progress bar bottom:**
- 4px tall, gradient green→blue
- Shimmer animation (oscillate width 50%-55%)

**Live indicator** di header card: dot blue dengan pulse + "Active"

**Edge cases:**
- `is_active === false` → matikan pulse, ganti badge jadi "Idle" muted
- Semua stages `done` → progress bar 100%, summary "Pipeline complete!" green

---

## `<DashboardBentoGrid />`

**Props:**
```typescript
{
  data: DashboardData;
  loading: boolean;
  onCardAction: (action: string, payload?: any) => void;
}
```

**Layout (CSS):**
```css
.bento {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  grid-auto-rows: minmax(120px, auto);
  gap: 14px;
}

/* Card spans */
.kpi-primary    { grid-column: span 4; grid-row: span 2; }
.channel-card   { grid-column: span 4; grid-row: span 2; }
.kpi-card       { grid-column: span 2; grid-row: span 1; }
.recent-videos  { grid-column: span 7; grid-row: span 3; }
.review-queue   { grid-column: span 5; grid-row: span 3; }
.chart-card     { grid-column: span 4; grid-row: span 2; }
.activity       { grid-column: span 4; grid-row: span 2; }
.pipeline       { grid-column: span 4; grid-row: span 2; }
```

**Stagger animation:** `:nth-child(n)` dengan `animation-delay: calc(n * 0.04s)`.

---

## `<EmptyState />` (Reusable Atom)

**Props:**
```typescript
{
  icon: ReactNode;
  title: string;
  description?: string;
  ctaText?: string;
  onCtaClick?: () => void;
}
```

**Visual:**
- Centered, padding 24px
- Icon 32px muted color
- Title 13px bold
- Description 11px muted
- CTA button kecil

---

## `<LoadingSkeleton />` (Reusable Atom)

**Props:**
```typescript
{
  width: string | number;
  height: string | number;
  borderRadius?: string | number;
}
```

**Visual:**
- Background: `linear-gradient(90deg, var(--bg-card) 0%, var(--bg-hover) 50%, var(--bg-card) 100%)`
- Background-size 200% 100%
- Animation: shimmer 1.5s infinite ease-in-out

```css
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```
