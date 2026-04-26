import { create } from "zustand";

interface UIStore {
  sidebarCollapsed: boolean;
  selectedClips: string[];
  reviewActiveClipId: string | null;

  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  toggleClipSelection: (id: string) => void;
  selectAllClips: (ids: string[]) => void;
  clearSelection: () => void;
  setReviewActiveClip: (id: string | null) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed: false,
  selectedClips: [],
  reviewActiveClipId: null,

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),

  toggleClipSelection: (id) =>
    set((s) => ({
      selectedClips: s.selectedClips.includes(id)
        ? s.selectedClips.filter((c) => c !== id)
        : [...s.selectedClips, id],
    })),

  selectAllClips: (ids) => set({ selectedClips: ids }),
  clearSelection: () => set({ selectedClips: [] }),
  setReviewActiveClip: (id) => set({ reviewActiveClipId: id }),
}));
