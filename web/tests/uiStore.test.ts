import { beforeEach, describe, expect, it } from "vitest";

import {
  PACKET_BUDGET,
  effectsOn,
  packetBudget,
  reduceMotion,
  uiStore,
} from "../src/state/uiStore";

const s = () => uiStore.getState();

beforeEach(() => uiStore.setState({ osReduce: false, userReduce: null, perfLevel: 0 }));

describe("uiStore", () => {
  it("follows the OS until M toggles reduce motion", () => {
    s().setOsReduce(true);
    expect(reduceMotion(s())).toBe(true);
    s().toggleReduce();
    expect(reduceMotion(s())).toBe(false);
    s().toggleReduce();
    expect(reduceMotion(s())).toBe(true);
  });

  it("effects and packets follow motion and performance levels", () => {
    expect(effectsOn(s())).toBe(true);
    expect(packetBudget(s())).toBe(PACKET_BUDGET);
    s().setPerfLevel(1);
    expect(effectsOn(s())).toBe(false);
    expect(packetBudget(s())).toBe(PACKET_BUDGET);
    s().setPerfLevel(2);
    expect(packetBudget(s())).toBe(PACKET_BUDGET / 2);
    s().setOsReduce(true);
    expect(packetBudget(s())).toBe(0);
  });
});
