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
export type MatcherTraceMsg = S["MatcherTraceMsg"];
export type MatcherTrace = S["MatcherTrace"];
export type TraceDetail = S["TraceDetail"];

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
  | ErrorMsg
  | MatcherTraceMsg;

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
  "matcher_trace",
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

// Phase 8 pages (D-135, D-136).
export type Installation = S["Installation"];
export type MatchResponse = S["MatchResponse"];
export type ExplainResponse = S["ExplainResponse"];
export type ContributionRow = S["ContributionRow"];
export type ExplainFlight = S["ExplainFlight"];
export type CaseSummary = S["CaseSummary"];
export type DecisionRequest = S["DecisionRequest"];
export type DecisionResponse = S["DecisionResponse"];
export type CaseDecision = DecisionRequest["decision"];
export type EvidencePackage = S["EvidencePackage"];
export type EvidenceVerifyResponse = S["EvidenceVerifyResponse"];
export type EvidenceCheck = S["EvidenceCheck"];

// Phase 9: the Swarm view (§14, §17.9, D-153).
export type SwarmResponse = S["SwarmResponse"];
export type SwarmFlight = S["SwarmFlightOut"];
export type SwarmMatch = S["SwarmMatchOut"];
export type SwarmCurves = S["SwarmCurves"];
export type SwarmIncident = S["SwarmIncident"];

// Phase 11: live mode (D-169, D-184). The live stream sends the §16.3 types plus three.
export type IncidentOpenedMsg = S["IncidentOpenedMsg"];
export type IncidentClosedMsg = S["IncidentClosedMsg"];
export type SwarmMatchMsg = S["SwarmMatchMsg"];
export type SwarmMatchItem = S["SwarmMatchItem"];
export type LiveStreamMessage =
  StreamMessage | IncidentOpenedMsg | IncidentClosedMsg | SwarmMatchMsg;
export const LIVE_TYPES: readonly LiveStreamMessage["type"][] = [
  ...STREAM_TYPES,
  "incident_opened",
  "incident_closed",
  "swarm_match",
];
export type LiveStatus = S["LiveStatus"];
export type LiveIncidentRow = S["LiveIncidentRow"];
export type ScenarioInfo = S["ScenarioInfo"];
export type SimLaunchRequest = S["SimLaunchRequest"];
export type SimLaunchResponse = S["SimLaunchResponse"];
export type LiveResetResponse = S["LiveResetResponse"];
export type RevealResponse = S["RevealResponse"];
export type RevealRerun = S["RevealRerun"];

// Phase 9: the optional chat (§18.3, D-162).
export type ChatStatus = S["ChatStatus"];
export type ChatMessage = S["ChatMessage"];
export type ChatResponse = S["ChatResponse"];
export type ChatToolCall = S["ChatToolCall"];
