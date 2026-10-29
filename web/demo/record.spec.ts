// The two-minute demo video (make demo-video, D-168): Director mode drives the story beat by beat,
// the recorder pauses on each beat while the narration overlay rings the element that matters and
// says how it works, and a visible pointer makes every click a person would make. Every number in
// a callout is read from the screen at that moment. Frames are captured in slow motion (kit.ts)
// and encoded by demo/encode.mjs.
import { rmSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { Capture, K, Narrator, v } from "./kit";
import { installOverlay } from "./overlay";
import { installTimeShim } from "./timeshim";

const INCIDENT = "DEMO-BRAVO-0828";
const CHAPTERS = 9;
const LONG = 600_000; // wall-clock waits: K times longer than the video's

async function press(page: Page, key: string): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
  await page.keyboard.press(key);
}

async function waitBeat(page: Page, id: string): Promise<void> {
  await expect(page.locator(`[data-testid="director-beat"][data-beat="${id}"]`)).toHaveCount(1, {
    timeout: LONG,
  });
  await expect(page.getByTestId("director-caption")).not.toHaveText("", { timeout: LONG });
}

async function paused(page: Page, want: boolean): Promise<void> {
  if ((await page.getByTestId("replay-status").textContent())?.includes("Paused") !== want) {
    await press(page, " ");
  }
  await expect(page.getByTestId("replay-status")).toHaveText(want ? "Paused" : "Live", {
    timeout: LONG,
  });
}

/** The visible text of the first match (screen-reader-only ids in parentheses dropped). */
const text = async (page: Page, sel: string) =>
  ((await page.locator(sel).first().innerText()) ?? "")
    .replace(/\s+/g, " ")
    .replace(/\s*\([A-Z0-9-]+\)\s*$/, "")
    .trim();

test("record the demo video", async ({ page }) => {
  test.setTimeout(60 * 60_000);
  await page.addInitScript(installTimeShim, K);
  await page.addInitScript(installOverlay);
  rmSync("../data/cache/demo/exports", { recursive: true, force: true });
  expect((await page.request.post("/api/admin/reseed")).ok()).toBeTruthy();
  expect((await page.request.post("/api/admin/reset")).ok()).toBeTruthy();

  const n = new Narrator(page);
  const cap = new Capture(page);
  const chapter = async (i: number, name: string, line: string) => {
    cap.mark(name);
    await n.progress(i / CHAPTERS);
    await n.chapter(i, CHAPTERS, name, line);
  };
  await page.goto(`/live/${INCIDENT}`);
  await expect(page.getByLabel("Live theater", { exact: true })).toBeVisible({ timeout: LONG });
  await expect(page.getByTestId("replay-status")).toHaveText(/Paused|Live/, { timeout: LONG });
  await page.waitForTimeout(4_000); // the scene, the fonts and the ledger panel settle

  // ---- Intro -------------------------------------------------------------------------------
  await cap.start();
  try {
    await story(page, n, cap, chapter);
  } finally {
    await cap.stop(); // the manifest is written even when a take fails, for the review
  }
});

