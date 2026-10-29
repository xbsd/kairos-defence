// The ledger chain panel's state (SPEC §17.6): blocks by seq, the verify result, the open record.
import { createStore } from "zustand/vanilla";

import type { LedgerBlock, LedgerRecord, LedgerVerify } from "../api/messages";

export const BLOCKS_KEEP = 24;

export interface CaseState {
  blocks: LedgerBlock[];
  /** performance.now() when each block arrived live (the slide-in and connector draw). */
  arrived: Record<number, number>;
  verify: LedgerVerify | null;
  verifyError: string | null;
  selected: LedgerRecord | null;
}

export interface CaseActions {
  addBlocks: (bs: LedgerBlock[], live?: boolean, now?: number) => void;
  setVerify: (v: LedgerVerify | null, error?: string | null) => void;
  select: (r: LedgerRecord | null) => void;
  reset: () => void;
}

export const caseStore = createStore<CaseState & CaseActions>()((set, get) => ({
  blocks: [],
  arrived: {},
  verify: null,
  verifyError: null,
  selected: null,
  addBlocks: (bs, live = false, now = performance.now()) => {
    const s = get();
    const by = new Map(s.blocks.map((b) => [b.seq, b]));
    const arrived = { ...s.arrived };
    for (const b of bs) {
      if (live && !by.has(b.seq)) arrived[b.seq] = now;
      by.set(b.seq, b);
    }
    const blocks = [...by.values()].sort((a, b) => a.seq - b.seq).slice(-BLOCKS_KEEP);
    set({ blocks, arrived });
  },
  setVerify: (verify, verifyError = null) => set({ verify, verifyError }),
  select: (selected) => set({ selected }),
  reset: () => set({ blocks: [], arrived: {}, verify: null, verifyError: null, selected: null }),
}));

/** The chain head the panel shows (highest seq). */
export function headSeq(s: CaseState): number | null {
  return s.blocks.length ? (s.blocks[s.blocks.length - 1]?.seq ?? null) : null;
}
