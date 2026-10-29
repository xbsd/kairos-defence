// Shapes of the REST routes that return plain JSON documents (no response model): the ghost
// history, the case snapshot, graph and diff, the shift delta and the eval report (SPEC §16.4).
// The Python side is the source of truth: memory/graph.py, memory/diff.py, memory/delta.py,
// api/routes.py (history), eval/report.py. Times are ISO 8601 UTC with Z.

/** GET /api/history/{track}?frame=target: [t_s, x, y, alt] rows, target-relative meters. */
export interface HistoryPath {
  track_id: string;
  incident_id: string;
  installation_id: string;
  target_asset_id: string;
  start_ts: string;
  frame: "target" | "region";
  columns: string[];
  points: [number, number | null, number | null, number | null][];
}

export interface GraphNode {
  id: string;
  kind: "case" | "incident" | "report" | "assessment";
  seq: number | null;
  recorded_at: string | null;
  status?: string;
  base?: string | null;
  member?: boolean;
  contradiction?: boolean;
  source?: string;
  grade?: string;
  label?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: "member_of" | "proposed" | "report_of" | "assessed";
  seq: number;
  recorded_at: string;
  score?: number;
}

/** GET /api/cases/{id}/graph?as_of= */
export interface CaseGraph {
  case_id: string;
  as_of: string;
  exists: boolean;
  status: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DiffItem {
  group: string;
  seq: number;
  event_type: string;
  recorded_at: string;
  subject_id: string | null;
  case_id: string | null;
  summary: string;
  actor?: string;
  new_member?: boolean;
}

/** GET /api/cases/{id}/diff?t1=&t2= */
export interface CaseDiff {
  case_id: string;
  t1: string;
  t2: string;
  items: DiffItem[];
  groups: Record<string, DiffItem[]>;
}

/** One proposal in a case snapshot (memory/views.proposal_view). */
export interface PendingProposal {
  seq: number;
  incident_id: string;
  query_incident: string | null;
  rank: number | null;
  score: number | null;
  reasons: string[];
  /** The replay second the matcher proposed it at. */
  t_s: number | null;
  recorded_at: string;
}

/** GET /api/cases/{id}?as_of= (the fields the Case board reads). */
export interface CaseSnapshot {
  case_id: string;
  as_of: string;
  exists: boolean;
  status: string;
  founder: string | null;
  members: string[];
  pending: PendingProposal[];
  claims: { seq: number; subject_id: string; value: string; recorded_at: string }[];
  decisions: { seq: number; decision: string; recorded_at: string; actor: string }[];
  contradictions: { subject_id: string; values: string[] }[];
  head_seq: number | null;
}

/** GET /api/delta?since=&until= */
export interface ShiftDeltaDoc {
  since: string;
  until: string;
  installation_id: string | null;
  groups: Record<string, DiffItem[]>;
  count: number;
  head_seq: number | null;
}

export interface EvalTarget {
  key: string;
  op: ">=" | "<=";
  value: number;
  label: string;
  spec: string;
  phase: number;
  fmt: "ratio" | "pct" | "signed" | "m" | "ms";
  report_only: boolean;
  pending: string | null;
  text: string;
}

export interface DemoRow {
  key: string;
  expected: string;
  observed: string;
  status: string;
}

export interface EvalOutcome {
  actor_type: string;
  at_s: number;
  ran: boolean;
  forecast_error_m: number | null;
}

/** GET /api/eval/latest (the newest reports/eval_<date>.json). */
export interface EvalReport {
  file: string;
  method: string;
  model_version?: string;
  created_at: string;
  metrics: Record<string, number | null>;
  recall_by_t: Record<
    string,
    {
      recall_at_5_probers: number | null;
      top3_probers: number | null;
      recall_at_5_copycats: number | null;
      ran: boolean;
    }
  >;
  demo: DemoRow[];
  targets?: EvalTarget[];
  outcomes?: EvalOutcome[];
}
