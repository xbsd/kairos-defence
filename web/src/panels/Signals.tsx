import { useEffect, useRef } from "react";

import type { FeaturesMsg } from "../api/messages";
import { num, tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { clockNow, FEATURES_WINDOW_S, replayStore } from "../state/replayStore";
import { token } from "../theme/colors";
import { Panel } from "./Panel";

type Key = "speed_ms" | "alt_m" | "turn_rate_dps" | "dist_target_m";

const LANES: { key: Key; label: string; unit: string; digits: number }[] = [
  { key: "speed_ms", label: "Speed", unit: "m/s", digits: 1 },
  { key: "alt_m", label: "Altitude", unit: "m", digits: 0 },
  { key: "turn_rate_dps", label: "Turn rate", unit: "°/s", digits: 1 },
  { key: "dist_target_m", label: "Distance to target", unit: "m", digits: 0 },
];

const PHASE: Record<FeaturesMsg["phase"], string> = {
  approach: "Approach",
  loiter: "Loiter",
  egress: "Egress",
};

/** The second loiter began, when that start is inside the window (the bone marker, §17.5). A
 * window that opens mid-loiter has no marker: its start is out of view, not unknown. */
function firstLoiter(f: FeaturesMsg[]): number | null {
  for (let i = 1; i < f.length; i++) {
    if (f[i]?.phase === "loiter" && f[i - 1]?.phase !== "loiter") return f[i]?.t_s ?? null;
  }
  return null;
}

/** Draw one lane: the last 120 s ending at `now`, fading toward the left like phosphor. */
function drawLane(
  c: HTMLCanvasElement,
  feats: FeaturesMsg[],
  key: Key,
  now: number,
  loiter: number | null,
): void {
  const ctx = c.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth;
  const h = c.clientHeight;
  if (w === 0 || h === 0) return;
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const t0 = now - FEATURES_WINDOW_S;
  const x = (t: number) => ((t - t0) / FEATURES_WINDOW_S) * w;
  // baseline
  ctx.strokeStyle = token("--hairline");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, h - 0.5);
  ctx.lineTo(w, h - 0.5);
  ctx.stroke();
  const vals = feats.filter((f) => f.t_s > t0 && f.t_s <= now);
  const ys = vals.map((f) => f[key]).filter((v): v is number => v !== null && Number.isFinite(v));
  if (ys.length >= 2) {
    let lo = Math.min(...ys);
    let hi = Math.max(...ys);
    if (hi - lo < 1e-6) {
      lo -= 1;
      hi += 1;
    }
    const pad = (hi - lo) * 0.12;
    lo -= pad;
    hi += pad;
    const y = (v: number) => h - 2 - ((v - lo) / (hi - lo)) * (h - 4);
    ctx.strokeStyle = token("--flash");
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.beginPath();
    let pen = false;
    for (const f of vals) {
      const v = f[key];
      if (v === null || !Number.isFinite(v)) {
        pen = false; // a gap in the track stays a gap
        continue;
      }
      if (pen) ctx.lineTo(x(f.t_s), y(v));
      else ctx.moveTo(x(f.t_s), y(v));
      pen = true;
    }
    ctx.stroke();
    // phosphor: erase progressively toward the left edge
    ctx.globalCompositeOperation = "destination-out";
    const g = ctx.createLinearGradient(0, 0, w * 0.7, 0);
    g.addColorStop(0, "rgba(0, 0, 0, 0.85)");
    g.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w * 0.7, h);
    ctx.globalCompositeOperation = "source-over";
  }
  if (loiter !== null && loiter > t0 && loiter <= now) {
    ctx.strokeStyle = token("--bone");
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(Math.round(x(loiter)) + 0.5, 0);
    ctx.lineTo(Math.round(x(loiter)) + 0.5, h);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

/** Four lanes over the last 120 s: speed, altitude, turn rate, distance to target (§17.5). */
export function Signals() {
  const canvases = useRef<(HTMLCanvasElement | null)[]>([]);
  const s = useThrottledStore(replayStore, (st) => ({
    last: st.features[st.features.length - 1] ?? null,
    loiter: firstLoiter(st.features),
  }));

  useEffect(() => {
    if (typeof requestAnimationFrame !== "function") return;
    let raf = 0;
    let seen = -1;
    let lastNow = -1;
    const frame = () => {
      raf = requestAnimationFrame(frame);
      const st = replayStore.getState();
      const now = clockNow(st);
      if (st.version === seen && Math.abs(now - lastNow) < 0.02) return; // nothing moved
      seen = st.version;
      lastNow = now;
      const loiter = firstLoiter(st.features);
      LANES.forEach((lane, i) => {
        const c = canvases.current[i];
        if (c) drawLane(c, st.features, lane.key, now, loiter);
      });
    };
    raf = requestAnimationFrame(frame);
    const ro =
      typeof ResizeObserver === "function"
        ? new ResizeObserver(() => {
            seen = -1; // redraw at the new size
          })
        : null;
    for (const c of canvases.current) if (c && ro) ro.observe(c);
    return () => {
      cancelAnimationFrame(raf);
      ro?.disconnect();
    };
  }, []);

  const last = s.last;
  return (
    <Panel
      id="signals"
      title="Signals"
      meta={
        last ? (
          <span>
            <span className="text-ink-hi">{PHASE[last.phase]}</span>
            {s.loiter !== null ? (
              <span className="text-bone" data-testid="signals-loiter" data-t={s.loiter}>
                {last.phase === "loiter" ? " since " : ", loiter began "}
                {tPlus(s.loiter)}
              </span>
            ) : null}
          </span>
        ) : (
          "Last 120 s"
        )
      }
    >
      <div className="absolute inset-0 flex flex-col gap-1 px-3 pb-2" aria-hidden="true">
        {LANES.map((lane, i) => (
          <div key={lane.key} className="flex min-h-0 flex-1 items-stretch gap-2">
            <div className="relative min-w-0 flex-1">
              <span className="absolute top-0 left-0 text-12 text-ink-mid">{lane.label}</span>
              <canvas
                ref={(el) => {
                  canvases.current[i] = el;
                }}
                data-testid="signal-lane"
                data-lane={lane.key}
                className="block h-full w-full"
              />
            </div>
            <div className="flex w-[4.75rem] shrink-0 flex-col items-end justify-center">
              <span className="font-mono text-13 text-ink-hi" data-testid={`signal-${lane.key}`}>
                {last ? num(last[lane.key], lane.digits) : "–"}
              </span>
              <span className="text-12 text-ink-mid">{lane.unit}</span>
            </div>
          </div>
        ))}
      </div>
      <dl className="sr-only" data-testid="signals-text">
        {LANES.map((lane) => (
          <div key={lane.key}>
            <dt>{lane.label}</dt>
            <dd>{last ? `${num(last[lane.key], lane.digits)} ${lane.unit}` : "no value yet"}</dd>
          </div>
        ))}
        <div>
          <dt>Flight phase</dt>
          <dd>{last ? PHASE[last.phase] : "unknown"}</dd>
        </div>
        {s.loiter !== null ? (
          <div>
            <dt>Loiter detected</dt>
            <dd>{tPlus(s.loiter)}</dd>
          </div>
        ) : null}
      </dl>
    </Panel>
  );
}
