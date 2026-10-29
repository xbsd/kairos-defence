import { useEffect, useRef } from "react";

import { ms } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { recordedTotal, replayStore, WRITE_HISTORY } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { animate, EASE_OUT } from "./anim";
import { Panel } from "./Panel";

const TABLES = ["live_points", "live_rf", "live_rid"] as const;

/** A stack of row glyphs dropping into a table glyph, once per real write batch (§17.6). */
function DropGlyph({ count, rows, reduce }: { count: number; rows: number; reduce: boolean }) {
  const stack = useRef<SVGGElement>(null);
  const table = useRef<SVGGElement>(null);
  useEffect(() => {
    if (count === 0) return;
    animate(
      stack.current,
      [
        { transform: "translateY(-14px)", opacity: 0 },
        { transform: "translateY(-6px)", opacity: 1, offset: 0.35 },
        { transform: "translateY(4px)", opacity: 0 },
      ],
      { duration: 600, easing: EASE_OUT },
      reduce,
    );
    animate(
      table.current,
      [{ opacity: 1 }, { opacity: 0.6, offset: 0.6 }, { opacity: 1 }],
      { duration: 600, easing: EASE_OUT },
      reduce,
    );
  }, [count, reduce]);
  const n = Math.min(Math.max(rows, 1), 4);
  return (
    <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true" className="shrink-0">
      <g ref={stack} className="fill-flash" style={{ opacity: 0 }}>
        {Array.from({ length: n }, (_, i) => (
          <rect key={i} x="12" y={4 + i * 3} width="16" height="2" rx="1" />
        ))}
      </g>
      <g ref={table} className="fill-none stroke-ink-mid" strokeWidth="1.25">
        <rect x="6" y="20" width="28" height="16" rx="2" />
        <line x1="6" y1="25.5" x2="34" y2="25.5" />
        <line x1="6" y1="30.5" x2="34" y2="30.5" />
        <line x1="15.5" y1="20" x2="15.5" y2="36" />
      </g>
    </svg>
  );
}

/** Write-time history: one bar per batch, newest on the right (real `write_ms`). */
function History({ values }: { values: number[] }) {
  const max = Math.max(0.5, ...values);
  const w = 3;
  const gap = 1;
  const width = WRITE_HISTORY * (w + gap);
  return (
    <svg
      viewBox={`0 0 ${width} 24`}
      preserveAspectRatio="none"
      className="h-6 w-full"
      role="img"
      aria-label={`Last ${values.length} write times, up to ${ms(max)}`}
    >
      {values.map((v, i) => {
        const h = Math.max(1, (v / max) * 24);
        const x = (WRITE_HISTORY - values.length + i) * (w + gap);
        return <rect key={i} x={x} y={24 - h} width={w} height={h} className="fill-flash/70" />;
      })}
    </svg>
  );
}

/** The real DuckDB write path (§16.2, §17.6): statement shape, rows, totals and write times. */
export function Recorder() {
  const s = useThrottledStore(replayStore, (st) => ({
    last: st.lastIngest,
    total: recordedTotal(st),
    tables: { ...st.tables },
    history: st.writeHistory.slice(),
    count: st.ingestCount,
  }));
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const last = s.last;
  return (
    <Panel id="recorder" title="Recorder" meta="DuckDB live tables">
      <div className="absolute inset-0 flex flex-col gap-2 overflow-y-auto px-3 pb-2">
        <div className="flex items-center gap-3">
          <DropGlyph count={s.count} rows={last?.rows ?? 0} reduce={reduce} />
          <code
            data-testid="recorder-statement"
            className="min-w-0 flex-1 font-mono text-12 break-words text-ink-hi"
            title={last?.statement ?? ""}
          >
            {last ? last.statement : "No write yet"}
          </code>
        </div>
        <dl className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 text-12">
          <dt className="text-ink-mid">Rows recorded</dt>
          <dd data-testid="recorder-total" className="text-right font-mono text-15 text-ink-hi">
            {s.total.toLocaleString("en-US")}
          </dd>
          <dt className="text-ink-mid">Last batch</dt>
          <dd className="text-right font-mono text-13 text-ink-hi">
            {last ? `${last.rows.toLocaleString("en-US")} row${last.rows === 1 ? "" : "s"}` : "–"}
          </dd>
          <dt className="text-ink-mid">Last write</dt>
          <dd data-testid="recorder-last-ms" className="text-right font-mono text-13 text-ink-hi">
            {last ? ms(last.write_ms) : "–"}
          </dd>
        </dl>
        <History values={s.history} />
        <table className="w-full text-12">
          <caption className="sr-only">Rows per live table</caption>
          <tbody>
            {TABLES.map((t) => (
              <tr key={t} data-testid="recorder-table" data-table={t}>
                <th scope="row" className="py-0.5 text-left font-mono font-normal text-ink-mid">
                  {t}
                </th>
                <td className="text-right font-mono text-ink-hi">
                  {(s.tables[t]?.total_rows ?? 0).toLocaleString("en-US")}
                </td>
                <td className="w-16 text-right font-mono text-ink-mid">
                  {s.tables[t] ? ms(s.tables[t].write_ms) : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
