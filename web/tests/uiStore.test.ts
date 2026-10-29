import { beforeEach, describe, expect, it } from "vitest";

import { perfLabel } from "../src/three/perf";
import {
  PACKET_BUDGET,
  beamsOn,
  effectsOn,
  packetBudget,
  reduceMotion,
  uiStore,
} from "../src/state/uiStore";

const s = () => uiStore.getState();

beforeEach(() =>
  uiStore.setState({ osReduce: false, userReduce: null, perfLevel: 0, perfMode: false }),
);

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

  it("Performance mode turns bloom, grain and beams off and halves packets", () => {
    expect(beamsOn(s())).toBe(true);
    s().togglePerfMode();
    expect(s().perfMode).toBe(true);
    expect(effectsOn(s())).toBe(false);
    expect(beamsOn(s())).toBe(false);
    expect(packetBudget(s())).toBe(PACKET_BUDGET / 2);
    expect(perfLabel(0, false, true)).toBe("performance");
    expect(perfLabel(0, true, true)).toBe("reduced");
    s().togglePerfMode();
    expect(effectsOn(s())).toBe(true);
  });

  it("has a forecast camera preset", () => {
    s().setCamera("forecast");
    expect(s().camera).toBe("forecast");
  });
});
