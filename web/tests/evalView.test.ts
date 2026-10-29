import { describe, expect, it } from "vitest";

import {
  demoRows,
  forecastErrors,
  formatValue,
  histogram,
  recallSeries,
  tiles,
} from "../src/eval/evalView";
import { EVAL } from "./real";

describe("Eval view model (D-140)", () => {
  it("reads pass, gap, report only and pending from the targets the eval wrote", () => {
    const ts = tiles(EVAL);
    if (!ts) throw new Error("no targets in the fixture");
    const by = Object.fromEntries(ts.map((t) => [t.key, t]));
    expect(by.recall_at_5_t120?.status).toBe("pass");
    expect(by.latency_dtw_p95_ms?.status).toBe("report only");
    expect(by.swarm_top1?.status).toBe("pending");
    expect(by.swarm_top1?.target).toBe("≥ 0.80 (phase 9)");
    expect(by.forecast_median_t90_m?.value).toBe("340 m");
    const gap = tiles({ ...EVAL, metrics: { ...EVAL.metrics, recall_at_5_t120: 0.5 } });
    expect(gap?.find((t) => t.key === "recall_at_5_t120")?.status).toBe("gap");
    expect(tiles({ ...EVAL, targets: undefined } as never)).toBeNull(); // a stale report
  });

  it("formats values as the targets do", () => {
    expect(formatValue(0.5217, "signed")).toBe("+0.52");
    expect(formatValue(0.05, "pct")).toBe("5%");
    expect(formatValue(117.2, "ms")).toBe("117 ms");
    expect(formatValue(null, "ratio")).toBe("–");
  });

  it("bins forecast errors from 0 in equal widths", () => {
    expect(histogram([0, 50, 99, 100, 250, Number.POSITIVE_INFINITY], 100)).toEqual([
      { lo: 0, hi: 100, n: 3 },
      { lo: 100, hi: 200, n: 1 },
      { lo: 200, hi: 300, n: 1 },
    ]);
    expect(histogram([], 100)).toEqual([]);
    const errs = forecastErrors(EVAL, 90);
    expect(errs.length).toBeGreaterThan(5);
    expect(histogram(errs, 100).reduce((a, b) => a + b.n, 0)).toBe(errs.length);
  });

  it("keeps the demo rows as written, the accepted gap included", () => {
    const rows = demoRows(EVAL);
    expect(rows).toHaveLength(6);
    expect(rows.find((r) => r.key === "live_top3_incidents")?.word).toBe("Fail");
    expect(rows.find((r) => r.key === "swarm_top1")?.word).toMatch(/^Pending/);
    expect(recallSeries(EVAL).map((r) => r.t)).toEqual([45, 60, 90, 120, 180]);
  });
});
