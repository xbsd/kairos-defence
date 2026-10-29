import { useEffect, useState, type RefObject } from "react";

/** An element's content size in CSS pixels, kept current with a ResizeObserver. */
export function useSize(
  ref: RefObject<HTMLElement | null>,
  fallback: { width: number; height: number } = { width: 320, height: 320 },
): { width: number; height: number } {
  const [size, setSize] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => {
      const width = Math.max(120, Math.floor(el.clientWidth || fallback.width));
      const height = Math.max(0, Math.floor(el.clientHeight || fallback.height));
      setSize((s) => (s.width === width && s.height === height ? s : { width, height }));
    };
    read();
    if (typeof ResizeObserver !== "function") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback.width, fallback.height]);
  return size;
}

/** An element's content width in CSS pixels. */
export function useWidth(ref: RefObject<HTMLElement | null>, fallback = 320): number {
  return useSize(ref, { width: fallback, height: 0 }).width;
}
