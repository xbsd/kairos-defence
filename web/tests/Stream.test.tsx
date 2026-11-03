import { render, screen, within } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StreamPanel } from "../src/panels/Stream";
import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";
import { clock, HELLO, point, rf } from "./fixtures";
import { flush, nth, resetStores } from "./panelKit";

beforeEach(resetStores);
afterEach(() => vi.restoreAllMocks());

describe("StreamPanel", () => {
  it("says so before any detection", () => {
    render(<StreamPanel />);
    expect(screen.getByText("No detections yet.")).toBeInTheDocument();
    expect(screen.getByTestId("stream-total")).toHaveTextContent("0");
  });

  it("lists rows newest first with kind badges, rate and total", async () => {
    render(<StreamPanel />);
    act(() => {
      const s = replayStore.getState();
      s.apply(HELLO);
      for (let t = 0; t <= 10; t++) s.apply(point(t, 21680 + t, -4880, 90));
      s.apply(rf(9, 335));
      s.apply(clock(10));
    });
    await flush();
    const rows = screen.getAllByTestId("stream-row");
    expect(rows).toHaveLength(12);
    expect(rows[0]).toHaveAttribute("data-kind", "rf");
    expect(within(nth(rows, 0)).getByText("RF 1")).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("18.2");
    expect(rows[1]).toHaveTextContent("T+00:10");
    expect(rows[1]).toHaveTextContent("21690");
    expect(within(nth(rows, 1)).getByText("Radar 1")).toBeInTheDocument();
    expect(rows[11]).toHaveTextContent("T+00:00");
    // 5 points (6..10) and 1 RF in (5, 10] → 6 / 5 s
    expect(screen.getByTestId("stream-rate")).toHaveTextContent("1.2/s");
    expect(screen.getByTestId("stream-total")).toHaveTextContent("12");
  });

  it("keeps 200 rows and freezes while hovered", async () => {
    render(<StreamPanel />);
    act(() => {
      const s = replayStore.getState();
      for (let t = 0; t < 250; t++) s.apply(point(t));
    });
    await flush();
    expect(screen.getAllByTestId("stream-row")).toHaveLength(200);
    expect(screen.getByTestId("stream-total")).toHaveTextContent("250");
    const scroller = screen.getByRole("table").parentElement as HTMLElement;
    act(() => {
      scroller.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    });
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.mouseEnter(scroller);
    act(() => replayStore.getState().apply(point(300)));
    await flush();
    expect(screen.getAllByTestId("stream-row")[0]).toHaveTextContent("T+04:09");
    fireEvent.mouseLeave(scroller);
    await flush();
    expect(screen.getAllByTestId("stream-row")[0]).toHaveTextContent("T+05:00");
  });

  it("fades new rows in, except when they arrive faster than 10 a second (D-191)", async () => {
    uiStore.setState({ userReduce: false, osReduce: false });
    const proto = HTMLElement.prototype as unknown as { animate?: unknown };
    const had = proto.animate;
    const anim = vi.fn();
    proto.animate = anim;
    try {
      render(<StreamPanel />);
      act(() => {
        const s = replayStore.getState();
        s.apply(HELLO);
        s.apply(clock(10, true, 1));
        for (let t = 0; t <= 10; t++) s.apply(point(t, 21680 + t, -4880, 90));
      });
      await flush();
      expect(anim).toHaveBeenCalledTimes(2 * 11); // fade and left edge per row at 1x
      anim.mockClear();
      act(() => {
        const s = replayStore.getState();
        s.apply(clock(20, true, 20)); // a live feed at 20x: 2 rows per feed second, 40 a second
        for (let t = 11; t <= 20; t++) s.apply(point(t, 21680 + t, -4880, 90));
        for (let t = 11; t <= 20; t++) s.apply(rf(t, 335));
      });
      await flush();
      expect(screen.getAllByTestId("stream-row")).toHaveLength(31); // every row is there
      expect(anim).not.toHaveBeenCalled(); // and none waits on a fade to be seen
      act(() => {
        const s = replayStore.getState();
        s.apply(clock(40, true, 20)); // a dropout at 20x: one RF row in 5 feed seconds
        s.apply(rf(39, 335));
      });
      await flush();
      expect(screen.getAllByTestId("stream-row")).toHaveLength(32);
      expect(anim).not.toHaveBeenCalled(); // a feed faster than 10x never fades
    } finally {
      proto.animate = had;
    }
  });
});
