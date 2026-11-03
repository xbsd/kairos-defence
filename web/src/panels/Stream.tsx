import { useEffect, useRef, useState } from "react";

import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { detectionRate, replayStore, type RowKind, type StreamRow } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { token } from "../theme/colors";
import { animate, EASE_OUT } from "./anim";
import { Panel } from "./Panel";

const KIND: Record<RowKind, { label: string; className: string }> = {
  radar: { label: "Radar", className: "border-flash text-flash" },
  rf: { label: "RF", className: "border-ink-mid text-ink-hi" },
  rid: { label: "Remote ID", className: "border-bone text-bone" },
};

function n0(v: number | null): string {
  return v === null || !Number.isFinite(v) ? "–" : String(Math.round(v));
}

function value(r: StreamRow): string {
  if (r.value === null || !Number.isFinite(r.value)) return "–";
  return r.valueLabel === "SNR" ? r.value.toFixed(1) : r.value.toFixed(2);
}

/** "BRAVO-RADAR-1" → "1"; a Remote ID serial stays whole. */
function sensorShort(r: StreamRow): string {
  if (r.kind === "rid") return "";
  const parts = r.sensor.split("-");
  return parts[parts.length - 1] ?? r.sensor;
}

/** One row; a new one fades in over 120 ms with a flash-blue left edge that decays (§17.4). */
function Row({ r, reduce }: { r: StreamRow; reduce: boolean }) {
  const ref = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    animate(
      ref.current,
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 120, easing: EASE_OUT },
      reduce,
    );
    animate(
      ref.current?.firstElementChild ?? null,
      [{ borderLeftColor: token("--flash") }, { borderLeftColor: "transparent" }],
      { duration: 1200, easing: EASE_OUT },
      reduce,
    );
    // mount only: an existing row does not flash again
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const k = KIND[r.kind];
  const short = sensorShort(r);
  const what = r.valueLabel === "SNR" ? "SNR, dB" : r.valueLabel === "quality" ? "quality" : "";
  return (
    <tr ref={ref} data-testid="stream-row" data-kind={r.kind} className="border-b border-hairline">
      <td className="border-l-2 border-l-transparent py-0.5 pr-1.5 pl-1.5 font-mono text-ink-hi">
        {tPlus(r.t_s)}
      </td>
      <td className="pr-1.5" title={r.sensor}>
        <span
          className={`inline-block rounded-chip border px-1.5 text-12 leading-4 whitespace-nowrap ${k.className}`}
        >
          {k.label}
          {short ? ` ${short}` : ""}
        </span>
        <span className="sr-only"> {r.sensor}</span>
      </td>
      <td className="pr-1.5 text-right font-mono text-ink-hi">{n0(r.x)}</td>
      <td className="pr-1.5 text-right font-mono text-ink-hi">{n0(r.y)}</td>
      <td className="pr-1.5 text-right font-mono text-ink-hi">{n0(r.alt)}</td>
      <td className="pr-1.5 text-right font-mono text-ink-mid" title={what}>
        {value(r)}
      </td>
    </tr>
  );
}

/** Above this many new rows per wall second (the panel's 10 Hz redraw) rows appear without
 * the fade: they would arrive faster than it plays, and on a slow machine a fade that has not
 * started yet leaves the newest rows blank (D-191). A feed faster than 10× never fades. */
const FADE_MAX_ROWS_PER_S = 10;

/** Live detection rows, newest on top (SPEC §17.4). Hovering pauses the list. */
export function StreamPanel() {
  const s = useThrottledStore(replayStore, (st) => ({
    rows: st.rows.slice(),
    rate: detectionRate(st),
    total: st.total,
    speed: st.clock?.speed ?? 1,
  }));
  const reduceAll = useThrottledStore(uiStore, reduceMotion);
  // at least one row per feed second: a dropout must not bring the fade back mid-flight
  const reduce = reduceAll || Math.max(1, s.rate) * s.speed > FADE_MAX_ROWS_PER_S;
  const [frozen, setFrozen] = useState<StreamRow[] | null>(null);
  const rows = frozen ?? s.rows;
  return (
    <Panel
      id="stream"
      title="Stream"
      meta={
        <span className="flex gap-3">
          <span>
            Rate{" "}
            <span data-testid="stream-rate" className="font-mono text-ink-hi">
              {s.rate.toFixed(1)}/s
            </span>
          </span>
          <span>
            Total{" "}
            <span data-testid="stream-total" className="font-mono text-ink-hi">
              {s.total.toLocaleString("en-US")}
            </span>
          </span>
          {frozen ? <span className="text-flash">Paused while you point</span> : null}
        </span>
      }
    >
      <div
        // a scrolling list must be reachable by keyboard (§17.12; axe scrollable-region-focusable)
        tabIndex={0}
        role="region"
        aria-label="Stream rows, newest first"
        className="absolute inset-0 overflow-auto px-1 pb-1"
        onMouseEnter={() => setFrozen(s.rows)}
        onMouseLeave={() => setFrozen(null)}
        onFocus={() => setFrozen(s.rows)}
        onBlur={() => setFrozen(null)}
      >
        {rows.length === 0 ? (
          <p className="px-2 py-1 text-13 text-ink-mid">No detections yet.</p>
        ) : (
          <table className="w-full border-collapse text-12 whitespace-nowrap">
            <caption className="sr-only">
              Live detections, newest first: time, sensor and kind, x and y in region meters,
              altitude in meters, radar quality or RF signal-to-noise ratio in dB
            </caption>
            <thead className="sticky top-0 bg-scope text-left text-ink-mid">
              <tr>
                <th scope="col" className="py-0.5 pl-1.5 font-normal">
                  Time
                </th>
                <th scope="col" className="font-normal">
                  Sensor
                </th>
                <th scope="col" className="pr-1.5 text-right font-normal">
                  x
                </th>
                <th scope="col" className="pr-1.5 text-right font-normal">
                  y
                </th>
                <th scope="col" className="pr-1.5 text-right font-normal">
                  Alt
                </th>
                <th scope="col" className="pr-1.5 text-right font-normal">
                  Q/SNR
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Row key={r.key} r={r} reduce={reduce} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Panel>
  );
}
