import { Component, Suspense, type ReactNode } from "react";

import type { Scene } from "../api/messages";
import { Theater } from "./Theater";

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

function TheaterLoading() {
  return (
    <div className="grid h-full place-items-center p-8 text-center">
      <p className="text-13 text-ink-mid">Starting the 3D theater</p>
    </div>
  );
}

/** The theater with its own error boundary and its own Suspense boundary: its fonts and shaders
 * suspend inside the canvas, which must not blank the rails around it (D-185). */
export function TheaterFrame({ scene }: { scene: Scene | null }) {
  return (
    <TheaterBoundary>
      <Suspense fallback={<TheaterLoading />}>
        <Theater scene={scene} />
      </Suspense>
    </TheaterBoundary>
  );
}
