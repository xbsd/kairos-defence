// End-to-end tests (SPEC §17.13, D-113). Playwright starts its own API on :8765 with scratch
// ledger and live files under data/cache/e2e, so it never touches data/memory.duckdb and never
// collides with `make demo` on :8000. One worker: the specs share that server and its ledger.
import { defineConfig, devices } from "@playwright/test";

export const PORT = 8765;
export const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 30_000 },
  reporter: [["list"]],
  use: {
    baseURL: BASE,
    viewport: { width: 1440, height: 900 },
    trace: "off",
    screenshot: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        launchOptions: {
          // Prefer the GPU; allow SwiftShader as the fallback WebGL (recorded in perf.json).
          args: ["--ignore-gpu-blocklist", "--use-angle=metal", "--enable-unsafe-swiftshader"],
        },
      },
    },
  ],
  webServer: {
    command:
      `uv run kairos-defense api --static web/dist --port ${PORT} ` +
      "--memory data/cache/e2e/memory.duckdb --live-db data/cache/e2e/live.duckdb --reseed",
    cwd: "..",
    url: `${BASE}/api/health`,
    timeout: 240_000,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
  },
});
