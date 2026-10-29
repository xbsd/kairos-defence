import { beforeEach, describe, expect, it } from "vitest";

import { decisionOf, matchStore, top3Key } from "../src/state/matchStore";
import { match } from "./fixtures";

const s = () => matchStore.getState();

beforeEach(() => {
  matchStore.setState({ entrance: 0, top3: "", decisions: {}, busy: {} });
  s().clear();
});

describe("matchStore", () => {
  it("a match replaces the list", () => {
    s().apply(match(90));
    s().apply(match(95, ["P1-DELTA-260419", "P1-CHARLIE-260710", "P1-ALPHA-260303"]));
    expect(s().match?.t_s).toBe(95);
    expect(s().match?.matches[1]?.incident_id).toBe("P1-CHARLIE-260710");
  });

  it("the entrance runs only for a new top-3 set", () => {
    s().apply(match(90));
    expect(s().entrance).toBe(1);
    s().apply(match(95, ["P1-ALPHA-260502", "P1-DELTA-260419", "P1-ALPHA-260303"]));
    expect(s().entrance).toBe(1); // same set, another order
    s().apply(match(100, ["P1-DELTA-260419", "P1-ALPHA-260303", "P1-CHARLIE-260710"]));
    expect(s().entrance).toBe(2);
    expect(top3Key(null)).toBe("");
  });

  it("a session decision overrides the server's until it knows", () => {
    s().apply(match(90));
    const seq = s().match?.matches[0]?.proposal_seq ?? null;
    expect(decisionOf(s(), seq, null)).toBeNull();
    s().decide(seq ?? 0, "approved");
    expect(decisionOf(s(), seq, null)).toBe("approved");
    expect(decisionOf(s(), null, "approved")).toBeNull();
    expect(decisionOf(s(), 1, "rejected")).toBe("rejected");
  });

  it("passes memory status through", () => {
    s().apply(match(90));
    expect(s().match?.matches[0]?.memory_status).toBe("Closed as hobbyist on Apr 20");
  });

  it("keeps forecast, recall and the lens", () => {
    s().apply({
      type: "forecast",
      t_s: 105,
      at_s: 105,
      target_asset_id: "BRAVO-fuel_farm",
      anchor: "match_kind",
      center_x_m: 1,
      center_y_m: 2,
      radius_m: 370,
      path: [[1, 2]],
      roads: ["County Rd 12"],
      analogs: [],
    });
    expect(s().forecast?.roads).toEqual(["County Rd 12"]);
    s().clear();
    expect(s().forecast).toBeNull();
  });
});
