import { useEffect, useMemo, useRef } from "react";

import { revealOf } from "../director/engine";
import { localDay } from "../director/captions";
import { baseName } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { overlayStore } from "../state/overlayStore";
import { sceneStore } from "../state/sceneStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { chooseReport, segments, zoneNote, zoneRoad } from "./clues";
import { RESOLVE_MS, scrambled } from "./scramble";

const SOURCE: Record<string, string> = {
  security_forces: "security forces",
  local_police: "local police",
  public_tip: "public tip",
};

/**
 * Report recall (SPEC §17.8, D-131): the top report at the theater's lower left, its text
 * resolving from glyphs over 600 ms (a plain fade in reduce motion), vehicle clues in afterglow
 * and road clues in bone, and the zone note when a road crosses tonight's predicted zone.
 */
export function RecallOverlay({ raised }: { raised: boolean }) {
  const recall = useThrottledStore(matchStore, (s) => s.recall, 4);
  const shown = useThrottledStore(directorStore, (d) => revealOf(d.active, d.beat).recall, 4);
  const collapsed = useThrottledStore(overlayStore, (s) => s.collapsed, 4);
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const offsets = useThrottledStore(sceneStore, (s) => s.installations, 2);
  const chosen = useMemo(() => chooseReport(recall), [recall]);
  const report = chosen?.report ?? null;
  const segs = useMemo(() => (report ? segments(report.text, report.clues) : []), [report]);
  const zone = zoneRoad(report, recall);
  const note = zoneNote(report, recall);
  const spans = useRef<(HTMLSpanElement | null)[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const id = report?.report_id ?? null;

  // resolve the text once per new report (deterministic glyphs, requestAnimationFrame)
  useEffect(() => {
    if (!report || collapsed || !shown) return;
    const write = (t: number) => {
      const all = scrambled(report.text, t);
      let at = 0;
      segs.forEach((s, k) => {
        const el = spans.current[k];
        if (el) el.textContent = all.slice(at, at + s.text.length);
        at += s.text.length;
      });
    };
    if (reduce || typeof requestAnimationFrame !== "function") {
      write(RESOLVE_MS);
      const el = box.current;
      if (reduce && el && typeof el.animate === "function")
        el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 240, easing: "ease-out" });
      return;
    }
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = now - t0;
      write(t);
      if (t < RESOLVE_MS) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // a new report id restarts the resolve; reruns with the same report do not
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, collapsed, shown, reduce]);

  if (!chosen || !report || !shown) return null;
  const off =
    offsets.find((i) => i.installation_id === chosen.match.installation_id)?.utc_offset_hours ?? 0;
  const day = localDay(report.event_ts, off);
  const base = baseName(chosen.match.installation_id);
  const source = SOURCE[report.source] ?? report.source.replace(/_/g, " ");
  return (
    <section
      aria-labelledby="recall-title"
      data-testid="recall-overlay"
      data-report={report.report_id}
      className={`absolute left-3 z-10 w-[min(26rem,calc(100%-1.5rem))] rounded-panel border border-hairline bg-glass backdrop-blur-glass ${
        raised ? "bottom-[7.5rem]" : "bottom-3"
      }`}
    >
      <header className="flex items-baseline justify-between gap-2 px-3 pt-2">
        <h2 id="recall-title" className="text-13 font-bold text-ink-mid">
          Report recall
        </h2>
        <button
          type="button"
          aria-expanded={!collapsed}
          onClick={() => overlayStore.getState().setCollapsed(!collapsed)}
          className="rounded-button px-2 py-0.5 text-12 text-ink-mid hover:bg-hairline hover:text-ink-hi"
        >
          {collapsed ? "Show report" : "Hide report"}
        </button>
      </header>
      {collapsed ? null : (
        <div ref={box} className="px-3 pb-3">
          <p className="text-12 text-ink-mid">
            {base} {source} report{day ? `, ${day}` : ""}, rank {report.rank} for the {base} match
          </p>
          <p className="mt-1.5 text-15 leading-snug text-ink-hi" data-testid="recall-text">
            {segs.map((s, k) => (
              <span
                key={k}
                ref={(el) => {
                  spans.current[k] = el;
                }}
                data-testid={s.clue ? `clue-${s.clue.type}` : undefined}
                data-clue-value={s.clue?.value}
                data-zone={s.clue && zone && s.clue.value === zone.value ? "true" : undefined}
                className={
                  s.clue?.type === "vehicle"
                    ? "rounded-button bg-afterglow/15 px-0.5 text-afterglow"
                    : s.clue?.type === "road"
                      ? "rounded-button bg-bone/15 px-0.5 text-bone"
                      : undefined
                }
              >
                {s.text}
              </span>
            ))}
          </p>
          {note ? (
            <p className="mt-2 text-13 text-bone" data-testid="zone-note">
              {note}
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
