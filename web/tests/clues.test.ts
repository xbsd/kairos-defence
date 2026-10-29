import { describe, expect, it } from "vitest";

import type { RecallMsg } from "../src/api/messages";
import { chooseReport, segments, zoneNote, zoneRoad } from "../src/overlay/clues";
import { GLYPHS, RESOLVE_MS, scrambled } from "../src/overlay/scramble";
import { T120 } from "./real";

describe("recall overlay helpers (D-131)", () => {
  it("chooses the rank-1 report with a linked clue (T+120: the DELTA report)", () => {
    const c = chooseReport(T120.recall);
    expect(c?.report.report_id).toBe("R-P1-DELTA-260419-1");
    expect(c?.match.incident_id).toBe("P1-DELTA-260419");
    expect(chooseReport(null)).toBeNull();
  });

  it("falls back to the first match's rank-1 report when no clue is linked", () => {
    const r: RecallMsg = {
      ...T120.recall,
      matches: T120.recall.matches.map((m) => ({
        ...m,
        reports: m.reports.map((rp) => ({
          ...rp,
          clues: rp.clues.map((c) => ({ ...c, linked: false })),
        })),
      })),
    };
    expect(chooseReport(r)?.match.incident_id).toBe(T120.recall.matches[0]?.incident_id);
  });

  it("cuts the text into exact plain and clue substrings", () => {
    const rep = chooseReport(T120.recall)?.report;
    if (!rep) throw new Error("no report");
    const segs = segments(rep.text, rep.clues);
    expect(segs.map((s) => s.text).join("")).toBe(rep.text);
    const clues = segs.filter((s) => s.clue);
    expect(clues.map((s) => [s.clue?.type, s.text])).toEqual([
      ["vehicle", "white pickup"],
      ["road", "County Rd 12"],
    ]);
    // overlapping spans keep the first
    expect(
      segments("abcdef", [
        { type: "road", value: "bcd", start: 1, end: 4, links: [], linked: false },
        { type: "vehicle", value: "cde", start: 2, end: 5, links: [], linked: false },
      ]).map((s) => s.text),
    ).toEqual(["a", "bcd", "ef"]);
  });

  it("notes the zone road only when it is one of zone_roads", () => {
    const rep = chooseReport(T120.recall)?.report ?? null;
    expect(zoneRoad(rep, T120.recall)?.value).toBe("County Rd 12");
    expect(zoneNote(rep, T120.recall)).toBe("County Rd 12 runs through tonight's predicted zone.");
    expect(zoneNote(rep, { ...T120.recall, zone_roads: [] })).toBeNull();
  });

  it("scrambles deterministically, keeps the length and ends on the text", () => {
    const text = "A white pickup on County Rd 12.";
    expect(scrambled(text, 0)).toBe(scrambled(text, 0));
    expect(scrambled(text, 0)).toHaveLength(text.length);
    expect(scrambled(text, RESOLVE_MS)).toBe(text);
    expect(scrambled(text, 0)).not.toBe(text);
    expect(
      [...scrambled(text, 0)].filter((_ch, i) => text[i] === " ").every((ch) => ch === " "),
    ).toBe(true);
    expect([...scrambled(text, 0)].some((ch) => GLYPHS.includes(ch))).toBe(true);
  });
});
