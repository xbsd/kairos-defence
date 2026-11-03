import { fireEvent, render, screen, within } from "@testing-library/react";
import { act, Profiler } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { matchStore } from "../src/state/matchStore";
import { uiStore } from "../src/state/uiStore";
import { WorkbenchButton, WorkbenchDialog } from "../src/workbench/WorkbenchDialog";
import { WorkbenchPanel } from "../src/workbench/WorkbenchPanel";
import {
  aligned,
  endMs,
  fusionMs,
  landingMs,
  SHORTLIST_MS,
} from "../src/workbench/workbenchMachine";
import { workbenchStore } from "../src/workbench/workbenchStore";
import { flush, resetStores, stubDialog } from "./panelKit";
import { makeTrace, SIMS } from "./workbenchFixtures";

const msg = makeTrace(90);
const items = aligned(msg.trace);
const noop = () => undefined;

function panel(
  elapsed: number,
  rate = 6,
  extra: Partial<Parameters<typeof WorkbenchPanel>[0]> = {},
) {
  return render(
    <WorkbenchPanel
      msg={msg}
      items={items}
      elapsed={elapsed}
      rate={rate}
      playing
      onPlaying={noop}
      onStep={noop}
      onReplay={noop}
      onRate={noop}
      {...extra}
    />,
  );
}

const rows = (testId: string) =>
  within(screen.getByTestId(testId))
    .getAllByRole("listitem")
    .map((li) => li.getAttribute("data-track"));

beforeEach(() => {
  resetStores();
  stubDialog();
  workbenchStore.getState().close();
});
afterEach(() => vi.restoreAllMocks());

