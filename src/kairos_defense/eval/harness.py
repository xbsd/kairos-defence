"""Evaluation harness (SPEC §19.1-§19.2).

Query sets: prober and copycat tracks of history incidents on nights 2026-03-01 to 2026-08-31
(local, months 13-18, D-055); the swarm incidents of the same nights are matched by
``eval.swarm`` (phase 9, §14). Each query
is run as if live at T in ``T_GRID`` seconds after its first radar point, against history that
started before it (the matcher's own no-look-ahead filter). T below ``live.min_track_s`` does not
run (a miss). A query with no earlier same-actor track cannot be answered: it is counted and left
out of the rank metrics (D-009). Truth is read here, and only here, to label the outcomes.

Methods (``METHODS``): ``euclidean`` is the §10.2 baseline; ``dtw`` is the phase 4 matcher (DTW +
fusion). Both return the fused ranking and the prefilter order of the same candidates, so the DTW
lift is measured on one run, one index and one query set (D-076).

After the ranker is timed, ``downstream.Downstream`` forecasts the recovery zone (T = 90 and
120 s) and, given a report index, recalls the reports of the top 3 matched incidents (T = 120 s);
truth labels the forecast error and the report linkage (phase 5, D-088).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from kairos_defense.config import Config
from kairos_defense.eval.downstream import Downstream
from kairos_defense.eval.metrics import Outcome
from kairos_defense.eval.swarm import incident_starts, incident_teams, swarm_cases, swarm_outcomes
from kairos_defense.match.baseline import MODEL_VERSION as EUCLIDEAN_VERSION
from kairos_defense.match.baseline import rank_candidates
from kairos_defense.match.matcher import DtwMatcher, MatchResult
from kairos_defense.match.prefilter import prefilter
from kairos_defense.match.query import Query, load_query
from kairos_defense.match.swarm import SwarmMatcher
from kairos_defense.ports import ReportIndex, TrackStore, VectorStore

T_GRID = (30, 45, 60, 90, 120, 180)
FIRST_NIGHT, LAST_NIGHT = date(2026, 3, 1), date(2026, 8, 31)  # months 13-18 (§19.1)
NIGHT_SHIFT_H = 12  # a local time before noon belongs to the previous night

Ranker = Callable[[Query], MatchResult]


def euclidean(
    cfg: Config, store: TrackStore, vstore: VectorStore, models_dir=None
) -> tuple[Ranker, str]:
    """The §10.2 baseline, timing the prefilter (LanceDB search + grouping) on its own."""

    def rank(q: Query) -> MatchResult:
        t0 = time.perf_counter()
        cands = prefilter(q, vstore, cfg.scoring)
        ms = (time.perf_counter() - t0) * 1000.0
        matches = rank_candidates(q, cands)
        return MatchResult(matches, matches, {"prefilter_ms": ms, "total_ms": ms})

    return rank, EUCLIDEAN_VERSION


def dtw(cfg: Config, store: TrackStore, vstore: VectorStore, models_dir=None) -> tuple[Ranker, str]:
    """The phase 4 matcher with the models in ``models_dir`` (default ``paths.models``)."""
    m = DtwMatcher(store, vstore, cfg.scoring, models_dir or cfg.app.paths.models)
    return m.match, m.model_version


# method -> factory returning (ranker, model version)
METHODS: dict[str, Callable[..., tuple[Ranker, str]]] = {"euclidean": euclidean, "dtw": dtw}


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


def track_list(store: TrackStore) -> pd.DataFrame:
    """Every track: ids, first radar point (``start_ts``), incident ``status`` and ``is_swarm``,
    and the region's ``utc_offset_hours``."""
    return store.sql(
        """SELECT p.track_id, p.incident_id, p.installation_id, p.region_id,
                  min(p.ts) AS start_ts, any_value(i.status) AS status,
                  any_value(i.is_swarm) AS is_swarm,
                  any_value(r.utc_offset_hours) AS utc_offset_hours
           FROM track_points p JOIN incidents i USING (incident_id)
           JOIN regions r ON r.region_id = p.region_id
           GROUP BY p.track_id, p.incident_id, p.installation_id, p.region_id"""
    )


