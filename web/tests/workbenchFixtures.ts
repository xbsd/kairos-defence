// A small matcher trace (D-187) for the workbench tests: 8 candidates in prefilter order, paths
// for the first 4 (`trace_paths`) and for order 6, a final top-10 track beyond them. Shape
// similarities are chosen so the ranking re-sorts as candidates land, with one tie.
import type { MatcherTraceMsg } from "../src/api/messages";

export const SIMS = [0.42, 0.61, 0.55, 0.61, 0.3, 0.2, 0.88, 0.1];
const N = 30;

function detail(order: number) {
  return {
    order,
    track_id: `T${order}`,
    path: [
      [0, 0],
      [10, 9 + order],
      [N - 1, 40 + order],
    ],
    path_len: 52 + order,
    curve: [400, 380 - order, 360, 330, 300],
    cost: Array.from({ length: 12 }, (_, i) =>
      Array.from({ length: 12 }, (_, j) => (i === 0 && j === 11 ? null : i + j)),
    ),
  };
}

export function makeTrace(t_s = 90, incident = "LIVE-BRAVO-TEST"): MatcherTraceMsg {
  const n = SIMS.length;
  const ids = SIMS.map((_, k) => `T${k}`);
  const fused = [6, 1, 3, 2, 0]; // the fused top 5 by score (fusion, not shape alone)
  return {
    type: "matcher_trace",
    t_s,
    incident_id: incident,
    trace: {
      t_s,
      version: 1,
      trace_paths: 4,
      channel: "dist_target_m",
      query: {
        track_id: `${incident}-T1`,
        incident_id: incident,
        at_s: t_s,
        window_s: 30,
        rows_used: N,
        n: N,
        curve: [410, 385, 362, 331, 298],
      },
      prefilter: {
        ms: 4.2,
        k_windows: 2000,
        candidates: n,
        track_id: ids,
        incident_id: ids.map((x) => `INC-${x}`),
        start_ts_ms: ids.map((_, k) => Date.UTC(2026, 3, 10 + k, 22)),
        distance: ids.map((_, k) => 0.1 * (k + 1)),
        window_s: ids.map(() => 30),
        offset_s: ids.map((_, k) => k * 5),
      },
      dtw: {
        ms: 23.4,
        band_fraction: 0.15,
        normalize: "per_channel_scale",
        n: N,
        distance: SIMS.map((s) => Math.round(-Math.log(s) * 0.5 * Math.sqrt(N) * 1e5) / 1e5),
        d_norm: SIMS.map((s) => -Math.log(s) * 0.5),
        band: SIMS.map(() => 6),
        m: SIMS.map((_, k) => 40 + k + 1),
        ms_each: SIMS.map((_, k) => 0.5 + k / 10),
        shape_sim: SIMS,
        detail: [0, 1, 2, 3, 6].map(detail),
      },
      fusion: {
        ms: 1.1,
        features: ["shape_sim", "rf_same_family"],
        tau: 0.5,
        coefficients: [3.1, 1.2],
        intercept: -2.0,
        values: SIMS.map((s) => [s, 1]),
        score: SIMS.map((s) => Math.round(s * 0.9 * 1e6) / 1e6),
      },
      ranking: fused.map((k, r) => ({
        rank: r + 1,
        track_id: `T${k}`,
        incident_id: `INC-T${k}`,
        installation_id: "BRAVO",
        score: SIMS[k] ?? null,
        shape_sim: SIMS[k] ?? null,
        reasons: [`same RF family (${k})`],
      })),
      explain_ms: 2.0,
      total_ms: 31.5,
      trace_ms: 12.3,
    },
  };
}
