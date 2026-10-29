// The replay's high-frequency state (SPEC §17.11): written per stream message, outside React.
// Buffers are mutated in place and `version` bumps on every change; the theater reads
// getState() inside useFrame, DOM panels re-render through useThrottledStore (≤ 10 Hz).
import { createStore } from "zustand/vanilla";

import type {
  ClockMsg,
  FeaturesMsg,
  HelloMsg,
  IngestMsg,
  PointMsg,
  RfMsg,
  RidMsg,
} from "../api/messages";
import type { StreamStatus } from "../api/stream";

export const ROWS_KEEP = 200;
export const FEATURES_WINDOW_S = 120;
export const RATE_WINDOW_S = 5;
export const TRACK_KEEP = 900; // points per track (15 min at 1 Hz)
export const DETECTIONS_KEEP = 300; // for data packets (§17.3: at most 300 in flight)
export const WRITE_HISTORY = 40;

export interface TrackPoint {
  t_s: number;
  x: number;
  y: number;
  alt: number;
}

export type RowKind = "radar" | "rf" | "rid";

export interface StreamRow {
  key: string;
  t_s: number;
  kind: RowKind;
  sensor: string;
  x: number | null;
  y: number | null;
  alt: number | null;
  /** Radar quality (0–1) or RF SNR (dB). */
  value: number | null;
  valueLabel: "quality" | "SNR" | "";
}

/** One real detection, for a data packet (drone → sensor → core). */
export interface Detection {
  seq: number;
  t_s: number;
  kind: RowKind;
  sensor: string;
  track: string | null;
  x: number | null;
  y: number | null;
  alt: number | null;
  bearing: number | null;
  wall: number;
}

export interface TableWrite {
  rows: number;
  total_rows: number;
  write_ms: number;
  statement: string;
}

export interface ReplayState {
  status: StreamStatus | "idle";
  hello: HelloMsg | null;
  clock: { t_s: number; ts: string; speed: number; playing: boolean } | null;
  /** performance.now() when the last clock arrived (the theater interpolates from it). */
  clockWall: number;
  tracks: Record<string, TrackPoint[]>;
  rf: RfMsg[];
  rid: RidMsg[];
  features: FeaturesMsg[];
  rows: StreamRow[];
  detections: Detection[];
  detSeq: number;
  /** Distinct detections received (a seek's catch-up is not counted twice). */
  total: number;
  seen: Set<string>;
  tables: Record<string, TableWrite>;
  lastIngest: IngestMsg | null;
  writeHistory: number[];
  ingestCount: number;
  ingestWall: number;
  error: string | null;
  version: number;
}

export interface ReplayActions {
  setStatus: (s: StreamStatus | "idle") => void;
  apply: (
    m: HelloMsg | ClockMsg | PointMsg | RfMsg | RidMsg | FeaturesMsg | IngestMsg,
    now?: number,
  ) => void;
  setError: (message: string | null) => void;
  clearBuffers: () => void;
  reset: () => void;
}

const empty = (): Omit<ReplayState, "status" | "hello" | "version"> => ({
  clock: null,
  clockWall: 0,
  tracks: {},
  rf: [],
  rid: [],
  features: [],
  rows: [],
  detections: [],
  detSeq: 0,
  total: 0,
  seen: new Set(),
  tables: {},
  lastIngest: null,
  writeHistory: [],
  ingestCount: 0,
  ingestWall: 0,
  error: null,
});

function pushCapped<T>(arr: T[], item: T, keep: number): void {
  arr.push(item);
  if (arr.length > keep) arr.splice(0, arr.length - keep);
}

