import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toggleFullscreen } from "../src/app/fullscreen";
import { handleKey, keyAction, SHORTCUTS } from "../src/app/keys";
import type { ReplayStream } from "../src/api/stream";
import { setStream } from "../src/state/controls";
import { directorStore } from "../src/state/directorStore";
import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";
import { clock } from "./fixtures";
import { resetStores } from "./panelKit";

function key(k: string, target: EventTarget = document.body): KeyboardEvent {
  const e = new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true });
  Object.defineProperty(e, "target", { value: target });
  return e;
}

beforeEach(() => {
  resetStores();
  directorStore.setState({ active: false, page: null, beat: 0, log: [] });
  window.history.replaceState(null, "", "/live/DEMO-BRAVO-0828");
});
afterEach(() => setStream(null));

describe("keys (§17.10)", () => {
  it("maps every listed key to an action", () => {
    const want: Record<string, string> = {
      d: "director",
      " ": "space",
      ArrowRight: "next",
      ArrowLeft: "prev",
      r: "reset",
      m: "reduce",
      f: "fullscreen",
      "?": "shortcuts",
      Escape: "escape",
    };
    for (const [k, a] of Object.entries(want))
      expect(keyAction({ key: k, metaKey: false, ctrlKey: false, altKey: false })).toBe(a);
    expect(keyAction({ key: "d", metaKey: true, ctrlKey: false, altKey: false })).toBeNull();
    expect(SHORTCUTS.map(([k]) => k)).toEqual(["D", "Space", "→", "←", "R", "M", "F", "?", "Esc"]);
  });

  it("Space plays and pauses on Live watch, not while typing or on a focused button", () => {
    const sent: string[] = [];
    setStream({
      play: () => sent.push("play"),
      pause: () => sent.push("pause"),
    } as unknown as ReplayStream);
    replayStore.getState().apply(clock(10, false));
    handleKey(key(" "));
    replayStore.getState().apply(clock(10, true));
    handleKey(key(" "));
    handleKey(key(" ", document.createElement("input")));
    handleKey(key(" ", document.createElement("button")));
    expect(sent).toEqual(["play", "pause"]);
    window.history.replaceState(null, "", "/cases");
    handleKey(key(" "));
    expect(sent).toEqual(["play", "pause"]);
  });

  it("arrows act only in Director; M and ? toggle", () => {
    const sent: string[] = [];
    setStream({ seek: (t: number) => sent.push(`seek ${t}`) } as unknown as ReplayStream);
    handleKey(key("ArrowRight"));
    expect(sent).toEqual([]);
    directorStore.setState({ active: true });
    replayStore.getState().apply(clock(50));
    handleKey(key("ArrowRight"));
    handleKey(key("ArrowLeft"));
    expect(sent).toEqual(["seek 90", "seek 15"]);
    uiStore.setState({ userReduce: false });
    handleKey(key("m"));
    expect(uiStore.getState().userReduce).toBe(true);
    handleKey(key("?"));
    expect(uiStore.getState().shortcutsOpen).toBe(true);
    handleKey(key("Escape"));
    expect(uiStore.getState().shortcutsOpen).toBe(false);
  });

  it("F asks for full screen, and leaves it when already there", () => {
    const request = vi.fn(() => Promise.resolve());
    const exit = vi.fn(() => Promise.resolve());
    const doc = {
      fullscreenElement: null,
      exitFullscreen: exit,
      documentElement: { requestFullscreen: request },
    } as unknown as Document;
    toggleFullscreen(doc);
    expect(request).toHaveBeenCalledOnce();
    toggleFullscreen({ ...doc, fullscreenElement: {} } as unknown as Document);
    expect(exit).toHaveBeenCalledOnce();
  });
});
