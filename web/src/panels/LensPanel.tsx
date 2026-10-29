import { useEffect, useRef } from "react";

import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { useSize } from "../lib/useWidth";
import { TimeWarpLens } from "../lens/TimeWarpLens";
import { revealOf } from "../director/engine";
import { controls } from "../state/controls";
import { directorStore } from "../state/directorStore";
import { DEFAULT_CHANNEL, lensDtw, matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { Panel } from "./Panel";

/** The memory rail's time-warp lens (§17.7): the stream's `dtw`, or a chosen match and channel. */
export function LensPanel() {
  const s = useThrottledStore(matchStore, (st) => ({
    match: st.match,
    dtw: lensDtw(st),
    sel: st.lensSel,
    mode: st.lensMode,
  }));
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const shown = useThrottledStore(directorStore, (d) => revealOf(d.active, d.beat).lens, 4);
  const hello = useThrottledStore(replayStore, (st) => st.hello, 2);
  const box = useRef<HTMLDivElement>(null);
  const { height } = useSize(box, { width: 360, height: 300 });
  const top = s.match?.matches.slice(0, 3) ?? [];
  const track = s.dtw?.match_track_id ?? s.sel?.track ?? top[0]?.track_id ?? null;
  const channel = s.sel?.channel ?? s.dtw?.channel ?? DEFAULT_CHANNEL;

  // a new rerun: ask again for the chosen match so the lens follows the replay clock
  const t = s.match?.t_s ?? null;
  const want = s.sel;
  useEffect(() => {
    if (t === null || !want) return;
    if (!top.some((m) => m.track_id === want.track)) return;
    controls.dtw(want.track, want.channel);
    // top is derived from the same match as t
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, want?.track, want?.channel]);

  const pick = (trackId: string, ch: string) => {
    matchStore.getState().setLensSel({ track: trackId, channel: ch });
    controls.dtw(trackId, ch);
  };

  let waiting: string | null = null;
  if (!s.match || !top.length)
    waiting = hello
      ? `The lens opens with the first match at ${tPlus(hello.min_track_s)}`
      : "Waiting for the replay";
  else if (!shown) waiting = "The lens opens at the time-warp beat";

  return (
    <Panel
      id="lens"
      title="Time-warp lens"
      className="min-h-[13rem] flex-[1_1_0]"
      meta={s.dtw ? `At ${tPlus(s.dtw.t_s)}` : undefined}
    >
      <div ref={box} className="absolute inset-0 overflow-y-auto px-3 pb-2">
        {waiting ? (
          <p className="text-13 text-ink-mid" data-testid="lens-waiting">
            {waiting}
          </p>
        ) : (
          <TimeWarpLens
            dtw={s.dtw}
            matches={top}
            track={track}
            channel={channel}
            mode={s.mode}
            reduce={reduce}
            variant="compact"
            budget={height - 96}
            onMode={(m) => matchStore.getState().setLensMode(m)}
            onTrack={(tr) => pick(tr, channel)}
            onChannel={(ch) => pick(track ?? top[0]?.track_id ?? "", ch)}
          />
        )}
      </div>
    </Panel>
  );
}
