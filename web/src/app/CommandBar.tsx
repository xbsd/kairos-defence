import type { ReactNode } from "react";

import { AskButton } from "../chat/ChatPanel";
import { localHM } from "../director/captions";
import { toggleDirector } from "../director/actions";
import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { controls } from "../state/controls";
import { directorStore } from "../state/directorStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { Link } from "./Link";
import { PAGES, usePath } from "./routes";
import { replayStatus } from "./status";

/** "21:41:36" local at the installation, from the replay clock (UTC), or null. */
function localTime(ts: string | null, offset: number | null): string | null {
  if (!ts || offset === null) return null;
  const t = Date.parse(ts);
  const hm = localHM(ts, offset);
  if (!hm || !Number.isFinite(t)) return null;
  return `${hm}:${String(new Date(t + offset * 3600_000).getUTCSeconds()).padStart(2, "0")}`;
}

export interface CommandBarProps {
  /** Breadcrumb after the product name, e.g. ["Live watch", "Installation Bravo"]. */
  trail: string[];
  /** True on a page with a replay (Live watch); elsewhere the controls are idle. */
  replay?: boolean;
}

function IconButton(props: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={props.label}
      title={props.label}
      disabled={props.disabled}
      onClick={props.onClick}
      className="grid size-8 place-items-center rounded-button text-ink-hi transition-colors duration-(--dur-micro) ease-(--ease-out) hover:bg-hairline disabled:cursor-not-allowed disabled:text-ink-low disabled:hover:bg-transparent"
    >
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor">
        {props.children}
      </svg>
    </button>
  );
}

const SPEEDS = [1, 2, 5] as const;

