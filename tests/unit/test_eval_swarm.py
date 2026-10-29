"""Swarm evaluation (SPEC §19.1-§19.3): team labels, answerability, the metric and the demo row."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from kairos_defense.eval.swarm import (
    SwarmCase,
    SwarmOutcome,
    incident_teams,
    swarm_cases,
    swarm_demo,
    swarm_metrics,
    top1_share,
)

TRUTH = pd.DataFrame({
    "track_id": ["A-T1", "A-T2", "B-T1", "C-T1", "D-T1", "P-T1"],
    "incident_id": ["A", "A", "B", "C", "D", "P"],
    "actor_id": ["S1", "S1", "S2", "S1", "S2", "P1"],
    "actor_type": ["swarm", "swarm", "swarm", "swarm", "swarm", "prober"],
})  # fmt: skip
STARTS = pd.DataFrame({
    "incident_id": ["A", "B", "C", "D", "L"],
    "start_ts": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
                                "2026-02-15"]),
    "status": ["history", "history", "history", "history", "live"],
})  # fmt: skip


def test_incident_teams_reads_swarm_rows_only() -> None:
    assert incident_teams(TRUTH) == {"A": "S1", "B": "S2", "C": "S1", "D": "S2"}


def test_first_event_of_a_team_is_unanswerable() -> None:
    cases = swarm_cases(["A", "B", "C", "D"], STARTS, incident_teams(TRUTH))
    by = {c.incident_id: c for c in cases}
    assert not by["A"].answerable and not by["B"].answerable  # first S1, first S2
    assert by["C"].n_earlier == 1 and by["D"].n_earlier == 1
    assert [c.incident_id for c in cases if c.answerable] == ["C", "D"]
    assert swarm_cases(["X"], STARTS, incident_teams(TRUTH)) == []  # no team label


def _o(inc: str, team: str, at, top_team: str | None) -> SwarmOutcome:
    return SwarmOutcome(inc, team, at, "Z" if top_team else None, top_team, 1, 3, 10.0)


def test_swarm_metrics_on_hand_made_outcomes() -> None:
    cases = [SwarmCase("A", "S1", pd.Timestamp("2026-01-01"), 0),
             SwarmCase("C", "S1", pd.Timestamp("2026-03-01"), 1),
             SwarmCase("D", "S2", pd.Timestamp("2026-04-01"), 1)]  # fmt: skip
    outs = [_o("C", "S1", None, "S1"), _o("D", "S2", None, "S1"),
            _o("C", "S1", 120, "S1"), _o("D", "S2", 120, "S2"),
            _o("C", "S1", 30, None), _o("D", "S2", 30, None)]  # fmt: skip
    m = swarm_metrics(cases, outs, (30, 120))
    assert m["swarm_top1"] == pytest.approx(0.5)
    assert m["swarm_top1_by_t"] == {"30": 0.0, "120": 1.0}
    assert m["swarm_queries"] == 3 and m["swarm_unanswerable"] == 1
    assert m["latency_swarm_p95_ms"] == pytest.approx(10.0)
    assert top1_share([], None) is None and not _o("C", "S1", None, None).correct


class _Matcher:
    def __init__(self, ranked: list[str] | None) -> None:
        self.ranked = ranked

    def match(self, incident_id: str, at_s=None, k: int = 5):
        if self.ranked is None:
            raise KeyError(incident_id)
        ms = [SimpleNamespace(rank=i, incident_id=inc, similarity=0.5, warp_ratio=1.0)
              for i, inc in enumerate(self.ranked, 1)]  # fmt: skip
        return SimpleNamespace(matches=ms)


def test_demo_row_pass_fail_and_pending(cfg) -> None:
    want = cfg.scenario.expectations.swarm_top1
    ok = swarm_demo(cfg, _Matcher([want, "JULIET-260511-0024"]))
    assert ok.key == "swarm_top1" and ok.status == "pass" and ok.observed.startswith(f"#1 {want}")
    bad = swarm_demo(cfg, _Matcher(["JULIET-260511-0024", want]))
    assert bad.status == "fail"
    assert swarm_demo(cfg, _Matcher([])).status == "fail"
    assert swarm_demo(cfg, _Matcher(None)).status.startswith("pending")
