// The Eval page's view model (SPEC §17.9, §19.4, D-140): tiles against the targets written in the
// eval JSON, the forecast error histogram, the demo rows. Nothing is recomputed here beyond
// binning: every number is what `make eval` wrote.
import type { DemoRow, EvalReport, EvalTarget } from "../api/pages";

export type TileStatus = "pass" | "gap" | "report only" | "pending" | "missing";

export interface Tile {
  key: string;
  label: string;
  spec: string;
  value: string;
  target: string;
  status: TileStatus;
}

export function formatValue(v: number | null | undefined, fmt: EvalTarget["fmt"]): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  switch (fmt) {
    case "pct":
      return `${Math.round(v * 100)}%`;
    case "signed":
      return `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}`;
    case "m":
      return `${Math.round(v).toLocaleString("en-US")} m`;
    case "ms":
      return `${v < 10 ? v.toFixed(1) : Math.round(v).toLocaleString("en-US")} ms`;
    default:
      return v.toFixed(2);
  }
}

export function tiles(r: EvalReport): Tile[] | null {
  if (!r.targets) return null;
  return r.targets.map((t) => {
    const v = r.metrics[t.key];
    const has = v !== null && v !== undefined && Number.isFinite(v);
    const met = has ? (t.op === ">=" ? (v as number) >= t.value : (v as number) <= t.value) : null;
    let status: TileStatus;
    if (t.pending && !has) status = "pending";
    else if (!has) status = "missing";
    else if (t.report_only) status = "report only";
    else status = met ? "pass" : "gap";
    return {
      key: t.key,
      label: t.label,
      spec: t.spec,
      value: formatValue(has ? (v as number) : null, t.fmt),
      target: `${t.text}${t.pending && !has ? ` (${t.pending})` : ""}`,
      status,
    };
  });
}

export interface Bin {
  lo: number;
  hi: number;
  n: number;
}

/** Equal-width bins from 0 to the largest value (the last bin closed). */
export function histogram(values: number[], width: number): Bin[] {
  const xs = values.filter((v) => Number.isFinite(v) && v >= 0);
  if (!xs.length) return [];
  const top = Math.max(...xs);
  const n = Math.max(1, Math.ceil((top + 1e-9) / width));
  const bins: Bin[] = Array.from({ length: n }, (_, i) => ({
    lo: i * width,
    hi: (i + 1) * width,
    n: 0,
  }));
  for (const v of xs) {
    const i = Math.min(n - 1, Math.floor(v / width));
    (bins[i] as Bin).n += 1;
  }
  return bins;
}

/** Forecast errors of prober queries at one T (meters; infinite = no forecast, left out). */
export function forecastErrors(r: EvalReport, atS = 90): number[] {
  return (r.outcomes ?? [])
    .filter((o) => o.actor_type === "prober" && o.at_s === atS && o.ran)
    .map((o) => o.forecast_error_m)
    .filter((v): v is number => v !== null && Number.isFinite(v));
}

/** Demo rows as written, with a plain status word. */
export function demoRows(r: EvalReport): (DemoRow & { word: string })[] {
  return r.demo.map((d) => ({
    ...d,
    word:
      d.status === "pass"
        ? "Pass"
        : d.status === "fail"
          ? "Fail"
          : d.status.replace(/^pending/, "Pending"),
  }));
}

/** Recall@5 and top 3 for probers by T, the seconds the eval ran. */
export function recallSeries(r: EvalReport): { t: number; r5: number; top3: number }[] {
  return Object.entries(r.recall_by_t)
    .filter(([, v]) => v.ran)
    .map(([t, v]) => ({ t: Number(t), r5: v.recall_at_5_probers ?? 0, top3: v.top3_probers ?? 0 }))
    .sort((a, b) => a.t - b.t);
}
