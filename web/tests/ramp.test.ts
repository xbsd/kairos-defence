import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { costPixels, hexToRgb, makeRamp } from "../src/lens/ramp";

function tokenFromCss(name: string): string {
  const css = readFileSync("src/theme/tokens.css", "utf8");
  const m = new RegExp(`${name}:\\s*([^;\\s]+)`).exec(css);
  if (!m?.[1]) throw new Error(`no ${name}`);
  return m[1];
}

describe("the lens ramp (OKLab, scope glass to afterglow)", () => {
  const scope = tokenFromCss("--scope");
  const afterglow = tokenFromCss("--afterglow");
  const ramp = makeRamp(scope, afterglow);

  it("ends on the two tokens", () => {
    expect(ramp(0)).toEqual(hexToRgb(scope));
    expect(ramp(1)).toEqual(hexToRgb(afterglow));
    expect(ramp(-1)).toEqual(ramp(0));
  });

  it("brightens monotonically", () => {
    const lum = (t: number) => ramp(t).reduce((a, b) => a + b, 0);
    for (let t = 0.1; t <= 1; t += 0.1) expect(lum(t)).toBeGreaterThanOrEqual(lum(t - 0.1));
  });

  it("leaves NaN cells transparent", () => {
    const px = costPixels(new Float32Array([0, Number.NaN, 10]), 0, 10, ramp);
    expect(px[3]).toBe(255);
    expect(px[7]).toBe(0);
    expect(Array.from(px.slice(8, 11))).toEqual(hexToRgb(afterglow));
  });
});
