// Live mode (D-169, D-184): the Live page launches the simulator as a separate process at speed
// 20, an incident opens, matches appear, the incident closes, and "Reveal who flew" shows the
// operator and the verdict (D-170). Live data is reset before and after, and the ledger reseeded
// after, so no other spec sees what this one did.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

import { FIGURES } from "./helpers";

async function clean(request: APIRequestContext): Promise<void> {
  expect((await request.post("/api/live/reset")).ok()).toBeTruthy();
}

test.beforeAll(async ({ request }) => clean(request));

test.afterAll(async ({ request }) => {
  await clean(request);
  expect((await request.post("/api/admin/reseed")).ok()).toBeTruthy();
});

test("a returning prober flown live is recognized and revealed", async ({ page }) => {
  // queued reruns at speed 20 can trail the feed on a slow machine; the close waits for them
  test.setTimeout(420_000);
  await page.goto("/live");
  await expect(page.getByTestId("live-mode")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Live");
  await expect(page.getByTestId("live-idle")).toContainText("Nothing is flying at Bravo");
  await expect(page.getByRole("button", { name: "Speed 1 times" })).toHaveCount(0);

  await expect(page.getByLabel("Scenario", { exact: true })).toHaveValue("returning-prober");
  await expect(page.getByLabel("Prober", { exact: true })).toHaveValue("P1");
  await page.getByLabel("Base", { exact: true }).selectOption("BRAVO");
  await page.getByLabel("Speed", { exact: true }).selectOption("20");
  await page.getByRole("button", { name: "Launch" }).click();
  await expect(page.getByTestId("simulator-state")).toContainText("Simulator running", {
    timeout: 30_000,
  });

  const row = page.getByTestId("live-incident").first();
  await expect(row).toHaveAttribute("data-state", "open", { timeout: 90_000 });
  await expect(page.getByTestId("replay-status")).toContainText("Live feed, 20×");
  await expect(page.getByTestId("live-idle")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Reveal who flew/ })).toHaveCount(0);
  const matches = page.getByRole("list", { name: "Best matches, best first" });
  await expect(matches.getByRole("listitem").first()).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("panel-matchlist")).toContainText(/At T\+0\d:\d\d/);
  await page.screenshot({ path: `${FIGURES}/phase11-live-incident-1440.png` });
  const res = await new AxeBuilder({ page }).exclude("canvas").analyze();
  const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.help}`)).toEqual([]);

  await expect(row).toHaveAttribute("data-state", "closed", { timeout: 300_000 });
  await row.getByRole("button", { name: /Reveal who flew/ }).click();
  const card = page.getByTestId("reveal-card");
  await expect(card).toBeVisible();
  await expect(page.getByTestId("reveal-actor")).toHaveText("P1, County Rd operator", {
    timeout: 30_000,
  });
  await expect(page.getByTestId("reveal-words")).toContainText("P1, County Rd operator.");
  await expect(page.getByTestId("reveal-verdict")).toContainText(/Expectation (met|missed)/);
  await page.screenshot({ path: `${FIGURES}/phase11-live-reveal-1440.png` });
  await card.getByRole("button", { name: "Close" }).click();
  await expect(card).toHaveCount(0);
});
