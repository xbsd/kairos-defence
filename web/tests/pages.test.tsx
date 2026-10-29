import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { setFetch } from "../src/api/client";
import { CaseBoard } from "../src/pages/CaseBoard";
import { Eval } from "../src/pages/Eval";
import { Evidence } from "../src/pages/Evidence";
import { MatchExplainer } from "../src/pages/MatchExplainer";
import { ShiftDelta } from "../src/pages/ShiftDelta";
import { directorStore } from "../src/state/directorStore";
import { sceneStore } from "../src/state/sceneStore";
import { flush, resetStores, stubCanvas, stubDialog } from "./panelKit";
import {
  CASES,
  DELTA,
  DIFF,
  EVAL,
  EXPLAIN,
  GRAPH_NOW,
  GRAPH_THEN,
  INSTALLATIONS,
  T090,
} from "./real";
import { calls, routeFetch } from "./route";

const CASE = "CASE-P1-DELTA-260419";

beforeEach(() => {
  resetStores();
  stubCanvas();
  stubDialog();
  sceneStore.getState().setInstallations(INSTALLATIONS);
  directorStore.setState({ facts: {} });
});
afterEach(() => setFetch((...a) => fetch(...a)));

const SNAP_NOW = {
  case_id: CASE,
  as_of: GRAPH_NOW.as_of,
  exists: true,
  status: "closed",
  founder: "P1-DELTA-260419",
  members: ["P1-DELTA-260419"],
  pending: [
    {
      seq: 4683,
      incident_id: "P1-ALPHA-260303",
      query_incident: "DEMO-BRAVO-0828",
      rank: 2,
      score: 0.99,
      reasons: [],
      recorded_at: GRAPH_NOW.as_of,
    },
  ],
  claims: [],
  decisions: [],
  contradictions: [],
  head_seq: 4690,
};
const SNAP_THEN = {
  ...SNAP_NOW,
  as_of: GRAPH_THEN.as_of,
  pending: [],
  claims: [
    {
      seq: 3569,
      subject_id: "P1-DELTA-260419",
      value: "hobbyist",
      recorded_at: "2026-04-20T14:10:00.000000Z",
    },
  ],
  decisions: [
    {
      seq: 3570,
      decision: "close",
      recorded_at: "2026-04-20T14:10:00.000000Z",
      actor: "generator",
    },
  ],
};

