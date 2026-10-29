import { describe, expect, it } from "vitest";

import type { BeatId } from "../src/director/beats";
import { caption, localHM, paceOf, type CaptionCtx } from "../src/director/captions";
import { INSTALLATIONS, SCENE, T090, T105, T120 } from "./real";

const offsets = Object.fromEntries(
  INSTALLATIONS.map((i) => [i.installation_id, i.utc_offset_hours]),
);

function ctx(over: Partial<CaptionCtx> = {}): CaptionCtx {
  return {
    hello: T090.hello,
    firstPoint: [21680, -4930],
    scene: SCENE,
    offsets,
    rows: 1234,
    writeMs: 0.42,
    match: T090.match,
    lensTrack: "P1-DELTA-260419-T1",
    forecast: T105.forecast,
    recall: T120.recall,
    facts: { caseBase: "Delta", caseLabel: "hobbyist", caseClosedOn: "Apr 20", pending: 4 },
    ...over,
  };
}

const ALL: BeatId[] = [
  "detection",
  "recording",
  "recognition",
  "time-warp",
  "forecast",
  "recall",
  "known",
  "evidence",
];

describe("Director captions (D-125)", () => {
  it("are computed from the real results", () => {
    const c = ctx();
    expect(caption("detection", c)).toBe(
      "First radar contact at Bravo's north fence, 21:40 local.",
    );
    expect(caption("recording", c)).toBe(
      "Every detection is written as it arrives: 1,234 rows so far, 0.4 ms per write.",
    );
    expect(caption("recognition", c)).toBe(
      "After 45 seconds of track, Kairos Defense searches every past flight at every base.",
    );
    expect(caption("time-warp", c)).toBe(
      "Delta, Apr 19: the same shape, flown 19% faster. Warping time lines the two flights up.",
    );
    expect(caption("forecast", c)).toBe(
      "Those flights ended about 2.2 km northwest, in Bravo's radar shadow.",
    );
    expect(caption("recall", c)).toBe(
      "A Delta report from Apr 19 mentions a white pickup on County Rd 12, which runs through tonight's predicted zone.",
    );
    expect(caption("known", c)).toBe(
      "Delta closed this as hobbyist on Apr 20. Here is what was known then, and what is known now.",
    );
    expect(caption("evidence", c)).toMatch(/^4 proposed links wait for an analyst\. /);
  });

  it("drops the radar-shadow clause outside the shadow", () => {
    const shadowless = { ...SCENE, radar_shadow: null };
    expect(caption("forecast", ctx({ scene: shadowless }))).toBe(
      "Those flights ended about 2.2 km northwest.",
    );
  });

  it("never shows a missing value", () => {
    const empty: CaptionCtx = {
      hello: null,
      firstPoint: null,
      scene: null,
      offsets: {},
      rows: 0,
      writeMs: null,
      match: null,
      lensTrack: null,
      forecast: null,
      recall: null,
      facts: {},
    };
    for (const b of ALL) {
      const text = caption(b, empty);
      expect(text.length).toBeGreaterThan(10);
      expect(text).not.toMatch(/undefined|NaN|null|\{|\}/);
    }
  });

  it("uses the matcher's pace words and local times", () => {
    expect(paceOf(0.8417)).toBe("flown 19% faster");
    expect(paceOf(1.2)).toBe("flown 17% slower");
    expect(paceOf(1.03)).toBeNull();
    expect(localHM("2026-08-29T02:40:06.000Z", -5)).toBe("21:40");
    expect(localHM("garbage", -5)).toBeNull();
  });
});
