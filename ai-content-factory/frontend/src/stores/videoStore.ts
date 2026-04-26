import { create } from "zustand";
import type { Video, VideoDetail } from "@/types";
import { videosApi } from "@/lib/api";

interface ProcessingStatus {
  video_id: string;
  status: string;
  progress_percent: number;
  current_stage?: string;
  error_message?: string;
}

interface VideoStore {
  videos: Video[];
  activeVideoId: string | null;
  processingJobs: Map<string, ProcessingStatus>;
  isLoading: boolean;
  error: string | null;

  fetchVideos: (params?: { status?: string }) => Promise<void>;
  setActiveVideo: (id: string | null) => void;
  updateProcessingStatus: (status: ProcessingStatus) => void;
  removeVideo: (id: string) => void;
}

export const useVideoStore = create<VideoStore>((set, get) => ({
  videos: [],
  activeVideoId: null,
  processingJobs: new Map(),
  isLoading: false,
  error: null,

  fetchVideos: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const res = await videosApi.list(params);
      set({ videos: res.data, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  setActiveVideo: (id) => set({ activeVideoId: id }),

  updateProcessingStatus: (status) =>
    set((state) => {
      const jobs = new Map(state.processingJobs);
      jobs.set(status.video_id, status);
      return { processingJobs: jobs };
    }),

  removeVideo: (id) =>
    set((state) => ({
      videos: state.videos.filter((v) => v.id !== id),
    })),
}));
