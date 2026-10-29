import { beforeEach, describe, expect, it } from "vitest";

import { toBlock } from "../src/api/messages";
import { BLOCKS_KEEP, caseStore, headSeq } from "../src/state/caseStore";
import { ledger } from "./fixtures";

const s = () => caseStore.getState();

beforeEach(() => s().reset());

describe("caseStore", () => {
  it("sorts and dedupes blocks by seq", () => {
    s().addBlocks([toBlock(ledger(5)), toBlock(ledger(3))]);
    s().addBlocks([toBlock(ledger(4)), toBlock(ledger(5))], true, 100);
    expect(s().blocks.map((b) => b.seq)).toEqual([3, 4, 5]);
    expect(s().arrived).toEqual({ 4: 100 });
    expect(headSeq(s())).toBe(5);
  });

  it("keeps the newest blocks", () => {
    s().addBlocks(Array.from({ length: 40 }, (_, i) => toBlock(ledger(i + 1))));
    expect(s().blocks).toHaveLength(BLOCKS_KEEP);
    expect(s().blocks[0]?.seq).toBe(40 - BLOCKS_KEEP + 1);
  });

  it("holds the verify state and the selected record", () => {
    s().setVerify({ intact: true, first_broken_seq: null, rows: 9, head_seq: 9, head_hash: "h" });
    expect(s().verify?.intact).toBe(true);
    s().setVerify(null, "network down");
    expect(s().verifyError).toBe("network down");
    const rec = {
      ...toBlock(ledger(9)),
      predicate: null,
      object_json: { a: 1 },
      valid_from: null,
      valid_to: null,
      source_type: null,
      source_id: null,
      source_grade: null,
      confidence: null,
      supersedes_seq: null,
    };
    s().select(rec);
    expect(s().selected?.seq).toBe(9);
  });
});
