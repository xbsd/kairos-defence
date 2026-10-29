import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TimeWarpLens } from "../src/lens/TimeWarpLens";
import { warpedConnectors, type Pair } from "../src/lens/lensMath";
import { stubCanvas } from "./panelKit";
import { T090 } from "./real";

beforeEach(() => {
  stubCanvas();
});

function lens(over: Partial<Parameters<typeof TimeWarpLens>[0]> = {}) {
  const onMode = vi.fn();
  const onTrack = vi.fn();
  const onChannel = vi.fn();
  const r = render(
    <TimeWarpLens
      dtw={T090.dtw}
      matches={T090.match.matches.slice(0, 3)}
      track={T090.dtw.match_track_id}
      channel="dist_target_m"
      mode="warped"
      reduce
      variant="compact"
      onMode={onMode}
      onTrack={onTrack}
      onChannel={onChannel}
      {...over}
    />,
  );
  return { ...r, onMode, onTrack, onChannel };
}

describe("TimeWarpLens", () => {
  it("draws warped connectors on the real DTW path and the readouts in words", () => {
    lens();
    const want = warpedConnectors(T090.dtw.path as Pair[]);
    const lines = screen.getAllByTestId("lens-connector");
    expect(lines.map((l) => [Number(l.dataset.i), Number(l.dataset.j)])).toEqual(want);
    expect(screen.getByRole("button", { name: "Warped" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("lens-dtw")).toHaveTextContent(
      `${T090.dtw.dtw_distance.toFixed(1)} m`,
    );
    expect(screen.getByTestId("lens-euclid")).toHaveTextContent(
      `${T090.dtw.euclid_distance.toFixed(1)} m`,
    );
    expect(screen.getByTestId("lens-pace")).toHaveTextContent("Flown 19% faster");
    expect(screen.getByTestId("cost-matrix")).toHaveAttribute("data-shape", "60x120");
  });

  it("same-time connectors join equal indices below the overlap", () => {
    lens({ mode: "same" });
    expect(screen.getByRole("button", { name: "Same time" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const shown = screen.getAllByTestId("lens-connector").filter((l) => l.dataset.shown === "true");
    expect(shown.length).toBeGreaterThan(0);
    for (const l of shown) {
      expect(l.dataset.i).toBe(l.dataset.j);
      expect(Number(l.dataset.i)).toBeLessThan(T090.dtw.overlap);
    }
  });

  it("switches mode and asks for another match or channel", () => {
    const { onMode, onTrack, onChannel } = lens();
    fireEvent.click(screen.getByRole("button", { name: "Same time" }));
    expect(onMode).toHaveBeenCalledWith("same");
    fireEvent.change(screen.getByRole("combobox", { name: "Match" }), {
      target: { value: "P1-ALPHA-260303-T1" },
    });
    expect(onTrack).toHaveBeenCalledWith("P1-ALPHA-260303-T1");
    fireEvent.change(screen.getByRole("combobox", { name: "Channel" }), {
      target: { value: "speed_ms" },
    });
    expect(onChannel).toHaveBeenCalledWith("speed_ms");
  });

  it("says it is loading before the payload arrives", () => {
    lens({ dtw: null });
    expect(screen.getByTestId("lens-loading")).toBeInTheDocument();
  });
});
