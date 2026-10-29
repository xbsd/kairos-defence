import { useCallback, useEffect, useMemo, useState } from "react";

import { ANALYST, api } from "../api/client";
import type { CaseDecision, CaseSummary } from "../api/messages";
import type { CaseDiff, CaseGraph as Graph, CaseSnapshot } from "../api/pages";
import { Link } from "../app/Link";
import { CaseControls } from "../case/CaseControls";
import { CaseGraph } from "../case/CaseGraph";
import { DiffList } from "../case/DiffList";
import { GraphText } from "../case/GraphText";
import { Scrubber } from "../case/Scrubber";
import { localStamp } from "../case/time";
import { localDay } from "../director/captions";
import { baseName } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { directorStore } from "../state/directorStore";
import { sceneStore } from "../state/sceneStore";
import { reduceMotion, uiStore } from "../state/uiStore";

/** Earlier than any event: the diff "since the beginning" gives every tick (§17.9). */
const EPOCH = "2025-01-01T00:00:00Z";

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

/** `/cases`: every case as known at the ledger head (D-136). */
export function CaseList() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .cases()
      .then(setCases)
      .catch((e: unknown) => setError(errText(e)));
  }, []);
  return (
    <main aria-labelledby="cases-title" className="min-h-0 flex-1 overflow-y-auto p-4">
      <div className="mx-auto max-w-5xl">
        <h1 id="cases-title" className="text-24 font-bold text-ink-hi">
          Case board
        </h1>
        <p className="mt-1 text-15 text-ink-mid">
          Every case in the memory, as known now. Open one to scrub through what was known when.
        </p>
        {error ? (
          <p role="alert" className="mt-3 text-15 text-alert">
            {error}
          </p>
        ) : null}
        <table className="mt-4 w-full text-left text-13" data-testid="case-list">
          <thead className="text-ink-mid">
            <tr>
              <th scope="col" className="py-2">
                Case
              </th>
              <th scope="col">Base</th>
              <th scope="col">Status</th>
              <th scope="col">Members</th>
              <th scope="col">Pending links</th>
              <th scope="col">Claims</th>
              <th scope="col">Contradictions</th>
            </tr>
          </thead>
          <tbody>
            {(cases ?? []).map((c) => (
              <tr key={c.case_id} className="border-t border-hairline text-ink-hi">
                <td className="py-2">
                  <Link
                    to={`/cases/${c.case_id}`}
                    className="text-flash underline-offset-2 hover:underline"
                  >
                    {c.case_id}
                  </Link>
                </td>
                <td>{c.base ? baseName(c.base) : "–"}</td>
                <td>{c.status}</td>
                <td className="font-mono">{c.members.length}</td>
                <td className="font-mono">{c.pending}</td>
                <td>{c.claims.join(", ") || "–"}</td>
                <td className={`font-mono ${c.contradictions ? "text-alert" : ""}`}>
                  {c.contradictions}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {cases && !cases.length ? <p className="mt-3 text-15 text-ink-mid">No case yet.</p> : null}
      </div>
    </main>
  );
}

interface Frame {
  head: CaseSnapshot;
  headGraph: Graph;
  then: number;
  now: number;
  first: number;
  ticks: number[];
  base: string | null;
}

/**
 * The Case board (SPEC §17.9, D-138): an "as of" scrubber with event ticks and the Known then /
 * Known now jumps; the graph as known at the scrub time (refetched, debounced 150 ms, so every
 * state is the server's own as-of); the diff since Known then; approvals and decisions.
 */
export function CaseBoard({ caseId, focus }: { caseId: string; focus: string | null }) {
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const installations = useThrottledStore(sceneStore, (s) => s.installations, 2);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [scrub, setScrub] = useState<number | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [diff, setDiff] = useState<CaseDiff | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  // the frame: the head snapshot, Known then (the case's opening), the event ticks
  useEffect(() => {
    let alive = true;
    Promise.all([api.caseSnapshot(caseId), api.caseGraph(caseId), api.caseDiff(caseId, EPOCH)])
      .then(([head, g, all]) => {
        if (!alive) return;
        const caseNode = g.nodes.find((n) => n.kind === "case");
        const then = Date.parse(caseNode?.recorded_at ?? head.as_of);
        const now = Date.parse(head.as_of);
        const ticks = all.items.map((i) => Date.parse(i.recorded_at)).filter(Number.isFinite);
        const first = Math.min(then, ...ticks);
        const founder = g.nodes.find((n) => n.kind === "incident");
        setFrame({ head, headGraph: g, then, now, first, ticks, base: founder?.base ?? null });
        setScrub((s) => (s === null || version > 0 ? now : s));
      })
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
  }, [caseId, version]);

  const offset = useMemo(
    () => installations.find((i) => i.installation_id === frame?.base)?.utc_offset_hours ?? 0,
    [installations, frame?.base],
  );

  // the graph and the diff at the scrub time, debounced
  useEffect(() => {
    if (!frame || scrub === null) return;
    let alive = true;
    const t = setTimeout(() => {
      const at = iso(scrub);
      api
        .caseGraph(caseId, at)
        .then((g) => alive && setGraph(g))
        .catch((e: unknown) => alive && setError(errText(e)));
      if (scrub > frame.then)
        api
          .caseDiff(caseId, iso(frame.then), at)
          .then((d) => alive && setDiff(d))
          .catch(() => undefined);
      else setDiff({ case_id: caseId, t1: at, t2: at, items: [], groups: {} });
    }, 150);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [caseId, frame, scrub]);

  // the Director's "known then" caption reads these (D-125)
  useEffect(() => {
    if (!frame) return;
    let alive = true;
    api
      .caseSnapshot(caseId, iso(frame.then))
      .then((s) => {
        if (!alive) return;
        const label = s.claims[0]?.value;
        const close = s.decisions.find((d) => d.decision === "close");
        const on = close ? localDay(close.recorded_at, offset) : null;
        directorStore.getState().setFacts({
          ...(frame.base ? { caseBase: baseName(frame.base) } : {}),
          ...(label ? { caseLabel: label } : {}),
          ...(on ? { caseClosedOn: on } : {}),
          pending: frame.head.pending.length,
        });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [caseId, frame, offset]);

  const link = useCallback(
    async (seq: number, d: "approve" | "reject") => {
      if (!frame) return;
      setBusy(true);
      setError(null);
      try {
        await api.decideLink(caseId, seq, d, frame.head.as_of);
        setVersion((v) => v + 1);
      } catch (e: unknown) {
        setError(errText(e));
      } finally {
        setBusy(false);
      }
    },
    [caseId, frame],
  );

  const decide = useCallback(
    async (d: CaseDecision) => {
      setBusy(true);
      setError(null);
      try {
        await api.recordDecision(caseId, d, frame?.head.as_of);
        setVersion((v) => v + 1);
      } catch (e: unknown) {
        setError(errText(e));
      } finally {
        setBusy(false);
      }
    },
    [caseId, frame],
  );

  return (
    <main
      aria-labelledby="case-title"
      className="min-h-0 flex-1 overflow-y-auto p-4"
      data-testid="case-board"
    >
      <div className="mx-auto flex max-w-[110rem] flex-col gap-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 id="case-title" className="text-24 font-bold text-ink-hi">
            {caseId}
          </h1>
          <p className="text-15 text-ink-mid">
            {frame
              ? `${frame.base ? `${baseName(frame.base)}, ` : ""}${frame.head.status}, ${frame.head.members.length} member${frame.head.members.length === 1 ? "" : "s"}, ${frame.head.pending.length} pending; opened ${localStamp(iso(frame.then), offset)}`
              : "Loading the case"}
          </p>
        </header>
        {error ? (
          <p role="alert" className="text-15 text-alert">
            {error}
          </p>
        ) : null}
        {frame && scrub !== null ? (
          <section
            aria-label="As of"
            className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
          >
            <Scrubber
              t0={frame.first}
              t1={frame.now}
              value={scrub}
              ticks={frame.ticks}
              then={frame.then}
              offsetH={offset}
              onChange={setScrub}
            />
          </section>
        ) : null}
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_26rem]">
          <section
            aria-labelledby="graph-title"
            className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
          >
            <h2 id="graph-title" className="text-13 font-bold text-ink-mid">
              What the memory held{graph ? ` as of ${localStamp(graph.as_of, offset)}` : ""}
            </h2>
            {graph ? (
              <>
                <CaseGraph graph={graph} head={frame?.headGraph ?? graph} reduce={reduce} />
                <GraphText graph={graph} />
                <p className="text-12 text-ink-mid">
                  Diamond: the case. Circles: incidents, colored by base; green ring: an approved
                  member; red ring: a contradiction. Squares: reports. Rounded: assessments. Dashed:
                  a proposed link.{focus ? ` Focus: ${focus}.` : ""}
                </p>
              </>
            ) : (
              <p className="text-13 text-ink-mid">Loading the graph</p>
            )}
          </section>
          <div className="flex flex-col gap-3">
            <section
              aria-labelledby="diff-title"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="diff-title" className="mb-2 text-13 font-bold text-ink-mid">
                Changed since Known then
              </h2>
              <DiffList diff={diff} />
            </section>
            <section
              aria-labelledby="act-title"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="act-title" className="mb-2 text-13 font-bold text-ink-mid">
                Act on it now, as analyst "{ANALYST}"
              </h2>
              <CaseControls
                pending={frame?.head.pending ?? []}
                busy={busy}
                onLink={(seq, d) => void link(seq, d)}
                onDecision={(d) => void decide(d)}
              />
              <p className="mt-3 text-13">
                <Link
                  to={`/evidence?case=${caseId}`}
                  className="text-flash underline-offset-2 hover:underline"
                >
                  Evidence for this case
                </Link>
              </p>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