async function story(
  page: Page,
  n: Narrator,
  cap: Capture,
  chapter: (i: number, name: string, line: string) => Promise<void>,
): Promise<void> {
  await n.title({
    kicker: "Kairos Defense",
    title: "Have we seen this drone before?",
    sub:
      "One shared memory of every drone flight, across every installation: " +
      "matched live, recalled in seconds, remembered for good.",
    foot: "All data synthetic · runs offline · DuckDB + LanceDB",
    instant: true,
  });
  cap.mark("start");
  await n.hold(5.6);

  // ---- 1 Detect ------------------------------------------------------------------------------
  await n.hideTitle();
  await chapter(1, "Detect", "Live sensors stream in");
  await page.getByRole("button", { name: "Speed 5 times" }).click();
  await press(page, "d");
  await waitBeat(page, "detection");
  await n.hold(0.8);
  await n.callout("stream", page.getByTestId("panel-stream"), {
    side: "at",
    at: { x: 24, y: 300 },
    kicker: "Live",
    title: "Every detection, as it arrives",
    body:
      "Radar, radio and Remote ID from BRAVO's sensors stream in <b>second by second</b> " +
      "and are written to DuckDB the moment they land.",
    tone: "flash",
    width: 390,
  });
  await waitBeat(page, "recording");
  await n.uncallout("stream");
  await n.callout(
    "record",
    [page.getByTestId("panel-recorder"), page.getByTestId("panel-ledgerchain")],
    {
      side: "at",
      at: { x: 1004, y: 118 },
      kicker: "Recorded",
      title: "A memory that can't be rewritten",
      body:
        "Each row is written the moment it lands, and every case event is appended to a " +
        "<b>hash-chained ledger</b>: each block carries the hash of the one before.",
      tone: "flash",
      width: 400,
    },
  );
  await n.hold(4.2);

  // ---- 2 Recognize ---------------------------------------------------------------------------
  await waitBeat(page, "recognition");
  await paused(page, true);
  await n.clear();
  await chapter(2, "Recognize", "Shape matching across every base");
  await n.hold(0.6);
  const top = await text(page, '[data-testid="match-entry"] h3');
  await n.callout("matches", page.getByTestId("panel-matchlist"), {
    side: "left",
    kicker: "Have we seen this before?",
    title: "45 seconds of track is enough",
    body:
      "Its shape is compared with <b>every past flight at all 12 bases</b>, then weighed with " +
      `radio family, time of night, bearing and launch area. Best so far: ${v(top)}.`,
    tone: "afterglow",
    width: 410,
  });
  await n.hold(4.6);
  await paused(page, false);
  await n.hold(2.2);
  await n.uncallout("matches");
  await n.callout("rerun", page.getByTestId("panel-matchlist"), {
    side: "left",
    kicker: "Live re-ranking",
    title: "The ranking firms up as the track grows",
    body: "The matcher reruns every few seconds on the points seen so far, never on the future.",
    tone: "afterglow",
    width: 410,
  });

  // ---- 3 Time warp ---------------------------------------------------------------------------
  await waitBeat(page, "time-warp");
  await paused(page, true);
  await n.clear();
  await chapter(3, "Time warp", "Dynamic time warping aligns the flights");
  await expect(page.getByTestId("lens-curves")).toHaveAttribute("data-mode", "warped", {
    timeout: LONG,
  });
  const match = await page
    .locator('select[aria-label="Match"]')
    .evaluate((s: HTMLSelectElement) => s.options[s.selectedIndex]?.text ?? "");
  const pace = await text(page, '[data-testid="lens-pace"]');
  await n.callout("lens", page.getByTestId("panel-lens"), {
    side: "left",
    kicker: "Dynamic time warping",
    title: "Same shape, different pace",
    body:
      "DTW stretches time until the two tracks line up, so a flight flown faster still " +
      `matches. Here: ${v(match)}, ${v(pace.toLowerCase())}. The amber ghosts are the matched ` +
      "flights, replayed in tonight's frame.",
    tone: "afterglow",
    width: 420,
  });
  await n.hold(6.4);

  // ---- 4 Anticipate --------------------------------------------------------------------------
  await paused(page, false);
  await waitBeat(page, "forecast");
  await paused(page, true);
  await n.clear();
  await chapter(4, "Anticipate", "Where will it land?");
  await n.hold(0.8);
  await n.callout("forecast", null, {
    side: "at",
    at: { x: 24, y: 120 },
    kicker: "Analog forecast",
    title: "Where those flights ended",
    body:
      "The matched flights' recovery points, weighted by how well each matched, become " +
      "tonight's <b>predicted recovery zone</b>, with the roads that cross it.",
    tone: "bone",
    width: 400,
  });
  await n.hold(4.6);

  // ---- 5 Recall ------------------------------------------------------------------------------
  await paused(page, false);
  await waitBeat(page, "recall");
  await paused(page, true);
  await n.clear();
  await chapter(5, "Recall", "The report nobody connected");
  await expect(page.getByTestId("recall-overlay")).toBeVisible({ timeout: LONG });
  await n.hold(1.0);
  const which = await text(page, '[data-testid="recall-overlay"] p.text-12');
  const road = await text(page, '[data-testid="recall-text"] [data-zone="true"]');
  await n.callout("recall", page.getByTestId("recall-overlay"), {
    side: "top",
    kicker: "Hybrid search",
    title: "Meaning and keywords, at once",
    body:
      `Reports about the matched flights are searched both ways: ${v(which)}. ` +
      `Its clue, ${v(road)}, runs through tonight's zone.`,
    tone: "afterglow",
    width: 420,
  });
  await n.hold(5.6);

  // ---- 6 Remember: the Case board ------------------------------------------------------------
  await n.clear();
  await press(page, "ArrowRight");
  await waitBeat(page, "known");
  await expect(page.getByTestId("case-graph")).toBeVisible({ timeout: LONG });
  await chapter(6, "Remember", "What was known then, and what is known now");
  await n.hold(0.8);
  const knownThen = page.getByRole("button", { name: "Known then" });
  await n.click(knownThen);
  const asOf = (await text(page, '[data-testid="scrub-time"]')).replace(/^As of\s*/i, "");
  await n.callout("then", page.getByTestId("scrubber"), {
    side: "at",
    at: { x: 100, y: 268 },
    kicker: "Bitemporal memory",
    title: "Back to the morning DELTA closed it",
    body:
      `As of ${v(asOf)}: one flight, assessed ` +
      "<b>hobbyist</b>, case closed, no links. Every fact keeps two times: when it was true, " +
      "and when the memory learned it.",
    tone: "afterglow",
    width: 440,
  });
  await n.hold(4.4);
  await n.uncallout("then");
  await n.click(page.getByRole("button", { name: "Known now" }));
  await n.hold(0.6);
  await n.callout("now", page.getByTestId("case-diff"), {
    side: "left",
    kicker: "Known now",
    title: "Tonight changed the picture",
    body:
      "The matcher proposed links to the same pattern at other bases. Proposals, not facts: " +
      "nothing joins the case until an analyst says so.",
    tone: "afterglow",
    width: 410,
  });
  await n.hold(3.6);
  await n.uncallout("now");
  await n.callout("approve", page.getByTestId("case-controls"), {
    side: "left",
    kicker: "Humans decide",
    title: "Each approval is a signed event",
    body: "Approving appends a new ledger block; nothing is ever updated or deleted.",
    tone: "verified",
    width: 400,
  });
  for (let guard = 0; guard < 6; guard++) {
    const b = page.getByRole("button", { name: /^Approve link: / }).first();
    if (!(await b.count())) break;
    const before = await page.getByTestId("pending-proposal").count();
    await n.click(b, 520);
    await expect
      .poll(() => page.getByTestId("pending-proposal").count(), { timeout: LONG })
      .toBeLessThan(before);
  }
  await n.hold(1.6);

  // ---- 7 Prove: Evidence ---------------------------------------------------------------------
  await n.clear();
  await n.cursorHide();
  await press(page, "ArrowRight");
  await waitBeat(page, "evidence");
  await expect(page.getByTestId("evidence-export")).toBeVisible({ timeout: LONG });
  await chapter(7, "Prove", "Signed, verifiable evidence");
  await n.hold(0.6);
  await n.click(page.getByTestId("evidence-export"));
  await n.click(page.getByRole("button", { name: "Approve and export" }), 520);
  await expect(page.getByTestId("evidence-done")).toHaveAttribute("data-passed", "true", {
    timeout: LONG,
  });
  await n.hold(0.6);
  const checks = page.getByTestId("evidence-check");
  await n.callout("checks", page.getByTestId("evidence-done"), {
    side: "right",
    kicker: "Evidence package",
    title: "Signed and hash-chained",
    body:
      `Every file hashed, the manifest signed with <b>Ed25519</b>, the chain recomputed: ` +
      `${v(String(await checks.count()))} checks pass. Change one byte and they fail.`,
    tone: "verified",
    width: 380,
  });
  await n.hold(2.6);
  await n.click(page.getByRole("button", { name: "Verify package" }).first(), 600);
  await expect(page.getByTestId("verify-result").first()).toHaveAttribute("data-passed", "true", {
    timeout: LONG,
  });
  await n.hold(2.4);

  // ---- 8 Swarms: the encore ------------------------------------------------------------------
  await n.clear();
  await n.cursorHide();
  await press(page, "ArrowRight");
  await waitBeat(page, "encore");
  await expect(page.getByTestId("swarm-ghost")).toBeVisible({ timeout: LONG });
  await chapter(8, "Swarms", "Formations have fingerprints too");
  await n.hold(1.2);
  const best = await text(page, '[data-testid="swarm-match"] span.truncate');
  await n.callout("swarm", page.getByTestId("swarm-curves"), {
    side: "left",
    kicker: "Choreography matching",
    title: "Same dance, six weeks apart",
    body:
      "Spread, spacing and rotation of the formation, second by second, aligned with DTW. " +
      `Best match: ${v(best.replace(/\s*\(.*\)\s*$/, ""))}.`,
    tone: "afterglow",
    width: 420,
  });
  await n.hold(6.6);

  // ---- 9 Measured: Eval ----------------------------------------------------------------------
  await n.clear();
  await press(page, "d"); // Director off; the pages stay
  await n.click(page.locator("summary", { hasText: "Pages" }), 600);
  await n.click(page.getByRole("link", { name: "Eval", exact: true }), 500);
  await expect(page.getByTestId("eval-tile").first()).toBeVisible({ timeout: LONG });
  await n.cursorHide();
  await chapter(9, "Measured", "Every number scored against ground truth");
  const tiles = page.getByTestId("eval-tile");
  const tile = async (i: number) => ((await tiles.nth(i).innerText()).split("\n")[1] ?? "").trim();
  await n.hold(0.6);
  await n.callout("eval", [tiles.nth(0), tiles.nth(9)], {
    side: "bottom",
    kicker: "Measured, not claimed",
    title: "Scored by make eval",
    body:
      `Recall@5 ${v(await tile(0))} · DTW lift ${v(await tile(1))} · forecast error ` +
      `${v(await tile(7))} · swarm top-1 ${v(await tile(9))}, against ground truth that only ` +
      "the evaluation may read.",
    tone: "verified",
    spotlight: true,
    width: 560,
  });
  await n.hold(5.4);

  // ---- Outro ---------------------------------------------------------------------------------
  await n.clear();
  await n.hideChapter();
  await n.progress(1);
  await n.title({
    kicker: "Kairos Defense",
    title: "Recognize · Recall · Anticipate · Remember",
    sub: "One memory of every drone flight, across every installation.",
    foot: "All data synthetic · offline · make demo",
  });
  await n.hold(5.2);
  cap.mark("end");
}
