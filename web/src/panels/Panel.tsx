import type { ReactNode } from "react";

/** A docked instrument (SPEC §17.1): glass, hairline border, 6 px radius, a 13 px bold title. */
export function Panel(props: {
  id: string;
  title: string;
  /** Right side of the title row: live readouts. */
  meta?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={`${props.id}-title`}
      data-testid={`panel-${props.id}`}
      className={`flex min-h-0 min-w-0 flex-col rounded-panel border border-hairline bg-glass backdrop-blur-glass ${props.className ?? ""}`}
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
