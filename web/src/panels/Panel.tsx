import type { ReactNode } from "react";

import { dimmedIn } from "../director/engine";
import { useThrottledStore } from "../lib/useThrottledStore";
import { directorStore } from "../state/directorStore";

/** A docked instrument (SPEC §17.1): glass, hairline border, 6 px radius, a 13 px bold title. */
export function Panel(props: {
  id: string;
  title: string;
  /** Right side of the title row: live readouts. */
  meta?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const dimmed = useThrottledStore(
    directorStore,
    (s) => dimmedIn(props.id, s.active, s.beat, s.page),
    4,
  );
  return (
    <section
      aria-labelledby={`${props.id}-title`}
      data-testid={`panel-${props.id}`}
      data-dimmed={dimmed ? "true" : "false"}
      className={`flex min-h-0 min-w-0 flex-col rounded-panel border border-hairline bg-glass backdrop-blur-glass transition-opacity duration-(--dur-reveal) ease-(--ease-out) ${
        dimmed ? "opacity-45" : "opacity-100"
      } ${props.className ?? ""}`}
    >
      <header className="flex items-baseline justify-between gap-3 px-3 pt-2 pb-1">
        <h2
          id={`${props.id}-title`}
          className="shrink-0 text-13 font-bold whitespace-nowrap text-ink-mid"
        >
          {props.title}
        </h2>
        {props.meta ? (
          <div className="min-w-0 truncate text-12 text-ink-mid">{props.meta}</div>
        ) : null}
      </header>
      <div className="relative min-h-0 flex-1">{props.children}</div>
    </section>
  );
}
