// The demo video recorder's own Playwright run (make demo-video, D-168): its own API on :8766 with
// scratch ledger, live and export files under data/cache/demo, so it never touches the real ledger
// and never collides with `make demo` (:8000) or `make e2e` (:8765).
import { defineConfig, devices } from "@playwright/test";

export const PORT = 8766;
/** Slow-motion factor (kit.ts reads the same variable): the API's replays run at 1/K. */
const K = Number(process.env.DEMO_SLOW ?? 5);

export default defineConfig({
  testDir: ".",
  testMatch: /\.spec\.ts$/,
  outputDir: "../test-results/demo",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 900_000,
  expect: { timeout: 60_000 },
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    actionTimeout: 120_000, // a click that cannot happen fails the take instead of hanging it
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
        launchOptions: { args: ["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"] },
      },
    },
  ],
  webServer: {
    command:
      `uv run kairos-defense api --static web/dist --port ${PORT} ` +
      "--memory data/cache/demo/memory.duckdb --live-db data/cache/demo/live.duckdb " +
      `--exports data/cache/demo/exports --reseed --time-scale ${1 / K}`,
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/health`,
    timeout: 240_000,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
  },
});
