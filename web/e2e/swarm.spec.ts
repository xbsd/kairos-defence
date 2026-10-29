// SPEC §20 phase 9 and §17.13: the Swarm view at both sizes: the demo swarm's best earlier swarm
// is S1-GOLF-260503 (§14), its afterglow ghost and the descriptor curves show, Play advances the
// playhead over the recorded seconds, a screenshot per size, and axe finds nothing serious.
import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { FIGURES } from "./helpers";

mkdirSync(FIGURES, { recursive: true });

const SWARM = "DEMO-SWARM-ECHO-0614";

interface Doc {
  query: { curves: { t_s: number[]; spread_m: (number | null)[] } };
}

for (const [w, h] of [
  [1440, 900],
  [1920, 1080],
] as const) {
  test(`Swarm view at ${w}x${h}`, async ({ page, request }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/swarm"); // no incident: opens the live swarm
    await expect(page).toHaveURL(new RegExp(`/swarm\\?incident=${SWARM}$`), { timeout: 30_000 });
    const first = page.getByTestId("swarm-match").first();
    await expect(first).toHaveAttribute("data-incident", "S1-GOLF-260503", { timeout: 60_000 });
    await expect(first).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("swarm-ghost")).toContainText("Golf");
    for (const id of ["spread", "pairs", "rotation"])
      await expect(page.getByTestId(`swarm-curve-${id}`)).toBeVisible();
    await expect(page.getByTestId("swarm-scene").locator("canvas")).toBeVisible();

    // Play moves the playhead through the recorded seconds; Pause holds it
    const playhead = page.getByTestId("swarm-playhead");
    const t0 = Number(await playhead.getAttribute("data-t"));
    await page.getByTestId("swarm-play").click();
    await expect
      .poll(async () => Number(await playhead.getAttribute("data-t")))
      .toBeGreaterThan(t0 + 5);
    await page.getByTestId("swarm-play").click();
    await expect(page.getByTestId("swarm-play")).toHaveText("Play");

    // the screenshot at tonight's widest formation (the split), the same second every run
    const doc = (await (await request.get(`/api/swarm/${SWARM}`)).json()) as Doc;
    const c = doc.query.curves;
    let best = 0;
    c.spread_m.forEach((v, i) => {
      if ((v ?? -1) > (c.spread_m[best] ?? -1)) best = i;
    });
    await page.getByTestId("swarm-scrubber").fill(String(c.t_s[best]));
    await expect(playhead).toHaveAttribute("data-t", String(c.t_s[best]));
    await page.waitForTimeout(1500); // the follow camera settles
    await page.screenshot({ path: `${FIGURES}/phase09-swarm-${w}x${h}.png` });

    const res = await new AxeBuilder({ page }).exclude("canvas").analyze();
    const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual(
      [],
    );
  });
}
