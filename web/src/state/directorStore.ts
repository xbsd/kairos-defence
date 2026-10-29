// Director mode state (SPEC §17.10, D-123, D-142): outside React so it survives page changes.
// The current beat is derived: a page beat once the presenter moved there, else the clock's.
import { createStore } from "zustand/vanilla";

import type { DirectorFacts } from "../director/captions";

export interface BeatLog {
  beat: string;
  n: number;
  /** Replay seconds when the beat began (null on a page beat). */
  t_s: number | null;
  /** Local wall time of the replay at that moment ("21:41:36"), when known. */
  local: string | null;
  /** performance.now() (ms) when it began. */
  wall: number;
}

export interface DirectorState {
  active: boolean;
  /** Index of the page beat being shown, or null while on Live watch. */
  page: number | null;
  /** The beat last activated (index into BEATS). */
  beat: number;
  log: BeatLog[];
  facts: DirectorFacts;
  incidentId: string | null;
  caseId: string | null;
  /** A seek (and play) to apply once Live watch's stream is open again. */
  pendingSeek: number | null;
  pendingPlay: boolean;
}

export interface DirectorActions {
  start: (incidentId: string | null) => void;
  stop: () => void;
  activate: (beat: number, entry: Omit<BeatLog, "n">) => void;
  setPage: (page: number | null) => void;
  setFacts: (f: DirectorFacts) => void;
  setCase: (caseId: string | null) => void;
  setIncident: (id: string | null) => void;
  requestSeek: (t: number | null, play?: boolean) => void;
  reset: () => void;
}

const initial = {
  active: false,
  page: null,
  beat: 0,
  log: [],
  facts: {},
  incidentId: null,
  caseId: null,
  pendingSeek: null,
  pendingPlay: false,
} satisfies DirectorState;

export const directorStore = createStore<DirectorState & DirectorActions>()((set, get) => ({
  ...initial,
  start: (incidentId) =>
    set({ ...initial, active: true, beat: -1, incidentId, pendingSeek: 0, pendingPlay: true }),
  stop: () => set({ active: false, page: null, pendingSeek: null, pendingPlay: false }),
  activate: (beat, entry) => set({ beat, log: [...get().log, { ...entry, n: beat + 1 }] }),
  setPage: (page) => set({ page }),
  setFacts: (f) => set({ facts: { ...get().facts, ...f } }),
  setCase: (caseId) => set({ caseId }),
  setIncident: (incidentId) => set({ incidentId }),
  requestSeek: (pendingSeek, pendingPlay = false) => set({ pendingSeek, pendingPlay }),
  reset: () => set({ beat: -1, page: null, log: [] }),
}));
