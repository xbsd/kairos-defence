import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { setFetch } from "../src/api/client";
import { CommandBar } from "../src/app/CommandBar";
import { liveStatus } from "../src/app/status";
import { IncidentList } from "../src/live/IncidentList";
import { Launcher } from "../src/live/Launcher";
import { RevealCard } from "../src/live/RevealCard";
import { liveStore } from "../src/state/liveStore";
import { replayStore } from "../src/state/replayStore";
import { HELLO, clock } from "./fixtures";
import { REVEAL, SCENARIOS } from "./liveFixtures";
import { flush, nth, resetStores, stubDialog } from "./panelKit";
import { calls, routeFetch } from "./route";

const ROW = {
  incident_id: "LIVE-BRAVO-260901-210104",
  installation_id: "BRAVO",
  start_ts: "2026-09-02T02:01:04.000Z",
  end_ts: "2026-09-02T02:04:10.000Z",
  n_tracks: 1,
  is_swarm: false,
  reruns: 29,
};

beforeEach(() => {
  resetStores();
  stubDialog();
  liveStore.getState().clear();
  liveStore.getState().setInstallation("BRAVO");
  liveStore.getState().setScenarios(SCENARIOS);
  liveStore.getState().setLaunch(false);
});
afterEach(() => setFetch((...a) => fetch(...a)));

