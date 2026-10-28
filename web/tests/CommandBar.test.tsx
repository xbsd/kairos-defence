import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../src/app/App";
import { CommandBar } from "../src/app/CommandBar";

describe("CommandBar", () => {
  it("shows the product, the trail and an idle replay", () => {
    render(<CommandBar trail={["Live watch"]} replayClock={null} speed={1} live={false} />);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Kairos Defense/Live watch",
    );
    expect(screen.getByRole("status")).toHaveTextContent("No replay loaded");
    expect(screen.getByRole("timer", { name: "Replay time: none" })).toHaveTextContent("T+--:--");
    for (const name of ["Play", "Pause", "Restart", "Director"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });

  it("enables the controls and says Live only when a replay is live", () => {
    render(
      <CommandBar
        trail={["Live watch", "Installation Bravo"]}
        replayClock="T+01:02"
        speed={5}
        live={true}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Live");
    expect(screen.getByRole("timer", { name: "Replay time T+01:02" })).toHaveTextContent("T+01:02");
    expect(screen.getByLabelText("Speed 5 times")).toHaveTextContent("5×");
    expect(screen.getByRole("button", { name: "Play" })).toBeEnabled();
  });
});

describe("App", () => {
  it("renders the placeholder Live watch screen with no fake data", () => {
    render(<App />);
    expect(screen.getByRole("main", { name: "Live theater" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No replay loaded" })).toBeInTheDocument();
    expect(screen.queryByText(/\d+\.\d\d/)).toBeNull(); // no scores or telemetry yet
  });
});
