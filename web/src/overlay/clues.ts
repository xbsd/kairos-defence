// Report recall overlay helpers (SPEC §17.8, §12.4, D-131): which report to show, its text cut
// into plain and clue spans, and the zone note. Pure functions over the `recall` message.
import type { RecallMsg } from "../api/messages";

type RecallMatch = RecallMsg["matches"][number];
export type Report = RecallMatch["reports"][number];
export type Clue = Report["clues"][number];

export interface Chosen {
  match: RecallMatch;
  report: Report;
}

/**
 * The report to show: the rank-1 report of the first recall match whose rank-1 report has a
 * linked clue; otherwise the rank-1 report of the first match that has any report.
 */
export function chooseReport(r: RecallMsg | null): Chosen | null {
  if (!r) return null;
  for (const match of r.matches) {
    const report = match.reports[0];
    if (report && report.clues.some((c) => c.linked)) return { match, report };
  }
  for (const match of r.matches) {
    const report = match.reports[0];
    if (report) return { match, report };
  }
  return null;
}

export interface Segment {
  text: string;
  /** Vehicles glow afterglow, roads bone (§17.8); plain text has no clue. */
  clue: Clue | null;
}

/** The text as plain and clue segments (exact substrings, in order, overlaps dropped). */
export function segments(text: string, clues: Clue[]): Segment[] {
  const sorted = [...clues]
    .filter((c) => c.start >= 0 && c.end <= text.length && c.end > c.start)
    .sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let at = 0;
  for (const c of sorted) {
    if (c.start < at) continue; // overlaps an earlier clue
    if (c.start > at) out.push({ text: text.slice(at, c.start), clue: null });
    out.push({ text: text.slice(c.start, c.end), clue: c });
    at = c.end;
  }
  if (at < text.length) out.push({ text: text.slice(at), clue: null });
  return out;
}

/** The road clue tied to tonight's zone, if any (its value is one of `zone_roads`). */
export function zoneRoad(report: Report | null, r: RecallMsg | null): Clue | null {
  if (!report || !r) return null;
  return report.clues.find((c) => c.type === "road" && r.zone_roads.includes(c.value)) ?? null;
}

/** The zone note: the server's linked note for that road (§12.4), else the plain sentence. */
export function zoneNote(report: Report | null, r: RecallMsg | null): string | null {
  const c = zoneRoad(report, r);
  if (!c) return null;
  return c.links[0] ?? `${c.value} runs through tonight's predicted zone.`;
}
