import { create } from "zustand";

interface ProcessingStatus {
  video_id: string;
  status: string;
  progress_percent: number;
  current_stage?: string;
  error_message?: string;
}

interface VideoStore {
  activeVideoId: string | null;
  processingJobs: Map<string, ProcessingStatus>;
  setActiveVideo: (id: string | null) => void;
  updateProcessingStatus: (status: ProcessingStatus) => void;
  removeProcessingJob: (id: string) => void;
}

export const useVideoStore = create<VideoStore>((set) => ({
  activeVideoId: null,
  processingJobs: new Map(),

  setActiveVideo: (id) => set({ activeVideoId: id }),

  updateProcessingStatus: (status) =>
    set((state) => {
      const jobs = new Map(state.processingJobs);
      jobs.set(status.video_id, status);
      return { processingJobs: jobs };
    }),

  removeProcessingJob: (id) =>
    set((state) => {
      const jobs = new Map(state.processingJobs);
      jobs.delete(id);
      return { processingJobs: jobs };
    }),
}));
