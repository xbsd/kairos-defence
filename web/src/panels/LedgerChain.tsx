import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { LedgerBlock } from "../api/messages";
import { shortHash } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { caseStore } from "../state/caseStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { animate, EASE_OUT } from "./anim";
import { LedgerRecordDialog } from "./LedgerRecord";
import { Panel } from "./Panel";

/** Blocks that arrived this long ago or less animate in; older ones are drawn at rest. */
const FRESH_MS = 2500;

/** A small glyph per event type (shape, not color, carries the kind). */
function EventIcon({ type }: { type: string }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.4 } as const;
  let shape;
  switch (type) {
    case "match_proposed":
      shape = <path d="M3 8h10M9 4l4 4-4 4" {...common} />;
      break;
    case "link_approved":
      shape = <path d="M3 8.5l3 3 7-7" {...common} />;
      break;
    case "link_rejected":
      shape = <path d="M4 4l8 8M12 4l-8 8" {...common} />;
      break;
    case "incident_recorded":
      shape = <circle cx="8" cy="8" r="4.5" {...common} />;
      break;
    case "model_registered":
      shape = <rect x="3.5" y="3.5" width="9" height="9" {...common} />;
      break;
    case "evidence_exported":
      shape = <path d="M8 2.5v8M4.5 7l3.5 3.5L11.5 7M3 13.5h10" {...common} />;
      break;
    case "report_recorded":
      shape = <path d="M4 3h8v10H4zM6 6h4M6 9h4" {...common} />;
      break;
    case "assessment_asserted":
      shape = <path d="M8 2.5l5.5 10h-11z" {...common} />;
      break;
    default:
      shape = <path d="M8 3l5 5-5 5-5-5z" {...common} />;
  }
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      {shape}
    </svg>
  );
}

function words(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function Block(props: {
  b: LedgerBlock;
  first: boolean;
  arrivedAt: number | undefined;
  reduce: boolean;
  onOpen: (seq: number) => void;
}) {
  const { b, first, arrivedAt, reduce } = props;
  const li = useRef<HTMLLIElement>(null);
  const link = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (arrivedAt === undefined || performance.now() - arrivedAt > FRESH_MS) return;
    animate(
      li.current,
      [
        { transform: "translateX(24px)", opacity: 0 },
        { transform: "translateX(0)", opacity: 1 },
      ],
      { duration: 240, easing: EASE_OUT },
      reduce,
    );
    animate(
      link.current,
      [{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }],
      { duration: 400, easing: EASE_OUT, delay: 120, fill: "backwards" },
      reduce,
    );
    // mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const live = arrivedAt !== undefined;
  return (
    <li ref={li} className="flex shrink-0 items-center">
      {first ? null : (
        <span
          ref={link}
          aria-hidden="true"
          className="block h-px w-3 origin-left bg-ink-mid"
          data-testid="ledger-link"
        />
      )}
      <button
        type="button"
        data-testid="ledger-block"
        data-seq={b.seq}
        title={`${words(b.event_type)} by ${b.actor} at ${b.recorded_at}`}
        onClick={() => props.onOpen(b.seq)}
        className={`flex w-[5.5rem] flex-col items-start gap-0.5 rounded-button border px-2 py-1 text-left transition-colors duration-(--dur-micro) ease-(--ease-out) hover:border-flash ${
          live ? "border-flash/60" : "border-hairline"
        }`}
      >
        <span className="flex w-full items-center justify-between font-mono text-12 text-ink-hi">
          {b.seq}
          <span className={live ? "text-flash" : "text-ink-mid"}>
            <EventIcon type={b.event_type} />
          </span>
        </span>{" "}
        <span className="font-mono text-12 text-ink-mid">{shortHash(b.hash)}</span>
        <span className="sr-only">
          {", "}block {b.seq}, {words(b.event_type)}
        </span>
      </button>
    </li>
  );
}

function Verified() {
  const v = useThrottledStore(caseStore, (s) => ({ verify: s.verify, error: s.verifyError }));
  if (v.error)
    return (
      <span data-testid="ledger-verified" data-state="error" className="text-alert">
        Could not verify the chain
      </span>
    );
  if (!v.verify)
    return (
      <span data-testid="ledger-verified" data-state="checking" className="text-ink-mid">
        Checking
      </span>
    );
  if (v.verify.intact)
    return (
      <span data-testid="ledger-verified" data-state="verified" className="text-verified">
        Chain verified
      </span>
    );
  return (
    <span data-testid="ledger-verified" data-state="broken" className="text-alert">
      Broken at seq {v.verify.first_broken_seq}
    </span>
  );
}

/** The hash-chained ledger as blocks, newest on the right (§17.6). Click a block for its row. */
export function LedgerChain() {
  const s = useThrottledStore(caseStore, (st) => ({
    blocks: st.blocks,
    arrived: st.arrived,
    selected: st.selected,
  }));
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const scroller = useRef<HTMLDivElement>(null);
  const opener = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const head = s.blocks[s.blocks.length - 1]?.seq;

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = el.scrollWidth; // keep the head in view
  }, [head]);

  const open = (seq: number) => {
    opener.current = seq;
    setError(null);
    api
      .ledgerRecord(seq)
      .then((r) => caseStore.getState().select(r))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  };
  const close = () => {
    caseStore.getState().select(null);
    const seq = opener.current;
    if (seq !== null)
      scroller.current
        ?.querySelector<HTMLButtonElement>(`[data-testid="ledger-block"][data-seq="${seq}"]`)
        ?.focus();
  };

  const verifiedRows = useThrottledStore(caseStore, (st) => st.verify?.rows ?? null);
  return (
    <Panel id="ledgerchain" title="Ledger chain" meta={<Verified />}>
      <div className="absolute inset-0 flex flex-col gap-2 px-3 pb-2">
        <div ref={scroller} className="overflow-x-auto pt-1 pb-2">
          {s.blocks.length === 0 ? (
            <p className="text-13 text-ink-mid">No blocks loaded yet.</p>
          ) : (
            <ol aria-label="Ledger blocks, oldest to newest" className="flex w-max items-center">
              {s.blocks.map((b, i) => (
                <Block
                  key={b.seq}
                  b={b}
                  first={i === 0}
                  arrivedAt={s.arrived[b.seq]}
                  reduce={reduce}
                  onOpen={open}
                />
              ))}
            </ol>
          )}
        </div>
        {head !== undefined ? (
          <p className="text-12 text-ink-mid">
            {verifiedRows !== null ? `${verifiedRows.toLocaleString("en-US")} rows; head` : "Head"}{" "}
            seq <span className="font-mono text-ink-hi">{head}</span>
            {s.blocks.length ? (
              <>
                {" "}
                hash{" "}
                <span className="font-mono text-ink-hi">
                  {shortHash(s.blocks[s.blocks.length - 1]?.hash)}
                </span>
              </>
            ) : null}
            . Every block's previous hash is the block before it.
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-12 text-alert">
            {error}
          </p>
        ) : null}
      </div>
      {s.selected ? <LedgerRecordDialog record={s.selected} onClose={close} /> : null}
    </Panel>
  );
}
