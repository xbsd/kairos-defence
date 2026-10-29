import type { SwarmMatch } from "../api/messages";
import { navigate } from "../app/routes";
import { paceOf } from "../director/captions";
import { baseName, localDate } from "../lib/format";
import { localYmd } from "./swarmMath";

/** "May 3" at the installation's offset, else the UTC date. */
function day(m: SwarmMatch, offsets: Record<string, number>): string {
  return localDate(localYmd(m.start_ts, offsets[m.installation_id] ?? 0) ?? m.start_ts);
}

/**
 * Earlier swarms, best first (§14 output): base, local date, drones, similarity and pace. The
 * selected one is the ghost; choosing another reloads the page for it (URL `match=`).
 */
export function SwarmMatches(props: {
  incident: string;
  matches: SwarmMatch[];
  selected: string | null;
  offsets: Record<string, number>;
}) {
  if (!props.matches.length)
    return (
      <p data-testid="swarm-no-match" className="px-3 py-2 text-13 text-ink-mid">
        No earlier swarm to compare with.
      </p>
    );
  return (
    <ol aria-label="Earlier swarms, best first" className="flex flex-col">
      {props.matches.map((m) => {
        const on = m.incident_id === props.selected;
        const pace = paceOf(m.warp_ratio);
        return (
          <li key={m.incident_id} className="border-t border-hairline first:border-t-0">
            <button
              type="button"
              aria-pressed={on}
              data-testid="swarm-match"
              data-incident={m.incident_id}
              onClick={() =>
                navigate(
                  `/swarm?incident=${encodeURIComponent(props.incident)}&match=${encodeURIComponent(m.incident_id)}`,
                )
              }
              className={`grid w-full grid-cols-[2rem_minmax(0,1fr)_auto] items-baseline gap-x-2 border-l-2 px-3 py-2 text-left transition-colors duration-(--dur-micro) ease-(--ease-out) hover:bg-hairline ${
                on ? "border-afterglow bg-hairline" : "border-transparent"
              }`}
            >
              <span className={`font-mono text-13 ${on ? "text-ink-hi" : "text-ink-mid"}`}>
                #{m.rank}
              </span>
              <span className="min-w-0 truncate text-15 text-ink-hi">
                {baseName(m.installation_id)} · {day(m, props.offsets)}
                <span className="sr-only"> ({m.incident_id})</span>
              </span>
              <span
                className="font-mono text-15 text-ink-hi"
                title="Similarity, 1 / (1 + DTW distance)"
              >
                {m.similarity.toFixed(2)}
              </span>
              <span />
              <span className="col-span-2 text-12 text-ink-mid">
                {m.n_drones} drones · pace {m.warp_ratio.toFixed(2)}
                {pace ? ` (${pace})` : ""}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
