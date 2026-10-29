import { Component, useEffect, useState, type ReactNode } from "react";

import { api } from "../api/client";
import type { SwarmResponse } from "../api/messages";
import { navigate } from "../app/routes";
import { baseName, localDate } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { Panel } from "../panels/Panel";
import { directorStore } from "../state/directorStore";
import { sceneStore } from "../state/sceneStore";
import { swarmStore } from "../state/swarmStore";
import { DescriptorCurves } from "../swarm/DescriptorCurves";
import { PlaybackBar } from "../swarm/PlaybackBar";
import { SwarmMatches } from "../swarm/SwarmMatches";
import { SwarmScene } from "../swarm/SwarmScene";
import { SwarmTable } from "../swarm/SwarmTable";
import { localYmd, swarmFacts } from "../swarm/swarmMath";
import { usePlayback } from "../swarm/usePlayback";

/** Keeps the page's text, charts and table if WebGL fails (headless browsers, old GPUs). */
class SceneBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  override state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : String(e) };
  }
  override render() {
    if (this.state.error)
      return (
        <div role="alert" className="grid h-full place-items-center p-8 text-center">
          <p className="text-15 text-ink-hi">The 3D swarm could not start: {this.state.error}</p>
        </div>
      );
    return this.props.children;
  }
}

function offsetsOf(list: { installation_id: string; utc_offset_hours: number }[]) {
  return Object.fromEntries(list.map((i) => [i.installation_id, i.utc_offset_hours]));
}

/** "Echo · Jun 14" for a flight, at its installation's offset (UTC date when unknown). */
function flightName(f: { installation_id: string; start_ts: string }, off: Record<string, number>) {
  const ymd = localYmd(f.start_ts, off[f.installation_id] ?? 0);
  return `${baseName(f.installation_id)} · ${localDate(ymd ?? f.start_ts)}`;
}

