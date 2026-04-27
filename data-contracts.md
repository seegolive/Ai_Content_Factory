# Data Contracts — Dashboard

TypeScript interface untuk semua data shapes yang dikonsumsi Dashboard. Gunakan ini sebagai kontrak — jika backend belum mengembalikan field tertentu, mock data harus mengikuti struktur ini sehingga integration nanti tinggal swap.

## Master Hook Output

```typescript
interface DashboardData {
  user: User;
  overview: DashboardOverview;
  pendingReview: PendingReviewSummary;
  channel: ConnectedChannel;
  recentVideos: RecentVideo[];
  reviewQueue: QueueClip[];
  performanceTrend: PerformanceTrend;
  aiActivity: ActivityEntry[];
  pipeline: PipelineStatus;
}
```

---

## User & Overview

```typescript
interface User {
  id: string;
  name: string;        // "Seego"
  initial: string;     // "S" — derived if not provided
  email: string;
  avatar_url?: string;
}

interface DashboardOverview {
  total_videos: number;
  clips_generated_today: number;
  clips_generated_total: number;
  published_this_week: number;
  avg_viral_score: number;       // 0-100
  greeting_period: 'morning' | 'afternoon' | 'evening';
  current_date: string;          // "Mon, Apr 27"
}
```

---

## Pending Review (Primary KPI)

```typescript
interface PendingReviewSummary {
  count: number;                 // 6
  last_processed_at: string;     // ISO date
  last_processed_relative: string; // "2 hours ago"
  estimated_review_minutes: number; // 4
}
```

---

## Connected Channel

```typescript
interface ConnectedChannel {
  id: string;
  name: string;                  // "Seego GG"
  handle: string;                // "@seegogg"
  platform: 'youtube' | 'twitch' | 'tiktok';
  is_connected: boolean;
  avatar_url?: string;
  initial: string;               // fallback "S"

  // Stats
  subscribers: number;           // 2500
  subscribers_formatted: string; // "2.5K"
  total_views: number;
  total_views_formatted: string; // "128K"
  growth_30d_pct: number;        // 12 → "+12%"

  // Channel manage URL (internal app route)
  manage_url: string;            // "/settings/channels/youtube"
}
```

---

## Secondary KPIs

```typescript
interface KPICardData {
  key: 'videos' | 'clips' | 'published' | 'avg_score';
  label: string;                 // "Videos", "Clips", etc
  value: number;
  trend_pct: number;             // +1, +6, 0, +5
  trend_direction: 'up' | 'down' | 'flat';
  sparkline: number[];           // last 7 days values
  accent: 'purple' | 'green' | 'red' | 'blue';
  sublabel: string;              // "total uploaded", "generated today"
}
```

---

## Recent Videos

```typescript
interface RecentVideo {
  id: string;
  title: string;
  duration_seconds: number;
  duration_formatted: string;    // "1:42:11"
  thumbnail_url?: string;
  thumbnail_emoji_fallback: string; // "🎮" — emoji to show if no thumbnail
  uploaded_at: string;           // ISO
  uploaded_relative: string;     // "3h ago"
  is_live: boolean;

  clips_generated: number;
  clips_published: number;

  status: 'review' | 'published' | 'processing' | 'queued';
  processing_progress?: number;  // 0-100, only if status=processing
  avg_score?: number;            // 0-100, only if status=review

  detail_url: string;            // route to video detail
}
```

---

## Review Queue (Clips)

```typescript
interface QueueClip {
  id: string;
  title: string;
  duration_seconds: number;
  duration_formatted: string;    // "54s"

  thumbnail_url?: string;
  thumbnail_emoji_fallback: string;

  viral_score: number;           // 0-100
  score_tier: 'high' | 'mid' | 'low';  // ≥80 / 70-79 / <70

  primary_tag: 'clutch' | 'funny' | 'fail' | 'rage';
  source_video_id: string;

  review_url: string;
}
```

---

## Performance Trend

