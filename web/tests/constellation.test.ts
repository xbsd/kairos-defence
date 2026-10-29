import { describe, expect, it } from "vitest";

import type { MatchItem } from "../src/api/messages";
import { arcPath, layout, OTHER } from "../src/panels/constellation";
import { INSTALLATIONS, T090 } from "./real";

describe("region constellation (D-130)", () => {
  it("places the live region's bases inside the panel, north up", () => {
    const c = layout(INSTALLATIONS, "BRAVO", [], 360, 150, 26);
    expect(c.nodes.map((n) => n.id).sort()).toEqual(["ALPHA", "BRAVO", "CHARLIE", "DELTA"]);
    for (const n of c.nodes) {
      expect(n.x).toBeGreaterThanOrEqual(26 - 1e-9);
      expect(n.x).toBeLessThanOrEqual(334 + 1e-9);
      expect(n.y).toBeGreaterThanOrEqual(26 - 1e-9);
      expect(n.y).toBeLessThanOrEqual(124 + 1e-9);
    }
    const by = Object.fromEntries(c.nodes.map((n) => [n.id, n]));
    expect(by.DELTA?.y).toBeGreaterThan(by.CHARLIE?.y ?? 0); // DELTA is far south of CHARLIE
    expect(by.BRAVO?.live).toBe(true);
    expect(c.arcs).toEqual([]);
  });

  it("draws one arc per matched base to the live base, labeled with the dates", () => {
    const c = layout(INSTALLATIONS, "BRAVO", T090.match.matches.slice(0, 3), 360, 150);
    expect(c.arcs.map((a) => a.from).sort()).toEqual(["ALPHA", "CHARLIE", "DELTA"]);
    expect(c.arcs.find((a) => a.from === "DELTA")?.label).toBe("Apr 19");
    expect(c.arcs.every((a) => a.to === "BRAVO")).toBe(true);
    expect(c.nodes.find((n) => n.id === "DELTA")?.matched).toBe(true);
  });

  it("gathers matches from another region at the Other regions node", () => {
    const far = {
      ...T090.match.matches[0],
      installation_id: "GOLF",
      local_start: "2026-05-03T21:00",
    } as MatchItem;
    const c = layout(INSTALLATIONS, "BRAVO", [far], 360, 150);
    expect(c.nodes.find((n) => n.id === OTHER)?.name).toBe("Other regions");
    expect(c.arcs).toEqual([
      { from: OTHER, to: "BRAVO", label: "May 3", incidents: [far.incident_id] },
    ]);
    expect(layout(INSTALLATIONS, "NOPE", [], 360, 150).nodes).toEqual([]);
  });

  it("bends arcs and loops a base onto itself", () => {
    const a = { id: "A", name: "A", x: 10, y: 10, live: false, matched: true };
    const b = { id: "B", name: "B", x: 110, y: 10, live: true, matched: false };
    expect(arcPath(a, b)).toMatch(/^M 10\.0 10\.0 Q /);
    expect(arcPath(b, b)).toMatch(/ C /);
  });
});
