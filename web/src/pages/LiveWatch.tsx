import { Component, Suspense, type ReactNode } from "react";

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
import { Theater } from "../three/Theater";
import { directorStore } from "../state/directorStore";
import { useReplay } from "../state/useReplay";

/** Keeps the DOM panels alive if WebGL fails (headless browsers, old GPUs). */
class TheaterBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  override state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : String(e) };
  }
  override render() {
    if (this.state.error)
      return (
        <div role="alert" className="grid h-full place-items-center p-8 text-center">
          <div>
            <p className="text-15 text-ink-hi">The 3D theater could not start.</p>
            <p className="mt-1 text-13 text-ink-mid">{this.state.error}</p>
          </div>
        </div>
      );
    return this.props.children;
  }
}

export function TheaterLoading() {
  return (
    <div className="grid h-full place-items-center p-8 text-center">
      <p className="text-13 text-ink-mid">Starting the 3D theater</p>
    </div>
  );
}

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
          <TheaterBoundary>
            {/* the theater's own boundary: its fonts and shaders suspend inside the canvas, which
                must not blank the rails (D-185) */}
            <Suspense fallback={<TheaterLoading />}>
              <Theater scene={scene} />
            </Suspense>
          </TheaterBoundary>
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