def labelled_tracks(tracks: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """``tracks`` with truth's ``actor_id`` and ``actor_type`` and the local ``night``."""
    t = tracks.merge(truth[["track_id", "actor_id", "actor_type"]], on="track_id", validate="1:1")
    t["night"] = [night_of(ts, off) for ts, off in zip(t.start_ts, t.utc_offset_hours, strict=True)]
    return t


def query_cases(
    t: pd.DataFrame, kinds: tuple[str, ...], first: date, last: date
) -> list[QueryCase]:
    """History tracks of ``kinds`` actors on nights ``first``..``last`` from ``labelled_tracks``,
    oldest first, each with its count of earlier same-actor tracks in other incidents."""
    hist = t[t.status == "history"]
    window = hist[(hist.night >= first) & (hist.night <= last) & hist.actor_type.isin(kinds)]
    out = []
    for r in window.sort_values(["start_ts", "track_id"]).itertuples(index=False):
        same = hist[(hist.actor_id == r.actor_id) & (hist.incident_id != r.incident_id)]
        out.append(QueryCase(r.track_id, r.incident_id, r.installation_id, r.actor_id,
                             r.actor_type, pd.Timestamp(r.start_ts).to_pydatetime(), r.night,
                             int((same.start_ts < r.start_ts).sum())))  # fmt: skip
    return out


def query_sets(tracks: pd.DataFrame, truth: pd.DataFrame) -> QuerySets:
    """§19.1 from ``tracks`` (``track_list``) and ``truth`` (``track_id, actor_id, actor_type``)."""
    t = labelled_tracks(tracks, truth)
    cases = query_cases(t, ("prober", "copycat"), FIRST_NIGHT, LAST_NIGHT)
    out = QuerySets(
        probers=[c for c in cases if c.actor_type == "prober"],
        copycats=[c for c in cases if c.actor_type == "copycat"],
    )
    hist = t[(t.status == "history") & (t.night >= FIRST_NIGHT) & (t.night <= LAST_NIGHT)]
    out.swarm_incidents = sorted(hist[hist.is_swarm].incident_id.unique())
    return out


def _ranks(case: QueryCase, matches, truth_by_track: pd.DataFrame) -> tuple[int | None, ...]:
    """1-based ranks of the best same-actor track and of the best copycat of another actor."""
    true_rank = copycat_rank = None
    for i, m in enumerate(matches, 1):
        actor, kind = truth_by_track.loc[m.track_id, ["actor_id", "actor_type"]]
        if true_rank is None and actor == case.actor_id:
            true_rank = i
        if copycat_rank is None and kind == "copycat" and actor != case.actor_id:
            copycat_rank = i
    return true_rank, copycat_rank


def run_case(
    case: QueryCase,
    at_s: int,
    store: TrackStore,
    cfg: Config,
    ranker: Ranker,
    truth_by_track: pd.DataFrame,
    downstream: Downstream | None = None,
) -> Outcome:
    """One query at one T: run the method, then label ranks with truth; with ``downstream``, also
    the forecast error and report linkage (outside the timed span)."""
    base = {"track_id": case.track_id, "actor_id": case.actor_id,
            "actor_type": case.actor_type, "at_s": at_s}  # fmt: skip
    if at_s < cfg.scoring.live.min_track_s:
        return Outcome(**base, ran=False)
    t0 = time.perf_counter()
    q = load_query(store, case.track_id, at_s, cfg.scoring)
    t1 = time.perf_counter()
    res = ranker(q)
    t2 = time.perf_counter()
    true_rank, copycat_rank = _ranks(case, res.matches, truth_by_track)
    b_true, b_copy = _ranks(case, res.baseline, truth_by_track)
    tm = res.timings
    extra = downstream.outcome_fields(q, res) if downstream is not None else {}
    return Outcome(**base, ran=True, true_rank=true_rank, copycat_rank=copycat_rank,
                   window_s=q.window_s, query_ms=(t1 - t0) * 1000.0,
                   prefilter_ms=tm.get("prefilter_ms"), total_ms=(t2 - t0) * 1000.0,
                   top=tuple(m.track_id for m in res.matches[:5]), baseline_rank=b_true,
                   baseline_copycat_rank=b_copy, dtw_ms=tm.get("dtw_ms"),
                   candidates=len(res.matches), **extra)  # fmt: skip


@dataclass
class EvalRun:
    method: str
    created_at: datetime
    sets: QuerySets
    outcomes: dict[str, list[Outcome]]  # "probers" / "copycats" -> answerable outcomes
    demo: list = field(default_factory=list)  # DemoRow
    elapsed_s: float = 0.0
    model_version: str = ""
    candidate_tracks: int = 0
    reports_indexed: bool = False  # report linkage was measured (a report index was given)
    swarm_cases: list = field(default_factory=list)  # eval.swarm.SwarmCase (phase 9)
    swarm_outcomes: list = field(default_factory=list)  # eval.swarm.SwarmOutcome


def evaluate(
    cfg: Config,
    store: TrackStore,
    vstore: VectorStore,
    truth: pd.DataFrame,
    method: str,
    models_dir: Path | str | None = None,
    reports: ReportIndex | None = None,
) -> EvalRun:
    """Run the protocol for ``method`` over the prober and copycat query sets. ``truth`` is
    ``eval.truth.track_truth``; ``reports`` (the report index) enables report linkage."""
    from kairos_defense.eval.demo import demo_rows

    t0 = time.perf_counter()
    ranker, version = METHODS[method](cfg, store, vstore, models_dir)
    down = Downstream(cfg, store, vstore, truth, reports)
    sets = query_sets(track_list(store), truth)
    by_track = truth.set_index("track_id")
    outcomes: dict[str, list[Outcome]] = {}
    for name, cases in (("probers", sets.probers), ("copycats", sets.copycats)):
        outcomes[name] = [
            run_case(c, at, store, cfg, ranker, by_track, down if name == "probers" else None)
            for c in cases
            if c.answerable
            for at in T_GRID
        ]
    run = EvalRun(method, datetime.now(UTC).replace(tzinfo=None), sets, outcomes)
    run.model_version = version
    run.candidate_tracks = cfg.scoring.prefilter.candidate_tracks
    run.reports_indexed = reports is not None
    swarm = SwarmMatcher(store, vstore, cfg.scoring)
    teams = incident_teams(truth)
    run.swarm_cases = swarm_cases(sets.swarm_incidents, incident_starts(store), teams)
    run.swarm_outcomes = swarm_outcomes(run.swarm_cases, swarm, teams, T_GRID)
    run.demo = demo_rows(cfg, store, truth, ranker, assert_top3=method != "euclidean",
                         downstream=down, swarm=swarm)  # fmt: skip
    run.elapsed_s = time.perf_counter() - t0
    return run
