// The DTW workbench (D-187 to D-189): the slow-motion replay of one rerun's recorded matcher
// computation. On the Live page during a returning-prober flight at 20×, it pins the rerun it
// opened with while newer reruns arrive; after the incident closes, the latest rerun is the one
// the Matches panel shows, and the workbench settles on the same second and the same top 3. Also
// opened from the Match explainer on the replay incident. Live data is reset before and after,
// and the ledger reseeded after, so no other spec sees what this one did.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { FIGURES, INCIDENT } from "./helpers";

async function clean(request: APIRequestContext): Promise<void> {
  expect((await request.post("/api/live/reset")).ok()).toBeTruthy();
}

test.beforeAll(async ({ request }) => clean(request));

test.afterAll(async ({ request }) => {
  await clean(request);
  expect((await request.post("/api/admin/reseed")).ok()).toBeTruthy();
});

function tPlus(t: number): string {
  const s = Math.max(0, Math.floor(t));
  return `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

async function attr(page: Page, name: string): Promise<string> {
  return (await page.getByTestId("workbench").getAttribute(name)) ?? "";
}

/** Let the replay finish at 10 candidates per second. */
async function settle(page: Page): Promise<void> {
  await page.getByTestId("workbench-dialog").getByLabel("Candidates per second").selectOption("10");
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-stage", "done", {
    timeout: 30_000,
  });
}

async function axe(page: Page): Promise<void> {
  const res = await new AxeBuilder({ page }).include("[data-testid=workbench-dialog]").analyze();
  const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

test("the workbench replays a live rerun, pinned, and settles on the Matches panel's", async ({
  page,
}) => {
  test.setTimeout(480_000);
  await page.goto("/live");
  await expect(page.getByTestId("live-mode")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "DTW workbench" })).toHaveCount(0); // no matches
  await expect(page.getByLabel("Scenario", { exact: true })).toHaveValue("returning-prober");
  await page.getByLabel("Base", { exact: true }).selectOption("BRAVO");
  await page.getByLabel("Speed", { exact: true }).selectOption("20");
  await page.getByRole("button", { name: "Launch" }).click();
  const row = page.getByTestId("live-incident").first();
  await expect(row).toHaveAttribute("data-state", "open", { timeout: 90_000 });
  const open = page.getByRole("button", { name: "DTW workbench" });
  await expect(open).toBeEnabled({ timeout: 120_000 });

  // mid-flight: the replay aligns candidates one by one under the rerun it opened with
  await open.click();
  const dialog = page.getByTestId("workbench-dialog");
  await expect(dialog).toBeVisible();
  const pinned = await attr(page, "data-t");
  await expect(
    page.getByRole("heading", { name: /DTW workbench: LIVE-BRAVO-.*, rerun T\+/ }),
  ).toContainText(tPlus(Number(pinned)));
  await expect(page.getByTestId("workbench-headline")).toContainText(
    `Slow-motion replay of rerun ${tPlus(Number(pinned))}`,
  );
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-stage", "align", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-step", /^([3-9]|\d\d)$/, {
    timeout: 10_000,
  });
  await expect(page.getByTestId("workbench-path")).toBeVisible();
  await expect(page.getByTestId("workbench-curves")).toBeVisible();
  await expect(page.getByTestId("workbench-readout")).toContainText("Similarity");
  // newer reruns arrive every second or so at 20×: only offered, never switched to on their own
  await expect(page.getByRole("button", { name: /Newer rerun available/ })).toBeVisible({
    timeout: 30_000,
  });
  expect(await attr(page, "data-t")).toBe(pinned);
  await page.screenshot({ path: `${FIGURES}/phase12-workbench-1440.png` });
  await axe(page);
  await settle(page);
  expect(await attr(page, "data-t")).toBe(pinned);
  await expect(page.getByTestId("workbench-fusion").getByRole("listitem")).toHaveCount(5);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({ path: `${FIGURES}/phase12-workbench-done-1920.png` });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: `${FIGURES}/phase12-workbench-done-1440.png` });
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();

  // closed: no fresh rerun follows, so the latest trace is the rerun the Matches panel shows
  await expect(row).toHaveAttribute("data-state", "closed", { timeout: 300_000 });
  const meta = await page.getByTestId("panel-matchlist").textContent();
  const shown = /At (T\+\d\d:\d\d)/.exec(meta ?? "")?.[1];
  expect(shown).toBeTruthy();
  const top3 = await page
    .getByTestId("match-entry")
    .evaluateAll((els) => els.slice(0, 3).map((e) => e.getAttribute("data-track")));
  await open.click();
  await expect(dialog).toBeVisible();
  await settle(page);
  expect(tPlus(Number(await attr(page, "data-t")))).toBe(shown);
  const fused = await page
    .getByTestId("workbench-fusion")
    .getByRole("listitem")
    .evaluateAll((els) => els.slice(0, 3).map((e) => e.getAttribute("data-track")));
  expect(fused).toEqual(top3);
  await expect(page.getByRole("button", { name: /Newer rerun available/ })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("the workbench from the Match explainer replays that replay second", async ({ page }) => {
  await page.goto(`/explainer?incident=${INCIDENT}&at=90&track=P1-DELTA-260419-T1`);
  await expect(page.getByTestId("contribution-bar").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Watch the matcher work" }).click();
  const dialog = page.getByTestId("workbench-dialog");
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-t", "90");
  await expect(
    page.getByRole("heading", { name: `DTW workbench: ${INCIDENT}, rerun T+01:30` }),
  ).toBeVisible();
  // Pause, then Step: one candidate per click
  await dialog.getByRole("button", { name: "Pause" }).click();
  const s0 = Number(await attr(page, "data-step"));
  await dialog.getByRole("button", { name: "Step" }).click();
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-step", String(s0 + 1));
  await dialog.getByRole("button", { name: "Step" }).click();
  await expect(page.getByTestId("workbench")).toHaveAttribute("data-step", String(s0 + 2));
  await expect(page.getByTestId("workbench-path")).toBeVisible();
  await page.screenshot({ path: `${FIGURES}/phase12-workbench-explainer-1440.png` });
  await axe(page);
  await dialog.getByRole("button", { name: "Play", exact: true }).click();
  await settle(page);
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();
});
