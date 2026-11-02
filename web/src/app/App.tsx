import { lazy, Suspense, useEffect, type ReactNode } from "react";

import { api } from "../api/client";
import { ChatPanel } from "../chat/ChatPanel";
import { loadChatStatus } from "../chat/chatStore";
import { DirectorCaption, DirectorRail } from "../director/DirectorOverlay";
import { useDirector } from "../director/useDirector";
import { Home } from "../pages/Home";
import { NotFound } from "../pages/Planned";
import { sceneStore } from "../state/sceneStore";
import { prefersReducedMotion } from "../theme/motion";
import { uiStore } from "../state/uiStore";
import { CommandBar } from "./CommandBar";
import { routeTitle, useRoute, type Route } from "./routes";
import { ShortcutsDialog } from "./Shortcuts";
import { useShortcuts } from "./keys";

// Pages load on demand (D-141): only Live watch pulls in the 3D chunk.
const LiveWatch = lazy(() => import("../pages/LiveWatch").then((m) => ({ default: m.LiveWatch })));
const MatchExplainer = lazy(() =>
  import("../pages/MatchExplainer").then((m) => ({ default: m.MatchExplainer })),
);
const CaseBoard = lazy(() => import("../pages/CaseBoard").then((m) => ({ default: m.CaseBoard })));
const CaseList = lazy(() => import("../pages/CaseBoard").then((m) => ({ default: m.CaseList })));
const Evidence = lazy(() => import("../pages/Evidence").then((m) => ({ default: m.Evidence })));
const ShiftDelta = lazy(() =>
  import("../pages/ShiftDelta").then((m) => ({ default: m.ShiftDelta })),
);
const Eval = lazy(() => import("../pages/Eval").then((m) => ({ default: m.Eval })));
const SwarmView = lazy(() => import("../pages/SwarmView").then((m) => ({ default: m.SwarmView })));
const LiveMode = lazy(() => import("../pages/LiveMode").then((m) => ({ default: m.LiveMode })));

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

function useInstallations(): void {
  useEffect(() => {
    if (sceneStore.getState().installations.length) return;
    api
      .installations()
      .then((list) => sceneStore.getState().setInstallations(list))
      .catch(() => undefined);
  }, []);
}

/** Chat (§18.3) shows only when the server says a provider is configured: ask once. */
function useChatStatus(): void {
  useEffect(() => {
    void loadChatStatus();
  }, []);
}

function Loading() {
  return (
    <main aria-label="Loading" className="grid flex-1 place-items-center p-8">
      <p className="text-15 text-ink-mid">Loading</p>
    </main>
  );
}

function trail(r: Route): string[] {
  if (r.name === "case") return ["Case board", r.caseId];
  if (r.name === "evidence" && r.caseId) return ["Evidence", r.caseId];
  if (r.name === "swarm" && r.incident) return ["Swarm view", r.incident];
  return [routeTitle(r)];
}

function Page({ route }: { route: Route }): ReactNode {
  switch (route.name) {
    case "home":
      return <Home />;
    case "explainer":
      return <MatchExplainer incident={route.incident} at={route.at} track={route.track} />;
    case "cases":
      return <CaseList />;
    case "case":
      return <CaseBoard caseId={route.caseId} focus={route.focus} />;
    case "evidence":
      return <Evidence caseId={route.caseId} />;
    case "delta":
      return <ShiftDelta since={route.since} />;
    case "eval":
      return <Eval />;
    case "swarm":
      return <SwarmView incident={route.incident} match={route.match} />;
    case "notfound":
      return <NotFound path={route.path} />;
    case "live":
    case "livemode":
      return null;
  }
}

/** The shell (SPEC §17.2): the command bar on every page, then the routed page. */
export function App() {
  const route = useRoute();
  useShortcuts();
  useOsReducedMotion();
  useInstallations();
  useChatStatus();
  useDirector();
  return (
    <div className="flex h-full min-h-0 flex-col bg-scope">
      {route.name === "live" ? (
        <Suspense fallback={<Loading />}>
          <LiveWatch incidentId={route.incidentId} />
        </Suspense>
      ) : route.name === "livemode" ? (
        <Suspense fallback={<Loading />}>
          <LiveMode />
        </Suspense>
      ) : (
        <>
          <CommandBar trail={trail(route)} />
          <Suspense fallback={<Loading />}>
            <Page route={route} />
          </Suspense>
        </>
      )}
      <DirectorCaption placement="page" />
      <DirectorRail />
      <ChatPanel />
      <ShortcutsDialog />
    </div>
  );
}
