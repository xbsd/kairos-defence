import { rmSync } from "node:fs";

import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";

export const INCIDENT = "DEMO-BRAVO-0828";
export const CASE = "CASE-P1-DELTA-260419";
export const FIGURES = "../reports/figures/ui";
/** The e2e server's scratch export folder (playwright.config.ts, D-137). */
export const EXPORTS = "../data/cache/e2e/exports";

/** A clean ledger (seed head), empty live tables and no exported packages on the e2e server. */
export async function reseed(request: APIRequestContext): Promise<number> {
  rmSync(EXPORTS, { recursive: true, force: true });
  const r = await request.post("/api/admin/reseed");
  expect(r.ok()).toBeTruthy();
  expect((await request.post("/api/admin/reset")).ok()).toBeTruthy();
  return ((await r.json()) as { head_seq: number }).head_seq;
}

export async function openLive(page: Page): Promise<void> {
  await page.goto(`/live/${INCIDENT}`);
  await expect(page.getByTestId("replay-status")).toHaveText(/Paused|Live/);
  // Live watch is a lazy page: on a slow machine the command bar is ready before its chunk loads.
  await expect(page.getByLabel("Live theater", { exact: true })).toBeVisible({ timeout: 60_000 });
}

export async function play(page: Page, speed: 1 | 2 | 5 = 5): Promise<void> {
  await page.getByRole("button", { name: `Speed ${speed} times` }).click();
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.getByTestId("replay-status")).toHaveText("Live");
}

/** Change the speed only (Play is disabled while playing). */
export async function speed(page: Page, value: 1 | 2 | 5): Promise<void> {
  const b = page.getByRole("button", { name: `Speed ${value} times` });
  await b.click();
  await expect(b).toHaveAttribute("aria-pressed", "true");
}

export async function pause(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByTestId("replay-status")).toHaveText("Paused");
}

/** Seconds on the command bar's replay clock (T+mm:ss). */
export async function clockSeconds(page: Page): Promise<number> {
  const t = (await page.getByTestId("replay-clock").textContent()) ?? "";
  const m = /T\+(\d+):(\d+)/.exec(t);
  return m ? Number(m[1]) * 60 + Number(m[2]) : -1;
}

export async function waitForClock(page: Page, seconds: number, timeoutMs = 90_000) {
  await expect
    .poll(() => clockSeconds(page), { timeout: timeoutMs, intervals: [100] })
    .toBeGreaterThanOrEqual(seconds);
}

export async function numberIn(l: Locator): Promise<number> {
  const t = (await l.textContent()) ?? "";
  const m = /[\d,]+(\.\d+)?/.exec(t);
  return m ? Number(m[0].replaceAll(",", "")) : Number.NaN;
}

export async function headSeq(request: APIRequestContext): Promise<number> {
  const v = (await (await request.get("/api/ledger/verify")).json()) as { head_seq: number };
  return v.head_seq;
}

/** The Director rail's current beat id. */
export async function beatId(page: Page): Promise<string | null> {
  const el = page.getByTestId("director-beat");
  return (await el.count()) ? el.getAttribute("data-beat") : null;
}

export async function waitBeat(page: Page, id: string, timeoutMs = 90_000): Promise<void> {
  await expect(page.locator(`[data-testid="director-beat"][data-beat="${id}"]`)).toHaveCount(1, {
    timeout: timeoutMs,
  });
  await expect(page.getByTestId("director-caption")).not.toHaveText("", { timeout: 10_000 });
}

/** Start Director from Live watch at a speed: set the speed, then press D. */
export async function startDirector(page: Page, v: 1 | 2 | 5): Promise<void> {
  await speed(page, v);
  await press(page, "d");
  await waitBeat(page, "detection");
}

/** Approve every pending proposal on the Case board, one click at a time (a human's clicks). */
export async function approveAllPending(page: Page): Promise<number> {
  let n = 0;
  for (let guard = 0; guard < 12; guard++) {
    const b = page.getByRole("button", { name: /^Approve link: / }).first();
    if (!(await b.count())) break;
    const before = await page.getByTestId("pending-proposal").count();
    await b.click();
    // approving an incident also settles its proposals from earlier reruns (it is now a member)
    await expect
      .poll(() => page.getByTestId("pending-proposal").count(), { timeout: 15_000 })
      .toBeLessThan(before);
    n += 1;
  }
  return n;
}

/** Ledger rows after `seq` (event types), from the tail. */
export async function ledgerSince(request: APIRequestContext, seq: number): Promise<string[]> {
  const head = await headSeq(request);
  if (head <= seq) return [];
  const tail = (await (
    await request.get(`/api/ledger/tail?n=${Math.min(200, head - seq)}`)
  ).json()) as {
    seq: number;
    event_type: string;
  }[];
  return tail.filter((b) => b.seq > seq).map((b) => b.event_type);
}

/** A presenter's key press: nothing keeps focus (a clicked button would take Space for itself). */
export async function press(page: Page, key: string): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
  await page.keyboard.press(key);
}
