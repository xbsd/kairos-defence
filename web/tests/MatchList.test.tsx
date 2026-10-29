import { fireEvent, render, screen, within } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "../src/api/client";
import { toBlock } from "../src/api/messages";
import { MatchList } from "../src/panels/MatchList";
import { caseStore } from "../src/state/caseStore";
import { matchStore } from "../src/state/matchStore";
import { replayStore } from "../src/state/replayStore";
import { clock, HELLO, ledger, match } from "./fixtures";
import { flush, nth, resetStores } from "./panelKit";

beforeEach(resetStores);
afterEach(() => vi.restoreAllMocks());

describe("MatchList", () => {
  it("waits honestly before the matcher has run", async () => {
    render(<MatchList />);
    expect(screen.getByTestId("match-waiting")).toHaveTextContent("Waiting for the replay");
    act(() => replayStore.getState().apply(HELLO));
    await flush();
    expect(screen.getByTestId("match-waiting")).toHaveTextContent("The matcher starts at T+00:45");
    act(() => replayStore.getState().apply({ ...HELLO, matching: false, is_swarm: true }));
    await flush();
    expect(screen.getByTestId("match-waiting")).toHaveTextContent(
      "Swarm matching arrives in phase 9",
    );
  });

  it("shows three entries with score, ring, chips and memory status", async () => {
    render(<MatchList />);
    act(() => matchStore.getState().apply(match()));
    await flush();
    const es = screen.getAllByTestId("match-entry");
    expect(es.map((e) => e.getAttribute("data-incident"))).toEqual([
      "P1-DELTA-260419",
      "P1-ALPHA-260303",
      "P1-ALPHA-260502",
    ]);
    const first = nth(es, 0);
    expect(within(first).getByRole("heading")).toHaveTextContent("Delta, Apr 19");
    expect(within(first).getByTestId("match-score")).toHaveTextContent("0.94");
    expect(within(first).getByTestId("score-ring")).toHaveAttribute("data-state", "pending");
    expect(within(first).getAllByTestId("reason-chip")).toHaveLength(2);
    expect(within(first).getByTestId("memory-status")).toHaveTextContent(
      "Closed as hobbyist on Apr 20",
    );
    expect(within(first).getByText("flown 18% slower")).toBeInTheDocument();
    expect(screen.getByTestId("match-model")).toHaveTextContent(
      "Model fusion-v1, computed in 286 ms (cached)",
    );
  });

  it("approve posts the decision at the replay clock, turns the ring green, adds a block", async () => {
    const block = toBlock({ ...ledger(4690, "link_approved"), actor: "analyst:demo" });
    const spy = vi.spyOn(api, "decideLink").mockResolvedValue({
      case_id: "CASE-P1-DELTA-260419",
      proposal_seq: 4683,
      decision: "approve",
      block,
    });
    render(<MatchList />);
    act(() => {
      replayStore.getState().apply(HELLO);
      replayStore.getState().apply(clock(95));
      matchStore.getState().apply(match());
    });
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Approve link: Delta, Apr 19" }));
    await flush();
    expect(spy).toHaveBeenCalledWith(
      "CASE-P1-DELTA-260419",
      4683,
      "approve",
      "2026-08-29T02:41:08.000Z",
    );
    const first = nth(screen.getAllByTestId("match-entry"), 0);
    expect(within(first).getByTestId("score-ring")).toHaveAttribute("data-state", "approved");
    expect(within(first).getByTestId("match-decision")).toHaveTextContent("Linked");
    expect(within(first).getByRole("button", { name: /Approve link/ })).toBeDisabled();
    expect(caseStore.getState().blocks.map((b) => b.seq)).toEqual([4690]);
  });

  it("disables the buttons without a proposal seq", async () => {
    render(<MatchList />);
    const m = match();
    m.matches[1] = { ...nth(m.matches, 1), proposal_seq: null };
    act(() => matchStore.getState().apply(m));
    await flush();
    const second = nth(screen.getAllByTestId("match-entry"), 1);
    const b = within(second).getByRole("button", { name: /^Approve link/ });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("title", expect.stringContaining("No proposal was written"));
    expect(screen.getByRole("button", { name: "Approve link: Delta, Apr 19" })).toBeEnabled();
  });

  it("shows the server's message when a decision fails", async () => {
    vi.spyOn(api, "decideLink").mockRejectedValue(
      new ApiError(409, "proposal 4683 is already decided"),
    );
    render(<MatchList />);
    act(() => matchStore.getState().apply(match()));
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Reject: Delta, Apr 19" }));
    await flush();
    expect(screen.getByRole("alert")).toHaveTextContent("proposal 4683 is already decided");
    expect(screen.getAllByTestId("score-ring")[0]).toHaveAttribute("data-state", "pending");
  });
});
