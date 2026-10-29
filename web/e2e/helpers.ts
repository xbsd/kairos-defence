import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";

export const INCIDENT = "DEMO-BRAVO-0828";
export const FIGURES = "../reports/figures/ui";

/** A clean ledger (seed head) and empty live tables on the e2e server. */
export async function reseed(request: APIRequestContext): Promise<number> {
  const r = await request.post("/api/admin/reseed");
  expect(r.ok()).toBeTruthy();
  expect((await request.post("/api/admin/reset")).ok()).toBeTruthy();
  return ((await r.json()) as { head_seq: number }).head_seq;
}

export async function openLive(page: Page): Promise<void> {
  await page.goto(`/live/${INCIDENT}`);
  await expect(page.getByTestId("replay-status")).toHaveText(/Paused|Live/);
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
