// Formatting for the Command Center: replay time, meters, hashes, local dates, rates.

/** Replay time since first contact, e.g. tPlus(62) = "T+01:02". */
export function tPlus(t_s: number | null | undefined): string {
  if (t_s === null || t_s === undefined || !Number.isFinite(t_s)) return "T+--:--";
  const s = Math.max(0, Math.floor(t_s));
  const m = Math.floor(s / 60);
  return `T+${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Meters: "812 m" below 10 km, "12.4 km" above. */
export function meters(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  if (Math.abs(v) >= 10000) return `${(v / 1000).toFixed(1)} km`;
  return `${Math.round(v).toLocaleString("en-US")} m`;
}

/** A number with fixed decimals, or an en dash when missing. */
export function num(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return v.toFixed(digits);
}

/** First 8 characters of a hash. */
export function shortHash(h: string | null | undefined): string {
  return h ? h.slice(0, 8) : "";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-04-19T21:35" (a local wall time from the API) → "Apr 19". */
export function localDate(local: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(local);
  if (!m) return local;
  return `${MONTHS[Number(m[2]) - 1] ?? "?"} ${Number(m[3])}`;
}

/** Base name for display: "DELTA" → "Delta". */
export function baseName(id: string): string {
  return id.charAt(0) + id.slice(1).toLowerCase();
}

/** Detections per second, e.g. "1.4/s". */
export function rate(perSecond: number): string {
  return `${perSecond.toFixed(1)}/s`;
}

/** Milliseconds with two decimals below 10 ms, e.g. "0.42 ms". */
export function ms(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return v < 10 ? `${v.toFixed(2)} ms` : `${Math.round(v)} ms`;
}
