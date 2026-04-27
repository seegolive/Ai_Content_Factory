"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { analyticsApi } from "@/lib/api";

// ── Channel Overview ──────────────────────────────────────────────────────────

export function useChannelOverview(channelId: string | null) {
  return useQuery({
    queryKey: ["analytics", "overview", channelId],
    queryFn: () => analyticsApi.getOverview(channelId!).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 5 * 60 * 1000, // 5 min
  });
}

// ── Videos with Analytics ────────────────────────────────────────────────────

export function useVideosWithAnalytics(
  channelId: string | null,
  params?: { limit?: number; offset?: number; sort_by?: string }
) {
  return useQuery({
    queryKey: ["analytics", "videos", channelId, params],
    queryFn: () => analyticsApi.getVideos(channelId!, params).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 5 * 60 * 1000,
  });
}

// ── Retention Curve ───────────────────────────────────────────────────────────

export function useRetentionCurve(youtubeVideoId: string | null) {
  return useQuery({
    queryKey: ["analytics", "retention", youtubeVideoId],
    queryFn: () => analyticsApi.getRetentionCurve(youtubeVideoId!).then((r) => r.data),
    enabled: !!youtubeVideoId,
    staleTime: 30 * 60 * 1000, // retention data rarely changes
    retry: false, // 404 = no data, no retry
  });
}

// ── Daily Stats ───────────────────────────────────────────────────────────────

export function useDailyStats(channelId: string | null, days: number = 30) {
  return useQuery({
    queryKey: ["analytics", "daily-stats", channelId, days],
    queryFn: () => analyticsApi.getDailyStats(channelId!, days).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 10 * 60 * 1000,
  });
}

// ── Content DNA ───────────────────────────────────────────────────────────────

export function useContentDNA(channelId: string | null) {
  return useQuery({
    queryKey: ["analytics", "content-dna", channelId],
    queryFn: () => analyticsApi.getContentDNA(channelId!).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 30 * 60 * 1000,
  });
}

// ── Opportunities ─────────────────────────────────────────────────────────────

export function useOpportunities(channelId: string | null) {
  return useQuery({
    queryKey: ["analytics", "opportunities", channelId],
    queryFn: () => analyticsApi.getOpportunities(channelId!).then((r) => r.data.items),
    enabled: !!channelId,
    staleTime: 10 * 60 * 1000,
  });
}

// ── Weekly Report ─────────────────────────────────────────────────────────────

export function useWeeklyReport(channelId: string | null) {
  return useQuery({
    queryKey: ["analytics", "weekly-report", channelId],
    queryFn: () => analyticsApi.getWeeklyReport(channelId!).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}

// ── Game Performance ──────────────────────────────────────────────────────────

export function useGamePerformance(channelId: string | null) {
  return useQuery({
    queryKey: ["analytics", "game-performance", channelId],
    queryFn: () => analyticsApi.getGamePerformance(channelId!).then((r) => r.data),
    enabled: !!channelId,
    staleTime: 30 * 60 * 1000,
  });
}

// ── Sync Mutation ─────────────────────────────────────────────────────────────

export function useSyncAnalytics() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: string) =>
      analyticsApi.triggerSync(channelId).then((r) => r.data),
    onSuccess: (data, channelId) => {
      toast.success(data.message || "Sync analytics dimulai...");
      // Invalidate all analytics queries after a delay
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["analytics"] });
      }, 5000);
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      const msg = error.response?.data?.detail ?? "Gagal memulai sync";
      toast.error(msg);
    },
  });
}
