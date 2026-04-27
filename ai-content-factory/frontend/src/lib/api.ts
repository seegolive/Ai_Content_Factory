import axios, { AxiosInstance } from "axios";
import type {
  Clip,
  User,
  Video,
  VideoDetail,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const api: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Inject JWT token from localStorage
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 (logout) and 429 (rate limit with exponential backoff)
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    if (response?.status === 429 && config) {
      const retryCount: number = (config._retryCount ?? 0) + 1;
      if (retryCount <= 3) {
        config._retryCount = retryCount;
        const delay = Math.pow(2, retryCount) * 500; // 1s, 2s, 4s
        await new Promise<void>((resolve) => setTimeout(resolve, delay));
        return api(config);
      }
    }
    if (response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  getLoginUrl: () => api.get<{ auth_url: string; state: string }>("/auth/google/login"),
  getMe: () => api.get<User>("/auth/me"),
  logout: () => api.post("/auth/logout"),
};

// ── Videos ──────────────────────────────────────────────────────────────────

export const videosApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get<Video[]>("/videos", { params }),

  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<{ video_id: string; status: string; message: string }>(
      "/videos/upload",
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
        },
      }
    );
  },

  fromUrl: (youtube_url: string, youtube_account_id?: string) =>
    api.post<{ video_id: string; status: string; message: string }>("/videos/from-url", {
      youtube_url,
      youtube_account_id,
    }),

  getById: (id: string) => api.get<VideoDetail>(`/videos/${id}`),

  getStatus: (id: string) =>
    api.get<{
      video_id: string;
      status: string;
      checkpoint?: string;
      progress_percent: number;
      current_stage?: string;
      error_message?: string;
    }>(`/videos/${id}/status`),

  delete: (id: string) => api.delete(`/videos/${id}`),
};

// ── Clips ───────────────────────────────────────────────────────────────────

export const clipsApi = {
  list: (
    videoId: string,
    params?: { qc_status?: string; review_status?: string; viral_score_min?: number }
  ) => api.get<Clip[]>(`/videos/${videoId}/clips`, { params }),

  review: (clipId: string, action: "approve" | "reject", note?: string) =>
    api.patch<Clip>(`/clips/${clipId}/review`, { action, note }),

  bulkReview: (clip_ids: string[], action: "approve" | "reject") =>
    api.post("/clips/bulk-review", { clip_ids, action }),

  update: (clipId: string, data: { title?: string; description?: string; hashtags?: string[] }) =>
    api.patch<Clip>(`/clips/${clipId}`, data),

  publish: (clipId: string, platforms: string[], youtube_account_id?: string) =>
    api.post(`/clips/${clipId}/publish`, { platforms, youtube_account_id }),

  streamUrl: (clipId: string) => `${BASE_URL}/api/v1/clips/${clipId}/stream`,
};

// ── YouTube ──────────────────────────────────────────────────────────────────

export interface YTVideoStat {
  video_id: string;
  title: string;
  published_at: string;
  thumbnail_url: string | null;
  views: number;
  likes: number;
  comments: number;
  duration_seconds: number;
}

export interface YTChannelAnalytics {
  channel_id: string;
  channel_name: string;
  thumbnail_url: string | null;
  subscriber_count: number;
  total_views: number;
  total_videos: number;
  recent_videos: YTVideoStat[];
  top_videos: YTVideoStat[];
}

export const youtubeApi = {
  getStats: () => api.get<{
    connected: boolean;
    accounts: Array<{
      channel_id: string;
      channel_name?: string;
      subscriber_count?: number;
      thumbnail_url?: string;
      connected: boolean;
      error?: string;
    }>;
  }>("/youtube/stats"),

  getAnalytics: () =>
    api.get<{
      connected: boolean;
      analytics: YTChannelAnalytics | null;
      error?: string | null;
    }>("/youtube/analytics"),
};

// ── Analytics ────────────────────────────────────────────────────────────────

import type {
  ChannelOverview,
  ContentDNAModel,
  DailyStats,
  GamePerformanceResponse,
  RetentionCurve,
  VideoOpportunity,
  VideoWithAnalytics,
  WeeklyInsightReport,
} from "@/types/analytics";

export const analyticsApi = {
  getOverview: (channelId: string) =>
    api.get<ChannelOverview>(`/analytics/channel/${channelId}/overview`),

  getVideos: (
    channelId: string,
    params?: { limit?: number; offset?: number; sort_by?: string }
  ) =>
    api.get<{ items: VideoWithAnalytics[]; total: number; limit: number; offset: number }>(
      `/analytics/channel/${channelId}/videos`,
      { params }
    ),

  getRetentionCurve: (youtubeVideoId: string) =>
    api.get<RetentionCurve>(`/analytics/videos/${youtubeVideoId}/retention`),

  getContentDNA: (channelId: string) =>
    api.get<ContentDNAModel>(`/analytics/channel/${channelId}/content-dna`),

  getOpportunities: (channelId: string) =>
    api.get<{ items: VideoOpportunity[] }>(`/analytics/channel/${channelId}/opportunities`),

  getWeeklyReport: (channelId: string) =>
    api.get<WeeklyInsightReport>(`/analytics/channel/${channelId}/weekly-report/latest`),

  getDailyStats: (channelId: string, days: number = 30) =>
    api.get<DailyStats>(`/analytics/channel/${channelId}/daily-stats`, { params: { days } }),

  triggerSync: (channelId: string) =>
    api.post<{ task_id: string; message: string }>(`/analytics/channel/${channelId}/sync`),

  getGamePerformance: (channelId: string) =>
    api.get<GamePerformanceResponse>(`/analytics/channel/${channelId}/game-performance`),
};

export default api;
