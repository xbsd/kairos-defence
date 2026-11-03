// Phase 10 (docs/phases/PHASE_10.md, D-163): the user guide's screenshots, captured from the real
// running app by `make e2e` (Playwright's own server, scratch ledger and exports, D-113, D-137)
// into docs/guide/img/. No mock-ups, no editing, no placeholder or loading state: every shot first
// waits for the element that proves its state, then lets fades settle. Every image name is a
// literal in a `snap(page, "…")` call, which tests/unit/test_docs.py reads.
import { mkdirSync } from "node:fs";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  approveAllPending,
  CASE,
  clockSeconds,
  openLive,
  pause,
  play,
  press,
  reseed,
  startDirector,
  waitBeat,
  waitForClock,
} from "./helpers";

const IMG = "../docs/guide/img";
const SWARM = "DEMO-SWARM-ECHO-0614";
mkdirSync(IMG, { recursive: true });

async function snap(page: Page, name: string, settleMs = 1600): Promise<void> {
  await page.waitForTimeout(settleMs); // fades (0.6 s) and camera moves (1.2 s) settle
  await page.screenshot({ path: `${IMG}/${name}.png` });
}

/** Play Live watch at 2x to `t`, pause, and check the clock stopped inside [t, t + 7] (D-154). */
async function playTo(page: Page, t: number): Promise<void> {
  await play(page, 2);
  await waitForClock(page, t);
  await pause(page);
  const at = await clockSeconds(page);
  expect(at).toBeGreaterThanOrEqual(t);
  expect(at).toBeLessThanOrEqual(t + 7);
}