```typescript
interface PerformanceTrend {
  range: '7d' | '30d' | '90d';
  data_points: TrendPoint[];

  // Aggregates for footer stats
  total_views: number;
  total_views_formatted: string;     // "12.4K"
  views_change_pct: number;

  total_clips: number;
  clips_change_pct: number;

  total_watch_time_hours: number;
  watch_time_change_pct: number;
}

interface TrendPoint {
  date: string;                  // ISO
  views: number;
  clips: number;
  watch_time_hours: number;
}
```

---

## AI Activity

```typescript
interface ActivityEntry {
  id: string;
  timestamp: string;             // ISO
  timestamp_relative: string;    // "2 hours ago"
  type: 'success' | 'info' | 'warn' | 'error';

  // Renderable title with optional accented part
  title_template: string;        // "Generated {clips} from {video}"
  title_parts: ActivityTitlePart[];

  source: string;                // "Gemini Flash · 41s avg"

  // Optional CTA
  action_url?: string;
}

interface ActivityTitlePart {
  text: string;
  emphasis: boolean;             // if true, render with accent color
}
```

---

## Pipeline Status

```typescript
interface PipelineStatus {
  is_active: boolean;
  current_stage_index: number;   // 0-4
  stages: PipelineStage[];

  progress_pct: number;          // 0-100
  summary_text: string;          // "Stage 4 of 5 · Awaiting your review"
  eta_text: string;              // "ETA: ~4 min"
}

interface PipelineStage {
  index: number;                 // 0-4
  key: 'upload' | 'transcribe' | 'analyze' | 'review' | 'publish';
  label: string;                 // "Upload", "Transcribe", etc
  status: 'done' | 'active' | 'pending';
  count: number;                 // depends on stage:
                                 // upload=videos uploaded
                                 // analyze=clips generated
                                 // review=clips pending
                                 // publish=clips ready
  count_label: string;           // "1 done", "6 clips", "6 pending"
}
```

---

## Hook Implementation Template

```typescript
// hooks/useDashboardData.ts

import { useQuery } from '@tanstack/react-query';

export function useDashboardData(): {
  data: DashboardData | undefined;
  isLoading: boolean;
  error: Error | null;
} {
  // Combine multiple existing hooks or call a unified endpoint
  const overviewQuery = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
  });

  const recentQuery = useQuery({
    queryKey: ['dashboard', 'recent-videos'],
    queryFn: () => fetchRecentVideos({ limit: 5 }),
  });

  const queueQuery = useQuery({
    queryKey: ['dashboard', 'queue'],
    queryFn: () => fetchQueueClips({ limit: 6 }),
  });

  // ... etc

  return {
    data: combineDashboardData({
      overview: overviewQuery.data,
      recent: recentQuery.data,
      queue: queueQuery.data,
      // ...
    }),
    isLoading: overviewQuery.isLoading || recentQuery.isLoading || queueQuery.isLoading,
    error: overviewQuery.error || recentQuery.error || queueQuery.error,
  };
}
```

---

## Mock Data untuk Development

Jika backend endpoint belum siap, gunakan mock berikut sebagai dev fallback:

```typescript
// lib/mockDashboardData.ts
export const mockDashboardData: DashboardData = {
  user: { id: '1', name: 'Seego', initial: 'S', email: 'seego@example.com' },
  overview: {
    total_videos: 1,
    clips_generated_today: 6,
    clips_generated_total: 42,
    published_this_week: 0,
    avg_viral_score: 81,
    greeting_period: 'evening',
    current_date: 'Mon, Apr 27',
  },
  pendingReview: {
    count: 6,
    last_processed_at: '2026-04-27T17:12:00Z',
    last_processed_relative: '2 hours ago',
    estimated_review_minutes: 4,
  },
  channel: {
    id: 'ch_1',
    name: 'Seego GG',
    handle: '@seegogg',
    platform: 'youtube',
    is_connected: true,
    initial: 'S',
    subscribers: 2500,
    subscribers_formatted: '2.5K',
    total_views: 128000,
    total_views_formatted: '128K',
    growth_30d_pct: 12,
    manage_url: '/settings/channels/youtube',
  },
  // ... fill the rest following the interfaces above
};
```
