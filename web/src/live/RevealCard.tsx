import { useEffect, useRef } from "react";

import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { liveStore } from "../state/liveStore";
import { incidentName, verdictLabel } from "./liveText";

const SHOW_RERUNS = 8;

/** The reveal card (D-170): who really flew a closed live incident and how the matcher did,
 * from `kairos_defense.eval` on request (never stored). A native modal dialog. */
export function RevealCard() {
  const s = useThrottledStore(liveStore, (st) => ({
    id: st.revealOpen,
    r: st.revealOpen ? st.reveals[st.revealOpen] : undefined,
  }));
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d || !s.id || d.open) return;
    if (typeof d.showModal === "function") d.showModal();
    else d.setAttribute("open", "");
  }, [s.id]);
  if (!s.id) return null;
  const close = () => {
    const d = ref.current;
    if (d?.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
    liveStore.getState().openReveal(null);
  };
  const r = s.r;
  const doc = r?.state === "ready" ? r.doc : null;
  const rows = doc ? doc.reruns.slice(0, SHOW_RERUNS) : [];
  return (
    <dialog
      ref={ref}
      aria-labelledby="reveal-title"
      data-testid="reveal-card"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      className="m-auto max-h-[85vh] w-[min(38rem,92vw)] overflow-y-auto rounded-panel border border-afterglow bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
    >
      <h2 id="reveal-title" className="text-15 font-bold">
        Who flew {incidentName(s.id)}
      </h2>
      {!r || r.state === "loading" ? (
        <p className="mt-3 text-13 text-ink-mid">Asking the evaluation for the answer</p>
      ) : r.state === "error" ? (
        <p role="alert" className="mt-3 text-13 text-alert">
          {r.message}
        </p>
      ) : doc ? (
        <>
          <p data-testid="reveal-words" className="mt-3 text-18 text-afterglow">
            {doc.words}
          </p>
          <dl className="mt-3 grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-13">
            <dt className="text-ink-mid">Flown by</dt>
            <dd data-testid="reveal-actor">
              {doc.actor_id ? `${doc.actor_id}, ${doc.nickname ?? ""}` : "Not the simulator"}
            </dd>
            <dt className="text-ink-mid">Scenario</dt>
            <dd>
              {doc.scenario ?? "–"}
              {doc.seed !== null ? `, seed ${doc.seed}` : ""}
              {doc.flight && doc.flight > 1 ? `, flight ${doc.flight}` : ""}
            </dd>
            <dt className="text-ink-mid">Expected</dt>
            <dd>{doc.expectation.text || "–"}</dd>
            <dt className="text-ink-mid">Verdict</dt>
            <dd
              data-testid="reveal-verdict"
              className={doc.expectation.met === false ? "text-alert" : "text-verified"}
            >
              {verdictLabel(doc)}: {doc.expectation.observed}
            </dd>
            <dt className="text-ink-mid">Earlier flights</dt>
            <dd>
              {doc.same_actor_history} by the same {doc.actor_type === "swarm" ? "team" : "actor"}
            </dd>
          </dl>
          {rows.length ? (
            <table className="mt-3 w-full text-left text-12">
              <caption className="pb-1 text-left text-ink-mid">
                The first {rows.length} of {doc.reruns.length} reruns: where the true actor's own
                flights ranked among the matches shown
              </caption>
              <thead className="text-ink-mid">
                <tr>
                  <th className="py-0.5 font-normal">Rerun</th>
                  <th className="py-0.5 font-normal">Same actor's rank</th>
                  <th className="py-0.5 font-normal">Top match</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((x) => (
                  <tr key={`${x.kind}:${x.t_s}`} className="border-t border-hairline">
                    <td className="py-0.5">{tPlus(x.t_s)}</td>
                    <td className="py-0.5">{x.first_same_rank ?? "not shown"}</td>
                    <td className="truncate py-0.5">
                      {x.top_incident ?? "–"}
                      {x.top_actor ? ` (${x.top_actor})` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <p className="mt-3 text-12 text-ink-mid">
            Revealed by the evaluation from the simulator's ground truth, after the incident closed.
            The app never learns who flew while a flight is live, and nothing here is stored.
          </p>
        </>
      ) : null}
      <div className="mt-4 text-right">
        <button
          type="button"
          onClick={close}
          className="rounded-button border border-hairline px-3 py-1 text-13 hover:border-flash"
        >
          Close
        </button>
      </div>
    </dialog>
  );
}
