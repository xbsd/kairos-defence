import { CommandBar } from "../app/CommandBar";
import { baseName } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { IncidentList } from "../live/IncidentList";
import { Launcher } from "../live/Launcher";
import { RevealCard } from "../live/RevealCard";
import { SwarmMatchList } from "../live/SwarmMatchList";
import { RecallBeam } from "../overlay/RecallBeam";
import { RecallOverlay } from "../overlay/RecallOverlay";
import { LedgerChain } from "../panels/LedgerChain";
import { MatchList } from "../panels/MatchList";
import { Recorder } from "../panels/Recorder";
import { Signals } from "../panels/Signals";
import { StreamPanel } from "../panels/Stream";
import { liveStore } from "../state/liveStore";
import { replayStore } from "../state/replayStore";
import { sceneStore } from "../state/sceneStore";
import { useLive } from "../state/useLive";
import { TheaterFrame } from "../three/TheaterFrame";

/** Says so when nothing flies at the watched installation (D-184). */
function Idle({ installation }: { installation: string }) {
  const s = useThrottledStore(
    liveStore,
    (st) => ({
      open: Object.values(st.incidents).some(
        (r) => r.installation_id === installation && r.state !== "closed",
      ),
    }),
    4,
  );
  const hello = useThrottledStore(replayStore, (st) => st.hello?.incident_id ?? "", 4);
  if (s.open) return null;
  return (
    <div
      data-testid="live-idle"
      className="pointer-events-none absolute inset-x-0 top-16 flex justify-center px-4"
    >
      <p className="rounded-panel border border-hairline bg-glass px-4 py-2 text-15 text-ink-mid backdrop-blur-glass">
        Nothing is flying at {baseName(installation)}
        {hello ? " now: the last incident has closed" : ""}. Launch a scenario to watch it live.
      </p>
    </div>
  );
}

/**
 * The Live page (D-169, D-184): a simulated sensor network streams detections into the app, which
 * forms incidents, matches, forecasts and recalls them live. Same grid as Live watch: the theater
 * is the hero; the memory rail holds the launcher, the matches and this session's incidents; the
 * instrument rail shows the real stream, signals, writes and ledger. Everything shown comes from
 * the live stream or the live routes (rule 10).
 */
export function LiveMode() {
  const installation = useThrottledStore(liveStore, (s) => s.installation, 4);
  const swarm = useThrottledStore(liveStore, (s) => s.swarm !== null, 4);
  const installations = useThrottledStore(sceneStore, (s) => s.installations, 2);
  const { scene, sceneError } = useLive(installation);
  const ids = installations.length ? installations.map((i) => i.installation_id) : [installation];
  return (
    <>
      <CommandBar trail={["Live", `Installation ${baseName(installation)}`]} mode="live" />
      <div
        data-testid="live-mode"
        className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-y-auto p-2 xl:grid-cols-[minmax(0,1fr)_25rem] xl:grid-rows-[minmax(0,1fr)_17rem] xl:overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_28rem] 2xl:grid-rows-[minmax(0,1fr)_19rem]"
      >
        <main
          aria-label="Live theater"
          className="relative min-h-[28rem] overflow-hidden rounded-panel border border-hairline xl:col-start-1 xl:row-start-1 xl:min-h-0"
        >
          <TheaterFrame scene={scene} />
          {sceneError ? (
            <p role="alert" className="absolute top-3 left-3 text-13 text-alert">
              Scene: {sceneError}
            </p>
          ) : null}
          <Idle installation={installation} />
          <RecallOverlay raised={false} />
          <RecallBeam />
        </main>
        <aside
          aria-label="Memory rail"
          className="flex min-h-[20rem] flex-col gap-2 xl:col-start-2 xl:row-span-2 xl:row-start-1 xl:min-h-0 xl:overflow-y-auto"
        >
          <Launcher installations={ids} />
          {swarm ? <SwarmMatchList /> : <MatchList live />}
          <IncidentList />
        </aside>
        <section
          aria-label="Instrument rail"
          className="grid min-h-[17rem] grid-cols-1 gap-2 md:grid-cols-2 xl:col-start-1 xl:row-start-2 xl:min-h-0 xl:grid-cols-[1.45fr_1.2fr_0.95fr_1fr]"
        >
          <StreamPanel />
          <Signals />
          <Recorder />
          <LedgerChain />
        </section>
      </div>
      <RevealCard />
    </>
  );
}
