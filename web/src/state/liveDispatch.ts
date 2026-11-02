// Route each live stream message (D-184): the §16.3 types go to the same stores Live watch
// reads (so the theater and the rails work unchanged); a hello for another incident resets them
// first; the live types go to the live store.
import type { LiveStreamMessage } from "../api/messages";
import { dispatch } from "./dispatch";
import { liveStore } from "./liveStore";
import { matchStore } from "./matchStore";
import { replayStore } from "./replayStore";

export function dispatchLive(m: LiveStreamMessage, now: number = performance.now()): void {
  switch (m.type) {
    case "incident_opened":
      liveStore.getState().opened(m);
      return;
    case "incident_closed":
      liveStore.getState().closed(m);
      return;
    case "swarm_match":
      liveStore.getState().setSwarm(m);
      return;
    case "hello": {
      const prev = replayStore.getState().hello;
      if (prev && prev.incident_id !== m.incident_id) {
        replayStore.getState().clearBuffers();
        matchStore.getState().clear();
        liveStore.getState().setSwarm(null);
      }
      dispatch(m, now);
      return;
    }
    default:
      dispatch(m, now);
  }
}
