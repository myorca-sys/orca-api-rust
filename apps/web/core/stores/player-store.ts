import { create } from "zustand";
import type { VideoSource } from "@/core/types/anime";

interface PlayerState {
  isOpen: boolean;
  isMinimized: boolean;
  anilistId: number | null;
  episodeNum: number | null;
  title: string;
  poster: string;
  sources: VideoSource[];
  animeSlug: string;
  
  openPlayer: (data: Partial<PlayerState>) => void;
  closePlayer: () => void;
  minimizePlayer: () => void;
  maximizePlayer: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  isOpen: false,
  isMinimized: false,
  anilistId: null,
  episodeNum: null,
  title: "",
  poster: "",
  sources: [],
  animeSlug: "",

  openPlayer: (data) => set({ ...data, isOpen: true, isMinimized: false }),
  closePlayer: () => set({ isOpen: false, isMinimized: false, anilistId: null, episodeNum: null, sources: [] }),
  minimizePlayer: () => set({ isMinimized: true }),
  maximizePlayer: () => set({ isMinimized: false }),
}));