import { baseName, ms, tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { Panel } from "../panels/Panel";
import { liveStore } from "../state/liveStore";

/** A live swarm's matches (§14): the swarm matcher's ranking of earlier swarms at the latest
 * rerun, from the stream's `swarm_match` (D-184). */
export function SwarmMatchList() {
  const m = useThrottledStore(liveStore, (s) => s.swarm, 4);
  return (
    <Panel
      id="swarm-matches"
      title="Swarm matches"
      className="min-h-[10rem] flex-[1.6_1_0]"
      meta={m ? `At ${tPlus(m.t_s)}, ${m.n_drones} drones` : undefined}
    >
      {/* a scroll region keyboard users can reach even when its entries hold no enabled
          control (axe scrollable-region-focusable) */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Swarm matches, scrollable"
        className="absolute inset-0 flex flex-col overflow-y-auto"
      >
        {!m || m.matches.length === 0 ? (
          <p className="px-3 py-2 text-13 text-ink-mid">
            {m ? "No earlier swarm to match yet" : "Waiting for the swarm matcher"}
          </p>
        ) : (
          <>
            <ol aria-label="Best swarm matches, best first" className="flex flex-col">
              {m.matches.map((x) => (
                <li
                  key={x.incident_id}
                  data-testid="swarm-match"
                  className="flex items-center gap-3 border-t border-hairline px-3 py-1.5 text-13"
                >
                  <span className="w-4 font-mono text-ink-mid">{x.rank}</span>
                  <span className="min-w-0 flex-1 truncate text-afterglow">
                    {baseName(x.installation_id)}, {x.start_ts.slice(0, 10)}
                  </span>
                  <span className="font-mono text-ink-hi">{x.similarity.toFixed(2)}</span>
                </li>
              ))}
            </ol>
            <p className="mt-auto px-3 py-2 text-12 text-ink-mid">
              {m.model_version}, computed in {ms(m.elapsed_ms)}
              {m.detected ? "" : "; not yet a swarm by the §14 rules"}
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}
