import { useEffect, useRef } from "react";

import { api } from "../api/client";
import { Link } from "../app/Link";
import type { MatchItem } from "../api/messages";
import { baseName, localDate, ms, tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { caseStore } from "../state/caseStore";
import { decisionOf, matchStore, type Decision } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { animate, EASE_OUT } from "./anim";
import { Panel } from "./Panel";
import { ScoreRing } from "./ScoreRing";

const NO_PROPOSAL = "No proposal was written for this match: no case to link it to yet";

/** "flown 18% slower" from a warp ratio (the matcher's wording, §10.4), or null within ±10%. */
function warpText(k: number | null): string | null {
  if (k === null || !Number.isFinite(k) || k <= 0) return null;
  if (k > 1.1) return `flown ${Math.round((1 - 1 / k) * 100)}% slower`;
  if (k < 0.9) return `flown ${Math.round((1 / k - 1) * 100)}% faster`;
  return null;
}

async function decide(caseId: string | null, m: MatchItem, d: "approve" | "reject") {
  const seq = m.proposal_seq;
  if (caseId === null || seq === null) return;
  const st = matchStore.getState();
  const r = replayStore.getState();
  const clock = r.clock?.ts ?? r.hello?.start_ts ?? new Date().toISOString();
  st.setBusy(seq, true);
  st.setError(null);
  try {
    const res = await api.decideLink(caseId, seq, d, clock);
    matchStore.getState().decide(seq, d === "approve" ? "approved" : "rejected");
    caseStore.getState().addBlocks([res.block], true);
  } catch (e: unknown) {
    matchStore.getState().setError(e instanceof Error ? e.message : String(e));
  } finally {
    matchStore.getState().setBusy(seq, false);
  }
}

function Entry(props: {
  m: MatchItem;
  at: number;
  index: number;
  caseId: string | null;
  decision: Decision | null;
  busy: boolean;
  reduce: boolean;
  explain: boolean;
}) {
  const { m, decision, reduce } = props;
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    animate(
      ref.current,
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 240, delay: props.index * 120, easing: EASE_OUT, fill: "backwards" },
      reduce,
    );
    // mount only: entries appear once per new top-3 set (§17.8)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const name = `${baseName(m.installation_id)}, ${localDate(m.local_start)}`;
  const pace = warpText(m.warp_ratio);
  const showPace = pace !== null && !m.reasons.some((r) => r.includes("flown"));
  const disabled = m.proposal_seq === null || props.busy || decision !== null;
  const title =
    m.proposal_seq === null ? NO_PROPOSAL : decision !== null ? `Link ${decision}` : undefined;
  return (
    <li
      ref={ref}
      data-testid="match-entry"
      data-incident={m.incident_id}
      data-track={m.track_id}
      onMouseEnter={() => matchStore.getState().setHovered(m.track_id)}
      onMouseLeave={() => matchStore.getState().setHovered(null)}
      onFocus={() => matchStore.getState().setHovered(m.track_id)}
      onBlur={() => matchStore.getState().setHovered(null)}
      className="flex gap-3 border-b border-hairline px-3 py-2 last:border-b-0"
    >
      <ScoreRing score={m.score} state={decision ?? "pending"} reduce={reduce} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="truncate text-15 font-bold text-ink-hi" title={m.incident_id}>
            {name}
            <span className="sr-only"> ({m.incident_id})</span>
          </h3>
          <span data-testid="match-score" className="font-mono text-15 text-afterglow">
            {m.score.toFixed(2)}
          </span>
        </div>
        <ul aria-label="Reasons" className="mt-1 flex flex-wrap gap-1">
          {m.reasons.map((r) => (
            <li
              key={r}
              data-testid="reason-chip"
              className="rounded-chip border border-hairline px-1.5 py-px text-12 text-ink-hi"
            >
              {r}
            </li>
          ))}
          {showPace ? (
            <li className="rounded-chip border border-hairline px-1.5 py-px text-12 text-ink-hi">
              {pace}
            </li>
          ) : null}
        </ul>
        <p
          data-testid="memory-status"
          className={`mt-1 truncate text-13 ${m.memory_status.startsWith("Closed") ? "text-afterglow" : "text-ink-mid"}`}
        >
          {m.memory_status}
        </p>
        <div className="mt-1.5 flex items-center gap-2">
          <button
            type="button"
            aria-label={`Approve link: ${name}`}
            title={title}
            disabled={disabled}
            onClick={() => void decide(props.caseId, m, "approve")}
            className="rounded-button border border-hairline px-2.5 py-0.5 text-13 text-ink-hi transition-colors duration-(--dur-micro) ease-(--ease-out) hover:border-verified disabled:cursor-not-allowed disabled:text-ink-mid disabled:hover:border-hairline"
          >
            Approve link
          </button>
          <button
            type="button"
            aria-label={`Reject: ${name}`}
            title={title}
            disabled={disabled}
            onClick={() => void decide(props.caseId, m, "reject")}
            className="rounded-button border border-hairline px-2.5 py-0.5 text-13 text-ink-mid transition-colors duration-(--dur-micro) ease-(--ease-out) hover:border-alert hover:text-ink-hi disabled:cursor-not-allowed disabled:hover:border-hairline disabled:hover:text-ink-mid"
          >
            Reject
          </button>
          {props.explain ? (
            <Link
              to={`/explainer?incident=${encodeURIComponent(m.query_incident_id)}&at=${props.at}&track=${encodeURIComponent(m.track_id)}`}
              className="ml-auto rounded-button px-1.5 py-0.5 text-13 text-ink-mid underline-offset-2 hover:text-ink-hi hover:underline"
            >
              <span aria-hidden="true">Explain</span>
              <span className="sr-only">Explain the match {name}</span>
            </Link>
          ) : null}
          {decision ? (
            <span
              data-testid="match-decision"
              className={`text-13 ${decision === "approved" ? "text-verified" : "text-ink-mid"}`}
            >
              {decision === "approved" ? "Linked" : "Rejected"}
            </span>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/** The memory rail's match list (§17.8): three entries, best first, approve or reject each.
 * `live`: on the Live page (D-184): live incidents have no Match explainer yet. */
export function MatchList({ live = false }: { live?: boolean }) {
  const s = useThrottledStore(matchStore, (st) => ({
    match: st.match,
    entrance: st.entrance,
    busy: st.busy,
    error: st.error,
    decisions: st.decisions,
    state: st,
  }));
  const hello = useThrottledStore(replayStore, (st) => st.hello);
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const m = s.match;

  let waiting = live ? "Nothing is flying" : "Waiting for the replay";
  const swarm = !live && hello?.matching === false ? hello.incident_id : null;
  if (live && hello?.incident_id)
    waiting = hello.matching
      ? `The matcher starts at ${tPlus(hello.min_track_s)}`
      : "No matching: the models or the index are missing";
  else if (hello && !live)
    waiting = swarm
      ? "A swarm: single-flight matching does not apply. Its choreography match is in the"
      : `The matcher starts at ${tPlus(hello.min_track_s)}`;

  return (
    <Panel
      id="matchlist"
      title="Matches"
      className="min-h-[10rem] flex-[1.6_1_0]"
      meta={m ? `At ${tPlus(m.t_s)}` : undefined}
    >
      <div className="absolute inset-0 flex flex-col overflow-y-auto">
        {!m || m.matches.length === 0 ? (
          <p data-testid="match-waiting" className="px-3 py-2 text-13 text-ink-mid">
            {m ? "No earlier flight to match" : waiting}
            {!m && swarm ? (
              <>
                {" "}
                <Link
                  to={`/swarm?incident=${encodeURIComponent(swarm)}`}
                  className="rounded-button text-flash underline"
                >
                  Swarm view
                </Link>
                .
              </>
            ) : null}
          </p>
        ) : (
          <>
            <ol aria-label="Best matches, best first" className="flex flex-col">
              {m.matches.slice(0, 3).map((x, i) => (
                <Entry
                  // a new top-3 set remounts (and animates) its entries; a rerun does not
                  key={`${s.entrance}:${x.incident_id}`}
                  m={x}
                  at={m.t_s}
                  index={i}
                  caseId={m.case_id}
                  decision={decisionOf(s.state, x.proposal_seq, x.decision ?? null)}
                  busy={x.proposal_seq !== null && s.busy[x.proposal_seq] === true}
                  reduce={reduce}
                  explain={!live}
                />
              ))}
            </ol>
            {s.error ? (
              <p role="alert" className="px-3 py-2 text-13 text-alert">
                {s.error}
              </p>
            ) : null}
            <p data-testid="match-model" className="mt-auto px-3 py-2 text-12 text-ink-mid">
              Model {m.model_version}, computed in {ms(m.elapsed_ms)}
              {m.cached ? " (cached)" : ""}
              {m.case_id ? `; proposals go to ${m.case_id}` : "; no case to propose links to"}
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}