describe("WorkbenchPanel", () => {
  it("says what it shows from the trace's numbers", () => {
    panel(0);
    expect(screen.getByTestId("workbench-headline")).toHaveTextContent(
      "Slow-motion replay of rerun T+01:30: 8 alignments computed in 23 ms; the first 4 and 1 more " +
        "of the final top 10 replayed at 6 per second",
    );
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-stage", "shortlist");
    expect(screen.getByText(/1\. Shortlist: 8 tracks by vector distance/)).toBeInTheDocument();
    expect(screen.getByText("The alignments start after the shortlist.")).toBeInTheDocument();
  });

  it("shows the current candidate, its readout and the path at a given step", () => {
    panel(landingMs(2, 6));
    const root = screen.getByTestId("workbench");
    expect(root).toHaveAttribute("data-stage", "align");
    expect(root).toHaveAttribute("data-step", "3");
    expect(root).toHaveAttribute("data-track", "T2");
    const curves = screen.getByRole("img", { name: /aligned to INC-T2 \(amber, 43 s\)/ });
    expect(curves.querySelectorAll("line")).toHaveLength(3); // one connector per path point
    expect(
      screen.getByRole("img", { name: "Cost matrix of 30 by 43 cells with the warping path" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("workbench-path")).toBeInTheDocument();
    const dl = screen.getByTestId("workbench-readout");
    expect(dl).toHaveTextContent(`Similarity${SIMS[2]?.toFixed(3)}`);
    expect(dl).toHaveTextContent("30 × 43, band 6");
    expect(dl).toHaveTextContent("54 steps");
    expect(rows("workbench-ranking")).toEqual(["T1", "T2", "T0"]);
    expect(screen.getByRole("status")).toHaveTextContent("Aligning 3 of 5");
  });

  it("shows the fused top 5 with reasons at the end", () => {
    panel(endMs(items.length, 6));
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-stage", "done");
    expect(rows("workbench-fusion")).toEqual(msg.trace.ranking.slice(0, 5).map((r) => r.track_id));
    expect(screen.getByText("same RF family (6)")).toBeInTheDocument();
    // the alignment shown once fused is the fused #1's
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-track", "T6");
    expect(
      screen.getByText(/2\. DTW alignment: INC-T6 \(vector rank 7, fused rank 1\)/),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Done");
  });

  it("wires Pause, Step, Replay and the speed", () => {
    const onPlaying = vi.fn();
    const onStep = vi.fn();
    const onReplay = vi.fn();
    const onRate = vi.fn();
    panel(fusionMs(items.length, 6) - 1, 6, { onPlaying, onStep, onReplay, onRate });
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(onPlaying).toHaveBeenCalledWith(false);
    fireEvent.click(screen.getByRole("button", { name: "Step" }));
    fireEvent.click(screen.getByRole("button", { name: "Replay" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Candidates per second" }), {
      target: { value: "10" },
    });
    expect([onStep.mock.calls.length, onReplay.mock.calls.length]).toEqual([1, 1]);
    expect(onRate).toHaveBeenCalledWith(10);
  });
});

describe("WorkbenchDialog", () => {
  it("opens from the button on the stream's latest trace, pinned against newer ones", async () => {
    uiStore.setState({ userReduce: false, osReduce: false });
    render(
      <>
        <WorkbenchButton />
        <WorkbenchDialog />
      </>,
    );
    const button = screen.getByRole("button", { name: "DTW workbench" });
    expect(button).toBeDisabled(); // no trace yet
    act(() => matchStore.getState().apply(msg));
    await flush(300);
    fireEvent.click(screen.getByRole("button", { name: "DTW workbench" }));
    await flush();
    const dialog = screen.getByTestId("workbench-dialog");
    expect(dialog).toHaveAttribute("open");
    expect(
      screen.getByRole("heading", { name: /DTW workbench: LIVE-BRAVO-TEST, rerun T\+01:30/ }),
    ).toBeInTheDocument();
    expect(workbenchStore.getState().playing).toBe(true);
    act(() => {
      workbenchStore.getState().setPlaying(false); // hold it at the first candidate
      workbenchStore.setState({ elapsed: SHORTLIST_MS + 1 });
    });
    // a newer rerun arrives: nothing restarts, the replay keeps its trace; it is only offered
    const newer = makeTrace(105);
    act(() => matchStore.getState().apply(newer));
    await flush(300);
    expect(workbenchStore.getState().msg).toBe(msg);
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-t", "90");
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-step", "1");
    fireEvent.click(
      screen.getByRole("button", { name: /Newer rerun available \(T\+01:45\): replay it/ }),
    );
    await flush();
    expect(workbenchStore.getState().msg).toBe(newer);
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-t", "105");
    expect(screen.queryByRole("button", { name: /Newer rerun available/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await flush();
    expect(dialog).not.toHaveAttribute("open");
  });

  it("shows the final state at once with reduced motion", async () => {
    uiStore.setState({ userReduce: true, osReduce: false });
    render(
      <>
        <WorkbenchButton />
        <WorkbenchDialog />
      </>,
    );
    act(() => matchStore.getState().apply(msg));
    await flush(300);
    fireEvent.click(screen.getByRole("button", { name: "DTW workbench" }));
    await flush();
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-stage", "done");
    expect(workbenchStore.getState().playing).toBe(false);
    expect(rows("workbench-fusion")).toHaveLength(5);
  });

  it("re-renders at most 10 times per second while the replay runs (§17.11)", async () => {
    uiStore.setState({ userReduce: false, osReduce: false });
    let renders = 0;
    render(
      <Profiler id="wb" onRender={() => renders++}>
        <WorkbenchDialog />
      </Profiler>,
    );
    act(() => workbenchStore.getState().openWith(msg, "fetch", false));
    await flush();
    renders = 0;
    const t0 = performance.now();
    // 60 store updates per second for a second, as requestAnimationFrame would send
    for (let k = 0; k < 60; k++) {
      act(() => workbenchStore.getState().tick(16));
      await act(async () => {
        await new Promise((r) => setTimeout(r, 16));
      });
    }
    const s = (performance.now() - t0) / 1000;
    expect(workbenchStore.getState().version).toBeGreaterThan(60);
    expect(renders).toBeLessThanOrEqual(Math.ceil(10 * s) + 2);
    expect(renders).toBeGreaterThan(2);
  });
});
