// A small history-API router (D-112, D-141, D-160): no dependency, a few routes with query
// parameters.
import { useSyncExternalStore } from "react";

export type Route =
  | { name: "home" }
  | { name: "live"; incidentId: string }
  | { name: "livemode" }
  | { name: "explainer"; incident: string | null; at: number | null; track: string | null }
  | { name: "cases" }
  | { name: "case"; caseId: string; focus: string | null }
  | { name: "evidence"; caseId: string | null }
  | { name: "delta"; since: string | null }
  | { name: "eval" }
  | { name: "swarm"; incident: string | null; match: string | null }
  | { name: "notfound"; path: string };

/** The Pages menu, in §17.2 order. */
export const PAGES: { path: string; title: string }[] = [
  { path: "/live", title: "Live" },
  { path: "/explainer", title: "Match explainer" },
  { path: "/cases", title: "Case board" },
  { path: "/swarm", title: "Swarm view" },
  { path: "/evidence", title: "Evidence" },
  { path: "/delta", title: "Shift delta" },
  { path: "/eval", title: "Eval" },
];

const ID = /^[A-Za-z0-9._-]+$/;

function param(q: URLSearchParams, key: string): string | null {
  const v = q.get(key);
  return v && v.length <= 200 ? v : null;
}

export function matchRoute(path: string, search = ""): Route {
  const p = path.replace(/\/+$/, "") || "/";
  const q = new URLSearchParams(search);
  if (p === "/") return { name: "home" };
  const live = /^\/live\/([A-Za-z0-9-]+)$/.exec(p);
  if (live?.[1]) return { name: "live", incidentId: live[1] };
  const kase = /^\/cases\/([A-Za-z0-9._-]+)$/.exec(p);
  if (kase?.[1]) return { name: "case", caseId: kase[1], focus: param(q, "focus") };
  switch (p) {
    case "/live":
      return { name: "livemode" };
    case "/explainer": {
      const at = Number(q.get("at"));
      const incident = param(q, "incident");
      const track = param(q, "track");
      return {
        name: "explainer",
        incident: incident && ID.test(incident) ? incident : null,
        at: q.get("at") !== null && Number.isFinite(at) && at >= 0 ? at : null,
        track: track && ID.test(track) ? track : null,
      };
    }
    case "/cases":
      return { name: "cases" };
    case "/evidence": {
      const c = param(q, "case");
      return { name: "evidence", caseId: c && ID.test(c) ? c : null };
    }
    case "/delta":
      return { name: "delta", since: param(q, "since") };
    case "/eval":
      return { name: "eval" };
    case "/swarm": {
      const incident = param(q, "incident");
      const match = param(q, "match");
      return {
        name: "swarm",
        incident: incident && ID.test(incident) ? incident : null,
        match: match && ID.test(match) ? match : null,
      };
    }
  }
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

/** Path and query string (one string, so the snapshot is stable between changes). */
export function useLocation(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname + window.location.search);
}

export function useRoute(): Route {
  const loc = useLocation();
  const i = loc.indexOf("?");
  return i < 0 ? matchRoute(loc) : matchRoute(loc.slice(0, i), loc.slice(i));
}

/** The breadcrumb title of a route. */
export function routeTitle(r: Route): string {
  switch (r.name) {
    case "home":
    case "live":
      return "Live watch";
    case "livemode":
      return "Live";
    case "explainer":
      return "Match explainer";
    case "cases":
    case "case":
      return "Case board";
    case "evidence":
      return "Evidence";
    case "delta":
      return "Shift delta";
    case "eval":
      return "Eval";
    case "swarm":
      return "Swarm view";
    case "notfound":
      return "Not found";
  }
}
