// SPEC §17.12: every route renders the command bar; axe finds no serious or critical violation;
// at 1440 × 900 nothing scrolls sideways and both rails show; below 1280 px the rails stack.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { CASE, INCIDENT, openLive, reseed } from "./helpers";

const ROUTES = [
  `/live/${INCIDENT}`,
  "/explainer",
  `/explainer?incident=${INCIDENT}&at=90&track=P1-DELTA-260419-T1`,
  "/cases",
  `/cases/${CASE}`,
  "/swarm",
  "/evidence",
  "/delta",
  "/eval",
];

/** What each page shows once loaded (axe runs on the page as the user sees it). */
const READY: Record<string, string> = {
  "/explainer": "contribution-bar",
  "/cases": "case-list",
  "/evidence": "evidence-export",
  "/delta": "delta-group",
  "/eval": "eval-tile",
};

for (const route of ROUTES) {
  test(`axe and the command bar on ${route}`, async ({ page, request }) => {
    if (route.startsWith("/live")) {
      await reseed(request);
      await openLive(page);
    } else {
      await page.goto(route);
      const path = route.split("?")[0] ?? route;
      const ready = path.startsWith("/cases/") ? "case-graph" : READY[path];
      if (ready) await expect(page.getByTestId(ready).first()).toBeVisible({ timeout: 30_000 });
    }
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(
      "Kairos Defense",
    );
    const res = await new AxeBuilder({ page }).exclude("canvas").analyze();
    const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual(
      [],
    );
  });
}

test("the root opens Live watch for the live incident", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(new RegExp(`/live/${INCIDENT}$`));
});

test("layout holds at 1440 x 900", async ({ page, request }) => {
  await reseed(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openLive(page);
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(sideways).toBe(false);
  for (const name of ["Memory rail", "Instrument rail", "Live theater"]) {
    await expect(page.getByLabel(name, { exact: true })).toBeInViewport();
  }
});

test("rails stack under the theater below 1280 px", async ({ page, request }) => {
  await reseed(request);
  await page.setViewportSize({ width: 1200, height: 900 });
  await openLive(page);
  const theater = await page.getByLabel("Live theater", { exact: true }).boundingBox();
  const memory = await page.getByLabel("Memory rail", { exact: true }).boundingBox();
  const instruments = await page.getByLabel("Instrument rail", { exact: true }).boundingBox();
  if (!theater || !memory || !instruments) throw new Error("a region is not rendered");
  expect(memory.y).toBeGreaterThanOrEqual(theater.y + theater.height - 1);
  expect(instruments.y).toBeGreaterThanOrEqual(memory.y + memory.height - 1);
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(sideways).toBe(false);
});

test("shortcuts dialog lists M and closes with Escape", async ({ page }) => {
  await page.goto("/cases");
  await expect(page.getByRole("heading", { name: "Case board" })).toBeVisible();
  await page.locator("body").press("?");
  const dialog = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Reduce motion");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
