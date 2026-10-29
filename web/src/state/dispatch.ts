// Route each stream message to its store (SPEC §16.3). A `clock` with `seeked` drops the
// buffers: the server follows it with a catch-up of the last 120 s and the current result.
import { toBlock, type StreamMessage } from "../api/messages";
import { caseStore } from "./caseStore";
import { matchStore } from "./matchStore";
import { replayStore } from "./replayStore";

export function dispatch(m: StreamMessage, now: number = performance.now()): void {
  const replay = replayStore.getState();
  switch (m.type) {
    case "clock":
      if (m.seeked) {
        replay.clearBuffers();
        matchStore.getState().clear();
      }
      replay.apply(m, now);
      return;
    case "hello":
    case "point":
    case "rf":
    case "rid":
    case "features":
    case "ingest":
      replay.apply(m, now);
      return;
    case "match":
    case "forecast":
    case "recall":
    case "dtw":
      matchStore.getState().apply(m, now);
      return;
    case "ledger":
      caseStore.getState().addBlocks([toBlock(m)], true, now);
      return;
    case "error":
      replay.setError(m.message);
      return;
  }
}