describe("Launcher", () => {
  it("offers each scenario's actors and bases, defaulting to P1 at Bravo", async () => {
    render(<Launcher installations={["ALPHA", "BRAVO", "ECHO"]} />);
    await flush();
    expect(screen.getByLabelText("Scenario")).toHaveValue("returning-prober");
    expect(screen.getByLabelText("Prober")).toHaveValue("P1");
    expect(screen.getByLabelText("Base")).toHaveValue("BRAVO");
    fireEvent.change(screen.getByLabelText("Prober"), { target: { value: "P3" } });
    expect(screen.getByLabelText("Base")).toHaveValue("ECHO"); // P3 never flies at Bravo
    fireEvent.change(screen.getByLabelText("Scenario"), {
      target: { value: "new-operator-twice" },
    });
    expect(screen.queryByLabelText("Prober")).toBeNull();
    expect(screen.getByLabelText("Second base")).toHaveValue("CHARLIE");
    expect(screen.getByText(/Flight 2: flight 1, learned live/)).toBeInTheDocument();
  });

  it("launches with the chosen settings and follows the launch base", async () => {
    const f = routeFetch([
      [
        /\/api\/sim\/launch/,
        () => ({
          launched: true,
          scenario: "returning-prober",
          base: "ALPHA",
          second_base: null,
          speed: 50,
          seed: 7,
          pid: 1,
        }),
      ],
      [
        /\/api\/live\/status/,
        () => ({
          enabled: true,
          matching: true,
          problems: [],
          feeds: [],
          incidents: [],
          pending: 0,
          learned_tracks: 0,
          simulator: {
            running: true,
            scenario: "returning-prober",
            base: "ALPHA",
            second_base: null,
            speed: 50,
            seed: 7,
            started_at: null,
            exit_code: null,
          },
        }),
      ],
    ]);
    render(<Launcher installations={["ALPHA", "BRAVO"]} />);
    await flush();
    fireEvent.change(screen.getByLabelText("Base"), { target: { value: "ALPHA" } });
    fireEvent.change(screen.getByLabelText("Speed"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("Seed"), { target: { value: "7" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Launch" }));
      await new Promise((r) => setTimeout(r, 20));
    });
    const [url, init] = nth(
      calls(f).filter(([u]) => u.includes("/api/sim/launch")),
      0,
    );
    expect(url).toContain("/api/sim/launch");
    expect(JSON.parse(String(init?.body))).toEqual({
      scenario: "returning-prober",
      actor: "P1",
      base: "ALPHA",
      second_base: null,
      speed: 50,
      seed: 7,
    });
    expect(liveStore.getState().installation).toBe("ALPHA");
    await flush();
    expect(screen.getByTestId("simulator-state")).toHaveTextContent(
      "Simulator running: returning-prober at Alpha, 50×, seed 7",
    );
    expect(screen.getByRole("button", { name: "Launch" })).toBeDisabled(); // one at a time
  });

  it("stops a running simulator and keeps the session's incidents (D-192)", async () => {
    const sim = (running: boolean) => ({
      running,
      scenario: "returning-prober",
      base: "BRAVO",
      second_base: null,
      speed: 20,
      seed: 7,
      started_at: null,
      exit_code: running ? null : -15,
    });
    const status = (running: boolean) => ({
      enabled: true,
      matching: true,
      problems: [],
      feeds: [],
      incidents: [],
      pending: 0,
      learned_tracks: 0,
      simulator: sim(running),
    });
    liveStore.getState().setStatus(status(false)); // an earlier test may leave one running
    render(<Launcher installations={["ALPHA", "BRAVO"]} />);
    await flush();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled(); // nothing is flying
    act(() => liveStore.getState().setStatus(status(true)));
    await flush();
    expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
    const f = routeFetch([
      [/\/api\/sim\/stop/, () => ({ stopped: true, simulator: sim(false) })],
      [/\/api\/live\/status/, () => status(false)],
    ]);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Stop" }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(calls(f).some(([u]) => u.includes("/api/sim/stop"))).toBe(true);
    expect(calls(f).some(([u]) => u.includes("/api/live/reset"))).toBe(false); // Stop is not Reset
    await flush();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Launch" })).toBeEnabled();
  });
});

describe("IncidentList", () => {
  it("shows open incidents without a Reveal button and closed ones with it", async () => {
    liveStore.getState().setStatus({
      enabled: true,
      matching: true,
      problems: [],
      feeds: [],
      pending: 3,
      learned_tracks: 1,
      simulator: {
        running: false,
        scenario: null,
        base: null,
        second_base: null,
        speed: null,
        seed: null,
        started_at: null,
        exit_code: null,
      },
      incidents: [
        { ...ROW, state: "closed" },
        {
          ...ROW,
          incident_id: "LIVE-BRAVO-260901-213000",
          state: "open",
          start_ts: "2026-09-02T02:30:00.000Z",
        },
      ],
    });
    render(<IncidentList />);
    await flush();
    const items = screen.getAllByTestId("live-incident");
    expect(items.map((i) => i.getAttribute("data-state"))).toEqual(["open", "closed"]);
    expect(within(nth(items, 0)).queryByRole("button", { name: /Reveal who flew/ })).toBeNull();
    expect(
      within(nth(items, 1)).getByRole("button", { name: /Reveal who flew/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("3 reruns queued")).toBeInTheDocument();
  });

  it("asks for a confirmation before resetting live data", async () => {
    const f = routeFetch([
      [
        /\/api\/live\/reset/,
        () => ({
          reset: { live_points: 300, live_rf: 200 },
          vectors: 40,
          stopped_simulator: false,
        }),
      ],
      [
        /\/api\/live\/status/,
        () => ({
          enabled: true,
          matching: true,
          problems: [],
          feeds: [],
          incidents: [],
          pending: 0,
          learned_tracks: 0,
          simulator: {
            running: false,
            scenario: null,
            base: null,
            second_base: null,
            speed: null,
            seed: null,
            started_at: null,
            exit_code: null,
          },
        }),
      ],
    ]);
    render(<IncidentList />);
    fireEvent.click(screen.getByRole("button", { name: "Reset live data" }));
    expect(calls(f)).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls(f)).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Reset live data" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(nth(calls(f), 0)[0]).toContain("/api/live/reset");
    await flush();
    expect(screen.getByText(/Removed 500 live rows/)).toBeInTheDocument();
  });
});

describe("RevealCard", () => {
  it("says who flew and how the matcher did, in words", async () => {
    liveStore.getState().openReveal(REVEAL.incident_id);
    liveStore.getState().setReveal(REVEAL.incident_id, { state: "ready", doc: REVEAL });
    render(<RevealCard />);
    await flush();
    expect(screen.getByRole("heading", { name: "Who flew Bravo, 21:01:04" })).toBeInTheDocument();
    expect(screen.getByTestId("reveal-words")).toHaveTextContent(
      "P1, County Rd operator. First recognized at T+45 s (rank 2); top match from T+50 s.",
    );
    expect(screen.getByTestId("reveal-actor")).toHaveTextContent("P1, County Rd operator");
    expect(screen.getByTestId("reveal-verdict")).toHaveTextContent(
      "Expectation met: rank 2 at T+45 s",
    );
    expect(screen.getAllByRole("row")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(liveStore.getState().revealOpen).toBeNull();
  });
});

describe("CommandBar in live mode", () => {
  it("shows the feed and the incident clock, without replay controls or Director", async () => {
    liveStore.getState().setStatus({
      enabled: true,
      matching: true,
      problems: [],
      incidents: [],
      pending: 0,
      learned_tracks: 0,
      feeds: [
        { installation_id: "BRAVO", feed_ts: "2026-09-02T02:02:02.000Z", rate: 20, active: true },
      ],
      simulator: {
        running: true,
        scenario: "x",
        base: "BRAVO",
        second_base: null,
        speed: 20,
        seed: 1,
        started_at: null,
        exit_code: null,
      },
    });
    replayStore.getState().setStatus("open");
    replayStore.getState().apply({ ...HELLO, incident_id: "LIVE-BRAVO-1", duration_s: 0 });
    replayStore.getState().apply(clock(62, true, 20));
    render(<CommandBar trail={["Live"]} mode="live" />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Live feed, 20×");
    expect(screen.getByRole("timer", { name: "Incident time T+01:02" })).toBeInTheDocument();
    for (const name of ["Play", "Pause", "Restart", "Speed 1 times", "Director"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });

  it("names the feed's state", () => {
    expect(liveStatus("connecting", null, false)).toBe("Connecting");
    expect(liveStatus("open", null, false)).toBe("No feed yet");
    expect(liveStatus("open", { active: false, rate: 1 }, false)).toBe("Feed idle");
    expect(liveStatus("open", { active: true, rate: 5 }, false)).toBe("Feed on, 5×");
    expect(liveStatus("open", { active: true, rate: 5 }, true)).toBe("Live feed, 5×");
  });
});
