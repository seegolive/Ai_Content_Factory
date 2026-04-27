// Analytics module TypeScript types

export interface ChannelOverview {
  channel_id: string;
  channel_name: string;
  total_views: number;
  total_videos: number;
  avg_ctr: number;
  avg_view_duration_seconds: number;
  watch_time_hours: number;
  views_last_30d: number;
  subscribers_last_30d: number;
  views_trend_pct: number | null;
  content_dna_confidence: number;
  last_synced: string | null;
}

export interface VideoWithAnalytics {
  video_id: string;
  youtube_video_id: string;
  title: string;
  published_at: string | null;
  duration_seconds: number;
  views: number;
  avg_ctr: number;
  watch_time_minutes: number;
  avg_view_duration_seconds: number;
  avg_view_percentage: number;
  clips_generated: number;
  has_retention_data: boolean;
  clippable: boolean;
}

export interface RetentionDataPoint {
  elapsed_ratio: number;
  retention_ratio: number;
  timestamp_seconds: number;
}

export interface PeakMoment {
  elapsed_ratio: number;
  retention_ratio: number;
  timestamp_seconds: number;
  label: string;
  rise?: number;
}

export interface DropOffPoint {
  elapsed_ratio: number;
  retention_ratio: number;
  timestamp_seconds: number;
  drop_pct: number;
  label: string;
}

export interface ClipWindow {
  start: number;
  end: number;
  score: number;
  reason: string;
}

export interface RetentionCurve {
  youtube_video_id: string;
  duration_seconds: number;
  data_points: RetentionDataPoint[];
  peak_moments: PeakMoment[];
  drop_off_points: DropOffPoint[];
  optimal_clip_windows: ClipWindow[];
}

export interface DailyStats {
  dates: string[];
  views: number[];
  watch_time_minutes: number[];
  subscribers_net: number[];
}

export interface ContentDNAModel {
  channel_id: string;
  niche: string | null;
  sub_niches: string[];
  confidence_score: number;
  videos_analyzed: number;
  status: "building" | "ready";
  message?: string;
  viral_score_weights: Record<string, number>;
  top_performing_patterns: {
    title_patterns?: string[];
    avoid_patterns?: string[];
    best_clip_duration?: { min: number; max: number; optimal: number };
    best_upload_days?: string[];
    best_upload_hours?: number[];
  };
  game_performance: Record<
    string,
    { avg_views: number; avg_ctr: number; sample_size: number }
  >;
  underperforming_patterns?: Record<string, unknown>;
  last_updated: string | null;
}

export interface VideoOpportunity {
  video_id: string;
  title: string;
  duration_seconds: number;
  published_at: string | null;
  game_name: string | null;
  viral_potential_score: number;
  estimated_clips: number;
  peak_moments_count: number;
  has_retention_data: boolean;
  recommendation: string;
}

export interface WeeklyInsightReport {
  available: boolean;
  week_start?: string;
  week_end?: string;
  summary?: string;
  wins?: string[];
  issues?: string[];
  recommendations?: Array<{
    priority: "high" | "medium" | "low";
    action: string;
    reason: string;
    expected_impact: string;
  }>;
  top_clip_type?: string;
  views_change_pct?: number | null;
  subscribers_change?: number | null;
  generated_at?: string;
  message?: string;
}

export interface GamePerformance {
  name: string;
  video_count: number;
  avg_views: number;
  avg_ctr: number;
  trend: "up" | "stable" | "down";
  recommendation: string;
}

export interface GamePerformanceResponse {
  games: GamePerformance[];
  message?: string;
}
