export type UserPlan = "free" | "pro" | "agency";
export type VideoStatus = "queued" | "processing" | "review" | "done" | "error";
export type CopyrightStatus = "unchecked" | "clean" | "flagged";
export type ClipFormat = "horizontal" | "vertical" | "square";
export type QCStatus = "pending" | "passed" | "failed" | "manual_review";
export type ReviewStatus = "pending" | "approved" | "rejected";

export interface YoutubeAccount {
  id: string;
  channel_id: string;
  channel_name?: string;
}

export interface User {
  id: string;
  email: string;
  name?: string;
  avatar_url?: string;
  plan: UserPlan;
  credits_used: number;
  is_active: boolean;
  created_at: string;
  youtube_accounts: YoutubeAccount[];
}

export interface Video {
  id: string;
  title?: string;
  status: VideoStatus;
  checkpoint?: string;
  file_size_mb?: number;
  duration_seconds?: number;
  copyright_status: CopyrightStatus;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

export interface VideoDetail extends Video {
  transcript?: string;
  original_url?: string;
  error_message?: string;
}

export interface VideoStatusResponse {
  video_id: string;
  status: VideoStatus;
  checkpoint?: string;
  progress_percent: number;
  current_stage?: string;
  eta_seconds?: number;
  error_message?: string;
}

export type MomentType = "clutch" | "funny" | "achievement" | "rage" | "epic" | "fail";

export interface Clip {
  id: string;
  video_id: string;
  title?: string;
  description?: string;
  start_time: number;
  end_time: number;
  duration?: number;
  viral_score?: number;
  moment_type?: MomentType;
  hook_text?: string;
  hashtags: string[];
  thumbnail_path?: string;
  clip_path?: string;
  clip_path_horizontal?: string;
  clip_path_vertical?: string;
  clip_path_square?: string;
  format_generated: { horizontal?: boolean; vertical?: boolean; square?: boolean };
  format: ClipFormat;
  qc_status: QCStatus;
  qc_issues: { type: string; description: string; severity: string }[];
  review_status: ReviewStatus;
  reviewed_at?: string;
  platform_status: Record<string, { status: string; video_id?: string }>;
  ai_provider_used?: string;
  created_at: string;
}

export interface ProcessingJob {
  video_id: string;
  title: string;
  status: VideoStatus;
  progress_percent: number;
  current_stage?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
