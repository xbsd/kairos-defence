// Pure helpers for the Live page (D-184): launcher choices, labels and the reveal's rows.
import type { LiveIncidentRow, LiveStatus, RevealResponse, ScenarioInfo } from "../api/messages";
import { baseName } from "../lib/format";

export const SPEED_CHOICES = [1, 5, 10, 20, 50] as const;
export const RANDOM = "random";

/** The bases a scenario may fly at, for the chosen actor (all bases when it has no actor). */
export function basesFor(s: ScenarioInfo | undefined, actor: string | null): string[] {
  if (!s) return [];
  if (!s.actors.length) return s.bases;
  if (actor === RANDOM) return [...new Set(s.actors.flatMap((a) => a.bases))].sort();
  return s.actors.find((a) => a.id === actor)?.bases ?? [];
}

/** The default base: Bravo when allowed (the demo base), else the first. */
export function defaultBase(bases: string[]): string {
  return bases.includes("BRAVO") ? "BRAVO" : (bases[0] ?? "BRAVO");
}

/** The next installation after `base` (the default second base of new-operator-twice). */
export function nextBase(bases: string[], base: string): string {
  const i = bases.indexOf(base);
  return bases[(i + 1) % bases.length] ?? base;
}

/** "Feed live, 20x", "Feed idle", or "No feed yet". */
export function feedLabel(feed: LiveStatus["feeds"][number] | null): string {
  if (!feed) return "No feed yet";
  return feed.active ? `Feed live, ${feed.rate}×` : "Feed idle";
}

export function stateLabel(r: LiveIncidentRow): string {
  return r.state === "open" ? "Open" : r.state === "closing" ? "Closing" : "Closed";
}

/** "21:01 local" from an ISO UTC time and the region's offset. */
export function localClock(iso: string, utcOffsetHours: number | null): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t) || utcOffsetHours === null) return iso.slice(11, 16);
  const d = new Date(t + utcOffsetHours * 3_600_000);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** The incident as a short name: "Bravo, 21:01:36". */
export function incidentName(id: string): string {
  const m = /^LIVE-([A-Z]+)-\d{6}-(\d{2})(\d{2})(\d{2})/.exec(id);
  return m ? `${baseName(m[1] ?? "")}, ${m[2]}:${m[3]}:${m[4]}` : id;
}

/** The simulator line, without the actor (the app never keeps who flies, D-182). */
export function simulatorLine(s: LiveStatus["simulator"] | undefined): string {
  if (!s || !s.scenario) return "No simulator has run yet";
  const where = s.base ? ` at ${baseName(s.base)}` : "";
  const what = `${s.scenario}${where}, ${s.speed ?? 1}×, seed ${s.seed ?? "?"}`;
  if (s.running) return `Simulator running: ${what}`;
  return s.exit_code === 0
    ? `Last run finished: ${what}`
    : `Last run ended with code ${s.exit_code}: ${what}`;
}

/** The verdict's headline: met, missed or nothing to score. */
export function verdictLabel(doc: RevealResponse): string {
  const met = doc.expectation.met;
  if (met === true) return "Expectation met";
  if (met === false) return "Expectation missed";
  return "Nothing to score";
}