/** The command bar shared by every page (SPEC §17.2), wired to the replay stream. */
export function CommandBar({ trail, replay = false }: CommandBarProps) {
  const r = useThrottledStore(replayStore, (s) => ({
    t: s.clock?.t_s ?? null,
    speed: s.clock?.speed ?? s.hello?.speed ?? 1,
    playing: s.clock?.playing,
    status: s.status,
    hello: s.hello !== null,
    local: localTime(s.clock?.ts ?? null, s.hello?.utc_offset_hours ?? null),
  }));
  const ui = useThrottledStore(uiStore, (s) => ({ reduce: reduceMotion(s), perf: s.perfMode }));
  const director = useThrottledStore(directorStore, (s) => s.active);
  const path = usePath();
  const status = replay ? replayStatus(r.status, r.hello, r.playing) : "No replay loaded";
  const idle = !replay || !r.hello || r.status !== "open";
  const live = status === "Live";
  const clock = replay && r.hello ? tPlus(r.t) : null;
  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b border-hairline bg-glass px-4 backdrop-blur-glass">
      <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
        <ol className="flex items-center gap-2 truncate text-15">
          <li className="font-bold text-ink-hi">
            <Link to="/" className="rounded-button">
              Kairos Defense
            </Link>
          </li>
          {trail.map((item) => (
            <li key={item} className="flex items-center gap-2 text-ink-mid">
              <span aria-hidden="true" className="text-ink-low">
                /
              </span>
              {item}
            </li>
          ))}
        </ol>
      </nav>

      <span
        role="timer"
        aria-label={clock ? `Replay time ${clock}` : "Replay time: none"}
        className="font-mono text-15 text-ink-hi"
        data-testid="replay-clock"
        data-local-time={replay && r.local ? r.local : undefined}
        title={replay && r.local ? `${r.local} local` : undefined}
      >
        {clock ?? "T+--:--"}
      </span>

      <span
        role="status"
        data-testid="replay-status"
        className={`flex items-center gap-2 rounded-chip border px-3 py-1 text-13 ${
          live ? "border-flash text-flash" : "border-hairline text-ink-mid"
        }`}
      >
        <span
          aria-hidden="true"
          className={`size-2 rounded-chip ${live ? "bg-flash" : "border border-ink-mid"}`}
        />
        {status}
      </span>

      <div role="group" aria-label="Replay speed" className="flex items-center gap-1">
        {SPEEDS.map((v) => (
          <button
            key={v}
            type="button"
            aria-pressed={!idle && r.speed === v}
            aria-label={`Speed ${v} times`}
            disabled={idle}
            onClick={() => controls.speed(v)}
            className={`rounded-button px-2 py-1 font-mono text-13 transition-colors duration-(--dur-micro) ease-(--ease-out) disabled:cursor-not-allowed disabled:text-ink-low ${
              !idle && r.speed === v
                ? "bg-hairline text-flash"
                : "text-ink-mid hover:bg-hairline hover:text-ink-hi"
            }`}
          >
            {v}×
          </button>
        ))}
      </div>

      <div role="group" aria-label="Replay controls" className="flex items-center gap-1">
        <IconButton label="Play" disabled={idle || r.playing === true} onClick={controls.play}>
          <path d="M4 2.5v11l9-5.5z" />
        </IconButton>
        <IconButton label="Pause" disabled={idle || r.playing !== true} onClick={controls.pause}>
          <path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" />
        </IconButton>
        <IconButton label="Restart" disabled={idle} onClick={controls.restart}>
          <path d="M8 2.5a5.5 5.5 0 1 1-5.2 3.7l1.4.5A4 4 0 1 0 8 4v2L4.8 3.2 8 .5z" />
        </IconButton>
      </div>

      <button
        type="button"
        aria-pressed={ui.reduce}
        onClick={() => uiStore.getState().toggleReduce()}
        title="Reduce motion (M)"
        className={`rounded-button border px-3 py-1 text-13 whitespace-nowrap transition-colors duration-(--dur-micro) ease-(--ease-out) ${
          ui.reduce ? "border-flash text-flash" : "border-hairline text-ink-mid hover:text-ink-hi"
        }`}
      >
        Reduce motion
      </button>

      <button
        type="button"
        aria-pressed={ui.perf}
        onClick={() => uiStore.getState().togglePerfMode()}
        title="Performance mode: no bloom, grain or core beams; half the data packets"
        className={`rounded-button border px-3 py-1 text-13 whitespace-nowrap transition-colors duration-(--dur-micro) ease-(--ease-out) ${
          ui.perf ? "border-flash text-flash" : "border-hairline text-ink-mid hover:text-ink-hi"
        }`}
      >
        Performance mode
      </button>

      <details className="relative">
        <summary className="cursor-pointer list-none rounded-button border border-hairline px-3 py-1 text-13 text-ink-mid hover:text-ink-hi">
          Pages
        </summary>
        <ul className="absolute right-0 z-40 mt-1 w-56 rounded-panel border border-hairline bg-scope p-1 text-13">
          <li>
            <Link
              to="/"
              current={path === "/" || path.startsWith("/live/")}
              className="block rounded-button px-3 py-2 text-ink-hi hover:bg-hairline"
            >
              Live watch
            </Link>
          </li>
          {PAGES.map((p) => (
            <li key={p.path}>
              <Link
                to={p.path}
                current={path === p.path || path.startsWith(`${p.path}/`)}
                className="block rounded-button px-3 py-2 text-ink-mid hover:bg-hairline hover:text-ink-hi"
              >
                {p.title}
              </Link>
            </li>
          ))}
        </ul>
      </details>

      <AskButton />

      <button
        type="button"
        aria-pressed={director}
        onClick={() => void toggleDirector()}
        title="Director mode (D): the demo, beat by beat, from T+0"
        className={`rounded-button border px-3 py-1 text-13 transition-colors duration-(--dur-micro) ease-(--ease-out) ${
          director ? "border-flash text-flash" : "border-hairline text-ink-mid hover:text-ink-hi"
        }`}
      >
        Director
      </button>
    </header>
  );
}
