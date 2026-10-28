"""Evaluation harness (SPEC §19.1-§19.2).

Query sets: prober and copycat tracks of history incidents on nights 2026-03-01 to 2026-08-31
(local, months 13-18, D-055); swarm incidents of the same nights are listed for phase 9. Each query
is run as if live at T in ``T_GRID`` seconds after its first radar point, against history that
started before it (the matcher's own no-look-ahead filter). T below ``live.min_track_s`` does not
run (a miss). A query with no earlier same-actor track cannot be answered: it is counted and left
out of the rank metrics (D-009). Truth is read here, and only here, to label the outcomes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from kairos_defense.config import Config, ScoringConfig
from kairos_defense.eval.metrics import Outcome
from kairos_defense.match.baseline import rank_candidates
from kairos_defense.match.prefilter import prefilter
from kairos_defense.match.query import Query, load_query
from kairos_defense.match.types import Match
from kairos_defense.ports import TrackStore, VectorStore

T_GRID = (30, 45, 60, 90, 120, 180)
FIRST_NIGHT, LAST_NIGHT = date(2026, 3, 1), date(2026, 8, 31)  # months 13-18 (§19.1)
NIGHT_SHIFT_H = 12  # a local time before noon belongs to the previous night

Ranker = Callable[[Query, VectorStore, ScoringConfig], tuple[list[Match], dict[str, float]]]


def euclidean_ranker(
    q: Query, store: VectorStore, scoring: ScoringConfig
) -> tuple[list[Match], dict[str, float]]:
    """The §10.2 baseline, timing the prefilter (LanceDB search + grouping) on its own."""
    t0 = time.perf_counter()
    cands = prefilter(q, store, scoring)
    t1 = time.perf_counter()
    return rank_candidates(q, cands), {"prefilter_ms": (t1 - t0) * 1000.0}


METHODS: dict[str, Ranker] = {"euclidean": euclidean_ranker}


@dataclass(frozen=True)
class QueryCase:
    track_id: str
    incident_id: str
    installation_id: str
    actor_id: str
    actor_type: str
    start_ts: datetime
    night: date
    n_earlier: int  # earlier history tracks by the same actor (other incidents)

    @property
    def answerable(self) -> bool:
        return self.n_earlier > 0


@dataclass
class QuerySets:
    probers: list[QueryCase] = field(default_factory=list)
    copycats: list[QueryCase] = field(default_factory=list)
    swarm_incidents: list[str] = field(default_factory=list)


def night_of(ts_utc: datetime, utc_offset_hours: int) -> date:
    """The local night a UTC time belongs to (times before noon go to the previous night)."""
    return (pd.Timestamp(ts_utc) + timedelta(hours=utc_offset_hours - NIGHT_SHIFT_H)).date()


def query_sets(tracks: pd.DataFrame, truth: pd.DataFrame) -> QuerySets:
    """§19.1 from ``tracks`` (``TrackStore`` track list plus ``utc_offset_hours`` and ``is_swarm``)
    and ``truth`` (``track_id, actor_id, actor_type``)."""
    t = tracks.merge(truth[["track_id", "actor_id", "actor_type"]], on="track_id", validate="1:1")
    t["night"] = [night_of(ts, off) for ts, off in zip(t.start_ts, t.utc_offset_hours, strict=True)]
    hist = t[t.status == "history"]
    in_window = hist[(hist.night >= FIRST_NIGHT) & (hist.night <= LAST_NIGHT)]
    out = QuerySets()
    for r in in_window.sort_values(["start_ts", "track_id"]).itertuples(index=False):
        if r.actor_type not in ("prober", "copycat"):
            continue
        same = hist[(hist.actor_id == r.actor_id) & (hist.incident_id != r.incident_id)]
        case = QueryCase(r.track_id, r.incident_id, r.installation_id, r.actor_id, r.actor_type,
                         pd.Timestamp(r.start_ts).to_pydatetime(), r.night,
                         int((same.start_ts < r.start_ts).sum()))  # fmt: skip
        (out.probers if r.actor_type == "prober" else out.copycats).append(case)
    swarms = in_window[in_window.is_swarm]
    out.swarm_incidents = sorted(swarms.incident_id.unique())
    return out


def run_case(
    case: QueryCase,
    at_s: int,
    store: TrackStore,
    vstore: VectorStore,
    scoring: ScoringConfig,
    ranker: Ranker,
    truth_by_track: pd.DataFrame,
) -> Outcome:
    """One query at one T: run the method, then label ranks with truth."""
    base = {"track_id": case.track_id, "actor_id": case.actor_id,
            "actor_type": case.actor_type, "at_s": at_s}  # fmt: skip
    if at_s < scoring.live.min_track_s:
        return Outcome(**base, ran=False)
    t0 = time.perf_counter()
    q = load_query(store, case.track_id, at_s, scoring)
    t1 = time.perf_counter()
    matches, timing = ranker(q, vstore, scoring)
    t2 = time.perf_counter()
    true_rank = copycat_rank = None
    for i, m in enumerate(matches, 1):
        actor, kind = truth_by_track.loc[m.track_id, ["actor_id", "actor_type"]]
        if true_rank is None and actor == case.actor_id:
            true_rank = i
        if copycat_rank is None and kind == "copycat" and actor != case.actor_id:
            copycat_rank = i
    return Outcome(**base, ran=True, true_rank=true_rank, copycat_rank=copycat_rank,
                   window_s=q.window_s, query_ms=(t1 - t0) * 1000.0,
                   prefilter_ms=timing.get("prefilter_ms"), total_ms=(t2 - t0) * 1000.0,
                   top=tuple(m.track_id for m in matches[:5]))  # fmt: skip


@dataclass
class EvalRun:
    method: str
    created_at: datetime
    sets: QuerySets
    outcomes: dict[str, list[Outcome]]  # "probers" / "copycats" -> answerable outcomes
    demo: list = field(default_factory=list)  # DemoRow
    elapsed_s: float = 0.0


def evaluate(
    cfg: Config, store: TrackStore, vstore: VectorStore, truth: pd.DataFrame, method: str
) -> EvalRun:
    """Run the protocol for ``method`` over the prober and copycat query sets."""
    from kairos_defense.eval.demo import demo_rows

    t0 = time.perf_counter()
    ranker = METHODS[method]
    tracks = store.sql(
        """SELECT p.track_id, p.incident_id, p.installation_id, p.region_id,
                  min(p.ts) AS start_ts, any_value(i.status) AS status,
                  any_value(i.is_swarm) AS is_swarm,
                  any_value(r.utc_offset_hours) AS utc_offset_hours
           FROM track_points p JOIN incidents i USING (incident_id)
           JOIN regions r ON r.region_id = p.region_id
           GROUP BY p.track_id, p.incident_id, p.installation_id, p.region_id"""
    )
    sets = query_sets(tracks, truth)
    by_track = truth.set_index("track_id")
    outcomes: dict[str, list[Outcome]] = {}
    for name, cases in (("probers", sets.probers), ("copycats", sets.copycats)):
        outcomes[name] = [
            run_case(c, at, store, vstore, cfg.scoring, ranker, by_track)
            for c in cases
            if c.answerable
            for at in T_GRID
        ]
    run = EvalRun(method, datetime.now(UTC).replace(tzinfo=None), sets, outcomes)
    run.demo = demo_rows(cfg, store, vstore, truth, ranker)
    run.elapsed_s = time.perf_counter() - t0
    return run
