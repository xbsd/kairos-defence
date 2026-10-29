// SPEC §17.13: screenshots at the phase 7 moments (D-113: first contact, T+45, T+90, after an
// approval; Director beats arrive in phase 8), at 1920 × 1080 and 1440 × 900.
import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { FIGURES, openLive, pause, play, reseed, waitForClock } from "./helpers";

mkdirSync(FIGURES, { recursive: true });

async function shot(page: Page, moment: string, w: number, h: number) {
  await page.waitForTimeout(1500); // let 1.2 s fades and the 10 Hz panels settle
  await page.screenshot({ path: `${FIGURES}/phase07-${moment}-${w}x${h}.png` });
}

for (const [w, h] of [
  [1920, 1080],
  [1440, 900],
] as const) {
  test(`screenshots at ${w}x${h}`, async ({ page, request }) => {
    await reseed(request);
    await page.setViewportSize({ width: w, height: h });
    await openLive(page);
    await play(page, 2);
    await waitForClock(page, 4);
    await pause(page);
    await shot(page, "first-contact", w, h);
    await play(page, 5);
    await waitForClock(page, 46);
    await pause(page);
    await shot(page, "t045", w, h);
    await play(page, 5);
    await waitForClock(page, 91);
    await pause(page);
    await expect(page.getByTestId("match-entry")).toHaveCount(3);
    await shot(page, "t090", w, h);
    const approve = page
      .getByRole("button", { name: /^Approve link/ })
      .and(page.locator(":enabled"));
    await approve.first().click();
    await expect(page.locator('[data-testid="score-ring"][data-state="approved"]')).toHaveCount(1);
    await shot(page, "approved", w, h);
  });
}
