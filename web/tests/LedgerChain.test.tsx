import { fireEvent, render, screen, within } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/api/client";
import { toBlock, type LedgerRecord } from "../src/api/messages";
import { LedgerChain } from "../src/panels/LedgerChain";
import { caseStore } from "../src/state/caseStore";
import { ledger } from "./fixtures";
import { flush, nth, resetStores, stubDialog } from "./panelKit";

beforeEach(() => {
  resetStores();
  stubDialog();
});
afterEach(() => vi.restoreAllMocks());

function blocks(...seqs: number[]) {
  return seqs.map((s) => toBlock(ledger(s)));
}

describe("LedgerChain", () => {
  it("lists blocks by seq with short hashes and accessible names", async () => {
    render(<LedgerChain />);
    act(() => caseStore.getState().addBlocks(blocks(4683, 4681, 4682)));
    await flush();
    const bs = screen.getAllByTestId("ledger-block");
    expect(bs.map((b) => b.getAttribute("data-seq"))).toEqual(["4681", "4682", "4683"]);
    expect(bs[2]).toHaveAccessibleName("4683 aaaa4683, block 4683, match proposed");
    expect(within(nth(bs, 2)).getByText("aaaa4683")).toBeInTheDocument();
    expect(screen.getAllByTestId("ledger-link")).toHaveLength(2);
  });

  it("shows checking, verified and broken states", async () => {
    render(<LedgerChain />);
    expect(screen.getByTestId("ledger-verified")).toHaveTextContent("Checking");
    act(() =>
      caseStore.getState().setVerify({
        intact: true,
        first_broken_seq: null,
        rows: 4686,
        head_seq: 4686,
        head_hash: "x",
      }),
    );
    await flush();
    expect(screen.getByTestId("ledger-verified")).toHaveTextContent("Chain verified");
    expect(screen.getByTestId("ledger-verified")).toHaveAttribute("data-state", "verified");
    act(() =>
      caseStore.getState().setVerify({
        intact: false,
        first_broken_seq: 7,
        rows: 4686,
        head_seq: 4686,
        head_hash: "x",
      }),
    );
    await flush();
    expect(screen.getByTestId("ledger-verified")).toHaveTextContent("Broken at seq 7");
  });

  it("opens the full record on click and returns focus on close", async () => {
    const rec: LedgerRecord = {
      ...toBlock(ledger(4682)),
      predicate: "member_of",
      object_json: { query_incident: "DEMO-BRAVO-0828", rank: 1 },
      valid_from: "2026-08-29T02:41:36.000Z",
      valid_to: null,
      source_type: "matcher",
      source_id: "fusion-v1",
      source_grade: null,
      confidence: 0.94,
      supersedes_seq: null,
    };
    const spy = vi.spyOn(api, "ledgerRecord").mockResolvedValue(rec);
    render(<LedgerChain />);
    act(() => caseStore.getState().addBlocks(blocks(4681, 4682)));
    await flush();
    const b = nth(screen.getAllByTestId("ledger-block"), 1);
    fireEvent.click(b);
    await flush();
    expect(spy).toHaveBeenCalledWith(4682);
    const dialog = screen.getByTestId("ledger-record");
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByRole("heading")).toHaveTextContent("Ledger record 4682");
    expect(dialog).toHaveTextContent("member_of");
    expect(dialog).toHaveTextContent('"query_incident": "DEMO-BRAVO-0828"');
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await flush();
    expect(screen.queryByTestId("ledger-record")).toBeNull();
    expect(caseStore.getState().selected).toBeNull();
    expect(document.activeElement).toBe(screen.getAllByTestId("ledger-block")[1]);
  });
});
