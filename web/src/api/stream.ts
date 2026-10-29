// The replay WebSocket client (SPEC §16.3, D-112): dispatch by `type`, drop malformed messages,
// reconnect with backoff 0.5, 1, 2, 4, 8 s, and on reconnect restore speed, position and play.
import { STREAM_TYPES, type ClientMessage, type StreamMessage } from "./messages";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

export const BACKOFF_MS = [500, 1000, 2000, 4000, 8000] as const;

export interface StreamOptions {
  url: string;
  onMessage: (m: StreamMessage) => void;
  onStatus?: (s: StreamStatus) => void;
  WebSocketImpl?: typeof WebSocket;
  setTimeoutImpl?: (fn: () => void, ms: number) => unknown;
  clearTimeoutImpl?: (h: unknown) => void;
}

/** ws(s)://<this origin>/ws/replay/<incident> */
export function replayUrl(incidentId: string, loc: Location = window.location): string {
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}/ws/replay/${encodeURIComponent(incidentId)}`;
}

export function parseMessage(data: unknown): StreamMessage | null {
  if (typeof data !== "string") return null;
  let m: unknown;
  try {
    m = JSON.parse(data);
  } catch {
    return null;
  }
  if (!m || typeof m !== "object" || !("type" in m)) return null;
  const t = (m as { type: unknown }).type;
  return typeof t === "string" && (STREAM_TYPES as readonly string[]).includes(t)
    ? (m as StreamMessage)
    : null;
}

export class ReplayStream {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: unknown = null;
  private closed = false;
  private hadOpen = false;
  /** What to restore after a reconnect (from the last `clock`). */
  private last = { t_s: 0, speed: 1, playing: false };
  private readonly opts: StreamOptions;

  constructor(opts: StreamOptions) {
    this.opts = opts;
  }

  get position(): { t_s: number; speed: number; playing: boolean } {
    return { ...this.last };
  }

  connect(): void {
    this.closed = false;
    const WS = this.opts.WebSocketImpl ?? WebSocket;
    this.opts.onStatus?.(this.hadOpen ? "reconnecting" : "connecting");
    const ws = new WS(this.opts.url);
    this.ws = ws;
    ws.onopen = () => {
      const restore = this.hadOpen;
      this.hadOpen = true;
      this.attempt = 0;
      this.opts.onStatus?.("open");
      if (restore) {
        this.send({ type: "speed", value: this.last.speed as 1 | 2 | 5 });
        this.send({ type: "seek", t_s: this.last.t_s });
        if (this.last.playing) this.send({ type: "play" });
      }
    };
    ws.onmessage = (ev: MessageEvent) => {
      const m = parseMessage(ev.data);
      if (!m) return;
      if (m.type === "clock") this.last = { t_s: m.t_s, speed: m.speed, playing: m.playing };
      this.opts.onMessage(m);
    };
    ws.onclose = () => {
      this.ws = null;
      if (this.closed) {
        this.opts.onStatus?.("closed");
        return;
      }
      this.opts.onStatus?.("reconnecting");
      const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)] ?? 8000;
      this.attempt += 1;
      const st = this.opts.setTimeoutImpl ?? ((fn, ms) => setTimeout(fn, ms));
      this.timer = st(() => this.connect(), delay);
    };
  }

  send(m: ClientMessage): boolean {
    if (!this.ws || this.ws.readyState !== 1) return false;
    this.ws.send(JSON.stringify(m));
    return true;
  }

  play(): void {
    this.send({ type: "play" });
  }

  pause(): void {
    this.send({ type: "pause" });
  }

  seek(t_s: number): void {
    this.send({ type: "seek", t_s });
  }

  setSpeed(value: 1 | 2 | 5): void {
    this.send({ type: "speed", value });
  }

  requestDtw(matchTrackId: string, channel = "dist_target_m"): void {
    this.send({ type: "dtw", match_track_id: matchTrackId, channel });
  }

  close(): void {
    this.closed = true;
    if (this.timer !== null) {
      const ct = this.opts.clearTimeoutImpl ?? ((h) => clearTimeout(h as number));
      ct(this.timer);
      this.timer = null;
    }
    this.ws?.close();
  }
}
