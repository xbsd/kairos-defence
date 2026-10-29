import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Signals } from "../src/panels/Signals";
import { replayStore } from "../src/state/replayStore";
import { clock, features } from "./fixtures";
import { flush, resetStores, stubCanvas } from "./panelKit";

let calls: ReturnType<typeof vi.fn>;
beforeEach(() => {
  resetStores();
  calls = stubCanvas();
});
afterEach(() => vi.restoreAllMocks());

describe("Signals", () => {
  it("renders four lanes and a text equivalent before data", () => {
    render(<Signals />);
    const lanes = screen.getAllByTestId("signal-lane");
    expect(lanes.map((l) => l.getAttribute("data-lane"))).toEqual([
      "speed_ms",
      "alt_m",
      "turn_rate_dps",
      "dist_target_m",
    ]);
    expect(screen.getByTestId("signals-text")).toHaveTextContent("Flight phaseunknown");
  });

  it("shows the current values, the phase and when loiter began", async () => {
    render(<Signals />);
    act(() => {
      const s = replayStore.getState();
      for (let t = 1; t <= 90; t++) s.apply(features(t, t >= 87 ? "loiter" : "approach"));
      s.apply(clock(90));
    });
    await flush();
    const text = screen.getByTestId("signals-text");
    expect(text).toHaveTextContent("Speed15.0 m/s");
    expect(text).toHaveTextContent("Altitude90 m");
    expect(text).toHaveTextContent("Distance to target610 m");
    expect(text).toHaveTextContent("Flight phaseLoiter");
    expect(text).toHaveTextContent("Loiter detectedT+01:27");
    expect(screen.getByTestId("signal-speed_ms")).toHaveTextContent("15.0");
    expect(screen.getByTestId("panel-signals")).toHaveTextContent("Loiter since T+01:27");
  });

  it("draws in one animation frame loop and stops when unmounted", async () => {
    const cancel = vi.spyOn(window, "cancelAnimationFrame");
    const { unmount } = render(<Signals />);
    act(() => {
      const s = replayStore.getState();
      for (let t = 1; t <= 20; t++) s.apply(features(t));
      s.apply(clock(20, false));
    });
    // jsdom lays out nothing (zero size), so the loop runs without painting
    await flush(60);
    unmount();
    expect(cancel).toHaveBeenCalled();
    expect(calls).not.toHaveBeenCalledWith("lineTo", expect.anything(), Number.NaN);
  });
});
