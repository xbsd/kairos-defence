import { useEffect } from "react";

import { useThrottledStore } from "../lib/useThrottledStore";
import { useThrottledStores } from "../lib/useThrottledStores";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { sceneStore } from "../state/sceneStore";
import type { StoreApi } from "zustand/vanilla";
import { BEATS } from "./beats";
import { caption } from "./captions";
import { captionContext } from "./context";

const STORES = [
  directorStore,
  matchStore,
  replayStore,
  sceneStore,
] as unknown as StoreApi<unknown>[];

/**
 * The Director caption (24 px, bottom center, glass strip, read aloud politely) with the beat
 * name above it. `placement` "theater" sits inside Live watch's theater; "page" at the bottom of
 * the viewport on the page beats.
 */
export function DirectorCaption({ placement }: { placement: "theater" | "page" }) {
  const d = useThrottledStore(directorStore, (s) => ({
    active: s.active,
    beat: s.beat,
    page: s.page,
  }));
  const beat = d.beat >= 0 ? BEATS[d.beat] : undefined;
  const text = useThrottledStores(
    STORES,
    () => (beat ? caption(beat.id, captionContext()) : ""),
    4,
  );
  const onPage = placement === "page" && d.active && !!beat && d.page !== null;
  // pages scroll their last controls clear of the caption (index.css reads this)
  useEffect(() => {
    if (placement !== "page") return;
    document.body.dataset.director = onPage ? "page" : "";
  }, [placement, onPage]);
  if (!d.active || !beat) return null;
  if (placement === "theater" ? d.page !== null : d.page === null) return null;
  return (
    <div
      className={`pointer-events-none z-20 flex justify-center px-4 ${
        placement === "theater" ? "absolute inset-x-0 bottom-3" : "fixed inset-x-0 bottom-5"
      }`}
    >
      <div
        data-testid="director-caption-box"
        className="max-w-[56rem] rounded-panel border border-hairline bg-glass px-5 py-3 text-center backdrop-blur-glass"
      >
        <p className="text-13 text-ink-mid">
          Beat {d.beat + 1} of {BEATS.length}: {beat.title}
        </p>
        <p
          data-testid="director-caption"
          aria-live="polite"
          className="text-24 leading-tight text-ink-hi"
        >
          {text}
        </p>
      </div>
    </div>
  );
}

/** The thin progress rail along the bottom edge (§17.10): one segment per beat. */
export function DirectorRail() {
  const d = useThrottledStore(directorStore, (s) => ({
    active: s.active,
    beat: s.beat,
    log: s.log,
  }));
  if (!d.active) return null;
  const beat = d.beat >= 0 ? BEATS[d.beat] : undefined;
  const last = d.log[d.log.length - 1];
  return (
    <div
      data-testid="director-beat"
      data-beat={beat?.id ?? ""}
      data-n={d.beat + 1}
      data-t={last?.t_s ?? ""}
      role="progressbar"
      aria-label="Director progress"
      aria-valuemin={1}
      aria-valuemax={BEATS.length}
      aria-valuenow={Math.max(1, d.beat + 1)}
      aria-valuetext={beat ? `Beat ${d.beat + 1} of ${BEATS.length}: ${beat.title}` : "Starting"}
      className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex h-1 gap-px"
    >
      {BEATS.map((b, i) => (
        <span
          key={b.id}
          className={`h-full flex-1 transition-colors duration-(--dur-panel) ${
            i < d.beat ? "bg-ink-mid" : i === d.beat ? "bg-flash" : "bg-hairline"
          }`}
        />
      ))}
    </div>
  );
}