describe("Match explainer", () => {
  it("draws the bars by |contribution|, the logit sum and both flights", async () => {
    routeFetch([
      [
        /\/api\/match\//,
        () => ({
          incident_id: "DEMO-BRAVO-0828",
          at: 90,
          t_s: 90,
          waiting_for_s: 0,
          model_version: "fusion-v1",
          elapsed_ms: 1,
          cached: true,
          case_id: CASE,
          matches: T090.match.matches,
        }),
      ],
      [/\/api\/explain\//, () => EXPLAIN],
      [/\/api\/dtw\//, () => T090.dtw],
    ]);
    render(<MatchExplainer incident="DEMO-BRAVO-0828" at={90} track={EXPLAIN.match.track_id} />);
    await flush(200);
    const bars = screen.getAllByTestId("contribution-bar");
    expect(bars).toHaveLength(7);
    const mags = bars.map((b) => Math.abs(Number(b.dataset.value)));
    expect(mags).toEqual([...mags].sort((a, b) => b - a));
    const sum = EXPLAIN.intercept + EXPLAIN.contributions.reduce((a, r) => a + r.contribution, 0);
    expect(sum).toBeCloseTo(EXPLAIN.logit, 9);
    expect(screen.getByTestId("logit-line")).toHaveTextContent(EXPLAIN.score.toFixed(3));
    expect(screen.getByTestId("flight-tonight")).toBeInTheDocument();
    expect(screen.getByTestId("flight-past-segment")).toBeInTheDocument();
    expect(screen.getAllByTestId("lens-connector").length).toBeGreaterThan(10);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Why Delta, Apr 19 matches tonight",
    );
  });
});

describe("Case board", () => {
  function server() {
    return routeFetch([
      [/\/api\/cases\/[^/]+\/graph\?as_of=2026-04-20/, () => GRAPH_THEN],
      [/\/api\/cases\/[^/]+\/graph/, () => GRAPH_NOW],
      [/\/api\/cases\/[^/]+\/diff/, () => DIFF],
      [
        /\/api\/cases\/[^/]+\/links/,
        () => ({ case_id: CASE, proposal_seq: 4683, decision: "approve", block: { seq: 4691 } }),
      ],
      [
        /\/api\/cases\/[^/]+\/decisions/,
        () => ({ case_id: CASE, decision: "close", block: { seq: 4692 } }),
      ],
      [/\/api\/cases\/[^/?]+\?as_of=2026-04-20/, () => SNAP_THEN],
      [/\/api\/cases\/[^/?]+/, () => SNAP_NOW],
    ]);
  }

  it("Known then shows the hobbyist assessment and no links; Known now the diff and proposals", async () => {
    server();
    render(<CaseBoard caseId={CASE} focus={null} />);
    await flush(400);
    fireEvent.click(screen.getByRole("button", { name: "Known then" }));
    await flush(400);
    const g = screen.getByTestId("case-graph");
    expect(
      within(g)
        .getAllByTestId("graph-node")
        .filter((n) => n.dataset.kind === "assessment")
        .map((n) => n.dataset.label),
    ).toEqual(["hobbyist"]);
    expect(
      within(g)
        .queryAllByTestId("graph-edge")
        .filter((e) => e.dataset.kind === "proposed"),
    ).toHaveLength(0);
    expect(screen.getByTestId("diff-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Known now" }));
    await flush(400);
    expect(screen.getAllByTestId("diff-group").map((e) => e.dataset.group)).toContain("proposals");
    expect(
      within(screen.getByTestId("case-graph"))
        .getAllByTestId("graph-edge")
        .some((e) => e.dataset.kind === "proposed"),
    ).toBe(true);
    // the Director's known-then caption facts
    expect(directorStore.getState().facts).toMatchObject({
      caseBase: "Delta",
      caseLabel: "hobbyist",
      caseClosedOn: "Apr 20",
    });
  });

  it("Approve calls the links route; Close only after the confirm", async () => {
    const f = server();
    render(<CaseBoard caseId={CASE} focus={null} />);
    await flush(400);
    fireEvent.click(screen.getByRole("button", { name: "Approve link: P1-ALPHA-260303" }));
    await flush(100);
    const posted = calls(f).filter(([, i]) => i?.method === "POST");
    expect(posted.map(([u]) => u)).toEqual([`/api/cases/${CASE}/links`]);
    expect(JSON.parse(String(posted[0]?.[1]?.body))).toMatchObject({
      proposal_seq: 4683,
      decision: "approve",
    });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(calls(f).filter(([u]) => u.endsWith("/decisions"))).toHaveLength(0);
    const dialog = screen.getByRole("dialog", { hidden: true });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel", hidden: true }));
    expect(calls(f).filter(([u]) => u.endsWith("/decisions"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm: Close", hidden: true }));
    await flush(100);
    const d = calls(f).filter(([u]) => u.endsWith("/decisions"));
    expect(d).toHaveLength(1);
    expect(JSON.parse(String(d[0]?.[1]?.body))).toMatchObject({
      decision: "close",
      analyst: "demo",
    });
  });
});

describe("Evidence", () => {
  it("exports only after the confirm, then shows five files and the checks; Verify calls the route", async () => {
    const ndjson = [
      ...["case.json", "case.html", "pubkey.pem", "manifest.json", "manifest.sig"].map((name, i) =>
        JSON.stringify({
          type: "file",
          name,
          bytes: 100 + i,
          sha256: "ab".repeat(32),
          i: i + 1,
          n: 5,
        }),
      ),
      JSON.stringify({
        type: "done",
        dir: "exports/CASE_1",
        manifest_sha256: "cd".repeat(32),
        seq: 9,
        head_seq: 8,
        signed: true,
        passed: true,
        checks: [
          { name: "files", status: "PASS", detail: "5 files" },
          { name: "signature", status: "PASS", detail: "ok" },
        ],
      }),
    ].join("\n");
    const f = routeFetch([
      [/\/api\/cases\?|\/api\/cases$/, () => CASES],
      [
        /\/api\/evidence\/verify/,
        () => ({
          dir: "CASE_1",
          passed: true,
          checks: [{ name: "files", status: "PASS", detail: "5 files" }],
        }),
      ],
      [
        /\/api\/evidence/,
        () => [
          {
            dir: "CASE_1",
            case_id: CASE,
            created_at: "2026-08-29T02:42:00Z",
            manifest_sha256: "cd".repeat(32),
            signed: true,
            files: [],
          },
        ],
      ],
      [/\/api\/cases\/[^/]+\/evidence/, () => new Response(ndjson, { status: 200 })],
    ]);
    render(<Evidence caseId={CASE} />);
    await flush(150);
    expect(directorStore.getState().facts.pending).toBe(CASES[0]?.pending);
    fireEvent.click(screen.getByTestId("evidence-export"));
    expect(calls(f).some(([u]) => u.endsWith("/evidence") && u.includes("/cases/"))).toBe(false);
    const dialog = screen.getByRole("dialog", { hidden: true });
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole("button", { name: "Approve and export", hidden: true }),
      );
    });
    await flush(150);
    expect(screen.getAllByTestId("evidence-file")).toHaveLength(5);
    expect(screen.getByTestId("evidence-done")).toHaveAttribute("data-passed", "true");
    expect(screen.getAllByTestId("evidence-check").every((c) => c.dataset.status === "PASS")).toBe(
      true,
    );
    fireEvent.click(screen.getByRole("button", { name: "Verify package" }));
    await flush(100);
    expect(screen.getByTestId("verify-result")).toHaveAttribute("data-passed", "true");
    expect(calls(f).filter(([u]) => u.endsWith("/api/evidence/verify"))).toHaveLength(1);
  });
});

