import { useEffect, useRef } from "react";

import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { matchStore } from "../state/matchStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { WorkbenchPanel } from "./WorkbenchPanel";
import { startWorkbenchClock, workbenchStore } from "./workbenchStore";

/** The DTW workbench in a native modal dialog (D-189). It replays the trace it was opened with;
 * a newer rerun from the stream only offers "Newer rerun available: replay it". */
export function WorkbenchDialog() {
  const s = useThrottledStore(workbenchStore, (st) => ({
    open: st.open,
    msg: st.msg,
    items: st.items,
    elapsed: st.elapsed,
    rate: st.rate,
    playing: st.playing,
    source: st.source,
  }));
  const latest = useThrottledStore(matchStore, (st) => st.trace, 4);
  const reduce = useThrottledStore(uiStore, reduceMotion, 4);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (s.open && !d.open) {
      if (typeof d.showModal === "function") d.showModal();
      else d.setAttribute("open", "");
    }
    if (!s.open && d.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
  }, [s.open]);
  useEffect(() => (s.open ? startWorkbenchClock() : undefined), [s.open]);
  const newer =
    s.source === "stream" &&
    latest !== null &&
    s.msg !== null &&
    (latest.incident_id !== s.msg.incident_id || latest.t_s !== s.msg.t_s)
      ? latest
      : null;
  const st = workbenchStore.getState();
  return (
    <dialog
      ref={ref}
      aria-labelledby="workbench-title"
      data-testid="workbench-dialog"
      onCancel={(e) => {
        e.preventDefault();
        st.close();
      }}
      className="m-auto max-h-[92vh] w-[min(78rem,96vw)] overflow-y-auto rounded-panel border border-hairline bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
    >
      {s.open && s.msg ? (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="workbench-title" className="text-15 font-bold">
              DTW workbench: {s.msg.incident_id}, rerun {tPlus(s.msg.t_s)}
            </h2>
            <span className="flex items-center gap-2">
              {newer ? (
                <button
                  type="button"
                  onClick={() => st.pin(newer, reduce)}
                  className="rounded-button border border-flash px-2.5 py-0.5 text-13 text-flash hover:bg-hairline"
                >
                  Newer rerun available ({tPlus(newer.t_s)}): replay it
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => st.close()}
                className="rounded-button border border-hairline px-3 py-1 text-13 hover:border-flash"
              >
                Close
              </button>
            </span>
          </div>
          <div className="mt-3">
            <WorkbenchPanel
              msg={s.msg}
              items={s.items}
              elapsed={s.elapsed}
              rate={s.rate}
              playing={s.playing}
              onPlaying={(p) => st.setPlaying(p)}
              onStep={() => st.step()}
              onReplay={() => st.replay(reduce)}
              onRate={(r) => st.setRate(r)}
            />
          </div>
        </>
      ) : (
        <h2 id="workbench-title" className="sr-only">
          DTW workbench
        </h2>
      )}
    </dialog>
  );
}

/** Opens the workbench on the stream's latest trace (Live page, Live watch). */
export function WorkbenchButton() {
  const trace = useThrottledStore(matchStore, (st) => st.trace, 4);
  const reduce = useThrottledStore(uiStore, reduceMotion, 4);
  return (
    <button
      type="button"
      disabled={trace === null}
      onClick={() => trace && workbenchStore.getState().openWith(trace, "stream", reduce)}
      title="Replay this rerun's matcher computation in slow motion"
      className="shrink-0 rounded-button border border-hairline px-2 py-0.5 text-12 whitespace-nowrap text-ink-mid hover:border-flash hover:text-ink-hi disabled:cursor-not-allowed disabled:text-ink-low"
    >
      DTW workbench
    </button>
  );
}
