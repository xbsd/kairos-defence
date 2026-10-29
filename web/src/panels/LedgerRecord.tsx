import { useEffect, useRef } from "react";

import type { LedgerRecord as Rec } from "../api/messages";

const FIELDS: (keyof Rec)[] = [
  "seq",
  "recorded_at",
  "event_type",
  "actor",
  "case_id",
  "subject_id",
  "predicate",
  "valid_from",
  "valid_to",
  "source_type",
  "source_id",
  "source_grade",
  "confidence",
  "supersedes_seq",
  "prev_hash",
  "hash",
];

function show(v: unknown): string {
  return v === null || v === undefined ? "–" : String(v);
}

/** The full ledger row behind a clicked block (§17.6), in a native modal dialog. */
export function LedgerRecordDialog({ record, onClose }: { record: Rec; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const done = useRef(false);
  useEffect(() => {
    const d = ref.current;
    done.current = false;
    if (!d || d.open) return;
    if (typeof d.showModal === "function") d.showModal();
    else d.setAttribute("open", "");
  }, [record.seq]);
  const finish = () => {
    if (done.current) return; // the native close event and our button both end here
    done.current = true;
    onClose();
  };
  const close = () => {
    const d = ref.current;
    if (d?.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
    finish();
  };
  const title = `ledger-record-${record.seq}-title`;
  return (
    <dialog
      ref={ref}
      aria-labelledby={title}
      data-testid="ledger-record"
      onClose={finish}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      className="m-auto max-h-[80vh] w-[min(40rem,92vw)] overflow-y-auto rounded-panel border border-hairline bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
    >
      <h2 id={title} className="text-15 font-bold">
        Ledger record {record.seq}
      </h2>
      <dl className="mt-3 grid grid-cols-[9rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-13">
        {FIELDS.map((f) => (
          <div key={f} className="contents">
            <dt className="text-ink-mid">{f}</dt>
            <dd className="font-mono break-all text-ink-hi">{show(record[f])}</dd>
          </div>
        ))}
        <div className="contents">
          <dt className="text-ink-mid">object_json</dt>
          <dd>
            <pre className="max-h-64 overflow-auto rounded-button border border-hairline p-2 font-mono text-12 whitespace-pre-wrap text-ink-hi">
              {record.object_json ? JSON.stringify(record.object_json, null, 2) : "–"}
            </pre>
          </dd>
        </div>
      </dl>
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
