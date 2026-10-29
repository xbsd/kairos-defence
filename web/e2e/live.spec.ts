// SPEC §20 phase 7: open Live watch, play at 5×, stream rows and recorder totals rise, matches
// appear by T+90, the ledger gains a block; approve; reduce motion; offline (rule 5).
import { expect, test } from "@playwright/test";

import { BASE } from "../playwright.config";
import { headSeq, numberIn, openLive, play, reseed, waitForClock } from "./helpers";

test("streams real data at 5x", async ({ page, request }) => {
  await reseed(request);
  await openLive(page);
  await play(page, 5);
  const total = page.getByTestId("stream-total");
  const recorded = page.getByTestId("recorder-total");
  await waitForClock(page, 6);
  const t1 = await numberIn(total);
  const r1 = await numberIn(recorded);
  await waitForClock(page, 16);
  expect(await numberIn(total)).toBeGreaterThan(t1);
  expect(await numberIn(recorded)).toBeGreaterThan(r1);
  expect(await page.getByTestId("stream-row").count()).toBeGreaterThan(3);
  await expect(page.getByTestId("recorder-statement")).toContainText("INSERT INTO live_");
  await expect(page.getByTestId("theater-summary")).toContainText(/\d+ radar points/);
});

test("matches appear by T+90 and the ledger gains a block", async ({ page, request }) => {
  const seed = await reseed(request);
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 90);
  const entries = page.getByTestId("match-entry");
  await expect(entries).toHaveCount(3);
  for (let i = 0; i < 3; i++) {
    const e = entries.nth(i);
    await expect(e.getByTestId("match-score")).toHaveText(/^\d\.\d\d$/);
    expect(await e.getByTestId("reason-chip").count()).toBeGreaterThan(0);
    await expect(e.getByTestId("memory-status")).not.toBeEmpty();
  }
  const blocks = page.getByTestId("ledger-block");
  await expect
    .poll(async () =>
      Math.max(
        ...(await blocks.evaluateAll((bs) => bs.map((b) => Number(b.getAttribute("data-seq"))))),
      ),
    )
    .toBeGreaterThan(seed);
  await expect(page.getByTestId("ledger-verified")).toContainText("Chain verified");
});

test("approve link adds a block and turns the ring verified", async ({ page, request }) => {
  await reseed(request);
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 50);
  const enabled = page.getByRole("button", { name: /^Approve link/ }).and(page.locator(":enabled"));
  const entry = page.getByTestId("match-entry").filter({ has: enabled }).first();
  const target = entry.getByRole("button", { name: /^Approve link/ });
  await expect(target).toBeEnabled();
  const before = await headSeq(request);
  const incident = await entry.getAttribute("data-incident");
  await target.click();
  const approved = page.locator(`[data-testid="match-entry"][data-incident="${incident}"]`);
  await expect(approved.getByTestId("score-ring")).toHaveAttribute("data-state", "approved");
  expect(await headSeq(request)).toBeGreaterThan(before);
  await expect(
    page.locator(`[data-testid="ledger-block"][data-seq="${before + 1}"]`),
  ).toBeVisible();
});

test.describe("reduce motion", () => {
  test.use({ reducedMotion: "reduce" });
  test("reduce motion keeps the data", async ({ page, request }) => {
    await reseed(request);
    await openLive(page);
    await expect(page.getByTestId("theater")).toHaveAttribute("data-perf", "reduced");
    await play(page, 5);
    await waitForClock(page, 4);
    const t1 = await numberIn(page.getByTestId("stream-total"));
    await waitForClock(page, 12);
    expect(await numberIn(page.getByTestId("stream-total"))).toBeGreaterThan(t1);
  });
});

test("no request leaves the origin", async ({ page, request }) => {
  await reseed(request);
  const foreign: string[] = [];
  page.on("request", (r) => {
    const u = r.url();
    if (!u.startsWith(BASE) && !u.startsWith("ws://127.0.0.1:8765") && !/^(data|blob):/.test(u))
      foreign.push(u);
  });
  page.on("websocket", (ws) => {
    if (!ws.url().startsWith("ws://127.0.0.1:8765/")) foreign.push(ws.url());
  });
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 50);
  await expect(page.getByTestId("match-entry")).toHaveCount(3);
  expect(foreign).toEqual([]);
});
