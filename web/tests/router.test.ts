import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { matchRoute, navigate, routeTitle, useRoute } from "../src/app/routes";

describe("router", () => {
  it("matches paths", () => {
    expect(matchRoute("/")).toEqual({ name: "home" });
    expect(matchRoute("/live/DEMO-BRAVO-0828")).toEqual({
      name: "live",
      incidentId: "DEMO-BRAVO-0828",
    });
    expect(matchRoute("/cases/")).toEqual({ name: "cases" });
    expect(matchRoute("/eval")).toEqual({ name: "eval" });
    expect(matchRoute("/swarm")).toEqual({ name: "planned", page: "swarm" }); // phase 9
    expect(matchRoute("/nope")).toEqual({ name: "notfound", path: "/nope" });
    expect(matchRoute("/live/<script>")).toEqual({ name: "notfound", path: "/live/<script>" });
  });

  it("reads the phase 8 routes and their query parameters", () => {
    expect(matchRoute("/cases/CASE-P1-DELTA-260419", "?focus=P1-ALPHA-260303")).toEqual({
      name: "case",
      caseId: "CASE-P1-DELTA-260419",
      focus: "P1-ALPHA-260303",
    });
    expect(
      matchRoute("/explainer", "?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1"),
    ).toEqual({
      name: "explainer",
      incident: "DEMO-BRAVO-0828",
      at: 90,
      track: "P1-DELTA-260419-T1",
    });
    expect(matchRoute("/explainer", "?at=-3&incident=<x>")).toEqual({
      name: "explainer",
      incident: null,
      at: null,
      track: null,
    });
    expect(matchRoute("/evidence", "?case=CASE-P1-DELTA-260419")).toEqual({
      name: "evidence",
      caseId: "CASE-P1-DELTA-260419",
    });
    expect(matchRoute("/delta", "?since=2026-08-28T00:00:00Z")).toEqual({
      name: "delta",
      since: "2026-08-28T00:00:00Z",
    });
    expect(routeTitle(matchRoute("/cases/X"))).toBe("Case board");
    expect(routeTitle(matchRoute("/swarm"))).toBe("Swarm view");
  });

  it("navigates and follows popstate", () => {
    const { result } = renderHook(() => useRoute());
    act(() => navigate("/cases"));
    expect(result.current).toEqual({ name: "cases" });
    act(() => navigate("/evidence?case=CASE-1"));
    expect(result.current).toEqual({ name: "evidence", caseId: "CASE-1" });
    act(() => navigate("/live/DEMO-BRAVO-0828", true));
    expect(result.current.name).toBe("live");
    act(() => {
      window.history.pushState(null, "", "/eval");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current).toEqual({ name: "eval" });
  });
});
