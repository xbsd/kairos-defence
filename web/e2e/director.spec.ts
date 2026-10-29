// SPEC §20 phase 8 tests and §17.13: Director mode at 5×, every beat's key element, a screenshot
// per beat at 1920 × 1080 and 1440 × 900; Director never commits by itself (rule 8); the keys.
// Phase 9 adds the swarm encore as the ninth beat (the Swarm view).
import { mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import {
  approveAllPending,
  CASE,
  FIGURES,
  INCIDENT,
  clockSeconds,
  headSeq,
  ledgerSince,
  numberIn,
  openLive,
  press,
  reseed,
  startDirector,
  waitBeat,
} from "./helpers";

mkdirSync(FIGURES, { recursive: true });

const pad = (n: number) => String(n).padStart(2, "0");

/** Pause on a beat (Space, the presenter's key), let fades settle, save the screenshot. */
async function shot(page: Page, n: number, id: string, w: number, h: number, pause = true) {
  if (pause) await press(page, " ");
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${FIGURES}/phase08-beat-${pad(n)}-${id}-${w}x${h}.png` });
  if (pause) await press(page, " ");
}

for (const [w, h] of [
  [1440, 900],
  [1920, 1080],
] as const) {
  test(`Director at 5x shows every beat's key element at ${w}x${h}`, async ({ page, request }) => {
    test.setTimeout(240_000);
    await reseed(request);
    await page.setViewportSize({ width: w, height: h });
    await openLive(page);
    await startDirector(page, 5);

    // 1 Detection: the first radar contact
    await expect(page.getByTestId("stream-row").first()).toBeVisible();
    await expect(page.getByTestId("director-caption")).toContainText("First radar contact");
    await shot(page, 1, "detection", w, h);

    // 2 Recording: rows written
    await waitBeat(page, "recording");
    await expect.poll(() => numberIn(page.getByTestId("recorder-total"))).toBeGreaterThan(0);
    await expect(page.getByTestId("director-caption")).toContainText("written as it arrives");
    await shot(page, 2, "recording", w, h);

    // 3 Recognition: the matcher has run
    await waitBeat(page, "recognition");
    await expect(page.getByTestId("match-entry").first()).toBeVisible({ timeout: 30_000 });
    await shot(page, 3, "recognition", w, h);

    // 4 Time warp: three matches, the lens morphs to Warped, three ghosts
    await waitBeat(page, "time-warp");
    await press(page, " ");
    await expect(page.getByTestId("match-entry")).toHaveCount(3);
    await expect(page.getByTestId("lens-curves")).toHaveAttribute("data-mode", "warped", {
      timeout: 15_000,
    });
    await expect(page.getByTestId("ghost-count")).toHaveAttribute("data-n", "3", {
      timeout: 15_000,
    });
    await expect(page.getByTestId("constellation-arc").first()).toBeAttached();
    await expect(page.getByTestId("director-caption")).toContainText("the same shape");
    await shot(page, 4, "time-warp", w, h, false);
    await press(page, " ");

    // 5 Forecast: the zone, its computed label
    await waitBeat(page, "forecast");
    await press(page, " ");
    await expect(page.getByTestId("forecast-label")).toContainText("Predicted recovery zone", {
      timeout: 15_000,
    });
    await expect(page.getByTestId("director-caption")).toContainText("Those flights ended about");
    await shot(page, 5, "forecast", w, h, false);
    await press(page, " ");

    // 6 Recall: the report, its clues, the beam to the road
    await waitBeat(page, "recall");
    await press(page, " ");
    await expect(page.getByTestId("recall-overlay")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("clue-road")).toContainText("County Rd 12");
    await expect(page.getByTestId("zone-note")).toBeVisible();
    await expect(page.getByTestId("recall-beam")).toHaveAttribute("data-on", "true", {
      timeout: 10_000,
    });
    await shot(page, 6, "recall", w, h, false);

    // 7 Known then and now: the Case board (→ only on the page beats)
    await press(page, "ArrowRight");
    await expect(page).toHaveURL(new RegExp(`/cases/${CASE}$`));
    await waitBeat(page, "known");
    await expect(page.getByTestId("case-graph")).toBeVisible();
    await page.getByRole("button", { name: "Known then" }).click();
    const graph = page.getByTestId("case-graph");
    await expect(
      graph.locator('[data-testid="graph-node"][data-kind="assessment"]'),
    ).toHaveAttribute("data-label", "hobbyist");
    await expect(graph.locator('[data-testid="graph-edge"][data-kind="proposed"]')).toHaveCount(0);
    await expect(page.getByTestId("director-caption")).toContainText("closed this as hobbyist");
    await shot(page, 7, "known-then", w, h, false);
    await page.getByRole("button", { name: "Known now" }).click();
    await expect(page.locator('[data-testid="diff-group"][data-group="proposals"]')).toBeVisible();
    await shot(page, 7, "known-now", w, h, false);
    expect(await approveAllPending(page)).toBeGreaterThan(0);
    await expect(page.getByTestId("pending-proposal")).toHaveCount(0);

    // 8 Evidence: a human click and its confirm, five files, checks pass, verify passes
    await press(page, "ArrowRight");
    await expect(page).toHaveURL(new RegExp(`/evidence\\?case=${CASE}$`));
    await waitBeat(page, "evidence");
    await page.getByTestId("evidence-export").click();
    await page.getByRole("button", { name: "Approve and export" }).click();
    await expect(page.getByTestId("evidence-file")).toHaveCount(5, { timeout: 60_000 });
    await expect(page.getByTestId("evidence-done")).toHaveAttribute("data-passed", "true");
    await page.getByRole("button", { name: "Verify package" }).first().click();
    await expect(page.getByTestId("verify-result").first()).toHaveAttribute("data-passed", "true");
    await shot(page, 8, "evidence", w, h, false);

    // 9 Encore (phase 9): the Swarm view; it reads only, so the ledger head does not move
    const before = await headSeq(request);
    await press(page, "ArrowRight");
    await expect(page).toHaveURL(/\/swarm\?incident=DEMO-SWARM-ECHO-0614$/);
    await waitBeat(page, "encore");
    await expect(page.getByTestId("swarm-ghost")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("director-caption")).toContainText(
      "Same choreography, six weeks apart, in another region",
    );
    await shot(page, 9, "encore", w, h, false);
    expect(await headSeq(request)).toBe(before);
  });
}