/** Export the case's evidence package (a human's click and confirm) and verify it. */
async function exportAndVerify(page: Page): Promise<void> {
  await page.getByTestId("evidence-export").click();
  await page.getByRole("button", { name: "Approve and export" }).click();
  await expect(page.getByTestId("evidence-done")).toHaveAttribute("data-passed", "true", {
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Verify package" }).first().click();
  await expect(page.getByTestId("verify-result").first()).toHaveAttribute("data-passed", "true");
}

/** The Swarm view at tonight's widest formation (the split), the same second every run. */
async function swarmAtWidest(page: Page, request: APIRequestContext): Promise<void> {
  await page.goto(`/swarm?incident=${SWARM}`);
  await expect(page.getByTestId("swarm-match").first()).toHaveAttribute(
    "data-incident",
    "S1-GOLF-260503",
    { timeout: 60_000 },
  );
  await expect(page.getByTestId("swarm-ghost")).toBeVisible();
  const doc = (await (await request.get(`/api/swarm/${SWARM}`)).json()) as {
    query: { curves: { t_s: number[]; spread_m: (number | null)[] } };
  };
  const c = doc.query.curves;
  let best = 0;
  c.spread_m.forEach((v, i) => {
    if ((v ?? -1) > (c.spread_m[best] ?? -1)) best = i;
  });
  await page.getByTestId("swarm-scrubber").fill(String(c.t_s[best]));
  await expect(page.getByTestId("swarm-playhead")).toHaveAttribute("data-t", String(c.t_s[best]));
}

test("guide: Live watch at T+90 (both sizes) and T+120", async ({ page, request }) => {
  test.setTimeout(300_000);
  await reseed(request);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openLive(page);
  await playTo(page, 90);
  await expect(page.getByTestId("ghost-count")).toHaveAttribute("data-n", "3", { timeout: 20_000 });
  await expect(page.getByTestId("lens-curves")).toBeVisible();
  await snap(page, "live-watch-t090");
  await playTo(page, 120);
  await expect(page.getByTestId("recall-overlay")).toBeVisible({ timeout: 20_000 });
  // the Forecast camera frames the orbit, the recovery zone and County Rd 12 (1.2 s move)
  const forecastCam = page
    .getByRole("group", { name: "Camera" })
    .getByRole("button", { name: "Forecast" });
  await forecastCam.click();
  await expect(forecastCam).toHaveAttribute("aria-pressed", "true");
  await snap(page, "live-watch-t120", 2400);

  await reseed(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openLive(page); // a fresh replay session from T+0
  await playTo(page, 90);
  await expect(page.getByTestId("ghost-count")).toHaveAttribute("data-n", "3", { timeout: 20_000 });
  await snap(page, "live-watch-t090-1440x900");
});

test("guide: the nine Director beats at 1920x1080", async ({ page, request }) => {
  test.setTimeout(360_000);
  await reseed(request);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openLive(page);
  await startDirector(page, 5);
  const held = async (id: string, key: string) => {
    await waitBeat(page, id);
    await press(page, " "); // pause the replay clock on the beat (the presenter's Space)
    await expect(page.getByTestId(key).first()).toBeVisible({ timeout: 30_000 });
  };
  await held("detection", "stream-row");
  await snap(page, "director-01-detection");
  await press(page, " ");
  await held("recording", "recorder-total");
  await snap(page, "director-02-recording");
  await press(page, " ");
  await held("recognition", "match-entry");
  await snap(page, "director-03-recognition");
  await press(page, " ");
  await held("time-warp", "lens-curves");
  await expect(page.getByTestId("lens-curves")).toHaveAttribute("data-mode", "warped", {
    timeout: 15_000,
  });
  await expect(page.getByTestId("ghost-count")).toHaveAttribute("data-n", "3", { timeout: 15_000 });
  await snap(page, "director-04-time-warp");
  await press(page, " ");
  await held("forecast", "forecast-label");
  await snap(page, "director-05-forecast");
  await press(page, " ");
  await held("recall", "recall-overlay");
  await expect(page.getByTestId("recall-beam")).toHaveAttribute("data-on", "true", {
    timeout: 10_000,
  });
  await snap(page, "director-06-recall");
  // the page beats start only on →
  await press(page, "ArrowRight");
  await waitBeat(page, "known");
  await expect(page.getByTestId("case-graph")).toBeVisible();
  await page.getByRole("button", { name: "Known then" }).click();
  await expect(
    page.getByTestId("case-graph").locator('[data-testid="graph-node"][data-kind="assessment"]'),
  ).toHaveAttribute("data-label", "hobbyist");
  await snap(page, "director-07-known");
  await page.getByRole("button", { name: "Known now" }).click();
  expect(await approveAllPending(page)).toBeGreaterThan(0); // the analyst's clicks
  await press(page, "ArrowRight");
  await waitBeat(page, "evidence");
  await exportAndVerify(page);
  await snap(page, "director-08-evidence");
  await press(page, "ArrowRight");
  await waitBeat(page, "encore");
  await expect(page.getByTestId("swarm-ghost")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("director-caption")).toContainText("Same choreography");
  await snap(page, "director-09-encore", 2500);
});

test("guide: the pages at 1920x1080, Eval at 1440x900", async ({ page, request }) => {
  test.setTimeout(360_000);
  await reseed(request);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(`/explainer?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1`);
  await expect(page.getByTestId("contribution-bar").first()).toBeVisible({ timeout: 30_000 });
  await snap(page, "explainer");

  // the live loop proposes links at T+90: Known then has none, Known now shows them
  await openLive(page);
  await playTo(page, 95);
  await page.goto(`/cases/${CASE}`);
  await expect(page.getByTestId("case-graph")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Known then" }).click();
  await expect(
    page.getByTestId("case-graph").locator('[data-testid="graph-node"][data-kind="assessment"]'),
  ).toHaveAttribute("data-label", "hobbyist");
  await snap(page, "case-board-known-then");
  await page.getByRole("button", { name: "Known now" }).click();
  await expect(page.locator('[data-testid="diff-group"][data-group="proposals"]')).toBeVisible();
  await snap(page, "case-board-known-now");
  expect(await approveAllPending(page)).toBeGreaterThan(0);

  await page.goto(`/evidence?case=${CASE}`);
  await exportAndVerify(page);
  await snap(page, "evidence");

  await page.goto("/delta?since=2026-08-28T00:00Z");
  await expect(page.getByTestId("delta-group").first()).toBeVisible({ timeout: 30_000 });
  await snap(page, "shift-delta");

  await page.goto("/eval");
  await expect(page.getByTestId("eval-tile").first()).toBeVisible({ timeout: 30_000 });
  await snap(page, "eval");

  await swarmAtWidest(page, request);
  await snap(page, "swarm-view", 2500);

  await page.goto("/cases");
  await expect(page.getByTestId("case-list")).toBeVisible({ timeout: 30_000 });
  await page.locator("body").press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
  await snap(page, "shortcuts", 600);

  await page.setViewportSize({ width: 1440, height: 900 }); // Eval reflows to three tiles a row
  await page.goto("/eval");
  await expect(page.getByTestId("eval-tile").first()).toBeVisible({ timeout: 30_000 });
  await snap(page, "eval-1440x900");
});

test("guide: live mode at 1920x1080 (launcher, incident, workbench, reveal)", async ({
  page,
  request,
}) => {
  // a live flight at 20×; reruns can trail the feed on a slow machine and the close waits
  test.setTimeout(480_000);
  expect((await request.post("/api/live/reset")).ok()).toBeTruthy();
  try {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("/live");
    await expect(page.getByTestId("live-mode")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("live-idle")).toContainText("Nothing is flying");
    await page.getByLabel("Scenario", { exact: true }).selectOption("new-operator-twice");
    await expect(page.getByLabel("Second base", { exact: true })).toBeVisible();
    await snap(page, "live-mode-launcher", 800);

    await page.getByLabel("Scenario", { exact: true }).selectOption("returning-prober");
    await expect(page.getByLabel("Prober", { exact: true })).toHaveValue("P1");
    await page.getByLabel("Base", { exact: true }).selectOption("BRAVO");
    await page.getByLabel("Speed", { exact: true }).selectOption("20");
    await page.getByRole("button", { name: "Launch" }).click();
    const row = page.getByTestId("live-incident").first();
    await expect(row).toHaveAttribute("data-state", "open", { timeout: 90_000 });
    await expect(page.getByTestId("match-entry")).toHaveCount(3, { timeout: 120_000 });
    await expect(page.getByTestId("panel-matchlist")).toContainText(/At T\+0[1-9]:\d\d/, {
      timeout: 60_000,
    });
    await snap(page, "live-mode-incident");

    // the workbench held at its 8th aligned candidate (Pause, then Step)
    await page.getByRole("button", { name: "DTW workbench" }).click();
    const wb = page.getByTestId("workbench");
    const dialog = page.getByTestId("workbench-dialog");
    await expect(wb).toBeVisible();
    await dialog.getByRole("button", { name: "Pause" }).click();
    if (Number(await wb.getAttribute("data-step")) > 8) {
      await dialog.getByRole("button", { name: "Replay" }).click();
      await dialog.getByRole("button", { name: "Pause" }).click();
    }
    for (let k = 0; k < 12 && Number(await wb.getAttribute("data-step")) < 8; k++)
      await dialog.getByRole("button", { name: "Step" }).click();
    await expect(wb).toHaveAttribute("data-step", "8");
    await expect(page.getByTestId("workbench-path")).toBeVisible();
    await snap(page, "live-mode-workbench", 1200);
    await dialog.getByRole("button", { name: "Close" }).click();

    await expect(row).toHaveAttribute("data-state", "closed", { timeout: 300_000 });
    await row.getByRole("button", { name: /Reveal who flew/ }).click();
    await expect(page.getByTestId("reveal-actor")).toHaveText("P1, County Rd operator", {
      timeout: 30_000,
    });
    await expect(page.getByTestId("reveal-verdict")).toContainText(/Expectation (met|missed)/);
    await snap(page, "live-mode-reveal");
  } finally {
    expect((await request.post("/api/live/reset")).ok()).toBeTruthy();
    await reseed(request);
  }
});
