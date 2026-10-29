import { describe, expect, it } from "vitest";

import { BASE_TONES, baseTones, lcg, layoutGraph, toModel } from "../src/case/graphModel";
import { GRAPH_NOW, GRAPH_THEN } from "./real";

describe("Case board graph model (D-138)", () => {
  it("known then (2026-04-20 10:00 local): the hobbyist assessment and no links but the founder's", () => {
    const m = toModel(GRAPH_THEN);
    const assessments = m.nodes.filter((n) => n.kind === "assessment");
    expect(assessments.map((n) => n.label)).toEqual(["hobbyist"]);
    const links = m.links.filter((l) => l.kind === "member_of" || l.kind === "proposed");
    expect(links).toHaveLength(1);
    expect(links[0]?.source).toBe("P1-DELTA-260419");
    expect(m.links.some((l) => l.kind === "proposed")).toBe(false);
  });

  it("known now holds the live proposals", () => {
    const m = toModel(GRAPH_NOW);
    expect(m.links.filter((l) => l.kind === "proposed").length).toBeGreaterThan(0);
    expect(m.nodes.filter((n) => n.kind === "incident").length).toBeGreaterThan(1);
  });

  it("lays out identically for identical input, inside the box", () => {
    const a = layoutGraph(toModel(GRAPH_NOW), 640, 460);
    const b = layoutGraph(toModel(GRAPH_NOW), 640, 460);
    expect([...a.entries()]).toEqual([...b.entries()]);
    for (const p of a.values()) {
      expect(p.x).toBeGreaterThanOrEqual(40);
      expect(p.x).toBeLessThanOrEqual(600);
      expect(p.y).toBeGreaterThanOrEqual(40);
      expect(p.y).toBeLessThanOrEqual(420);
    }
    expect(a.get("CASE-P1-DELTA-260419")).toEqual({ x: 320, y: 230 }); // the case is pinned center
  });

  it("flags contradictions and colors incidents from the base palette", () => {
    const g = {
      ...GRAPH_THEN,
      nodes: GRAPH_THEN.nodes.map((n) =>
        n.kind === "incident" ? { ...n, contradiction: true } : n,
      ),
    };
    const m = toModel(g);
    const inc = m.nodes.find((n) => n.kind === "incident");
    expect(inc?.contradiction).toBe(true);
    expect(BASE_TONES).toContain(inc?.tone);
    expect(
      baseTones([
        { id: "a", kind: "incident", base: "DELTA", seq: 1, recorded_at: null },
        { id: "b", kind: "incident", base: "ALPHA", seq: 2, recorded_at: null },
      ]),
    ).toEqual({ ALPHA: BASE_TONES[0], DELTA: BASE_TONES[1] });
  });

  it("seeds its random source", () => {
    const r1 = lcg(7);
    const r2 = lcg(7);
    expect([r1(), r1(), r1()]).toEqual([r2(), r2(), r2()]);
  });
});
