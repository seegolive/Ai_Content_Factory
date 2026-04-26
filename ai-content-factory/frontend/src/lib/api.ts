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

// Handle 401 and 429
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
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

export default api;
