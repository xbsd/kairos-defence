// Past flights fetched for the afterglow ghosts (§17.3): one target-relative 1 Hz path per
// matched track, loaded once and kept (history does not change while the app runs).
import { createStore } from "zustand/vanilla";

import { api } from "../api/client";
import type { HistoryPath } from "../api/pages";

export type GhostLoad =
  | { status: "loading" }
  | { status: "ready"; path: HistoryPath }
  | { status: "error"; message: string };

export interface GhostState {
  paths: Record<string, GhostLoad>;
  load: (trackId: string) => void;
}

type Fetcher = (trackId: string) => Promise<HistoryPath>;
let fetcher: Fetcher = (t) => api.history(t);

/** Tests replace the transport. */
export function setGhostFetcher(f: Fetcher): void {
  fetcher = f;
}

export const ghostStore = createStore<GhostState>()((set, get) => ({
  paths: {},
  load: (trackId) => {
    if (get().paths[trackId]) return;
    set({ paths: { ...get().paths, [trackId]: { status: "loading" } } });
    fetcher(trackId)
      .then((path) => set({ paths: { ...get().paths, [trackId]: { status: "ready", path } } }))
      .catch((e: unknown) =>
        set({
          paths: {
            ...get().paths,
            [trackId]: { status: "error", message: e instanceof Error ? e.message : String(e) },
          },
        }),
      );
  },
}));

export function readyPath(s: GhostState, trackId: string): HistoryPath | null {
  const g = s.paths[trackId];
  return g?.status === "ready" ? g.path : null;
}
