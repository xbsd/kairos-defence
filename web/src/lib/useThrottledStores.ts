// useThrottledStore over several vanilla stores at once: re-render at most `hz` times a second
// when any of them changes, then read them all with `select` (SPEC §17.11).
import { useEffect, useReducer, useRef } from "react";
import type { StoreApi } from "zustand/vanilla";

export function useThrottledStores<T>(
  stores: readonly StoreApi<unknown>[],
  select: () => T,
  hz = 4,
): T {
  const [, force] = useReducer((n: number) => n + 1, 0);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);
  const last = useRef(0);
  useEffect(() => {
    const gap = 1000 / hz;
    const on = () => {
      if (pending.current !== null) return;
      const wait = Math.max(0, last.current + gap - performance.now());
      pending.current = setTimeout(() => {
        pending.current = null;
        last.current = performance.now();
        force();
      }, wait);
    };
    const unsubs = stores.map((s) => s.subscribe(on));
    return () => {
      unsubs.forEach((u) => u());
      if (pending.current !== null) clearTimeout(pending.current);
      pending.current = null;
    };
    // the store list is static per call site
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hz]);
  return select();
}
