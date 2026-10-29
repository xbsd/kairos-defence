// Typed stream messages for tests (shapes from the generated OpenAPI types).
import type {
  ClockMsg,
  FeaturesMsg,
  HelloMsg,
  IngestMsg,
  LedgerMsg,
  MatchItem,
  MatchMsg,
  PointMsg,
  RfMsg,
} from "../src/api/messages";

export const HELLO: HelloMsg = {
  type: "hello",
  incident_id: "DEMO-BRAVO-0828",
  installation_id: "BRAVO",
  region_id: "COASTAL",
  start_ts: "2026-08-29T02:40:06.000Z",
  duration_s: 515,
  speed: 1,
  playing: false,
  tracks: ["DEMO-BRAVO-0828-T1"],
  is_swarm: false,
  matching: true,
  min_track_s: 45,
  rerun_every_s: 5,
  utc_offset_hours: -5,
};

export function clock(t_s: number, playing = true, speed = 1, seeked = false): ClockMsg {
  return { type: "clock", t_s, ts: "2026-08-29T02:41:08.000Z", speed, playing, seeked };
}

export function point(t_s: number, x = 21680, y = -4880, alt = 90): PointMsg {
  return {
    type: "point",
    incident_id: "DEMO-BRAVO-0828",
    track_id: "DEMO-BRAVO-0828-T1",
    sensor_id: "BRAVO-RADAR-1",
    t_s,
    x_m: x,
    y_m: y,
    alt_m: alt,
    quality: 0.88,
  };
}

export function rf(t_s: number, bearing = 335): RfMsg {
  return {
    type: "rf",
    sensor_id: "BRAVO-RF-1",
    t_s,
    band: "2.4GHz",
    bearing_deg: bearing,
    protocol_family: "FAM-07",
    snr_db: 18.2,
  };
}

export function features(t_s: number, phase: FeaturesMsg["phase"] = "approach"): FeaturesMsg {
  return {
    type: "features",
    t_s,
    track_id: "DEMO-BRAVO-0828-T1",
    target_asset_id: "BRAVO-fuel_farm",
    speed_ms: 15,
    alt_m: 90,
    turn_rate_dps: -2,
    dist_target_m: 700 - t_s,
    vspeed_ms: 0.1,
    heading_deg: 140,
    phase,
  };
}

export function ingest(
  rows: number,
  total: number,
  table: IngestMsg["table"] = "live_points",
): IngestMsg {
  return {
    type: "ingest",
    table,
    rows,
    total_rows: total,
    write_ms: 0.42,
    statement: `INSERT INTO ${table} … ${rows} rows`,
  };
}

export function matchItem(
  incident: string,
  rank: number,
  seq: number | null = 4682 + rank,
): MatchItem {
  const base = incident.split("-")[1] ?? "DELTA";
  return {
    query_incident_id: "DEMO-BRAVO-0828",
    track_id: `${incident}-T1`,
    incident_id: incident,
    installation_id: base,
    start_ts: "2026-04-20T02:35:00.000Z",
    score: 0.95 - rank * 0.01,
    shape_sim: 0.8,
    features: { shape_sim: 0.8, rf_match: 1 },
    reasons: ["same RF family (FAM-07)", "similar approach bearing"],
    warp_ratio: 1.22,
    window_offset_s: 12,
    model_version: "fusion-v1",
    rank,
    local_start: "2026-04-19T21:35",
    proposal_seq: seq,
    decision: null,
    memory_status: rank === 1 ? "Closed as hobbyist on Apr 20" : "Open, unattributed",
  };
}

export function match(
  t_s = 90,
  ids = ["P1-DELTA-260419", "P1-ALPHA-260303", "P1-ALPHA-260502"],
): MatchMsg {
  return {
    type: "match",
    t_s,
    model_version: "fusion-v1",
    elapsed_ms: 286,
    cached: true,
    case_id: "CASE-P1-DELTA-260419",
    query_track: "DEMO-BRAVO-0828-T1",
    target_asset_id: "BRAVO-fuel_farm",
    matches: ids.map((id, i) => matchItem(id, i + 1)),
  };
}

export function ledger(seq: number, event_type = "match_proposed"): LedgerMsg {
  return {
    type: "ledger",
    seq,
    event_type,
    actor: "matcher@fusion-v1",
    recorded_at: "2026-08-29T02:41:36.000Z",
    hash: `${seq}`.padStart(8, "a") + "f".repeat(56),
    prev_hash: `${seq - 1}`.padStart(8, "a") + "f".repeat(56),
    case_id: "CASE-P1-DELTA-260419",
    subject_id: "P1-DELTA-260419",
  };
}