test("Director never commits by itself", async ({ page, request }) => {
  test.setTimeout(180_000);
  const seed = await reseed(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openLive(page);
  await startDirector(page, 5);
  await waitBeat(page, "recall");
  await press(page, "ArrowRight");
  await waitBeat(page, "known");
  await press(page, "ArrowRight");
  await waitBeat(page, "evidence");
  await page.waitForTimeout(1500);
  const types = new Set(await ledgerSince(request, seed));
  for (const t of types)
    expect(["incident_recorded", "model_registered", "match_proposed"]).toContain(t);
  expect(types.has("match_proposed")).toBe(true);
});

test("Director keys and modes: ←, Space, M, Performance mode, R", async ({ page, request }) => {
  test.setTimeout(180_000);
  const seed = await reseed(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openLive(page);
  await startDirector(page, 5);
  await waitBeat(page, "recall");

  // M keeps every result and caption, drops effects
  await press(page, "m");
  await expect(page.getByTestId("theater")).toHaveAttribute("data-perf", "reduced");
  await expect(page.getByTestId("director-caption")).not.toHaveText("");
  await expect(page.getByTestId("recall-text")).toContainText("County Rd 12");
  await expect(page.getByTestId("forecast-label")).toContainText("Predicted recovery zone");
  await press(page, "m");
  await page.getByRole("button", { name: "Performance mode" }).click();
  await expect(page.getByTestId("theater")).toHaveAttribute("data-perf", "performance");
  await page.getByRole("button", { name: "Performance mode" }).click();
  await expect(page.getByTestId("theater")).not.toHaveAttribute("data-perf", "performance");

  // → to the Case board, ← back to Live watch at the recall beat
  await press(page, "ArrowRight");
  await waitBeat(page, "known");
  await press(page, "ArrowLeft");
  await expect(page).toHaveURL(new RegExp(`/live/${INCIDENT}$`));
  await waitBeat(page, "recall");
  await expect.poll(() => clockSeconds(page), { timeout: 30_000 }).toBeGreaterThanOrEqual(120);

  // Space pauses and resumes
  await expect(page.getByTestId("replay-status")).toHaveText("Paused");
  await press(page, " ");
  await expect(page.getByTestId("replay-status")).toHaveText("Live");
  await press(page, " ");
  await expect(page.getByTestId("replay-status")).toHaveText("Paused");

  // R: live tables emptied, the ledger reseeded, back to T+0 and beat 1
  await press(page, "r");
  await waitBeat(page, "detection");
  await expect.poll(() => clockSeconds(page), { timeout: 15_000 }).toBeLessThanOrEqual(3);
  expect(await headSeq(request)).toBe(seed);
});
