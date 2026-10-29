import { beforeEach, describe, expect, it } from "vitest";

import {
  FEATURES_WINDOW_S,
  ROWS_KEEP,
  clockNow,
  detectionRate,
  recordedTotal,
  replayStore,
} from "../src/state/replayStore";
import { dispatch } from "../src/state/dispatch";
import { matchStore } from "../src/state/matchStore";
import { HELLO, clock, features, ingest, match, point, rf } from "./fixtures";

const s = () => replayStore.getState();

beforeEach(() => {
  s().reset();
  matchStore.getState().clear();
});

describe("replayStore", () => {
  it("fills buffers: tracks, rows newest first, detections for packets", () => {
    s().apply(HELLO);
    s().apply(point(1));
    s().apply(rf(1));
    s().apply(point(2));
    expect(s().tracks["DEMO-BRAVO-0828-T1"]?.map((p) => p.t_s)).toEqual([1, 2]);
    expect(s().rows.map((r) => r.kind)).toEqual(["radar", "rf", "radar"]);
    expect(s().rows[0]?.t_s).toBe(2);
    expect(s().detections.map((d) => d.seq)).toEqual([1, 2, 3]);
    expect(s().total).toBe(3);
  });

  it("caps stream rows at 200, newest first", () => {
    for (let t = 0; t < 250; t++) s().apply(point(t));
    expect(s().rows).toHaveLength(ROWS_KEEP);
    expect(s().rows[0]?.t_s).toBe(249);
    expect(s().total).toBe(250);
  });

  it("measures the detection rate over the last 5 replay seconds", () => {
    for (let t = 0; t <= 20; t++) s().apply(point(t));
    for (let t = 16; t <= 20; t += 2) s().apply(rf(t));
    s().apply(clock(20));
    expect(detectionRate(s())).toBeCloseTo((5 + 3) / 5);
  });

  it("keeps recorder totals from ingest messages", () => {
    s().apply(ingest(3, 3));
    s().apply(ingest(1, 4));
    s().apply(ingest(2, 2, "live_rf"));
    expect(recordedTotal(s())).toBe(6);
    expect(s().ingestCount).toBe(3);
    expect(s().writeHistory).toEqual([0.42, 0.42, 0.42]);
    expect(s().lastIngest?.table).toBe("live_rf");
  });

  it("a seeked clock clears buffers and the match, but not the totals", () => {
    s().apply(point(1));
    s().apply(ingest(1, 1));
    matchStore.getState().apply(match());
    dispatch(clock(200, false, 1, true));
    expect(s().rows).toEqual([]);
    expect(s().tracks).toEqual({});
    expect(matchStore.getState().match).toBeNull();
    expect(s().total).toBe(1);
    expect(recordedTotal(s())).toBe(1);
    s().apply(point(1)); // a catch-up resend is not counted twice
    expect(s().total).toBe(1);
  });

  it("keeps 120 s of features in order", () => {
    for (let t = 1; t <= 200; t++) s().apply(features(t));
    expect(s().features[0]?.t_s).toBe(200 - FEATURES_WINDOW_S + 1);
    expect(s().features[s().features.length - 1]?.t_s).toBe(200);
    s().apply(features(150, "loiter"));
    expect(s().features.find((f) => f.t_s === 150)?.phase).toBe("loiter");
  });

  it("interpolates the clock while playing, never past the end", () => {
    s().apply(HELLO);
    s().apply(clock(100, true, 5), 1000);
    expect(clockNow(s(), 1100)).toBeCloseTo(100.5);
    expect(clockNow(s(), 9000)).toBeCloseTo(101.25); // capped at one tick ahead
    s().apply(clock(514.9, true, 5), 2000);
    expect(clockNow(s(), 2200)).toBe(515);
    s().apply(clock(100, false, 5), 3000);
    expect(clockNow(s(), 9000)).toBe(100);
  });
});
