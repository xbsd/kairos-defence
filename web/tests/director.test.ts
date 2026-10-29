import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDirectorDriver,
  MORPH_HOLD_MS,
  selectLensForWarp,
} from "../src/director/useDirector";
import type { ReplayStream } from "../src/api/stream";
import { setStream } from "../src/state/controls";
import { directorStore } from "../src/state/directorStore";
import { matchStore } from "../src/state/matchStore";
import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";
import { clock } from "./fixtures";
import { resetStores } from "./panelKit";
import { T090 } from "./real";

function fakeStream() {
  const sent: string[] = [];
  const s = {
    play: () => sent.push("play"),
    pause: () => sent.push("pause"),
    seek: (t: number) => sent.push(`seek ${t}`),
    setSpeed: (v: number) => sent.push(`speed ${v}`),
    requestDtw: (t: string, c?: string) => sent.push(`dtw ${t} ${c}`),
  } as unknown as ReplayStream;
  setStream(s);
  return sent;
}

beforeEach(() => {
  resetStores();
  directorStore.setState({
    active: false,
    page: null,
    beat: 0,
    log: [],
    facts: {},
    pendingSeek: null,
    pendingPlay: false,
    incidentId: null,
    caseId: null,
  });
  window.history.replaceState(null, "", "/live/DEMO-BRAVO-0828");
});
afterEach(() => {
  setStream(null);
  vi.useRealTimers();
});

describe("Director driver (D-122 to D-127)", () => {
  it("seeks to T+0 and plays once the stream is open, then activates beats as the clock crosses them", () => {
    const sent = fakeStream();
    const d = createDirectorDriver(() => 1000);
    directorStore.getState().start("DEMO-BRAVO-0828");
    replayStore.getState().setStatus("open");
    replayStore.getState().apply(T090.hello);
    replayStore.getState().apply(clock(120)); // a stale clock from before the seek
    d.evaluate();
    expect(sent).toEqual(["seek 0", "play"]);
    expect(directorStore.getState().pendingSeek).toBeNull();
    d.evaluate();
    expect(directorStore.getState().log).toEqual([]); // waits for the seek to land
    replayStore.getState().apply(clock(0, true, 5, true));
    d.evaluate();
    expect(directorStore.getState().beat).toBe(0);
    replayStore.getState().apply(clock(15.2));
    d.evaluate();
    d.evaluate(); // a second look at the same beat logs nothing more
    expect(directorStore.getState().log.map((l) => [l.beat, l.n])).toEqual([
      ["detection", 1],
      ["recording", 2],
    ]);
    expect(directorStore.getState().log[1]?.t_s).toBe(15.2);
    expect(uiStore.getState().camera).toBe("overview");
    replayStore.getState().apply(clock(45));
    d.evaluate();
    expect(uiStore.getState().camera).toBe("follow");
    d.dispose();
  });

  it("in the time-warp beat, points the lens at the farthest-warp match and morphs to Warped", () => {
    vi.useFakeTimers();
    const sent = fakeStream();
    const d = createDirectorDriver(() => 0);
    directorStore.setState({ active: true, beat: 2 });
    replayStore.getState().setStatus("open");
    replayStore.getState().apply(T090.hello);
    replayStore.getState().apply(clock(90));
    matchStore.getState().apply(T090.match);
    d.evaluate();
    expect(directorStore.getState().beat).toBe(3);
    expect(uiStore.getState().camera).toBe("memory");
    expect(matchStore.getState().lensSel).toEqual({
      track: "P1-DELTA-260419-T1",
      channel: "dist_target_m",
    });
    expect(sent).toContain("dtw P1-DELTA-260419-T1 dist_target_m");
    expect(matchStore.getState().lensMode).toBe("same");
    vi.advanceTimersByTime(MORPH_HOLD_MS + 10);
    expect(matchStore.getState().lensMode).toBe("warped");
    d.dispose();
  });

  it("never commits: the driver only seeks, plays, sets the camera and the lens", () => {
    const sent = fakeStream();
    const d = createDirectorDriver(() => 0);
    directorStore.setState({ active: true, beat: -1 });
    replayStore.getState().setStatus("open");
    replayStore.getState().apply(T090.hello);
    matchStore.getState().apply(T090.match);
    for (const t of [0, 15, 45, 90, 105, 120]) {
      replayStore.getState().apply(clock(t));
      d.evaluate();
    }
    expect(sent.every((s) => /^(seek|play|dtw) /.test(s) || s === "play")).toBe(true);
    expect(directorStore.getState().log.map((l) => l.beat)).toEqual([
      "detection",
      "recording",
      "recognition",
      "time-warp",
      "forecast",
      "recall",
    ]);
    d.dispose();
  });

  it("selectLensForWarp keeps the top match when no pace differs", () => {
    fakeStream();
    matchStore.getState().apply({
      ...T090.match,
      matches: T090.match.matches.map((m) => ({ ...m, warp_ratio: null })),
    });
    selectLensForWarp();
    expect(matchStore.getState().lensSel?.track).toBe(T090.match.matches[0]?.track_id);
  });
});
