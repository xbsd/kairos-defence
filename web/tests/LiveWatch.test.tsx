import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../src/three/Theater", () => ({
  Theater: () => <div data-testid="theater" data-perf="full" />,
}));
vi.mock("../src/state/useReplay", () => ({
  useReplay: () => ({ scene: null, sceneError: null }),
}));

const { LiveWatch } = await import("../src/pages/LiveWatch");

describe("LiveWatch", () => {
  it("lays out the theater, the memory rail and the instrument rail", () => {
    render(<LiveWatch incidentId="DEMO-BRAVO-0828" />);
    expect(screen.getByRole("main", { name: "Live theater" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Memory rail" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Instrument rail" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Live watch/DEMO-BRAVO-0828",
    );
    for (const id of ["stream", "signals", "recorder", "ledgerchain", "matchlist"]) {
      expect(screen.getByTestId(`panel-${id}`)).toBeInTheDocument();
    }
  });
});