export const replayStore = createStore<ReplayState & ReplayActions>()((set, get) => {
  const bump = (patch: Partial<ReplayState> = {}) => set({ ...patch, version: get().version + 1 });

  function row(r: StreamRow, d: Omit<Detection, "seq" | "wall">, now: number): void {
    const s = get();
    s.rows.unshift(r);
    if (s.rows.length > ROWS_KEEP) s.rows.length = ROWS_KEEP;
    const seq = s.detSeq + 1;
    pushCapped(s.detections, { ...d, seq, wall: now }, DETECTIONS_KEEP);
    let total = s.total;
    if (!s.seen.has(r.key)) {
      s.seen.add(r.key);
      total += 1;
    }
    bump({ detSeq: seq, total });
  }

  return {
    status: "idle",
    hello: null,
    version: 0,
    ...empty(),
    setStatus: (status) => bump({ status }),
    setError: (error) => bump({ error }),
    clearBuffers: () => {
      const s = get();
      bump({
        tracks: {},
        rf: [],
        rid: [],
        features: [],
        rows: [],
        detections: [],
        // the total, the recorder and the core keep counting real writes across seeks
        total: s.total,
        seen: s.seen,
      });
    },
    reset: () => bump({ status: "idle", hello: null, ...empty() }),
    apply: (m, now = performance.now()) => {
      const s = get();
      switch (m.type) {
        case "hello":
          bump({ hello: m, error: null });
          return;
        case "clock":
          bump({
            clock: { t_s: m.t_s, ts: m.ts, speed: m.speed, playing: m.playing },
            clockWall: now,
          });
          return;
        case "point": {
          const pts = (s.tracks[m.track_id] ??= []);
          if (m.x_m !== null && m.y_m !== null) {
            pushCapped(pts, { t_s: m.t_s, x: m.x_m, y: m.y_m, alt: m.alt_m ?? 0 }, TRACK_KEEP);
          }
          const key = `p:${m.track_id}:${m.t_s}`;
          row(
            {
              key,
              t_s: m.t_s,
              kind: "radar",
              sensor: m.sensor_id,
              x: m.x_m,
              y: m.y_m,
              alt: m.alt_m,
              value: m.quality,
              valueLabel: "quality",
            },
            {
              t_s: m.t_s,
              kind: "radar",
              sensor: m.sensor_id,
              track: m.track_id,
              x: m.x_m,
              y: m.y_m,
              alt: m.alt_m,
              bearing: null,
            },
            now,
          );
          return;
        }
        case "rf": {
          pushCapped(s.rf, m, 60);
          row(
            {
              key: `r:${m.sensor_id}:${m.t_s}:${m.bearing_deg}`,
              t_s: m.t_s,
              kind: "rf",
              sensor: m.sensor_id,
              x: null,
              y: null,
              alt: null,
              value: m.snr_db,
              valueLabel: "SNR",
            },
            {
              t_s: m.t_s,
              kind: "rf",
              sensor: m.sensor_id,
              track: null,
              x: null,
              y: null,
              alt: null,
              bearing: m.bearing_deg,
            },
            now,
          );
          return;
        }
        case "rid": {
          pushCapped(s.rid, m, 60);
          row(
            {
              key: `i:${m.serial}:${m.t_s}`,
              t_s: m.t_s,
              kind: "rid",
              sensor: m.serial,
              x: m.drone_x_m,
              y: m.drone_y_m,
              alt: null,
              value: null,
              valueLabel: "",
            },
            {
              t_s: m.t_s,
              kind: "rid",
              sensor: m.serial,
              track: null,
              x: m.drone_x_m,
              y: m.drone_y_m,
              alt: null,
              bearing: null,
            },
            now,
          );
          return;
        }
        case "features": {
          const f = s.features;
          if (f.length && (f[f.length - 1]?.t_s ?? -1) >= m.t_s) {
            const i = f.findIndex((x) => x.t_s >= m.t_s);
            if (i >= 0 && f[i]?.t_s === m.t_s) f[i] = m;
            else f.splice(i < 0 ? f.length : i, 0, m);
          } else f.push(m);
          const cut = m.t_s - FEATURES_WINDOW_S;
          while (f.length && (f[0]?.t_s ?? 0) <= cut) f.shift();
          bump();
          return;
        }
        case "ingest": {
          pushCapped(s.writeHistory, m.write_ms, WRITE_HISTORY);
          s.tables[m.table] = {
            rows: m.rows,
            total_rows: m.total_rows,
            write_ms: m.write_ms,
            statement: m.statement,
          };
          bump({ lastIngest: m, ingestCount: s.ingestCount + 1, ingestWall: now });
          return;
        }
      }
    },
  };
});

/** Detections per second over the last 5 replay seconds before the clock. */
export function detectionRate(s: ReplayState): number {
  const t = s.clock?.t_s;
  if (t === undefined) return 0;
  let n = 0;
  for (const r of s.rows) {
    if (r.t_s <= t - RATE_WINDOW_S) break; // rows are newest first
    if (r.t_s <= t) n += 1;
  }
  return n / RATE_WINDOW_S;
}

/** The replay clock now, interpolated from the last `clock` while playing (seconds). */
export function clockNow(s: ReplayState, now: number = performance.now()): number {
  const c = s.clock;
  if (!c) return 0;
  if (!c.playing) return c.t_s;
  const dt = Math.min(Math.max(0, (now - s.clockWall) / 1000), 0.25); // never run ahead > 1 tick
  const end = s.hello?.duration_s ?? Number.POSITIVE_INFINITY;
  return Math.min(c.t_s + c.speed * dt, end);
}

/** Total rows written to the live tables, from the last ingest per table. */
export function recordedTotal(s: ReplayState): number {
  return Object.values(s.tables).reduce((a, t) => a + t.total_rows, 0);
}
