// SPEC §17.9 pages (phase 8): Case board, Match explainer, Shift delta, Eval and Evidence, with a
// screenshot of each at 1920 × 1080 and 1440 × 900 (§17.13).
import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { CASE, FIGURES, INCIDENT, openLive, pause, play, reseed, waitForClock } from "./helpers";

mkdirSync(FIGURES, { recursive: true });

async function shot(page: Page, name: string) {
  const v = page.viewportSize();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${FIGURES}/phase08-page-${name}-${v?.width}x${v?.height}.png` });
}

/** Run the replay past T+90 so the planted case has live proposals (the stream writes them). */
async function proposals(page: Page) {
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 92);
  await pause(page);
}

for (const [w, h] of [
  [1920, 1080],
  [1440, 900],
] as const) {
  test(`phase 8 pages at ${w}x${h}`, async ({ page, request }) => {
    test.setTimeout(180_000);
    await reseed(request);
    await page.setViewportSize({ width: w, height: h });
    await proposals(page);

    // Match explainer: seven bars, both flights, the lens
    await page.goto(`/explainer?incident=${INCIDENT}&at=90&track=P1-DELTA-260419-T1`);
    await expect(page.getByTestId("contribution-bar")).toHaveCount(7);
    await expect(page.getByTestId("flight-tonight")).toBeVisible();
    await expect(page.getByTestId("flight-past-segment")).toBeAttached();
    await expect(page.getByTestId("lens-connector").first()).toBeAttached();
    await shot(page, "explainer");

    // Case board: known then (hobbyist, no links) and known now (proposals in the diff)
    await page.goto(`/cases/${CASE}`);
    await expect(page.getByTestId("case-graph")).toBeVisible();
    await page.getByRole("button", { name: "Known then" }).click();
    const g = page.getByTestId("case-graph");
    await expect(g.locator('[data-testid="graph-node"][data-kind="assessment"]')).toHaveAttribute(
      "data-label",
      "hobbyist",
    );
    await expect(g.locator('[data-testid="graph-edge"][data-kind="proposed"]')).toHaveCount(0);
    await shot(page, "case-then");
    await page.getByRole("button", { name: "Known now" }).click();
    await expect(page.locator('[data-testid="diff-group"][data-group="proposals"]')).toBeVisible();
    await expect(
      g.locator('[data-testid="graph-edge"][data-kind="proposed"]').first(),
    ).toBeAttached();
    await shot(page, "case-now");

    // Shift delta: groups, and a case item opens its Case board
    await page.goto("/delta");
    await expect(page.getByTestId("delta-group").first()).toBeVisible();
    await expect(page.locator('[data-testid="delta-group"][data-group="proposals"]')).toBeVisible();
    await shot(page, "delta");
    await page.locator(`a[href^="/cases/${CASE}?focus="]`).first().click();
    await expect(page).toHaveURL(new RegExp(`/cases/${CASE}\\?focus=`));
    await expect(page.getByTestId("case-graph")).toBeVisible();

    // Eval: tiles from the targets, the charts, six demo rows as written
    await page.goto("/eval");
    await expect(page.getByTestId("eval-tile").first()).toBeVisible();
    expect(await page.getByTestId("eval-tile").count()).toBeGreaterThanOrEqual(10);
    await expect(page.getByTestId("demo-row")).toHaveCount(6);
    await expect(page.getByTestId("chart-forecast")).toBeVisible();
    await shot(page, "eval");

    // Evidence: export (confirm), then the package is listed
    await page.goto(`/evidence?case=${CASE}`);
    await page.getByTestId("evidence-export").click();
    await page.getByRole("button", { name: "Approve and export" }).click();
    await expect(page.getByTestId("evidence-file")).toHaveCount(5, { timeout: 60_000 });
    await expect(page.getByTestId("evidence-package")).toHaveCount(1);
    await shot(page, "evidence");
    const list = (await (await request.get(`/api/evidence?case=${CASE}`)).json()) as unknown[];
    expect(list).toHaveLength(1);
  });
}
