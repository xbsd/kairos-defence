import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setFetch } from "../src/api/client";
import { encoreCaption } from "../src/director/captions";
import { directorStore } from "../src/state/directorStore";
import { sceneStore } from "../src/state/sceneStore";
import { swarmStore } from "../src/state/swarmStore";
import { tableRows } from "../src/swarm/swarmMath";
import { INSTALLATIONS, SWARM, SWARMS } from "./real";

vi.mock("../src/swarm/SwarmScene", () => ({
  SwarmScene: () => <div data-testid="swarm-scene" />,
}));

const { SwarmView } = await import("../src/pages/SwarmView");

const INC = "DEMO-SWARM-ECHO-0614";
const flush = () => act(() => new Promise((r) => setTimeout(r, 150)));

beforeEach(() => {
  sceneStore.getState().setInstallations(INSTALLATIONS);
  setFetch(async (input) => {
    const url = String(input);
    const body = url.startsWith("/api/swarms") ? SWARMS : SWARM;
    return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
  });
});

afterEach(() => {
  directorStore.getState().stop();
  directorStore.setState({ facts: {} });
  swarmStore.getState().setDoc(null);
  setFetch((...args) => fetch(...args));
});

describe("Swarm view (§17.9, real §14 result)", () => {
  it("ranks the earlier swarms and selects the best as the ghost", async () => {
    render(<SwarmView incident={INC} match={null} />);
    await flush();
    const entries = screen.getAllByTestId("swarm-match");
    expect(entries.map((e) => e.getAttribute("data-incident"))[0]).toBe("S1-GOLF-260503");
    expect(entries).toHaveLength(SWARM.matches.length);
    expect(entries[0]).toHaveAttribute("aria-pressed", "true");
    expect(entries[0]).toHaveTextContent("Golf · May 3");
    expect(entries[0]).toHaveTextContent(SWARM.matches[0]?.similarity.toFixed(2) ?? "?");
    expect(entries[0]).toHaveTextContent("5 drones · pace 0.75 (flown 33% faster)");
    expect(screen.getByTestId("swarm-ghost")).toHaveTextContent(
      "Afterglow ghost: Golf · May 3, aligned by DTW (pace 0.75)",
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Swarm view: Echo · Jun 14",
    );
    expect(screen.getByTestId("swarm-detection")).toHaveTextContent(
      "5 drones, flown together for 791 s (a swarm, §14); 820 s of track.",
    );
  });

  it("draws the three descriptor charts with tonight solid and the match dashed, and a table", async () => {
    render(<SwarmView incident={INC} match={null} />);
    await flush();
    for (const id of ["spread", "pairs", "rotation"]) {
      const fig = screen.getByTestId(`swarm-curve-${id}`);
      expect(fig.querySelectorAll("path").length).toBeGreaterThanOrEqual(2);
      expect(within(fig).getByTestId("swarm-curve-match")).toHaveAttribute("stroke-dasharray");
    }
    const legend = screen.getByRole("list", { name: "Legend" });
    expect(legend).toHaveTextContent("Echo · Jun 14 (tonight's swarm)");
    expect(legend).toHaveTextContent("Golf · May 3, aligned by DTW");
    const rows = within(screen.getByTestId("swarm-table")).getAllByRole("row");
    expect(rows).toHaveLength(tableRows(SWARM).length + 1);
  });

  it("gives the encore its computed caption and plays itself only in Director", async () => {
    render(<SwarmView incident={INC} match={null} />);
    await flush();
    const f = directorStore.getState().facts.swarm;
    expect(f).toMatchObject({ weeks: 6, otherRegion: true, matchBase: "Golf", queryBase: "Echo" });
    expect(encoreCaption(f)).toBe(
      "Same choreography, six weeks apart, in another region: Golf on May 3 and Echo on Jun 14.",
    );
    expect(swarmStore.getState().playing).toBe(false);
    fireEvent.click(screen.getByTestId("swarm-play"));
    expect(swarmStore.getState().playing).toBe(true);
    fireEvent.click(screen.getByTestId("swarm-play"));
    expect(swarmStore.getState().playing).toBe(false);
  });

  it("autoplays at 20x when Director opens the encore", async () => {
    directorStore.getState().start("DEMO-BRAVO-0828");
    render(<SwarmView incident={INC} match={null} />);
    await flush();
    expect(swarmStore.getState()).toMatchObject({ playing: true, speed: 20 });
  });
});
