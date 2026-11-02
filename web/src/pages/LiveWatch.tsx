import { CommandBar } from "../app/CommandBar";
import { DirectorCaption } from "../director/DirectorOverlay";
import { useThrottledStore } from "../lib/useThrottledStore";
import { RecallBeam } from "../overlay/RecallBeam";
import { RecallOverlay } from "../overlay/RecallOverlay";
import { LedgerChain } from "../panels/LedgerChain";
import { LensPanel } from "../panels/LensPanel";
import { MatchList } from "../panels/MatchList";
import { RegionConstellation } from "../panels/RegionConstellation";
import { Recorder } from "../panels/Recorder";
import { Signals } from "../panels/Signals";
import { StreamPanel } from "../panels/Stream";
import { TheaterFrame } from "../three/TheaterFrame";
import { directorStore } from "../state/directorStore";
import { useReplay } from "../state/useReplay";

/**
 * Live watch (SPEC §17.2): the theater is the hero, the memory rail docks on the right and the
 * instrument rail along the bottom. Below 1280 px the rails stack under the theater.
 */
export function LiveWatch({ incidentId }: { incidentId: string }) {
  const { scene, sceneError } = useReplay(incidentId);
  const trail = ["Live watch", scene?.name ?? incidentId];
  // the Director caption sits at the theater's bottom center; the report stacks above it
  const captioned = useThrottledStore(directorStore, (d) => d.active && d.page === null, 4);
  return (
    <>
      <CommandBar trail={trail} replay />
      <div
        data-testid="live-watch"
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
          <RecallOverlay raised={captioned} />
          <RecallBeam />
          <DirectorCaption placement="theater" />
        </main>
        <aside
          aria-label="Memory rail"
          className="flex min-h-[20rem] flex-col gap-2 xl:col-start-2 xl:row-span-2 xl:row-start-1 xl:min-h-0"
        >
          <MatchList />
          <RegionConstellation />
          <LensPanel />
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
    </>
  );
}
