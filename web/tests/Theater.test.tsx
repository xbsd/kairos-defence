import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";
import { theaterSummary } from "../src/three/summary";
import { clock, features, HELLO, point } from "./fixtures";

vi.mock("@react-three/fiber", () => ({
  Canvas: () => <div data-testid="canvas" />,
  useFrame: () => undefined,
}));
vi.mock("@react-three/postprocessing", () => ({
  EffectComposer: () => null,
  Bloom: () => null,
  Vignette: () => null,
}));

const { Theater } = await import("../src/three/Theater");

function wait(ms: number) {
  return act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

beforeEach(() => {
  replayStore.getState().reset();
  uiStore.setState({ userReduce: null, osReduce: false, perfLevel: 0, camera: "overview" });
});

describe("theaterSummary", () => {
  it("describes each track in words, from real detections only", () => {
    const s = replayStore.getState();
    expect(theaterSummary(s)).toBe("No replay loaded.");
    s.apply(HELLO);
    expect(theaterSummary(replayStore.getState())).toBe("Waiting for the first detection.");
    s.apply(clock(90, false));
    s.apply(point(89));
    s.apply(point(90));
    s.apply(features(90, "loiter"));
    expect(theaterSummary(replayStore.getState())).toBe(
      "DEMO-BRAVO-0828-T1: 2 radar points, last at T+01:30, 610 m from BRAVO-fuel_farm, loiter, No Remote ID.",
    );
  });
});

describe("Theater", () => {
  it("shows the performance level, camera presets and the text summary", async () => {
    render(<Theater scene={null} />);
    const t = screen.getByTestId("theater");
    expect(t).toHaveAttribute("data-perf", "full");
    expect(screen.getByText("Loading the installation")).toBeInTheDocument();
    const follow = screen.getByRole("button", { name: "Follow" });
    expect(screen.getByRole("button", { name: "Overview" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(follow);
    await wait(150);
    expect(follow).toHaveAttribute("aria-pressed", "true");
    expect(uiStore.getState().camera).toBe("follow");
    act(() => uiStore.getState().toggleReduce());
    await wait(300);
    expect(t).toHaveAttribute("data-perf", "reduced");
    act(() => {
      uiStore.setState({ userReduce: false });
      uiStore.getState().setPerfLevel(1);
    });
    await wait(300);
    expect(t).toHaveAttribute("data-perf", "no-bloom");
    act(() => {
      const s = replayStore.getState();
      s.apply(HELLO);
      s.apply(clock(10, false));
      s.apply(point(10));
    });
    await wait(1100);
    expect(screen.getByTestId("theater-summary")).toHaveTextContent(
      "1 radar point, last at T+00:10",
    );
  });
});
