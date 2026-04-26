"use client";
import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { clipsApi, videosApi } from "@/lib/api";
import type { Clip, Video, VideoDetail } from "@/types";

// ── Videos ──────────────────────────────────────────────────────────────────

export function useVideos(params?: { status?: string }) {
  return useQuery({
    queryKey: ["videos", params],
    queryFn: () => videosApi.list(params).then((r) => r.data),
    staleTime: 30_000,
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clips"] }),
  });
}
