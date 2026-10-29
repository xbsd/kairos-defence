import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommandBar } from "../src/app/CommandBar";
import { replayStatus } from "../src/app/status";
import { setStream } from "../src/state/controls";
import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";
import type { ReplayStream } from "../src/api/stream";
import { HELLO } from "./fixtures";

function tick() {
  return act(async () => {
    await new Promise((r) => setTimeout(r, 120));
  });
}

beforeEach(() => {
  replayStore.getState().reset();
  uiStore.setState({ userReduce: null, osReduce: false });
});

describe("replayStatus", () => {
  it("names the state from the stream and the clock", () => {
    expect(replayStatus("idle", false, undefined)).toBe("No replay loaded");
    expect(replayStatus("connecting", false, undefined)).toBe("Connecting");
    expect(replayStatus("reconnecting", true, true)).toBe("Reconnecting");
    expect(replayStatus("open", true, false)).toBe("Paused");
    expect(replayStatus("open", true, true)).toBe("Live");
  });
});

describe("CommandBar", () => {
  it("is idle without a replay", () => {
    render(<CommandBar trail={["Live watch"]} />);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Kairos Defense/Live watch",
    );
    expect(screen.getByRole("status")).toHaveTextContent("No replay loaded");
    expect(screen.getByRole("timer", { name: "Replay time: none" })).toHaveTextContent("T+--:--");
    for (const name of ["Play", "Pause", "Restart", "Speed 5 times"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    const director = screen.getByRole("button", { name: "Director" });
    expect(director).toBeEnabled();
    expect(director).toHaveAttribute("aria-pressed", "false");
  });

  it("follows the stream: clock, Live, speed, and sends commands", async () => {
    const sent: string[] = [];
    const fake = {
      play: () => sent.push("play"),
      pause: () => sent.push("pause"),
      seek: (t: number) => sent.push(`seek ${t}`),
      setSpeed: (v: number) => sent.push(`speed ${v}`),
      requestDtw: vi.fn(),
    } as unknown as ReplayStream;
    setStream(fake);
    render(<CommandBar trail={["Live watch", "Installation Bravo"]} replay />);
    act(() => {
      const s = replayStore.getState();
      s.setStatus("open");
      s.apply(HELLO);
      s.apply({
        type: "clock",
        t_s: 62.4,
        ts: "2026-08-29T02:41:08.400Z",
        speed: 5,
        playing: true,
        seeked: false,
      });
    });
    await tick();
    expect(screen.getByRole("status")).toHaveTextContent("Live");
    expect(screen.getByRole("timer", { name: "Replay time T+01:02" })).toHaveTextContent("T+01:02");
    expect(screen.getByRole("button", { name: "Speed 5 times" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    fireEvent.click(screen.getByRole("button", { name: "Speed 2 times" }));
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(sent).toEqual(["pause", "speed 2", "seek 0"]);
    setStream(null);
  });

  it("shows the replay's local time for the 1x record", async () => {
    render(<CommandBar trail={["Live watch"]} replay />);
    act(() => {
      const s = replayStore.getState();
      s.setStatus("open");
      s.apply(HELLO);
      s.apply({
        type: "clock",
        t_s: 62,
        ts: "2026-08-29T02:41:08.000Z",
        speed: 1,
        playing: true,
        seeked: false,
      });
    });
    await tick();
    // HELLO is BRAVO at UTC-5: 02:41:08Z is 21:41:08 local
    expect(screen.getByTestId("replay-clock")).toHaveAttribute("data-local-time", "21:41:08");
  });

  it("toggles Performance mode and shows Director as pressed while on", async () => {
    const { directorStore } = await import("../src/state/directorStore");
    render(<CommandBar trail={["Live watch"]} />);
    const perf = screen.getByRole("button", { name: "Performance mode" });
    expect(perf).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(perf);
    await tick();
    expect(perf).toHaveAttribute("aria-pressed", "true");
    expect(uiStore.getState().perfMode).toBe(true);
    act(() => directorStore.setState({ active: true }));
    await tick();
    expect(screen.getByRole("button", { name: "Director" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    act(() => directorStore.setState({ active: false }));
    uiStore.setState({ perfMode: false });
  });

  it("toggles reduce motion", async () => {
    render(<CommandBar trail={["Live watch"]} />);
    const b = screen.getByRole("button", { name: "Reduce motion" });
    expect(b).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(b);
    await tick();
    expect(b).toHaveAttribute("aria-pressed", "true");
  });
});
