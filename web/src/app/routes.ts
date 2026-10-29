// A small history-API router (D-112): no dependency, a few routes.
import { useSyncExternalStore } from "react";

export type Route =
  | { name: "home" }
  | { name: "live"; incidentId: string }
  | { name: "planned"; page: PlannedPage }
  | { name: "notfound"; path: string };

export type PlannedPage = "explainer" | "cases" | "swarm" | "evidence" | "delta" | "eval";

export const PLANNED: Record<PlannedPage, { title: string; phase: number }> = {
  explainer: { title: "Match explainer", phase: 8 },
  cases: { title: "Case board", phase: 8 },
  swarm: { title: "Swarm view", phase: 9 },
  evidence: { title: "Evidence", phase: 8 },
  delta: { title: "Shift delta", phase: 8 },
  eval: { title: "Eval", phase: 8 },
};

export function matchRoute(path: string): Route {
  const p = path.replace(/\/+$/, "") || "/";
  if (p === "/") return { name: "home" };
  const live = /^\/live\/([A-Za-z0-9-]+)$/.exec(p);
  if (live?.[1]) return { name: "live", incidentId: live[1] };
  const page = p.slice(1);
  if (page in PLANNED) return { name: "planned", page: page as PlannedPage };
  return { name: "notfound", path: p };
}

const EVENT = "kd:navigate";

export function navigate(path: string, replace = false): void {
  if (replace) window.history.replaceState(null, "", path);
  else window.history.pushState(null, "", path);
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("popstate", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("popstate", cb);
    window.removeEventListener(EVENT, cb);
  };
}

export function usePath(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname);
}

export function useRoute(): Route {
  return matchRoute(usePath());
}
