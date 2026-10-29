import { useEffect } from "react";

import { swarmStore } from "../state/swarmStore";

/** Advances the playhead from requestAnimationFrame while playing (§17.11: no setInterval). */
export function usePlayback(): void {
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      swarmStore.getState().tick(Math.min(0.25, (now - last) / 1000));
      last = now;
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);
}
