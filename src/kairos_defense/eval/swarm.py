"""Swarm evaluation (SPEC §19.1-§19.3, D-152).

Queries: the history swarm incidents of nights 2026-03-01 to 2026-08-31 (``QuerySets.
swarm_incidents``). Truth labels each incident with its team (``track_truth.actor_id``; read here
only, rule 2). A query with no earlier history swarm incident of the same team cannot be answered
(D-009): it is counted and left out. ``swarm_top1`` is the share of answerable queries whose
top-1 match is an incident of the same team, each query seen over its whole observed flight (the
Swarm view's encore). The same share at each T of the §19.2 grid is report only
(``swarm_top1_by_t``). The demo row runs the live ``DEMO-SWARM-ECHO-0614`` the same way and passes
when its top 1 is the ``scenario_demo.yaml`` expectation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.eval.metrics import percentiles
from kairos_defense.match.swarm import SwarmMatcher
from kairos_defense.ports import TrackStore

FULL = None  # the whole observed flight


@dataclass(frozen=True)
class SwarmCase:
    incident_id: str
    team: str
    start_ts: datetime
    n_earlier: int  # earlier history swarm incidents of the same team

    @property
    def answerable(self) -> bool:
        return self.n_earlier > 0


@dataclass(frozen=True)
class SwarmOutcome:
    incident_id: str
    team: str
    at_s: int | None  # None: the whole observed flight
    top1: str | None
    top1_team: str | None
    true_rank: int | None  # rank of the best same-team incident, 1-based
    candidates: int
    total_ms: float

    @property
    def correct(self) -> bool:
        return self.top1_team is not None and self.top1_team == self.team


def incident_teams(truth: pd.DataFrame) -> dict[str, str]:
    """Swarm incident -> team, from ``track_truth`` rows whose ``actor_type`` is ``swarm``."""
    sw = truth[truth.actor_type == "swarm"]
    return sw.groupby("incident_id")["actor_id"].first().to_dict()


def incident_starts(store: TrackStore) -> pd.DataFrame:
    """``incident_id, start_ts, status`` of every swarm incident (start = first radar point, the
    same time the matcher's no-look-ahead filter uses)."""
    return store.sql(
        "SELECT p.incident_id, min(p.ts) AS start_ts, any_value(i.status) AS status "
        "FROM track_points p JOIN incidents i USING (incident_id) WHERE i.is_swarm "
        "GROUP BY p.incident_id ORDER BY start_ts, p.incident_id"
    )


def swarm_cases(
    query_ids: list[str], starts: pd.DataFrame, teams: dict[str, str]
) -> list[SwarmCase]:
    """One case per query incident with its count of earlier history swarms of the same team."""
    hist = starts[starts.status == "history"]
    by_id = starts.set_index("incident_id")
    out = []
    for inc in query_ids:
        team = teams.get(inc)
        if team is None or inc not in by_id.index:
            continue
        start = pd.Timestamp(by_id.loc[inc, "start_ts"])
        earlier = hist[(hist.start_ts < start) & (hist.incident_id != inc)]
        n = int(sum(teams.get(i) == team for i in earlier.incident_id))
        out.append(SwarmCase(inc, team, start.to_pydatetime(), n))
    return out


def run_swarm_case(case: SwarmCase, at_s: int | None, matcher: SwarmMatcher,
                   teams: dict[str, str]) -> SwarmOutcome:  # fmt: skip
    t0 = time.perf_counter()
    res = matcher.match(case.incident_id, at_s=at_s)
    ms = (time.perf_counter() - t0) * 1000.0
    ranked = [m.incident_id for m in res.matches]
    true_rank = next((i for i, inc in enumerate(ranked, 1) if teams.get(inc) == case.team), None)
    top1 = ranked[0] if ranked else None
    return SwarmOutcome(case.incident_id, case.team, at_s, top1,
                        teams.get(top1) if top1 else None, true_rank, len(ranked), ms)  # fmt: skip


def swarm_outcomes(cases: list[SwarmCase], matcher: SwarmMatcher, teams: dict[str, str],
                   grid: tuple[int, ...]) -> list[SwarmOutcome]:  # fmt: skip
    """Every answerable case over its whole flight and at each T of ``grid``."""
    return [run_swarm_case(c, at, matcher, teams)
            for c in cases if c.answerable for at in (FULL, *grid)]  # fmt: skip


def top1_share(outcomes: list[SwarmOutcome], at_s: int | None) -> float | None:
    rows = [o for o in outcomes if o.at_s == at_s]
    return float(np.mean([o.correct for o in rows])) if rows else None


def swarm_metrics(cases: list[SwarmCase], outcomes: list[SwarmOutcome],
                  grid: tuple[int, ...]) -> dict:  # fmt: skip
    """``swarm_top1`` (whole flight), its value at each T (report only), counts and timings."""
    p50, p95 = percentiles([o.total_ms for o in outcomes if o.at_s is FULL])
    return {
        "swarm_top1": top1_share(outcomes, FULL),
        "swarm_top1_by_t": {str(t): top1_share(outcomes, t) for t in grid},
        "swarm_queries": len(cases),
        "swarm_unanswerable": sum(not c.answerable for c in cases),
        "latency_swarm_p50_ms": p50,
        "latency_swarm_p95_ms": p95,
    }


def swarm_demo(cfg: Config, matcher: SwarmMatcher):
    """The ``swarm_top1`` demo row: the live demo swarm over its whole observed flight."""
    from kairos_defense.eval.demo import DemoRow

    want = cfg.scenario.expectations.swarm_top1
    live = next((s.incident_id for s in cfg.scenario.swarm_events if s.status == "live"), None)
    expected = f"{want} ranked first for {live} (whole observed flight)"
    if live is None:
        return DemoRow("swarm_top1", expected, "no live swarm incident", "fail")
    try:
        res = matcher.match(live)
    except KeyError:  # a partial dataset (test nights) without the demo swarm's night
        return DemoRow("swarm_top1", expected, f"{live} is not in the data", "pending (no data)")
    if not res.matches:
        return DemoRow("swarm_top1", expected, "no earlier swarm matched", "fail")
    parts = [f"#{m.rank} {m.incident_id} ({m.similarity:.3f}, pace {m.warp_ratio:.2f})"
             for m in res.matches[:3]]  # fmt: skip
    ok = res.matches[0].incident_id == want
    return DemoRow("swarm_top1", expected, "; ".join(parts), "pass" if ok else "fail")
