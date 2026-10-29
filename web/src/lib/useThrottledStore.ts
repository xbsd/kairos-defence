// Subscribe a DOM component to a vanilla store at most `hz` times per second (SPEC §17.11:
// panels redraw ≤ 10 Hz; high-frequency data never re-renders React per message).
import { useEffect, useReducer, useRef } from "react";
import type { StoreApi } from "zustand/vanilla";

export function useThrottledStore<S, T>(store: StoreApi<S>, select: (s: S) => T, hz = 10): T {
  const [, force] = useReducer((n: number) => n + 1, 0);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);
  const last = useRef(0);
  useEffect(() => {
    const gap = 1000 / hz;
    const unsub = store.subscribe(() => {
      if (pending.current !== null) return;
      const wait = Math.max(0, last.current + gap - performance.now());
      pending.current = setTimeout(() => {
        pending.current = null;
        last.current = performance.now();
        force();
      }, wait);
    });
    return () => {
      unsub();
      if (pending.current !== null) clearTimeout(pending.current);
      pending.current = null;
    };
  }, [store, hz]);
  return select(store.getState());
}
