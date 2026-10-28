// Motion helpers. Durations and easings live in tokens.css; read them from there so the CSS stays
// the single source of truth (SPEC §17.1, §21).

export type DurationToken = "--dur-micro" | "--dur-panel" | "--dur-reveal" | "--dur-cinema";
export type EaseToken = "--ease-out" | "--ease-inout";

/** Parse a CSS time ("240ms" or "1.2s") into milliseconds; NaN if it is not a time. */
export function parseCssTimeMs(value: string): number {
  const m = /^\s*(-?[\d.]+)(ms|s)\s*$/.exec(value);
  if (!m?.[1] || !m[2]) return Number.NaN;
  const n = Number(m[1]);
  return m[2] === "s" ? n * 1000 : n;
}

/** A duration token in milliseconds, read from the document's computed style. */
export function durationMs(token: DurationToken, el: Element = document.documentElement): number {
  return parseCssTimeMs(getComputedStyle(el).getPropertyValue(token));
}

/** True when the OS asks for reduced motion (SPEC §17.11). */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}
