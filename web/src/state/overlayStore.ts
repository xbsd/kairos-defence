// The theater-to-overlay handoff for the recall beam (§17.8): where the in-zone road segment's
// midpoint lands on screen, written by the Projector inside useFrame (no React state), read by
// the beam's requestAnimationFrame loop.
import { createStore } from "zustand/vanilla";

export interface ScreenPoint {
  /** Pixels from the theater's top-left corner. */
  x: number;
  y: number;
  /** False when the point is behind the camera or outside the theater. */
  on: boolean;
}

export interface OverlayState {
  road: ScreenPoint;
  /** The road the point belongs to (the beam joins that clue span). */
  roadName: string | null;
  /** The recall overlay is collapsed by the presenter. */
  collapsed: boolean;
}

export const overlayStore = createStore<
  OverlayState & {
    setRoad: (p: ScreenPoint, name: string | null) => void;
    setCollapsed: (c: boolean) => void;
  }
>()((set) => ({
  road: { x: 0, y: 0, on: false },
  roadName: null,
  collapsed: false,
  setRoad: (road, roadName) => set({ road, roadName }),
  setCollapsed: (collapsed) => set({ collapsed }),
}));
