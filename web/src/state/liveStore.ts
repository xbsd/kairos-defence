// Live mode's page state (D-184): the watched installation, the scenario catalog, the live
// incidents since the last reset (from GET /api/live/status, kept current by the stream's
// incident_opened and incident_closed), the latest swarm result and the reveals the user asked
// for. Every value comes from the server (rule 10).
import { createStore } from "zustand/vanilla";

import type {
  IncidentClosedMsg,
  IncidentOpenedMsg,
  LiveIncidentRow,
  LiveStatus,
  RevealResponse,
  ScenarioInfo,
  SwarmMatchMsg,
} from "../api/messages";

export type RevealState =
  | { state: "loading" }
  | { state: "ready"; doc: RevealResponse }
  | { state: "error"; message: string };

export interface LiveState {
  installation: string;
  scenarios: ScenarioInfo[];
  status: LiveStatus | null;
  statusError: string | null;
  incidents: Record<string, LiveIncidentRow>;
  swarm: SwarmMatchMsg | null;
  reveals: Record<string, RevealState>;
  revealOpen: string | null;
  launching: boolean;
  launchError: string | null;
  version: number;
}

export interface LiveActions {
  setInstallation: (id: string) => void;
  setScenarios: (s: ScenarioInfo[]) => void;
  setStatus: (s: LiveStatus | null, error?: string | null) => void;
  opened: (m: IncidentOpenedMsg) => void;
  closed: (m: IncidentClosedMsg) => void;
  setSwarm: (m: SwarmMatchMsg | null) => void;
  setReveal: (id: string, r: RevealState) => void;
  openReveal: (id: string | null) => void;
  setLaunch: (launching: boolean, error?: string | null) => void;
  clear: () => void;
}

export const DEFAULT_INSTALLATION = "BRAVO";

export const liveStore = createStore<LiveState & LiveActions>()((set, get) => {
  const bump = (patch: Partial<LiveState>) => set({ ...patch, version: get().version + 1 });
  return {
    installation: DEFAULT_INSTALLATION,
    scenarios: [],
    status: null,
    statusError: null,
    incidents: {},
    swarm: null,
    reveals: {},
    revealOpen: null,
    launching: false,
    launchError: null,
    version: 0,
    setInstallation: (installation) => bump({ installation, swarm: null }),
    setScenarios: (scenarios) => bump({ scenarios }),
    setStatus: (status, error = null) => {
      if (!status) {
        bump({ statusError: error });
        return;
      }
      // the server's list is the truth (it survives a reload); keep nothing it no longer has
      const incidents: Record<string, LiveIncidentRow> = {};
      for (const r of status.incidents) incidents[r.incident_id] = r;
      bump({ status, statusError: null, incidents });
    },
    opened: (m) => {
      const prev = get().incidents[m.incident_id];
      const row: LiveIncidentRow = prev ?? {
        incident_id: m.incident_id,
        installation_id: m.installation_id,
        start_ts: m.start_ts,
        end_ts: m.start_ts,
        n_tracks: 1,
        is_swarm: false,
        state: "open",
        reruns: 0,
      };
      bump({ incidents: { ...get().incidents, [m.incident_id]: row }, swarm: null });
    },
    closed: (m) => {
      const prev = get().incidents[m.incident_id];
      const row: LiveIncidentRow = {
        incident_id: m.incident_id,
        installation_id: m.installation_id,
        start_ts: prev?.start_ts ?? m.end_ts,
        end_ts: m.end_ts,
        n_tracks: m.n_tracks,
        is_swarm: m.is_swarm,
        state: "closed",
        reruns: m.reruns,
      };
      bump({ incidents: { ...get().incidents, [m.incident_id]: row } });
    },
    setSwarm: (swarm) => bump({ swarm }),
    setReveal: (id, r) => bump({ reveals: { ...get().reveals, [id]: r } }),
    openReveal: (revealOpen) => bump({ revealOpen }),
    setLaunch: (launching, launchError = null) => bump({ launching, launchError }),
    clear: () => bump({ incidents: {}, swarm: null, reveals: {}, revealOpen: null }),
  };
});

/** Incidents newest first (the "Live incidents this session" list). */
export function incidentList(s: LiveState): LiveIncidentRow[] {
  return Object.values(s.incidents).sort((a, b) =>
    a.start_ts === b.start_ts
      ? b.incident_id.localeCompare(a.incident_id)
      : b.start_ts.localeCompare(a.start_ts),
  );
}

/** The watched installation's feed, if it has one. */
export function feedOf(s: LiveState): LiveStatus["feeds"][number] | null {
  return s.status?.feeds.find((f) => f.installation_id === s.installation) ?? null;
}
