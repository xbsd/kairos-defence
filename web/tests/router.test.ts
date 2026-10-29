import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { matchRoute, navigate, useRoute } from "../src/app/routes";

describe("router", () => {
  it("matches paths", () => {
    expect(matchRoute("/")).toEqual({ name: "home" });
    expect(matchRoute("/live/DEMO-BRAVO-0828")).toEqual({
      name: "live",
      incidentId: "DEMO-BRAVO-0828",
    });
    expect(matchRoute("/cases/")).toEqual({ name: "planned", page: "cases" });
    expect(matchRoute("/eval")).toEqual({ name: "planned", page: "eval" });
    expect(matchRoute("/nope")).toEqual({ name: "notfound", path: "/nope" });
    expect(matchRoute("/live/<script>")).toEqual({ name: "notfound", path: "/live/<script>" });
  });

  it("navigates and follows popstate", () => {
    const { result } = renderHook(() => useRoute());
    act(() => navigate("/cases"));
    expect(result.current).toEqual({ name: "planned", page: "cases" });
    act(() => navigate("/live/DEMO-BRAVO-0828", true));
    expect(result.current.name).toBe("live");
    act(() => {
      window.history.pushState(null, "", "/eval");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current).toEqual({ name: "planned", page: "eval" });
  });
});
