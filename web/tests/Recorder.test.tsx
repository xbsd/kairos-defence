import { render, screen } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { Recorder } from "../src/panels/Recorder";
import { replayStore } from "../src/state/replayStore";
import { ingest } from "./fixtures";
import { flush, resetStores } from "./panelKit";

beforeEach(resetStores);

describe("Recorder", () => {
  it("waits for the first write", () => {
    render(<Recorder />);
    expect(screen.getByTestId("recorder-statement")).toHaveTextContent("No write yet");
    expect(screen.getByTestId("recorder-total")).toHaveTextContent("0");
  });

  it("shows the statement, totals and write time from real ingest messages", async () => {
    render(<Recorder />);
    act(() => {
      const s = replayStore.getState();
      s.apply(ingest(40, 40));
      s.apply(ingest(12, 12, "live_rf"));
      s.apply(ingest(3, 1043));
    });
    await flush();
    expect(screen.getByTestId("recorder-statement")).toHaveTextContent(
      "INSERT INTO live_points … 3 rows",
    );
    expect(screen.getByTestId("recorder-total")).toHaveTextContent("1,055");
    expect(screen.getByTestId("recorder-last-ms")).toHaveTextContent("0.42 ms");
    expect(screen.getByText("3 rows")).toBeInTheDocument();
    const points = screen
      .getAllByTestId("recorder-table")
      .find((r) => r.getAttribute("data-table") === "live_points");
    if (!points) throw new Error("no live_points row");
    expect(points).toHaveTextContent("1,043");
    expect(screen.getByRole("img", { name: /Last 3 write times/ })).toBeInTheDocument();
  });
});
