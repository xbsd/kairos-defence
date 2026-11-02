// The live stream client (D-184): `/ws/live/{installation}` sends the §16.3 types plus
// incident_opened, incident_closed and swarm_match. It takes no client messages: a reconnect
// gets a fresh catch-up from the server instead of restoring a replay position.
import { BACKOFF_MS, type StreamStatus } from "./stream";
import { LIVE_TYPES, type LiveStreamMessage } from "./messages";

export interface LiveStreamOptions {
  url: string;
  onMessage: (m: LiveStreamMessage) => void;
  onStatus?: (s: StreamStatus) => void;
  WebSocketImpl?: typeof WebSocket;
  setTimeoutImpl?: (fn: () => void, ms: number) => unknown;
  clearTimeoutImpl?: (h: unknown) => void;
}

/** ws(s)://<this origin>/ws/live/<installation> */
export function liveUrl(installationId: string, loc: Location = window.location): string {
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}/ws/live/${encodeURIComponent(installationId)}`;
}

export function parseLiveMessage(data: unknown): LiveStreamMessage | null {
  if (typeof data !== "string") return null;
  let m: unknown;
  try {
    m = JSON.parse(data);
  } catch {
    return null;
  }
  if (!m || typeof m !== "object" || !("type" in m)) return null;
  const t = (m as { type: unknown }).type;
  return typeof t === "string" && (LIVE_TYPES as readonly string[]).includes(t)
    ? (m as LiveStreamMessage)
    : null;
}

export class LiveStream {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: unknown = null;
  private closed = false;
  private hadOpen = false;
  private readonly opts: LiveStreamOptions;

  constructor(opts: LiveStreamOptions) {
    this.opts = opts;
  }

  connect(): void {
    this.closed = false;
    const WS = this.opts.WebSocketImpl ?? WebSocket;
    this.opts.onStatus?.(this.hadOpen ? "reconnecting" : "connecting");
    const ws = new WS(this.opts.url);
    this.ws = ws;
    ws.onopen = () => {
      this.hadOpen = true;
      this.attempt = 0;
      this.opts.onStatus?.("open");
    };
    ws.onmessage = (ev: MessageEvent) => {
      const m = parseLiveMessage(ev.data);
      if (m) this.opts.onMessage(m);
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
