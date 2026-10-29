import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { RecallOverlay } from "../src/overlay/RecallOverlay";
import { directorStore } from "../src/state/directorStore";
import { matchStore } from "../src/state/matchStore";
import { overlayStore } from "../src/state/overlayStore";
import { sceneStore } from "../src/state/sceneStore";
import { flush, resetStores } from "./panelKit";
import { INSTALLATIONS, T120 } from "./real";

beforeEach(() => {
  resetStores();
  directorStore.setState({ active: false, beat: 0, page: null });
  overlayStore.setState({ collapsed: false });
  sceneStore.getState().setInstallations(INSTALLATIONS);
});

describe("RecallOverlay", () => {
  it("shows the DELTA report with its clues and the zone note (reduce motion: plain text)", async () => {
    render(<RecallOverlay raised={false} />);
    act(() => matchStore.getState().apply(T120.recall));
    await flush();
    const o = screen.getByTestId("recall-overlay");
    expect(o).toHaveAttribute("data-report", "R-P1-DELTA-260419-1");
    expect(o).toHaveTextContent("Delta security forces report, Apr 19, rank 1 for the Delta match");
    expect(screen.getByTestId("recall-text")).toHaveTextContent(
      T120.recall.matches[0]?.reports[0]?.text ?? "x",
    );
    expect(screen.getByTestId("clue-vehicle")).toHaveTextContent("white pickup");
    const road = screen.getByTestId("clue-road");
    expect(road).toHaveTextContent("County Rd 12");
    expect(road).toHaveAttribute("data-zone", "true");
    expect(screen.getByTestId("zone-note")).toHaveTextContent(
      "County Rd 12 runs through tonight's predicted zone.",
    );
  });

  it("collapses on request and waits for the recall beat in Director", async () => {
    render(<RecallOverlay raised />);
    act(() => matchStore.getState().apply(T120.recall));
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Hide report" }));
    await flush();
    expect(screen.queryByTestId("recall-text")).toBeNull();
    expect(screen.getByRole("button", { name: "Show report" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    act(() => directorStore.setState({ active: true, beat: 4 }));
    await flush();
    expect(screen.queryByTestId("recall-overlay")).toBeNull();
    act(() => directorStore.setState({ active: true, beat: 5 }));
    await flush();
    expect(screen.getByTestId("recall-overlay")).toBeInTheDocument();
  });
});
