import type { SwarmResponse } from "../api/messages";
import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { playRange, SWARM_SPEEDS, swarmStore } from "../state/swarmStore";
import { matchSecond } from "./swarmMath";

/**
 * Play, pause, speed and a scrubber over the recorded seconds; the readout gives tonight's second
 * and the matched swarm's DTW-aligned second. Redraws at most 10 times a second.
 */
export function PlaybackBar({ doc }: { doc: SwarmResponse }) {
  const s = useThrottledStore(swarmStore, (st) => ({
    t: st.playhead,
    playing: st.playing,
    speed: st.speed,
  }));
  const [lo, hi] = playRange(doc);
  const ms = matchSecond(doc, s.t);
  const sec = Math.round(s.t);
  return (
    <div
      role="group"
      aria-label="Swarm replay"
      className="flex items-center gap-3 rounded-panel border border-hairline bg-glass px-3 py-2 backdrop-blur-glass"
    >
      <button
        type="button"
        onClick={() => {
          // the store, not the throttled snapshot: two quick clicks must toggle twice
          const st = swarmStore.getState();
          if (st.playing) st.pause();
          else st.play();
        }}
        aria-label={s.playing ? "Pause the swarm replay" : "Play the swarm replay"}
        data-testid="swarm-play"
        className="rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi hover:bg-hairline"
      >
        {s.playing ? "Pause" : "Play"}
      </button>
      <div role="group" aria-label="Swarm replay speed" className="flex items-center gap-1">
        {SWARM_SPEEDS.map((v) => (
          <button
            key={v}
            type="button"
            aria-pressed={s.speed === v}
            aria-label={`Swarm replay at ${v} times`}
            onClick={() => swarmStore.getState().setSpeed(v)}
            className={`rounded-button px-2 py-1 font-mono text-13 ${
              s.speed === v ? "bg-hairline text-flash" : "text-ink-mid hover:text-ink-hi"
            }`}
          >
            {v}×
          </button>
        ))}
      </div>
      <input
        type="range"
        min={lo}
        max={hi}
        step={1}
        value={Math.min(hi, Math.max(lo, sec))}
        onChange={(e) => swarmStore.getState().setPlayhead(Number(e.target.value))}
        aria-label="Swarm replay second"
        aria-valuetext={tPlus(sec)}
        data-testid="swarm-scrubber"
        className="min-w-0 flex-1 accent-(--flash)"
      />
      <span
        data-testid="swarm-playhead"
        data-t={sec}
        className="font-mono text-13 whitespace-nowrap text-ink-hi"
      >
        {tPlus(sec)}
        {ms !== null ? (
          <span className="text-ink-mid"> · match {tPlus(Math.round(ms))}</span>
        ) : null}
      </span>
    </div>
  );
}
