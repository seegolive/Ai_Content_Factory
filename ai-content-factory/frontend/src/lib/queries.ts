"use client";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { analyticsApi, clipsApi, videosApi, youtubeApi, type YTChannelAnalytics } from "@/lib/api";
import type { Clip, Video, VideoDetail } from "@/types";

// ── Videos ──────────────────────────────────────────────────────────────────

export function useVideos(params?: { status?: string }) {
  return useQuery({
    queryKey: ["videos", params],
    queryFn: () => videosApi.list(params).then((r) => r.data),
    // Poll actively when filtering for processing/queued, or when list contains active videos
    refetchInterval: (query) => {
      if (params?.status === "processing" || params?.status === "queued") return 5_000;
      const videos = query.state.data ?? [];
      const hasActive = videos.some(
        (v: { status: string }) => v.status === "processing" || v.status === "queued"
      );
      return hasActive ? 8_000 : 30_000;
    },
    staleTime: 5_000,
    retry: 2,
  });
}

export function useVideo(id: string) {
  return useQuery({
    queryKey: ["video", id],
    queryFn: () => videosApi.getById(id).then((r) => r.data),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useVideoStatus(id: string, enabled = true) {
  return useQuery({
    queryKey: ["videoStatus", id],
    queryFn: () => videosApi.getStatus(id).then((r) => r.data),
    enabled: !!id && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "queued" ? 3_000 : false;
    },
    staleTime: 0,
  });
}

export function useUploadVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (pct: number) => void }) =>
      videosApi.upload(file, onProgress).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["videos"] }),
  });
}

export function useDeleteVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => videosApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["videos"] }),
  });
}

// ── Clips ───────────────────────────────────────────────────────────────────

export function useClips(
  videoId: string,
  params?: { review_status?: string; viral_score_min?: number }
) {
  return useQuery({
    queryKey: ["clips", videoId, params],
    queryFn: () => clipsApi.list(videoId, params).then((r) => r.data),
    enabled: !!videoId,
    staleTime: 30_000,
  });
}

export function useClipStats() {
  return useQuery({
    queryKey: ["clipStats"],
    queryFn: () => clipsApi.stats().then((r) => r.data),
    staleTime: 15_000,
  });
}

export function useClip(clipId: string, enabled = true) {
  return useQuery({
    queryKey: ["clip", clipId],
    queryFn: () => clipsApi.getById(clipId).then((r) => r.data),
    enabled: !!clipId && enabled,
    staleTime: 5_000,
  });
}

/** Poll a clip's platform_status until it's published/failed. */
export function useClipPublishStatus(clipId: string, enabled = true) {
  return useQuery({
    queryKey: ["clipPublishStatus", clipId],
    queryFn: () => clipsApi.getById(clipId).then((r) => r.data.platform_status),
    enabled: !!clipId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data;
      if (!status) return 2_000;
      const values = Object.values(status);
      const isTerminal =
        values.length > 0 &&
        values.every(
          (s) => s.status === "published" || s.status === "failed" || s.status === "pending"
        );
      return isTerminal ? false : 2_000;
    },
    staleTime: 0,
  });
}

export function useReviewClip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      clipId,
      action,
      note,
    }: {
      clipId: string;
      action: "approve" | "reject";
      note?: string;
    }) => clipsApi.review(clipId, action, note).then((r) => r.data),
    onSuccess: (_, { clipId }) => {
      qc.invalidateQueries({ queryKey: ["clips"] });
      qc.invalidateQueries({ queryKey: ["clipStats"] });
    },
  });
}

export function useBulkReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clip_ids, action }: { clip_ids: string[]; action: "approve" | "reject" }) =>
      clipsApi.bulkReview(clip_ids, action).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clips"] }),
  });
}

export function useUpdateClip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      clipId,
      data,
    }: {
      clipId: string;
      data: { title?: string; description?: string; hashtags?: string[] };
    }) => clipsApi.update(clipId, data).then((r) => r.data),
    onSuccess: (_, { clipId }) => {
      qc.invalidateQueries({ queryKey: ["clips"] });
      qc.invalidateQueries({ queryKey: ["clip", clipId] });
    },
  });
}

export function useSavePublishSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      clipId,
      settings,
    }: {
      clipId: string;
      settings: {
        title?: string;
        description?: string;
        hashtags?: string[];
        privacy: "public" | "unlisted" | "private";
        category?: string;
      };
    }) => clipsApi.savePublishSettings(clipId, settings).then((r) => r.data),
    onSuccess: (_, { clipId }) => {
      qc.invalidateQueries({ queryKey: ["clip", clipId] });
      qc.invalidateQueries({ queryKey: ["clips"] });
    },
  });
}

// ── YouTube ──────────────────────────────────────────────────────────────────

export function usePublishClip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      clipId,
      platforms,
      youtube_account_id,
      privacy,
    }: {
      clipId: string;
      platforms: string[];
      youtube_account_id?: string;
      privacy?: string;
    }) => clipsApi.publish(clipId, platforms, youtube_account_id, privacy).then((r) => r.data),
    onSuccess: (_, { clipId }) => {
      qc.invalidateQueries({ queryKey: ["clips"] });
      qc.invalidateQueries({ queryKey: ["clip", clipId] });
      qc.invalidateQueries({ queryKey: ["clipPublishStatus", clipId] });
    },
  });
}

export function useResetPublishStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => clipsApi.resetPublishStatus(clipId).then((r) => r.data),
    onSuccess: (_, clipId) => {
      qc.invalidateQueries({ queryKey: ["clip", clipId] });
      qc.invalidateQueries({ queryKey: ["clipPublishStatus", clipId] });
    },
  });
}

export function useYoutubeStats() {
  return useQuery({
    queryKey: ["youtubeStats"],
    queryFn: () => youtubeApi.getStats().then((r) => r.data),
    staleTime: 5 * 60_000, // 5 min cache
    retry: 1,
  });
}

export function useYoutubeAnalytics() {
  return useQuery({
    queryKey: ["youtubeAnalytics"],
    queryFn: () => youtubeApi.getAnalytics().then((r) => r.data),
    staleTime: 5 * 60_000, // 5 min cache
    retry: 1,
  });
}

export function useAnalyticsDailyStats(channelId: string | undefined, days: number = 7) {
  return useQuery({
    queryKey: ["analyticsDailyStats", channelId, days],
    queryFn: () => analyticsApi.getDailyStats(channelId!, days).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 5 * 60_000,
    retry: 1,
  });
}
