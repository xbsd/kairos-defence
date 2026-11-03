import { useState } from "react";

import { api } from "../api/client";
import { baseName } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { Panel } from "../panels/Panel";
import { incidentList, liveStore } from "../state/liveStore";
import { matchStore } from "../state/matchStore";
import { refreshStatus } from "../state/useLive";
import { incidentName, stateLabel } from "./liveText";

async function reveal(id: string): Promise<void> {
  const st = liveStore.getState();
  st.openReveal(id);
  st.setReveal(id, { state: "loading" });
  try {
    st.setReveal(id, { state: "ready", doc: await api.reveal(id) });
  } catch (e) {
    st.setReveal(id, { state: "error", message: e instanceof Error ? e.message : String(e) });
  }
}

/** Reset live data, behind an inline confirm (rule 8: an explicit, confirmed action). */
function ResetLive() {
  const [confirming, setConfirming] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const go = async () => {
    setConfirming(false);
    try {
      const r = await api.liveReset();
      const rows = Object.values(r.reset).reduce((a, b) => a + b, 0);
      liveStore.getState().clear();
      matchStore.getState().clear();
      setMsg(`Removed ${rows.toLocaleString("en-US")} live rows; the history and ledger stay`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
    await refreshStatus();
  };
  if (confirming)
    return (
      <span role="group" aria-label="Confirm reset" className="flex items-center gap-1.5">
        <span className="text-12 text-ink-hi">Remove every live incident and learned flight?</span>
        <button
          type="button"
          onClick={() => void go()}
          className="rounded-button border border-alert px-2 py-0.5 text-12 text-ink-hi hover:bg-hairline"
        >
          Confirm reset
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          className="rounded-button border border-hairline px-2 py-0.5 text-12 text-ink-mid hover:text-ink-hi"
        >
          Cancel
        </button>
      </span>
    );
  return (
    <span className="flex min-w-0 items-center gap-2">
      {msg ? <span className="min-w-0 truncate text-12 text-ink-mid">{msg}</span> : null}
      <button
        type="button"
        onClick={() => {
          setMsg(null);
          setConfirming(true);
        }}
        className="shrink-0 rounded-button border border-hairline px-2 py-0.5 text-12 text-ink-mid hover:border-alert hover:text-ink-hi"
      >
        Reset live data
      </button>
    </span>
  );
}

/** "Live incidents this session" (D-184): every live incident since the last reset, newest
 * first; a closed one can reveal who flew it (D-170). */
export function IncidentList() {
  const rows = useThrottledStore(liveStore, incidentList, 4);
  const pending = useThrottledStore(liveStore, (s) => s.status?.pending ?? 0, 4);
  return (
    <Panel
      id="live-incidents"
      title="Live incidents this session"
      className="min-h-[9rem] flex-[1_1_0]"
      meta={pending ? `${pending} rerun${pending === 1 ? "" : "s"} queued` : undefined}
    >
      {/* a scroll region keyboard users can reach even when its entries hold no enabled
          control (axe scrollable-region-focusable) */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Live incidents, scrollable"
        className="absolute inset-0 flex flex-col overflow-y-auto"
      >
        <div className="flex justify-end px-3 pb-1">
          <ResetLive />
        </div>
        {rows.length === 0 ? (
          <p className="px-3 py-1 text-13 text-ink-mid">No live incident since the last reset</p>
        ) : (
          <ul aria-label="Live incidents" className="flex flex-col">
            {rows.map((r) => (
              <li
                key={r.incident_id}
                data-testid="live-incident"
                data-state={r.state}
                className="flex items-center gap-2 border-t border-hairline px-3 py-1.5 text-13"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-ink-hi" title={r.incident_id}>
                    {incidentName(r.incident_id)}
                  </span>
                  <span className="block truncate text-12 text-ink-mid">
                    {r.n_tracks} track{r.n_tracks === 1 ? "" : "s"}
                    {r.is_swarm ? ", a swarm" : ""}, {r.reruns} rerun{r.reruns === 1 ? "" : "s"}
                  </span>
                </span>
                <span
                  data-testid="live-incident-state"
                  className={`rounded-chip border px-2 py-px text-12 ${
                    r.state === "open" ? "border-flash text-flash" : "border-hairline text-ink-mid"
                  }`}
                >
                  {stateLabel(r)}
                </span>
                {r.state === "closed" ? (
                  <button
                    type="button"
                    onClick={() => void reveal(r.incident_id)}
                    className="rounded-button border border-afterglow px-2 py-0.5 text-12 text-afterglow hover:bg-hairline"
                  >
                    Reveal who flew
                    <span className="sr-only"> {incidentName(r.incident_id)}</span>
                  </button>
                ) : null}
                <span className="sr-only">at {baseName(r.installation_id)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}
