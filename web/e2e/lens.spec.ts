// SPEC §17.7, D-126: the lens connectors follow the real DTW path; same-time connectors join equal
// indices; the readouts are the payload's distances.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { INCIDENT, openLive, pause, play, reseed, waitForClock } from "./helpers";

test("lens connectors follow the DTW path", async ({ page, request }) => {
  test.setTimeout(120_000);
  await reseed(request);
  await openLive(page);
  await play(page, 5);
  await waitForClock(page, 91);
  await pause(page);
  const panel = page.getByTestId("panel-lens");
  await expect(panel.getByTestId("lens-curves")).toBeVisible();
  const track = await panel.getByRole("combobox", { name: "Match" }).inputValue();
  const d = (await (await request.get(`/api/dtw/${INCIDENT}/${track}?at=90`)).json()) as {
    path: [number, number][];
    overlap: number;
    dtw_distance: number;
    euclid_distance: number;
  };
  const pairs = new Set(d.path.map((p) => p.join(",")));
  const read = async () =>
    panel.getByTestId("lens-connector").evaluateAll((els) =>
      els.map((e) => ({
        i: Number(e.getAttribute("data-i")),
        j: Number(e.getAttribute("data-j")),
        shown: e.getAttribute("data-shown") === "true",
      })),
    );
  await panel.getByRole("button", { name: "Warped" }).click();
  await expect(panel.getByTestId("lens-curves")).toHaveAttribute("data-mode", "warped");
  const warped = await read();
  expect(warped.length).toBeGreaterThan(10);
  for (const c of warped) expect(pairs.has(`${c.i},${c.j}`)).toBe(true);
  const keys = new Set(warped.map((c) => `${c.i},${c.j}`));
  expect(keys.has(d.path[0]?.join(",") ?? "")).toBe(true);
  expect(keys.has(d.path[d.path.length - 1]?.join(",") ?? "")).toBe(true);
  await panel.getByRole("button", { name: "Same time" }).click();
  await expect(panel.getByTestId("lens-curves")).toHaveAttribute("data-mode", "same");
  const same = (await read()).filter((c) => c.shown);
  expect(same.length).toBeGreaterThan(0);
  for (const c of same) {
    expect(c.i).toBe(c.j);
    expect(c.i).toBeLessThan(d.overlap);
  }
  await expect(panel.getByTestId("lens-dtw")).toContainText(d.dtw_distance.toFixed(1));
  await expect(panel.getByTestId("lens-euclid")).toContainText(d.euclid_distance.toFixed(1));

  // axe on Live watch with every phase 8 layer showing: lens, constellation, recall overlay
  await play(page, 5);
  await waitForClock(page, 121);
  await pause(page);
  await expect(page.getByTestId("recall-overlay")).toBeVisible();
  const res = await new AxeBuilder({ page }).exclude("canvas").analyze();
  const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual(
    [],
  );
});
