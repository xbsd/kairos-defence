import { describe, expect, it } from "vitest";

import { BACKOFF_MS, ReplayStream, parseMessage, replayUrl } from "../src/api/stream";
import type { StreamMessage } from "../src/api/messages";

class FakeWS {
  static all: FakeWS[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(readonly url: string) {
    FakeWS.all.push(this);
  }
  send(s: string) {
    this.sent.push(s);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  push(m: unknown) {
    this.onmessage?.({ data: typeof m === "string" ? m : JSON.stringify(m) });
  }
  drop() {
    this.readyState = 3;
    this.onclose?.();
  }
}

function setup() {
  FakeWS.all = [];
  const got: StreamMessage[] = [];
  const statuses: string[] = [];
  const timers: { fn: () => void; ms: number }[] = [];
  const s = new ReplayStream({
    url: "ws://x/ws/replay/DEMO",
    onMessage: (m) => got.push(m),
    onStatus: (st) => statuses.push(st),
    WebSocketImpl: FakeWS as unknown as typeof WebSocket,
    setTimeoutImpl: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    clearTimeoutImpl: () => undefined,
  });
  return { s, got, statuses, timers };
}

describe("parseMessage", () => {
  it("accepts known types and drops malformed messages", () => {
    expect(parseMessage('{"type":"clock","t_s":1}')?.type).toBe("clock");
    expect(parseMessage("not json")).toBeNull();
    expect(parseMessage('{"type":"telemetry"}')).toBeNull();
    expect(parseMessage('{"no":"type"}')).toBeNull();
    expect(parseMessage(42)).toBeNull();
  });
});

describe("replayUrl", () => {
  it("uses the page origin", () => {
    expect(replayUrl("DEMO-BRAVO-0828", { protocol: "http:", host: "h:8000" } as Location)).toBe(
      "ws://h:8000/ws/replay/DEMO-BRAVO-0828",
    );
    expect(replayUrl("X", { protocol: "https:", host: "h" } as Location)).toBe(
      "wss://h/ws/replay/X",
    );
  });
});

describe("ReplayStream", () => {
  it("dispatches by type and drops malformed messages", () => {
    const { s, got } = setup();
    s.connect();
    const ws = FakeWS.all[0];
    ws?.open();
    ws?.push({ type: "point", t_s: 1 });
    ws?.push("garbage");
    ws?.push({ type: "nope" });
    expect(got.map((m) => m.type)).toEqual(["point"]);
  });

  it("reconnects with backoff 0.5, 1, 2, 4, 8 s", () => {
    const { s, timers, statuses } = setup();
    s.connect();
    for (let i = 0; i < 6; i++) {
      FakeWS.all[FakeWS.all.length - 1]?.drop();
      timers[timers.length - 1]?.fn();
    }
    expect(timers.map((t) => t.ms)).toEqual([...BACKOFF_MS, 8000]);
    expect(statuses).toContain("reconnecting");
  });

  it("restores speed, position and play after a reconnect", () => {
    const { s, timers } = setup();
    s.connect();
    const first = FakeWS.all[0];
    first?.open();
    first?.push({ type: "clock", t_s: 62.5, ts: "x", speed: 5, playing: true, seeked: false });
    first?.drop();
    timers[0]?.fn();
    const second = FakeWS.all[1];
    second?.open();
    expect(second?.sent.map((x) => JSON.parse(x) as object)).toEqual([
      { type: "speed", value: 5 },
      { type: "seek", t_s: 62.5 },
      { type: "play" },
    ]);
  });

  it("sends commands only while open, and close() stops reconnecting", () => {
    const { s, timers, statuses } = setup();
    s.connect();
    expect(s.send({ type: "play" })).toBe(false);
    FakeWS.all[0]?.open();
    s.setSpeed(2);
    s.requestDtw("T-1", "speed_ms");
    expect(FakeWS.all[0]?.sent.map((x) => JSON.parse(x) as object)).toEqual([
      { type: "speed", value: 2 },
      { type: "dtw", match_track_id: "T-1", channel: "speed_ms" },
    ]);
    s.close();
    expect(timers).toHaveLength(0);
    expect(statuses[statuses.length - 1]).toBe("closed");
  });
});
