import { create } from "zustand";
import type {
  ChannelOverview,
  ContentDNAModel,
  DailyStats,
  VideoOpportunity,
  VideoWithAnalytics,
  WeeklyInsightReport,
} from "@/types/analytics";

interface AnalyticsState {
  selectedChannelId: string | null;
  overviewData: ChannelOverview | null;
  videosData: VideoWithAnalytics[];
  dailyStats: DailyStats | null;
  contentDNA: ContentDNAModel | null;
  opportunities: VideoOpportunity[];
  weeklyReport: WeeklyInsightReport | null;
  isSyncing: boolean;
  lastSynced: Date | null;

  setSelectedChannel: (channelId: string | null) => void;
  setSyncing: (syncing: boolean) => void;
  setOverview: (data: ChannelOverview) => void;
  setLastSynced: (date: Date) => void;
}

export const useAnalyticsStore = create<AnalyticsState>((set) => ({
  selectedChannelId: null,
  overviewData: null,
  videosData: [],
  dailyStats: null,
  contentDNA: null,
  opportunities: [],
  weeklyReport: null,
  isSyncing: false,
  lastSynced: null,

  setSelectedChannel: (channelId) => set({ selectedChannelId: channelId }),
  setSyncing: (isSyncing) => set({ isSyncing }),
  setOverview: (data) => set({ overviewData: data }),
  setLastSynced: (date) => set({ lastSynced: date }),
}));
