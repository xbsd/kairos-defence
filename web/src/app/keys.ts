import { useEffect } from "react";

import { uiStore } from "../state/uiStore";

/** The keys that exist in phase 7 (§17.10 lists the rest, which arrive with Director mode). */
export const SHORTCUTS: [string, string][] = [
  ["M", "Reduce motion on or off"],
  ["?", "Show or hide this list"],
  ["Esc", "Close a dialog"],
];

export function useShortcuts(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)))
        return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const ui = uiStore.getState();
      if (e.key === "m" || e.key === "M") ui.toggleReduce();
      else if (e.key === "?") ui.setShortcuts(!ui.shortcutsOpen);
      else if (e.key === "Escape" && ui.shortcutsOpen) ui.setShortcuts(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
