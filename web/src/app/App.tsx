import { useEffect } from "react";

import { Home } from "../pages/Home";
import { LiveWatch } from "../pages/LiveWatch";
import { NotFound, Planned } from "../pages/Planned";
import { prefersReducedMotion } from "../theme/motion";
import { uiStore } from "../state/uiStore";
import { CommandBar } from "./CommandBar";
import { PLANNED, useRoute } from "./routes";
import { ShortcutsDialog } from "./Shortcuts";
import { useShortcuts } from "./keys";

function useOsReducedMotion(): void {
  useEffect(() => {
    uiStore.getState().setOsReduce(prefersReducedMotion());
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const on = (e: MediaQueryListEvent) => uiStore.getState().setOsReduce(e.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
}

/** The shell (SPEC §17.2): the command bar on every page, then the routed page. */
export function App() {
  const route = useRoute();
  useShortcuts();
  useOsReducedMotion();
  return (
    <div className="flex h-full min-h-0 flex-col bg-scope">
      {route.name === "live" ? (
        <LiveWatch incidentId={route.incidentId} />
      ) : (
        <>
          <CommandBar
            trail={route.name === "planned" ? [PLANNED[route.page].title] : ["Live watch"]}
          />
          {route.name === "home" ? <Home /> : null}
          {route.name === "planned" ? <Planned page={route.page} /> : null}
          {route.name === "notfound" ? <NotFound path={route.path} /> : null}
        </>
      )}
      <ShortcutsDialog />
    </div>
  );
}
