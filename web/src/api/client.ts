// Typed REST client (SPEC §16.4). Same origin: Vite proxies /api in dev, FastAPI serves both in
// the demo. Errors carry the server's message (FastAPI's `detail`).
import type {
  CaseDecision,
  CaseSummary,
  DecisionResponse,
  DtwMsg,
  EvidenceLine,
  EvidencePackage,
  EvidenceVerifyResponse,
  ExplainResponse,
  Health,
  IncidentSummary,
  Installation,
  LedgerBlock,
  LedgerRecord,
  LedgerVerify,
  LinkResponse,
  MatchResponse,
  Scene,
} from "./messages";
import type {
  CaseDiff,
  CaseGraph,
  CaseSnapshot,
  EvalReport,
  HistoryPath,
  ShiftDeltaDoc,
} from "./pages";

/** The analyst handle the Command Center approves as (D-112), as `memory demo` does. */
export const ANALYST = "demo";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Fetch = typeof fetch;
let fetchImpl: Fetch = (...args) => fetch(...args);

/** Tests replace the transport. */
export function setFetch(f: Fetch): void {
  fetchImpl = f;
}

async function detail(r: Response): Promise<string> {
  try {
    const body: unknown = await r.json();
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      return typeof d === "string" ? d : JSON.stringify(d);
    }
  } catch {
    // not JSON
  }
  return `${r.status} ${r.statusText}`;
}

async function getJson<T>(path: string): Promise<T> {
  const r = await fetchImpl(path, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new ApiError(r.status, await detail(r));
  return (await r.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetchImpl(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new ApiError(r.status, await detail(r));
  return (await r.json()) as T;
}

const enc = encodeURIComponent;

/** `?a=1&b=x` from the defined entries only. */
function qs(params: Record<string, string | number | null | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${enc(k)}=${enc(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  health: () => getJson<Health>("/api/health"),
  installations: () => getJson<Installation[]>("/api/installations"),
  /** A past flight's 1 Hz path in its target-relative frame (ghost trails, §17.3). */
  history: (trackId: string) => getJson<HistoryPath>(`/api/history/${enc(trackId)}?frame=target`),
  dtw: (incidentId: string, trackId: string, at: number, channel?: string) =>
    getJson<DtwMsg>(`/api/dtw/${enc(incidentId)}/${enc(trackId)}${qs({ at, channel })}`),
  match: (incidentId: string, at: number) =>
    getJson<MatchResponse>(`/api/match/${enc(incidentId)}${qs({ at })}`),
  explain: (incidentId: string, trackId: string, at: number) =>
    getJson<ExplainResponse>(`/api/explain/${enc(incidentId)}/${enc(trackId)}${qs({ at })}`),
  cases: (asOf?: string) => getJson<CaseSummary[]>(`/api/cases${qs({ as_of: asOf })}`),
  caseSnapshot: (caseId: string, asOf?: string) =>
    getJson<CaseSnapshot>(`/api/cases/${enc(caseId)}${qs({ as_of: asOf })}`),
  caseGraph: (caseId: string, asOf?: string) =>
    getJson<CaseGraph>(`/api/cases/${enc(caseId)}/graph${qs({ as_of: asOf })}`),
  caseDiff: (caseId: string, t1: string, t2?: string) =>
    getJson<CaseDiff>(`/api/cases/${enc(caseId)}/diff${qs({ t1, t2 })}`),
  /** A decision on a case (rule 8: only an explicit, confirmed click sends this). */
  recordDecision: (caseId: string, decision: CaseDecision, clock?: string) =>
    postJson<DecisionResponse>(`/api/cases/${enc(caseId)}/decisions`, {
      decision,
      analyst: ANALYST,
      ...(clock ? { clock } : {}),
    }),
  evidenceList: (caseId?: string) =>
    getJson<EvidencePackage[]>(`/api/evidence${qs({ case: caseId })}`),
  verifyEvidence: (dir: string) =>
    postJson<EvidenceVerifyResponse>("/api/evidence/verify", { dir }),
  delta: (since: string, until?: string) =>
    getJson<ShiftDeltaDoc>(`/api/delta${qs({ since, until })}`),
  evalLatest: () => getJson<EvalReport>("/api/eval/latest"),
  adminReset: () => postJson<{ reset: Record<string, number> }>("/api/admin/reset", {}),
  adminReseed: () => postJson<{ head_seq: number }>("/api/admin/reseed", {}),
  scene: (installationId: string) =>
    getJson<Scene>(`/api/installations/${encodeURIComponent(installationId)}/scene`),
  liveIncidents: () => getJson<IncidentSummary[]>("/api/incidents?status=live"),
  ledgerTail: (n = 12) => getJson<LedgerBlock[]>(`/api/ledger/tail?n=${n}`),
  ledgerRecord: (seq: number) => getJson<LedgerRecord>(`/api/ledger/${seq}`),
  ledgerVerify: () => getJson<LedgerVerify>("/api/ledger/verify"),
  /** Approve or reject a proposal (rule 8: only this explicit click commits a link). */
  decideLink: (
    caseId: string,
    proposalSeq: number,
    decision: "approve" | "reject",
    clock: string,
  ) =>
    postJson<LinkResponse>(`/api/cases/${encodeURIComponent(caseId)}/links`, {
      proposal_seq: proposalSeq,
      decision,
      analyst: ANALYST,
      clock,
    }),
  /** Export an evidence package; `onLine` gets each NDJSON line as the server hashes files. */
  exportEvidence: async (caseId: string, onLine: (l: EvidenceLine) => void): Promise<void> => {
    const r = await fetchImpl(`/api/cases/${encodeURIComponent(caseId)}/evidence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve: true, analyst: ANALYST }),
    });
    if (!r.ok) throw new ApiError(r.status, await detail(r));
    await readNdjson(r, onLine);
  },
};

/** Parse an NDJSON response line by line as it arrives. */
export async function readNdjson<T>(r: Response, onLine: (l: T) => void): Promise<void> {
  if (!r.body) {
    for (const line of (await r.text()).split("\n")) if (line.trim()) onLine(JSON.parse(line) as T);
    return;
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (value) buf += dec.decode(value, { stream: !done });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) onLine(JSON.parse(line) as T);
    }
    if (done) break;
  }
  if (buf.trim()) onLine(JSON.parse(buf) as T);
}
