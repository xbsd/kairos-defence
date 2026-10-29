import { useRef, useState } from "react";

import type { CaseDecision } from "../api/messages";
import type { PendingProposal } from "../api/pages";
import { tPlus } from "../lib/format";

const DECISIONS: [CaseDecision, string][] = [
  ["close", "Close"],
  ["reopen", "Reopen"],
  ["escalate", "Escalate"],
  ["notify_law_enforcement", "Notify law enforcement"],
];

/**
 * Approve or reject each pending proposal, and record a decision on the case (§17.9). Every
 * decision opens a confirm dialog first; nothing is written without that click (rule 8).
 */
export function CaseControls(props: {
  pending: PendingProposal[];
  busy: boolean;
  onLink: (seq: number, d: "approve" | "reject") => void;
  onDecision: (d: CaseDecision) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [asked, setAsked] = useState<CaseDecision | null>(null);
  const label = DECISIONS.find(([d]) => d === asked)?.[1] ?? "";
  return (
    <div className="flex flex-col gap-3" data-testid="case-controls">
      <section aria-labelledby="pending-title">
        <h3 id="pending-title" className="text-13 font-bold text-ink-mid">
          Proposed links ({props.pending.length})
        </h3>
        {props.pending.length ? (
          <ul className="mt-1 flex flex-col gap-1.5">
            {props.pending.map((p) => (
              <li
                key={p.seq}
                data-testid="pending-proposal"
                data-seq={p.seq}
                className="flex flex-wrap items-center gap-2 text-13"
              >
                <span className="text-ink-hi">{p.incident_id}</span>
                <span className="font-mono text-afterglow">
                  {p.score !== null ? p.score.toFixed(2) : "–"}
                </span>
                <span className="text-12 text-ink-mid">
                  {p.rank !== null ? `rank ${p.rank}` : ""}
                  {p.t_s !== null && p.t_s !== undefined ? ` at ${tPlus(p.t_s)}` : ""}
                </span>
                <span className="ml-auto flex gap-1">
                  <button
                    type="button"
                    disabled={props.busy}
                    aria-label={`Approve link: ${p.incident_id}`}
                    onClick={() => props.onLink(p.seq, "approve")}
                    className="rounded-button border border-hairline px-2 py-0.5 text-ink-hi hover:border-verified disabled:text-ink-mid"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={props.busy}
                    aria-label={`Reject link: ${p.incident_id}`}
                    onClick={() => props.onLink(p.seq, "reject")}
                    className="rounded-button border border-hairline px-2 py-0.5 text-ink-mid hover:border-alert hover:text-ink-hi disabled:text-ink-mid"
                  >
                    Reject
                  </button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-13 text-ink-mid">No proposal waits for a decision.</p>
        )}
      </section>
      <section aria-labelledby="decide-title">
        <h3 id="decide-title" className="text-13 font-bold text-ink-mid">
          Decisions
        </h3>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {DECISIONS.map(([d, text]) => (
            <button
              key={d}
              type="button"
              disabled={props.busy}
              onClick={() => {
                setAsked(d);
                dialog.current?.showModal?.();
              }}
              className="rounded-button border border-hairline px-2.5 py-1 text-13 text-ink-hi hover:border-flash disabled:text-ink-mid"
            >
              {text}
            </button>
          ))}
        </div>
      </section>
      <dialog
        ref={dialog}
        aria-labelledby="confirm-title"
        className="m-auto w-96 rounded-panel border border-hairline bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
        onClose={() => setAsked(null)}
      >
        <h2 id="confirm-title" className="text-15 font-bold">
          {label} this case?
        </h2>
        <p className="mt-2 text-13 text-ink-mid">
          This appends a decision to the ledger as analyst "demo". Ledger rows are never changed: a
          later decision supersedes this one.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => dialog.current?.close?.()}
            className="rounded-button border border-hairline px-3 py-1 text-13"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              const d = asked;
              dialog.current?.close?.();
              if (d) props.onDecision(d);
            }}
            className="rounded-button border border-flash px-3 py-1 text-13 text-flash"
          >
            Confirm: {label}
          </button>
        </div>
      </dialog>
    </div>
  );
}
