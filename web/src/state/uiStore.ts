// UI preferences: reduce motion (OS setting or M), camera preset, performance level (§17.11).
import { createStore } from "zustand/vanilla";

export type CameraPreset = "overview" | "follow" | "target" | "memory" | "forecast" | "swarm";

export interface UiState {
  osReduce: boolean;
  /** M toggles it; null follows the OS. */
  userReduce: boolean | null;
  camera: CameraPreset;
  /** 0 full effects, 1 bloom off, 2 bloom off and packets halved (auto-degrade). */
  perfLevel: 0 | 1 | 2;
  /** The presenter's Performance mode: no bloom, grain or core beams; half the packets. */
  perfMode: boolean;
  shortcutsOpen: boolean;
}

export interface UiActions {
  setOsReduce: (v: boolean) => void;
  toggleReduce: () => void;
  setCamera: (c: CameraPreset) => void;
  setPerfLevel: (l: 0 | 1 | 2) => void;
  setShortcuts: (open: boolean) => void;
  togglePerfMode: () => void;
}

export const uiStore = createStore<UiState & UiActions>()((set, get) => ({
  osReduce: false,
  userReduce: null,
  camera: "overview",
  perfLevel: 0,
  perfMode: false,
  shortcutsOpen: false,
  setOsReduce: (osReduce) => set({ osReduce }),
  toggleReduce: () => set({ userReduce: !reduceMotion(get()) }),
  setCamera: (camera) => set({ camera }),
  setPerfLevel: (perfLevel) => set({ perfLevel }),
  setShortcuts: (shortcutsOpen) => set({ shortcutsOpen }),
  togglePerfMode: () => set({ perfMode: !get().perfMode }),
}));

export function reduceMotion(s: UiState): boolean {
  return s.userReduce ?? s.osReduce;
}

/** Bloom, vignette and grain run only at full motion and full performance. */
export function effectsOn(s: UiState): boolean {
  return !reduceMotion(s) && !s.perfMode && s.perfLevel === 0;
}

/** Core beams count as particles (§17.11): off in reduce motion and Performance mode. */
export function beamsOn(s: UiState): boolean {
  return !reduceMotion(s) && !s.perfMode;
}

export const PACKET_BUDGET = 300;

export function packetBudget(s: UiState): number {
  if (reduceMotion(s)) return 0; // §17.11: no particles in reduce motion
  return s.perfLevel >= 2 || s.perfMode ? PACKET_BUDGET / 2 : PACKET_BUDGET;
}
