import { describe, expect, it } from "vitest";

import { parseCssTimeMs } from "../src/theme/motion";

describe("parseCssTimeMs", () => {
  it("reads ms and s", () => {
    expect(parseCssTimeMs("240ms")).toBe(240);
    expect(parseCssTimeMs(" 1.2s ")).toBe(1200);
  });
  it("rejects non-times", () => {
    expect(parseCssTimeMs("")).toBeNaN();
    expect(parseCssTimeMs("fast")).toBeNaN();
  });
});
