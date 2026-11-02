import { beforeEach, describe, expect, it } from "vitest";

import type { LiveStatus, SwarmMatchMsg } from "../src/api/messages";
import { parseLiveMessage } from "../src/api/liveStream";
import {
  basesFor,
  defaultBase,
  feedLabel,
  incidentName,
  nextBase,
  simulatorLine,
} from "../src/live/liveText";
import { dispatchLive } from "../src/state/liveDispatch";
import { feedOf, incidentList, liveStore } from "../src/state/liveStore";
import { matchStore } from "../src/state/matchStore";
import { replayStore } from "../src/state/replayStore";
import { HELLO, match } from "./fixtures";
import { SCENARIOS } from "./liveFixtures";
import { nth } from "./panelKit";

const STATUS: LiveStatus = {
  enabled: true,
  matching: true,
  problems: [],
  feeds: [
    { installation_id: "BRAVO", feed_ts: "2026-09-02T02:05:00.000Z", rate: 20, active: true },
  ],
  incidents: [
    {
      incident_id: "LIVE-BRAVO-260901-210104",
      installation_id: "BRAVO",
      start_ts: "2026-09-02T02:01:04.000Z",
      end_ts: "2026-09-02T02:04:10.000Z",
      n_tracks: 1,
      is_swarm: false,
      state: "closed",
      reruns: 29,
    },
  ],
  pending: 0,
  learned_tracks: 1,
  simulator: {
    running: true,
    scenario: "returning-prober",
    base: "BRAVO",
    second_base: null,
    speed: 20,
    seed: 1101,
    started_at: "2026-11-02T10:00:00Z",
    exit_code: null,
  },
};

beforeEach(() => {
  liveStore.getState().clear();
  liveStore.getState().setInstallation("BRAVO");
  replayStore.getState().reset();
  matchStore.getState().clear();
});

describe("liveStore", () => {
  it("takes the incident list from the status (it survives a reload)", () => {
    liveStore.getState().setStatus(STATUS);
    const s = liveStore.getState();
    expect(incidentList(s).map((r) => r.incident_id)).toEqual(["LIVE-BRAVO-260901-210104"]);
    expect(feedOf(s)?.rate).toBe(20);
    liveStore.getState().setStatus(null, "down");
    expect(liveStore.getState().statusError).toBe("down");
    expect(incidentList(liveStore.getState())).toHaveLength(1); // a failed poll keeps the list
  });

  it("keeps the list current from incident_opened and incident_closed, newest first", () => {
    liveStore.getState().setStatus(STATUS);
    dispatchLive({
      type: "incident_opened",
      incident_id: "LIVE-BRAVO-260901-211500",
      installation_id: "BRAVO",
      start_ts: "2026-09-02T02:15:00.000Z",
    });
    let rows = incidentList(liveStore.getState());
    expect(rows.map((r) => [r.incident_id, r.state])).toEqual([
      ["LIVE-BRAVO-260901-211500", "open"],
      ["LIVE-BRAVO-260901-210104", "closed"],
    ]);
    dispatchLive({
      type: "incident_closed",
      incident_id: "LIVE-BRAVO-260901-211500",
      installation_id: "BRAVO",
      end_ts: "2026-09-02T02:22:00.000Z",
      duration_s: 420,
      n_tracks: 1,
      is_swarm: false,
      reruns: 76,
      learned_tracks: 1,
    });
    rows = incidentList(liveStore.getState());
    expect(rows[0]).toMatchObject({
      state: "closed",
      reruns: 76,
      start_ts: "2026-09-02T02:15:00.000Z",
    });
  });

  it("keeps reveals by incident and one open card", () => {
    const st = liveStore.getState();
    st.openReveal("LIVE-X");
    st.setReveal("LIVE-X", { state: "loading" });
    expect(liveStore.getState().reveals["LIVE-X"]).toEqual({ state: "loading" });
    expect(liveStore.getState().revealOpen).toBe("LIVE-X");
    st.clear();
    expect(liveStore.getState().revealOpen).toBeNull();
  });
});

describe("dispatchLive", () => {
  it("sends the §16.3 types to the Live watch stores and resets them for a new incident", () => {
    dispatchLive({ ...HELLO, incident_id: "LIVE-A", duration_s: 0 });
    dispatchLive({ ...match(50), query_track: "LIVE-A-T1" });
    expect(matchStore.getState().match?.query_track).toBe("LIVE-A-T1");
    dispatchLive({ ...HELLO, incident_id: "LIVE-A", duration_s: 0 }); // the same incident again
    expect(matchStore.getState().match).not.toBeNull();
    dispatchLive({ ...HELLO, incident_id: "LIVE-B", duration_s: 0 });
    expect(matchStore.getState().match).toBeNull();
    expect(replayStore.getState().hello?.incident_id).toBe("LIVE-B");
  });

  it("puts a swarm result in the live store", () => {
    const m: SwarmMatchMsg = {
      type: "swarm_match",
      t_s: 300,
      incident_id: "LIVE-GOLF-1",
      model_version: "swarm-dtw-v1",
      elapsed_ms: 210,
      n_drones: 5,
      detected: true,
      matches: [],
    };
    dispatchLive(m);
    expect(liveStore.getState().swarm?.n_drones).toBe(5);
  });

  it("parses only known live types", () => {
    expect(parseLiveMessage('{"type":"incident_opened","incident_id":"x"}')?.type).toBe(
      "incident_opened",
    );
    expect(parseLiveMessage('{"type":"play"}')).toBeNull();
    expect(parseLiveMessage("not json")).toBeNull();
  });
});

describe("liveText", () => {
  it("lists the bases of the chosen actor and defaults to Bravo", () => {
    const rp = nth(SCENARIOS, 0);
    expect(basesFor(rp, "P1")).toEqual(["ALPHA", "BRAVO", "CHARLIE", "DELTA"]);
    expect(basesFor(rp, "P3")).toEqual(["ECHO", "FOXTROT", "HOTEL"]);
    expect(basesFor(rp, "random")).toContain("GOLF");
    expect(defaultBase(basesFor(rp, "P1"))).toBe("BRAVO");
    expect(defaultBase(basesFor(rp, "P3"))).toBe("ECHO");
    expect(nextBase(["ALPHA", "BRAVO", "CHARLIE"], "BRAVO")).toBe("CHARLIE");
  });

  it("names feeds, incidents and the simulator without the actor", () => {
    expect(feedLabel(null)).toBe("No feed yet");
    expect(feedLabel(nth(STATUS.feeds, 0))).toBe("Feed live, 20×");
    expect(incidentName("LIVE-BRAVO-260901-210104")).toBe("Bravo, 21:01:04");
    expect(simulatorLine(STATUS.simulator)).toBe(
      "Simulator running: returning-prober at Bravo, 20×, seed 1101",
    );
    expect(simulatorLine({ ...STATUS.simulator, running: false, exit_code: 0 })).toContain(
      "Last run finished",
    );
  });
});
