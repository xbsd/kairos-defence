// The caption context (D-125): everything a Director caption may need, read from the stores now.
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { recordedTotal, replayStore } from "../state/replayStore";
import { sceneStore } from "../state/sceneStore";
import type { CaptionCtx } from "./captions";

/** Everything a caption may need, read from the stores now. */
export function captionContext(): CaptionCtx {
  const r = replayStore.getState();
  const m = matchStore.getState();
  const sc = sceneStore.getState();
  const d = directorStore.getState();
  const track = r.hello?.tracks[0];
  const first = track ? r.tracks[track]?.[0] : undefined;
  return {
    hello: r.hello,
    // only the true first contact (a seek drops the early buffer)
    firstPoint: first && first.t_s <= 5 ? [first.x, first.y] : null,
    scene: sc.scene,
    offsets: Object.fromEntries(
      sc.installations.map((i) => [i.installation_id, i.utc_offset_hours]),
    ),
    rows: recordedTotal(r),
    writeMs: r.lastIngest?.write_ms ?? null,
    match: m.match,
    lensTrack: m.lensSel?.track ?? null,
    forecast: m.forecast,
    recall: m.recall,
    facts: d.facts,
  };
}
