// SPEC §20 phase 8 exit check: Director mode at 1× through every §1.2 row with times recorded,
// and the median frame rate (≥ 50 fps on the dev machine's GPU). Writes
// reports/figures/ui/director_1x.json (D-145). Arrow keys are pressed only on the page beats:
// on a clock beat → would seek, and the recorded times would not be natural 1× playback.
import { mkdirSync, writeFileSync } from "node:fs";
import os from "node:os";

import { expect, test, type Page } from "@playwright/test";

import { FIGURES, openLive, press, reseed, startDirector, waitBeat } from "./helpers";

interface Sample {
  now: number; // page performance.now(), ms
  beat: string | null;
  t: string | null; // the replay clock text
  local: string | null;
}

async function sample(page: Page): Promise<Sample> {
  return page.evaluate(() => {
    const b = document.querySelector('[data-testid="director-beat"]');
    const c = document.querySelector('[data-testid="replay-clock"]');
    return {
      now: performance.now(),
      beat: b?.getAttribute("data-beat") ?? null,
      t: c?.textContent ?? null,
      local: c?.getAttribute("data-local-time") ?? null,
    };
  });
}

function seconds(t: string | null): number | null {
  const m = /T\+(\d+):(\d+)/.exec(t ?? "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

const KEY: Record<string, string> = {
  detection: '[data-testid="stream-row"]',
  recording: '[data-testid="recorder-total"]',
  recognition: '[data-testid="match-entry"]',
  "time-warp": '[data-testid="lens-curves"][data-mode="warped"]',
  forecast: '[data-testid="forecast-label"]',
  recall: '[data-testid="recall-overlay"]',
  known: '[data-testid="case-graph"]',
  evidence: '[data-testid="evidence-export"]',
};

test("Director at 1x through every §1.2 row", async ({ page, request, browserName }) => {
  test.setTimeout(8 * 60_000);
  await reseed(request);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openLive(page);
  // frame times for the whole Live watch part of the run
  await page.evaluate(() => {
    const w = window as unknown as { __frames: number[] };
    w.__frames = [];
    const step = (t: number) => {
      w.__frames.push(t);
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
  await startDirector(page, 1);
  const t0 = (await sample(page)).now;

  const beats: Record<string, { at: Sample; key_visible_ms: number | null; key_t: number | null }> =
    {};
  let loiter: number | null = null;
  const order = ["detection", "recording", "recognition", "time-warp", "forecast", "recall"];
  const deadline = Date.now() + 5 * 60_000;
  while (Date.now() < deadline) {
    const s = await sample(page);
    if (s.beat && !beats[s.beat]) beats[s.beat] = { at: s, key_visible_ms: null, key_t: null };
    for (const [id, b] of Object.entries(beats)) {
      if (b.key_visible_ms !== null) continue;
      const sel = KEY[id];
      if (!sel) continue;
      // the forecast label's DOM twin is visually hidden (the 3D label is in the canvas)
      const shown =
        id === "forecast"
          ? (await page.locator(sel).count()) > 0
          : await page
              .locator(sel)
              .first()
              .isVisible()
              .catch(() => false);
      if (shown) {
        b.key_visible_ms = s.now - t0;
        b.key_t = seconds(s.t);
      }
    }
    if (loiter === null) {
      const l = page.getByTestId("signals-loiter");
      if (await l.count()) loiter = Number(await l.getAttribute("data-t"));
    }
    if (beats.recall?.key_visible_ms != null) break;
    await page.waitForTimeout(100);
  }
  for (const id of order) expect(beats[id], `beat ${id}`).toBeTruthy();
  await page.waitForTimeout(6000); // frames for the recall beat too (still 1× playback)
  const frames = await page.evaluate(() => (window as unknown as { __frames: number[] }).__frames);

  // page beats: → only here
  await press(page, "ArrowRight");
  await waitBeat(page, "known");
  const known = await sample(page);
  await expect(page.locator(KEY.known as string)).toBeVisible();
  beats.known = { at: known, key_visible_ms: (await sample(page)).now - t0, key_t: null };
  await press(page, "ArrowRight");
  await waitBeat(page, "evidence");
  const ev = await sample(page);
  await expect(page.locator(KEY.evidence as string)).toBeVisible();
  beats.evidence = { at: ev, key_visible_ms: (await sample(page)).now - t0, key_t: null };

  // frame rate over the Live watch beats (all, and per beat)
  const stats = (ts: number[]) => {
    const d = ts
      .slice(1)
      .map((t, i) => t - (ts[i] ?? t))
      .sort((a, b) => a - b);
    if (!d.length) return { frames: 0, fps_median: null, fps_p5: null };
    const q = (p: number) => d[Math.min(d.length - 1, Math.floor(p * d.length))] ?? Number.NaN;
    return {
      frames: ts.length,
      fps_median: Math.round((1000 / q(0.5)) * 10) / 10,
      fps_p5: Math.round((1000 / q(0.95)) * 10) / 10,
    };
  };
  const per: Record<string, unknown> = {};
  order.forEach((id, i) => {
    const a = beats[id]?.at.now ?? 0;
    const b = beats[order[i + 1] ?? ""]?.at.now ?? Number.POSITIVE_INFINITY;
    per[id] = stats(frames.filter((t) => t >= a && t < b));
  });
  const all = stats(frames.filter((t) => t >= t0));
  const gl = await page.evaluate(() => {
    const c = document.createElement("canvas").getContext("webgl2");
    if (!c) return { renderer: "no WebGL2", vendor: "" };
    const ext = c.getExtension("WEBGL_debug_renderer_info");
    return {
      renderer: String(
        ext ? c.getParameter(ext.UNMASKED_RENDERER_WEBGL) : c.getParameter(c.RENDERER),
      ),
      vendor: String(ext ? c.getParameter(ext.UNMASKED_VENDOR_WEBGL) : c.getParameter(c.VENDOR)),
    };
  });
  const software = /swiftshader|llvmpipe|software/i.test(gl.renderer);
  const rows = Object.fromEntries(
    Object.entries(beats).map(([id, b]) => [
      id,
      {
        activated_t: seconds(b.at.t),
        activated_clock: b.at.t,
        local_time: b.at.local,
        wall_s: Math.round(((b.at.now - t0) / 1000) * 10) / 10,
        key_visible_wall_s:
          b.key_visible_ms === null ? null : Math.round((b.key_visible_ms / 1000) * 10) / 10,
        key_visible_t: b.key_t,
      },
    ]),
  );
  const out = {
    measured_at: new Date().toISOString(),
    viewport: "1920x1080",
    speed: 1,
    beats: rows,
    t80_orbit: {
      loiter_marker_t: loiter,
      note: "§1.2 T+80 row, observed during the recognition beat",
    },
    encore: "phase 9",
    frame_rate: { overall: all, per_beat: per },
    renderer: gl,
    hardware_renderer: !software,
    browser: `${browserName} ${page.context().browser()?.version() ?? ""}`,
    cpu: os.cpus()[0]?.model ?? "unknown",
    cores: os.cpus().length,
    platform: `${os.platform()} ${os.release()}`,
    memory_gb: Math.round(os.totalmem() / 2 ** 30),
    theater_perf_level: "full until the Case board",
  };
  mkdirSync(FIGURES, { recursive: true });
  writeFileSync(`${FIGURES}/director_1x.json`, JSON.stringify(out, null, 1) + "\n");

  // the §1.2 rows land at their replay seconds (1×: the clock, not wall timers, drives beats)
  expect(rows.detection?.activated_t).toBeLessThanOrEqual(2);
  expect(rows["time-warp"]?.activated_t).toBeGreaterThanOrEqual(90);
  expect(rows.recall?.activated_t).toBeGreaterThanOrEqual(120);
  expect(loiter).not.toBeNull();
  if (software) {
    test.info().annotations.push({
      type: "frame rate",
      description: `software WebGL (${gl.renderer}): ${all.fps_median} fps recorded, the GPU was not used`,
    });
  } else {
    expect(all.fps_median ?? 0).toBeGreaterThanOrEqual(50);
  }
});