describe("Shift delta", () => {
  it("groups the changes and links case items to the Case board", async () => {
    routeFetch([
      [
        /\/api\/incidents/,
        () => [{ incident_id: "DEMO-BRAVO-0828", installation_id: "BRAVO", is_swarm: false }],
      ],
      [/\/api\/delta/, () => DELTA],
    ]);
    render(<ShiftDelta since="2026-08-27T00:00:00Z" />);
    await flush(150);
    const groups = screen.getAllByTestId("delta-group").map((g) => g.dataset.group);
    expect(groups).toContain("proposals");
    expect(groups).toContain("incidents");
    const links = screen.getAllByRole("link").map((a) => a.getAttribute("href") ?? "");
    expect(links.some((h) => h.startsWith(`/cases/${CASE}?focus=`))).toBe(true);
  });
});

describe("Eval page", () => {
  it("shows tiles from the targets, three charts and six demo rows", async () => {
    routeFetch([[/\/api\/eval\/latest/, () => EVAL]]);
    render(<Eval />);
    await flush(100);
    expect(screen.getAllByTestId("eval-tile")).toHaveLength(EVAL.targets?.length ?? -1);
    for (const id of ["chart-recall", "chart-lift", "chart-forecast"])
      expect(screen.getByTestId(id)).toBeInTheDocument();
    expect(screen.getAllByTestId("demo-row")).toHaveLength(6);
  });

  it("asks for a rerun when the report has no targets", async () => {
    routeFetch([[/\/api\/eval\/latest/, () => ({ ...EVAL, targets: undefined })]]);
    render(<Eval />);
    await flush(100);
    expect(screen.getByTestId("eval-stale")).toHaveTextContent("rerun make eval");
  });
});
