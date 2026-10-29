// Names for the generated OpenAPI types (SPEC §16.5). Never edit types.gen.ts by hand: change
// api/schemas.py, then `kairos-defense api --dump-openapi web/openapi.json && npm run gen:types`.
import type { components } from "./types.gen";

type S = components["schemas"];

export type HelloMsg = S["HelloMsg"];
export type ClockMsg = S["ClockMsg"];
export type PointMsg = S["PointMsg"];
export type RfMsg = S["RfMsg"];
export type RidMsg = S["RidMsg"];
export type FeaturesMsg = S["FeaturesMsg"];
export type IngestMsg = S["IngestMsg"];
export type MatchMsg = S["MatchMsg"];
export type MatchItem = S["MatchItem"];
export type DtwMsg = S["DtwMsg"];
export type ForecastMsg = S["ForecastMsg"];
export type RecallMsg = S["RecallMsg"];
export type LedgerMsg = S["LedgerMsg"];
export type ErrorMsg = S["ErrorMsg"];

export type StreamMessage =
  | HelloMsg
  | ClockMsg
  | PointMsg
  | RfMsg
  | RidMsg
  | FeaturesMsg
  | IngestMsg
  | MatchMsg
  | DtwMsg
  | ForecastMsg
  | RecallMsg
  | LedgerMsg
  | ErrorMsg;

export type StreamType = StreamMessage["type"];

export const STREAM_TYPES: readonly StreamType[] = [
  "hello",
  "clock",
  "point",
  "rf",
  "rid",
  "features",
  "ingest",
  "match",
  "dtw",
  "forecast",
  "recall",
  "ledger",
  "error",
];

export type ClientMessage =
  S["PlayCmd"] | S["PauseCmd"] | S["SeekCmd"] | S["SpeedCmd"] | S["DtwCmd"];

export type Scene = S["Scene"];
export type IncidentSummary = S["IncidentSummary"];
export type LedgerBlock = S["LedgerBlock"];
export type LedgerRecord = S["LedgerRecord"];
export type LedgerVerify = S["LedgerVerify"];
export type LinkResponse = S["LinkResponse"];
export type Health = S["Health"];
export type EvidenceFileLine = S["EvidenceFileLine"];
export type EvidenceDoneLine = S["EvidenceDoneLine"];
export type EvidenceErrorLine = S["EvidenceErrorLine"];
export type EvidenceLine = EvidenceFileLine | EvidenceDoneLine | EvidenceErrorLine;

/** A ledger message as a chain block (the stream adds only `type`). */
export function toBlock(m: LedgerMsg): LedgerBlock {
  return {
    seq: m.seq,
    event_type: m.event_type,
    actor: m.actor,
    recorded_at: m.recorded_at,
    hash: m.hash,
    prev_hash: m.prev_hash,
    case_id: m.case_id,
    subject_id: m.subject_id,
  };
}