/** The newest swarm to open when the URL names none: the live one, else the newest. */
function useDefaultIncident(incident: string | null): string | null {
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (incident) return;
    let alive = true;
    api
      .swarms()
      .then((list) => {
        const pick = list.find((s) => s.status === "live") ?? list[0];
        if (!alive) return;
        if (pick) navigate(`/swarm?incident=${encodeURIComponent(pick.incident_id)}`, true);
        else setError("No swarm incident in the data.");
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [incident]);
  return error;
}

/**
 * Swarm view (SPEC §17.9, §14, D-154): the 3D swarm with formation edges, the matched past swarm
 * as an afterglow ghost aligned by DTW time, and the descriptor curves. Reads only: it never
 * writes to the ledger (the encore, §15.6).
 */
export function SwarmView({ incident, match }: { incident: string | null; match: string | null }) {
  const pickError = useDefaultIncident(incident);
  const key = incident ? `${incident}|${match ?? ""}` : "";
  const [got, setGot] = useState<{ key: string; doc: SwarmResponse | null; error: string | null }>({
    key: "",
    doc: null,
    error: null,
  });
  const installations = useThrottledStore(sceneStore, (s) => s.installations, 2);
  usePlayback();

  useEffect(() => {
    if (!incident) return;
    let alive = true;
    api
      .swarm(incident, match)
      .then((doc) => {
        if (!alive) return;
        swarmStore.getState().setDoc(doc);
        // in Director the encore plays itself; elsewhere the analyst presses Play
        if (directorStore.getState().active) {
          swarmStore.getState().setSpeed(20);
          swarmStore.getState().play();
        }
        setGot({ key: `${incident}|${match ?? ""}`, doc, error: null });
      })
      .catch((e: unknown) => {
        if (alive)
          setGot({
            key: `${incident}|${match ?? ""}`,
            doc: null,
            error: e instanceof Error ? e.message : String(e),
          });
      });
    return () => {
      alive = false;
      swarmStore.getState().pause();
    };
  }, [incident, match]);

  const doc = got.key === key ? got.doc : null;
  const error = pickError ?? (got.key === key ? got.error : null);
  const offsets = offsetsOf(installations);

  // the encore caption reads these (D-155)
  useEffect(() => {
    const f = swarmFacts(doc, offsetsOf(installations));
    if (f) directorStore.getState().setFacts({ swarm: f });
  }, [doc, installations]);

  const tonight = doc ? flightName(doc.query, offsets) : null;
  const past = doc?.match ? flightName(doc.match, offsets) : null;
  const top = doc?.matches.find((m) => m.incident_id === doc.match?.incident_id) ?? null;
  return (
    <main
      aria-labelledby="swarm-title"
      data-testid="swarm-view"
      className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-y-auto p-2 xl:grid-cols-[minmax(0,1fr)_27rem] xl:overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_30rem]"
    >
      <section
        aria-label="Swarm theater"
        className="relative min-h-[30rem] overflow-hidden rounded-panel border border-hairline xl:min-h-0"
      >
        {doc && tonight ? (
          <SceneBoundary>
            <SwarmScene doc={doc} tonight={tonight} past={past} />
          </SceneBoundary>
        ) : null}
        <header className="pointer-events-none absolute top-2 left-2 max-w-[calc(100%-1rem)] rounded-panel border border-hairline bg-glass px-3 py-2 backdrop-blur-glass xl:max-w-[60%]">
          <h1 id="swarm-title" className="text-18 font-bold text-ink-hi">
            Swarm view{tonight ? `: ${tonight}` : ""}
          </h1>
          <p className="text-13 text-ink-mid" data-testid="swarm-detection">
            {doc
              ? `${doc.query.n_drones} drones, ${doc.query.is_swarm ? `flown together for ${doc.query.together_s} s (a swarm, §14)` : "not detected as a swarm"}; ${doc.observed_s} s of track.`
              : error
                ? ""
                : "Loading the swarm"}
          </p>
          {error ? (
            <p role="alert" className="text-13 text-alert">
              {error}
            </p>
          ) : null}
        </header>
        {doc?.match && past && top ? (
          <p
            data-testid="swarm-ghost"
            className="absolute top-2 right-2 flex max-w-[40%] items-center gap-2 rounded-panel border border-hairline bg-glass px-3 py-2 text-13 text-ink-hi backdrop-blur-glass"
          >
            <svg width={14} height={14} aria-hidden="true">
              <circle cx={7} cy={7} r={5} fill="none" stroke="var(--afterglow)" strokeWidth={1.5} />
            </svg>
            <span>
              Afterglow ghost: {past}, aligned by DTW (pace {top.warp_ratio.toFixed(2)})
            </span>
          </p>
        ) : null}
        {doc ? (
          <div className="absolute inset-x-2 bottom-2">
            <PlaybackBar doc={doc} />
          </div>
        ) : null}
        {doc ? (
          <p className="sr-only" data-testid="swarm-summary">
            {tonight}: {doc.query.n_drones} drones, flash blue, with lines to each drone&apos;s
            nearest neighbor.{" "}
            {past
              ? `The closest earlier swarm, ${past}, is drawn as an afterglow ghost on tonight's swarm at the second the DTW path aligns.`
              : "No earlier swarm to compare with."}
          </p>
        ) : null}
      </section>
      <aside aria-label="Swarm memory" className="flex min-h-[24rem] flex-col gap-2 xl:min-h-0">
        <Panel
          id="swarmmatches"
          title="Earlier swarms, best first"
          meta={doc ? `${doc.matches.length} compared` : undefined}
          className="shrink-0"
        >
          {doc && incident ? (
            <SwarmMatches
              incident={incident}
              matches={doc.matches}
              selected={doc.match?.incident_id ?? null}
              offsets={offsets}
            />
          ) : null}
        </Panel>
        <Panel
          id="swarmcurves"
          title="Choreography descriptors (§14)"
          className="min-h-[22rem] flex-1"
        >
          <div className="absolute inset-0 overflow-y-auto px-2 pb-2">
            {doc && tonight ? (
              <>
                <DescriptorCurves doc={doc} names={[tonight, past]} />
                <SwarmTable doc={doc} names={[tonight, past]} />
              </>
            ) : null}
          </div>
        </Panel>
      </aside>
    </main>
  );
}
