import type { ReactNode } from "react";

export interface CommandBarProps {
  /** Breadcrumb after the product name, e.g. ["Live watch", "Installation Bravo"]. */
  trail: string[];
  /** Replay clock relative to first contact, or null when no replay is loaded. */
  replayClock: string | null;
  /** Replay speed multiplier (1, 2 or 5). */
  speed: number;
  /** True only while a replay stream is connected and playing (CLAUDE.md rule 10). */
  live: boolean;
}

function IconButton(props: { label: string; disabled: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={props.label}
      title={props.label}
      disabled={props.disabled}
      className="grid size-8 place-items-center rounded-button text-ink-hi transition-colors duration-(--dur-micro) ease-(--ease-out) hover:bg-hairline disabled:cursor-not-allowed disabled:text-ink-low disabled:hover:bg-transparent"
    >
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor">
        {props.children}
      </svg>
    </button>
  );
}

/** The command bar shared by every page (SPEC §17.2). */
export function CommandBar({ trail, replayClock, speed, live }: CommandBarProps) {
  const idle = !live;
  return (
    <header className="flex h-12 items-center gap-6 border-b border-hairline bg-glass px-4 backdrop-blur-glass">
      <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
        <ol className="flex items-center gap-2 truncate text-15">
          <li className="font-bold text-ink-hi">Kairos Defense</li>
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
        aria-label={replayClock ? `Replay time ${replayClock}` : "Replay time: none"}
        className="font-mono text-15 text-ink-mid"
      >
        {replayClock ?? "T+--:--"}
      </span>

      <span
        role="status"
        className={`flex items-center gap-2 rounded-chip border px-3 py-1 text-13 ${
          live ? "border-flash text-flash" : "border-hairline text-ink-mid"
        }`}
      >
        <span
          aria-hidden="true"
          className={`size-2 rounded-chip ${live ? "bg-flash" : "border border-ink-mid"}`}
        />
        {live ? "Live" : "No replay loaded"}
      </span>

      <span className="font-mono text-13 text-ink-mid" aria-label={`Speed ${speed} times`}>
        {speed}×
      </span>

      <div role="group" aria-label="Replay controls" className="flex items-center gap-1">
        <IconButton label="Play" disabled={idle}>
          <path d="M4 2.5v11l9-5.5z" />
        </IconButton>
        <IconButton label="Pause" disabled={idle}>
          <path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" />
        </IconButton>
        <IconButton label="Restart" disabled={idle}>
          <path d="M8 2.5a5.5 5.5 0 1 1-5.2 3.7l1.4.5A4 4 0 1 0 8 4v2L4.8 3.2 8 .5z" />
        </IconButton>
      </div>

      <button
        type="button"
        disabled={idle}
        className="rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi transition-colors duration-(--dur-micro) ease-(--ease-out) hover:border-flash disabled:cursor-not-allowed disabled:text-ink-low disabled:hover:border-hairline"
      >
        Director
      </button>
    </header>
  );
}
