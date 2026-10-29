import { useEffect } from "react";

import { directorNext, directorPrev, resetDemo, toggleDirector } from "../director/actions";
import { controls } from "../state/controls";
import { directorStore } from "../state/directorStore";
import { replayStore } from "../state/replayStore";
import { uiStore } from "../state/uiStore";
import { toggleFullscreen } from "./fullscreen";

/** Every key (§17.10), as the ? dialog lists them. */
export const SHORTCUTS: [string, string][] = [
  ["D", "Director mode on or off (from T+0 on Live watch)"],
  ["Space", "Play or pause the replay"],
  ["→", "Director: next beat"],
  ["←", "Director: previous beat"],
  ["R", "Reset the demo: live tables emptied, ledger reseeded, back to T+0"],
  ["M", "Reduce motion on or off"],
  ["F", "Full screen on or off"],
  ["?", "Show or hide this list"],
  ["Esc", "Close a dialog"],
];

function onLive(): boolean {
  return window.location.pathname.startsWith("/live/");
}

/** A keydown to an action name, or null when the key does nothing here. */
export function keyAction(
  e: Pick<KeyboardEvent, "key" | "metaKey" | "ctrlKey" | "altKey">,
):
  | "director"
  | "space"
  | "next"
  | "prev"
  | "reset"
  | "reduce"
  | "fullscreen"
  | "shortcuts"
  | "escape"
  | null {
  if (e.metaKey || e.ctrlKey || e.altKey) return null;
  switch (e.key) {
    case "d":
    case "D":
      return "director";
    case " ":
      return "space";
    case "ArrowRight":
      return "next";
    case "ArrowLeft":
      return "prev";
    case "r":
    case "R":
      return "reset";
    case "m":
    case "M":
      return "reduce";
    case "f":
    case "F":
      return "fullscreen";
    case "?":
      return "shortcuts";
    case "Escape":
      return "escape";
  }
  return null;
}

function typing(el: HTMLElement | null): boolean {
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function handleKey(e: KeyboardEvent): void {
  const el = e.target as HTMLElement | null;
  if (typing(el)) return;
  const action = keyAction(e);
  if (!action) return;
  const ui = uiStore.getState();
  const director = directorStore.getState().active;
  switch (action) {
    case "director":
      void toggleDirector();
      break;
    case "space": {
      // a focused button keeps Space for itself
      if (el && (el.tagName === "BUTTON" || el.tagName === "A" || el.tagName === "SUMMARY")) return;
      if (!onLive()) return;
      e.preventDefault();
      if (replayStore.getState().clock?.playing) controls.pause();
      else controls.play();
      break;
    }
    case "next":
      if (!director) return;
      e.preventDefault();
      void directorNext();
      break;
    case "prev":
      if (!director) return;
      e.preventDefault();
      void directorPrev();
      break;
    case "reset":
      if (!onLive() && !director) return;
      void resetDemo();
      break;
    case "reduce":
      ui.toggleReduce();
      break;
    case "fullscreen":
      toggleFullscreen();
      break;
    case "shortcuts":
      ui.setShortcuts(!ui.shortcutsOpen);
      break;
    case "escape":
      if (ui.shortcutsOpen) ui.setShortcuts(false);
      break;
  }
}

export function useShortcuts(): void {
  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);
}
