"""Agent tools (SPEC §18.1, §20 phase 9 tests): JSON in and out, no look-ahead, and only the
proposal tools append, and only ``match_proposed`` events. On the P1 nights with the hand-set
models and a writable copy of the seeded ledger."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import pytest

from kairos_defense.agent.context import LedgerBusy, ToolContext
from kairos_defense.agent.tools import PROPOSALS, READ_ONLY, TOOL_SPECS, TOOLS, call_tool

LIVE = "DEMO-BRAVO-0828"
CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"


@pytest.fixture
def ctx(live_kit, ledger_copy):
    return ToolContext(live_kit.cfg, store=live_kit.store, vstore=live_kit.lance,
                       matcher=live_kit.matcher, recall=live_kit.recall, memory=ledger_copy,
                       lock=live_kit.lock, agent="test",
                       clock=lambda: datetime(2026, 8, 29, 2, 0))  # fmt: skip


def calls(ctx) -> dict[str, dict]:
    """Valid arguments for every tool (read-only first, proposals last)."""
    top = call_tool(ctx, "find_similar_flights", {"incident_id": LIVE, "window_s": 120})
    return {
        "find_similar_flights": {"incident_id": LIVE, "window_s": 90, "k": 5},
        "recall_reports": {"incident_id": LIVE, "match_incident_id":
                           top["matches"][0]["incident_id"], "k": 5},
        "forecast_recovery": {"incident_id": LIVE, "at_s": 105},
        "as_of_view": {"case_id": CASE, "as_of_ts": "2026-04-20T23:00Z"},
        "diff_case": {"case_id": CASE, "t1": "2026-04-19T00:00Z"},
        "shift_delta": {"since_ts": "2026-04-19T00:00Z", "installation_id": "DELTA"},
        "propose_link": {"case_id": CASE, "incident_id": LIVE,
                         "rationale": "same orbit shape and approach as the DELTA flight"},
        "propose_evidence_export": {"case_id": CASE},
    }  # fmt: skip


def test_every_tool_has_a_spec_and_the_sets_partition() -> None:
    assert set(TOOLS) == set(READ_ONLY) | set(PROPOSALS) == set(TOOL_SPECS)
    assert not set(READ_ONLY) & set(PROPOSALS) and len(READ_ONLY) == 6
    for spec in TOOL_SPECS.values():
        assert spec["parameters"]["type"] == "object" and spec["description"]


def test_tool_outputs_are_json_serializable(ctx) -> None:
    for name, args in calls(ctx).items():
        out = call_tool(ctx, name, args)
        assert "error" not in out, (name, out)
        text = json.dumps(out, allow_nan=False)  # strict JSON: no NaN, no numpy, no datetimes
        assert json.loads(text) == out, name


def test_find_similar_flights_searches_only_earlier_flights(ctx) -> None:
    out = call_tool(ctx, "find_similar_flights", {"incident_id": LIVE, "window_s": 90})
    start = pd.Timestamp(out["query_start"])
    assert out["window_s"] == 90 and out["matches"]
    assert all(pd.Timestamp(m["start_ts"]) < start for m in out["matches"])
    assert [m["rank"] for m in out["matches"]] == list(range(1, len(out["matches"]) + 1))
    assert LIVE not in {m["incident_id"] for m in out["matches"]}


def test_recall_reports_has_no_look_ahead(ctx) -> None:
    """Rule 3 at tool level: every report's event is before the query's start and it was filed
    by the replay time (start + at_s)."""
    args = calls(ctx)["recall_reports"]
    out = call_tool(ctx, "recall_reports", {**args, "at_s": 120})
    assert "error" not in out, out
    start_ms = pd.Timestamp(out["query_start"]).value // 1_000_000
    until_ms = start_ms + 1000 * out["at_s"]
    assert out["reports"], "the top match has reports on the P1 nights"
    for r in out["reports"]:
        assert r["event_ts_ms"] < start_ms and r["report_ts_ms"] <= until_ms
    assert f"event_ts_ms < {start_ms}" in out["where"]


def test_read_only_tools_do_not_write(ctx, ledger_copy) -> None:
    before = (ledger_copy.count(), ledger_copy.head())
    for name, args in calls(ctx).items():
        if name in READ_ONLY:
            assert "error" not in call_tool(ctx, name, args), name
    assert (ledger_copy.count(), ledger_copy.head()) == before


def test_propose_link_appends_one_match_proposed(ctx, ledger_copy) -> None:
    n = ledger_copy.count()
    out = call_tool(ctx, "propose_link", calls(ctx)["propose_link"])
    assert out["appended"] == 1 and out["event_type"] == "match_proposed"
    assert ledger_copy.count() == n + 1
    row = ledger_copy.events()[-1]
    assert row["seq"] == out["proposal_seq"] and row["event_type"] == "match_proposed"
    assert row["actor"] == "agent:test" and row["case_id"] == CASE and row["subject_id"] == LIVE
    o = row["object_json"]
    assert o["rationale"].startswith("same orbit") and o["proposed_by"] == "agent:test"
    # the live flight ranks the DELTA founder among its earlier matches: that is the evidence
    assert out["evidence"]["matched_incident"] == DELTA and o["query_incident"] == DELTA
    assert o["score"] is not None and o["reasons"]
    assert ledger_copy.verify_chain() is None
    snap = call_tool(ctx, "as_of_view", {"case_id": CASE, "as_of_ts": "2026-08-30T00:00Z"})
    assert LIVE in [p["incident_id"] for p in snap["pending"]] and LIVE not in snap["members"]


def test_propose_evidence_export_appends_nothing(ctx, ledger_copy) -> None:
    before = (ledger_copy.count(), ledger_copy.head())
    out = call_tool(ctx, "propose_evidence_export", {"case_id": CASE})
    assert (ledger_copy.count(), ledger_copy.head()) == before and out["appended"] == 0
    assert out["proposal_id"] == f"EXPORT-PROPOSAL-{CASE}-{before[1].seq}"
    assert any("--approve" in h for h in out["how"]) and out["members"] == [DELTA]


def test_only_proposal_tools_append_and_only_match_proposed(ctx, ledger_copy) -> None:
    """SPEC §20 phase 9: across every tool, the only appended events are match_proposed."""
    head = ledger_copy.head().seq
    for name, args in calls(ctx).items():
        n = ledger_copy.count()
        out = call_tool(ctx, name, args)
        assert "error" not in out, (name, out)
        grew = ledger_copy.count() - n
        assert grew == (1 if name == "propose_link" else 0), name
    new = [r for r in ledger_copy.events() if r["seq"] > head]
    assert [r["event_type"] for r in new] == ["match_proposed"]
    assert all(r["actor"].startswith("agent:") for r in new)


def test_bad_times_and_unknown_ids_return_errors(ctx) -> None:
    bad = [
        ("as_of_view", {"case_id": CASE, "as_of_ts": "2026-04-20T10:00"}, "bad time"),
        ("as_of_view", {"case_id": CASE, "as_of_ts": "yesterday"}, "bad time"),
        ("as_of_view", {"case_id": "CASE-NOPE", "as_of_ts": "2026-04-20T10:00Z"}, "no case"),
        ("diff_case", {"case_id": "not a case", "t1": "2026-04-20T10:00Z"}, "bad case_id"),
        ("find_similar_flights", {"incident_id": "NO-SUCH-1"}, "unknown incident"),
        ("find_similar_flights", {"incident_id": "lower-case"}, "bad incident_id"),
        ("find_similar_flights", {"incident_id": LIVE, "window_s": 10}, "from 45"),
        ("find_similar_flights", {"incident_id": LIVE, "k": 0}, "k must be"),
        ("recall_reports", {"incident_id": LIVE, "match_incident_id": LIVE}, "not among"),
        ("shift_delta", {"since_ts": "2026-04-19T00:00Z", "installation_id": "x;y"}, "bad"),
        ("propose_link", {"case_id": CASE, "incident_id": LIVE, "rationale": " "}, "rationale"),
        ("propose_link", {"case_id": CASE, "incident_id": DELTA, "rationale": "x"}, "already"),
        ("find_similar_flights", {"incident_id": LIVE, "colour": "red"}, "unknown"),
        ("as_of_view", {"case_id": CASE}, "missing"),
        ("drop_tables", {}, "not available"),
    ]
    for name, args, words in bad:
        out = call_tool(ctx, name, args)
        assert words in out.get("error", ""), (name, args, out)
    ro = call_tool(ctx, "propose_link", calls(ctx)["propose_link"], allowed=READ_ONLY)
    assert "not available" in ro["error"]


def test_ledger_busy_reads_through_the_api_and_refuses_proposals(ctx, monkeypatch) -> None:
    """While the API holds the ledger (D-010), the read tools ask its REST routes; a proposal is
    refused with the cause."""
    from contextlib import contextmanager

    @contextmanager
    def busy(write: bool = False):
        raise LedgerBusy("the ledger is held by another process")
        yield  # pragma: no cover

    asked = []
    monkeypatch.setattr(ctx, "ledger", busy)
    monkeypatch.setattr(ctx, "remote", lambda path, params=None: asked.append((path, params))
                        or {"case_id": CASE, "head_seq": 7, "members": [DELTA]})  # fmt: skip
    out = call_tool(ctx, "as_of_view", {"case_id": CASE, "as_of_ts": "2026-04-20T23:00Z"})
    assert out["head_seq"] == 7 and asked[-1] == (f"/api/cases/{CASE}",
                                                  {"as_of": "2026-04-20T23:00Z"})  # fmt: skip
    call_tool(ctx, "diff_case", {"case_id": CASE, "t1": "2026-04-19T00:00Z"})
    assert asked[-1][0] == f"/api/cases/{CASE}/diff"
    call_tool(ctx, "shift_delta", {"since_ts": "2026-04-19T00:00Z"})
    assert asked[-1][0] == "/api/delta"
    exp = call_tool(ctx, "propose_evidence_export", {"case_id": CASE})
    assert exp["proposal_id"] == f"EXPORT-PROPOSAL-{CASE}-7"
    out = call_tool(ctx, "propose_link", calls(ctx)["propose_link"])
    assert "held by another process" in out["error"]


def test_context_opens_the_ledger_per_call(live_kit, seeded_p1, tmp_path) -> None:
    """Without an injected memory the ledger file is opened for each call and closed after, so
    the MCP server never holds it between calls."""
    import shutil

    from kairos_defense.store.ledger_duck import DuckCaseMemory

    path = tmp_path / "mem.duckdb"
    shutil.copyfile(seeded_p1.path, path)
    c = ToolContext(live_kit.cfg, store=live_kit.store, vstore=live_kit.lance,
                    matcher=live_kit.matcher, memory_path=path, lock=live_kit.lock)  # fmt: skip
    out = call_tool(c, "as_of_view", {"case_id": CASE, "as_of_ts": "2026-04-20T23:00Z"})
    assert out["status"] == "closed" and out["members"] == [DELTA]
    with DuckCaseMemory(path, live_kit.cfg.app) as mem:  # a writer can open it right after
        assert mem.count() > 0
    missing = ToolContext(live_kit.cfg, store=live_kit.store, memory_path=tmp_path / "none.db")
    assert "no ledger" in call_tool(missing, "shift_delta", {"since_ts": "2026-01-01T00:00Z"})[
        "error"]  # fmt: skip


def test_context_without_data_reports_what_to_run(cfg, tmp_path) -> None:
    from tests.conftest import tmp_config

    c = ToolContext(tmp_config(cfg, tmp_path))
    out = call_tool(c, "find_similar_flights", {"incident_id": LIVE})
    assert "make data index models" in out["error"]
