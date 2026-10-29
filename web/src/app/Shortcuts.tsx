import { useEffect, useRef } from "react";

import { useThrottledStore } from "../lib/useThrottledStore";
import { uiStore } from "../state/uiStore";
import { SHORTCUTS } from "./keys";

export function ShortcutsDialog() {
  const open = useThrottledStore(uiStore, (s) => s.shortcutsOpen);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="shortcuts-title"
      onClose={() => uiStore.getState().setShortcuts(false)}
      className="m-auto w-96 rounded-panel border border-hairline bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
    >
      <h2 id="shortcuts-title" className="text-15 font-bold">
        Keyboard shortcuts
      </h2>
      <dl className="mt-3 grid grid-cols-[4rem_1fr] gap-y-2 text-13">
        {SHORTCUTS.map(([k, what]) => (
          <div key={k} className="contents">
            <dt>
              <kbd className="rounded-button border border-hairline px-2 py-0.5 font-mono">{k}</kbd>
            </dt>
            <dd className="text-ink-mid">{what}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-13 text-ink-mid">
        Director mode keys (Space, arrows, R, F) arrive with Director mode in phase 8.
      </p>
      <form method="dialog" className="mt-4 text-right">
        <button className="rounded-button border border-hairline px-3 py-1 text-13 hover:border-flash">
          Close
        </button>
      </form>
    </dialog>
  );
}
