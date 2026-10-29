// SPEC §20 phase 7 exit check: the median frame rate and the machine it was measured on
// (recorded, not asserted: phase 8 owns >= 50 fps). Written to reports/figures/ui/perf.json.
import { mkdirSync, writeFileSync } from "node:fs";
import os from "node:os";

import { expect, test } from "@playwright/test";

import { FIGURES, openLive, play, reseed, speed, waitForClock } from "./helpers";

test("frame rate over 10 s of 1x playback", async ({ page, request, browserName }) => {
  await reseed(request);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 5);
  await speed(page, 1);
  const frames = await page.evaluate(
    () =>
      new Promise<number[]>((resolve) => {
        const ts: number[] = [];
        const t0 = performance.now();
        const step = (t: number) => {
          ts.push(t);
          if (t - t0 < 10_000) requestAnimationFrame(step);
          else resolve(ts);
        };
        requestAnimationFrame(step);
      }),
  );
  const dts = frames
    .slice(1)
    .map((t, i) => t - (frames[i] ?? t))
    .sort((a, b) => a - b);
  const q = (p: number) => dts[Math.min(dts.length - 1, Math.floor(p * dts.length))] ?? Number.NaN;
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
  const perf = await page.getByTestId("theater").getAttribute("data-perf");
  const out = {
    measured_at: new Date().toISOString(),
    seconds: 10,
    frames: frames.length,
    fps_median: Math.round((1000 / q(0.5)) * 10) / 10,
    fps_p5: Math.round((1000 / q(0.95)) * 10) / 10,
    frame_ms_p50: Math.round(q(0.5) * 100) / 100,
    frame_ms_p95: Math.round(q(0.95) * 100) / 100,
    viewport: "1920x1080",
    browser: `${browserName} ${page.context().browser()?.version() ?? ""}`,
    user_agent: await page.evaluate(() => navigator.userAgent),
    webgl: gl,
    theater_perf_level: perf,
    cpu: os.cpus()[0]?.model ?? "unknown",
    cores: os.cpus().length,
    platform: `${os.platform()} ${os.release()}`,
    memory_gb: Math.round(os.totalmem() / 2 ** 30),
  };
  mkdirSync(FIGURES, { recursive: true });
  writeFileSync(`${FIGURES}/perf.json`, JSON.stringify(out, null, 1) + "\n");
  expect(out.frames).toBeGreaterThan(10);
});
