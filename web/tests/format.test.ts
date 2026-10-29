import { describe, expect, it } from "vitest";

import { baseName, localDate, meters, ms, num, rate, shortHash, tPlus } from "../src/lib/format";

describe("format", () => {
  it("replay time", () => {
    expect(tPlus(62)).toBe("T+01:02");
    expect(tPlus(0)).toBe("T+00:00");
    expect(tPlus(515.9)).toBe("T+08:35");
    expect(tPlus(null)).toBe("T+--:--");
  });
  it("meters", () => {
    expect(meters(812.4)).toBe("812 m");
    expect(meters(2164)).toBe("2,164 m");
    expect(meters(12400)).toBe("12.4 km");
    expect(meters(null)).toBe("–");
  });
  it("short hash, local date, base, rates and ms", () => {
    expect(shortHash("a361b4bf0123")).toBe("a361b4bf");
    expect(localDate("2026-04-19T21:35")).toBe("Apr 19");
    expect(localDate("2026-03-03T21:52")).toBe("Mar 3");
    expect(baseName("DELTA")).toBe("Delta");
    expect(rate(1.44)).toBe("1.4/s");
    expect(ms(0.4234)).toBe("0.42 ms");
    expect(ms(286.2)).toBe("286 ms");
    expect(num(Number.NaN)).toBe("–");
    expect(num(4.66, 1)).toBe("4.7");
  });
});
