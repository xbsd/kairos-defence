"""Seed the ledger with 18 months of history as Kairos Defense would have learned it (SPEC §15.5,
D-096).

Transaction times come from the data, so the seed is deterministic:

- ``incident_recorded`` at incident end + 5 min, valid time [start, end];
- ``report_recorded`` at ``report_ts``, valid from the report's ``event_ts``;
- ``assessment_asserted`` at ``assessed_ts``, valid from the incident's start;
- for every planted P1 flight with an assessment in the scenario (DELTA): ``case_opened`` and a
  ``close`` decision at the generator's assessment time, ordered case, assessment, decision (D-011).

Everything is recorded strictly before the live incident's first contact: that is the memory when
tonight's drone appears, and anything later would be look-ahead at demo time. Live incidents are
not seeded, and history holds no cross-base links (§15.5). Reads go through ``TrackStore.sql``
only; truth is never opened.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from kairos_defense.config.scenario import ScenarioConfig
from kairos_defense.memory.canonical import utc_naive
from kairos_defense.ports import CaseMemory, TrackStore

log = logging.getLogger(__name__)

INCIDENT_LAG = timedelta(minutes=5)  # §15.5: an incident is recorded 5 min after it ends
_RANK = {"incident_recorded": 0, "report_recorded": 1, "case_opened": 2,
         "assessment_asserted": 3, "decision_recorded": 4}  # fmt: skip


class SeedError(RuntimeError):
    """The data needed to seed is missing, or the ledger is not empty."""


@dataclass(frozen=True)
class SeedSummary:
    counts: dict[str, int]
    cutoff: datetime  # live first contact (naive UTC); every seeded row is strictly before it
    rows: int
    head_seq: int | None
    head_hash: str | None
    elapsed_s: float


def first_contact(store: TrackStore, scenario: ScenarioConfig) -> datetime:
    """The live incident's start (first radar contact, D-003), naive UTC."""
    df = store.sql("SELECT start_ts FROM incidents WHERE incident_id = $i",
                   {"i": scenario.live_incident})  # fmt: skip
    if df.empty:
        raise SeedError(f"live incident {scenario.live_incident} is not in the store: run "
                        "`make data`")  # fmt: skip
    return utc_naive(df["start_ts"].iloc[0])


def planted_cases(scenario: ScenarioConfig) -> list[str]:
    """Incidents whose planted assessment opens and closes a case (the DELTA night)."""
    return [f.incident_id for f in scenario.p1_flights if f.assessment is not None]


def _incidents(store: TrackStore) -> list[dict]:
    df = store.sql("SELECT incident_id, installation_id, region_id, start_ts, end_ts, "
                   "n_tracks, is_swarm FROM incidents WHERE status <> 'live' "
                   "ORDER BY incident_id")  # fmt: skip
    return [{"event_type": "incident_recorded", "actor": "generator",
             "recorded_at": utc_naive(r.end_ts) + INCIDENT_LAG, "subject_id": r.incident_id,
             "valid_from": r.start_ts, "valid_to": r.end_ts,
             "object_json": {"base": r.installation_id, "region_id": r.region_id,
                             "n_tracks": int(r.n_tracks), "is_swarm": bool(r.is_swarm)}}
            for r in df.itertuples(index=False)]  # fmt: skip


def _reports(store: TrackStore) -> list[dict]:
    df = store.sql("SELECT r.* FROM reports r JOIN incidents i USING (incident_id) "
                   "WHERE i.status <> 'live' ORDER BY r.report_id")  # fmt: skip
    return [{"event_type": "report_recorded", "actor": "generator", "recorded_at": r.report_ts,
             "subject_id": r.report_id, "valid_from": r.event_ts, "source_type": r.source,
             "source_id": r.report_id, "source_grade": r.source_grade,
             "object_json": {"incident_id": r.incident_id, "base": r.installation_id,
                             "source": r.source, "text": r.text}}
            for r in df.itertuples(index=False)]  # fmt: skip


def _assessments(store: TrackStore) -> list[dict]:
    df = store.sql("SELECT a.*, i.start_ts AS incident_start, i.installation_id AS base "
                   "FROM assessments a JOIN incidents i USING (incident_id) "
                   "WHERE i.status <> 'live' ORDER BY a.assessment_id")  # fmt: skip
    return [{"event_type": "assessment_asserted", "actor": "generator",
             "recorded_at": r.assessed_ts, "subject_id": r.incident_id,
             "predicate": "assessment", "valid_from": r.incident_start,
             "source_type": "assessment", "source_id": r.assessment_id,
             "object_json": {"label": r.label, "rationale": r.rationale, "author": r.author,
                             "assessment_id": r.assessment_id}}
            for r in df.itertuples(index=False)]  # fmt: skip


def _planted(scenario: ScenarioConfig, assessments: list[dict], bases: dict[str, str]) -> list:
    """``case_opened`` and the ``close`` decision for each planted assessment. Uses only the
    base-side fields of the generator's assessment row (label, author, assessed time)."""
    by_incident = {e["subject_id"]: e for e in assessments}
    out = []
    for inc in planted_cases(scenario):
        a = by_incident.get(inc)
        if a is None:
            raise SeedError(f"no assessment for planted incident {inc}: run `make data`")
        o, t, case = a["object_json"], a["recorded_at"], f"CASE-{inc}"
        out.append(
            {
                "event_type": "case_opened",
                "actor": "generator",
                "recorded_at": t,
                "case_id": case,
                "subject_id": inc,
                "valid_from": t,
                "object_json": {"base": bases.get(inc), "opened_by": o["author"]},
            }
        )
        out.append({"event_type": "decision_recorded", "actor": "generator", "recorded_at": t,
                    "case_id": case, "subject_id": inc, "predicate": "decision",
                    "valid_from": t,
                    "object_json": {"decision": "close", "rationale": f"assessed {o['label']}",
                                    "by": o["author"]}})  # fmt: skip
    return out


def seed_events(store: TrackStore, scenario: ScenarioConfig) -> list[dict]:
    """Every seeded event, in the order the ledger records them, all before first contact."""
    cutoff = first_contact(store, scenario)
    incidents, reports, assessments = _incidents(store), _reports(store), _assessments(store)
    bases = {e["subject_id"]: e["object_json"]["base"] for e in incidents}
    planted = set(planted_cases(scenario))
    events = [*incidents, *reports, *assessments, *_planted(scenario, assessments, bases)]
    for e in events:
        e["recorded_at"] = utc_naive(e["recorded_at"])
    trio = {"case_opened": 0, "assessment_asserted": 1, "decision_recorded": 2}

    def key(e: dict) -> tuple:
        # the planted trio shares one rank so nothing recorded at the same instant splits it
        if e["subject_id"] in planted and e["event_type"] in trio:
            return e["recorded_at"], 2, e["subject_id"], trio[e["event_type"]]
        return e["recorded_at"], _RANK[e["event_type"]], e["subject_id"], 0

    return sorted((e for e in events if e["recorded_at"] < cutoff), key=key)


def seed(memory: CaseMemory, store: TrackStore, scenario: ScenarioConfig) -> SeedSummary:
    """Seed an empty ledger in one transaction. Raises ``SeedError`` if it already has rows."""
    t0 = time.perf_counter()
    existing = memory.events()
    if existing:
        raise SeedError(f"the ledger already has {len(existing):,} rows: use "
                        "`kairos-defense memory reseed`")  # fmt: skip
    events = seed_events(store, scenario)
    seqs = memory.append_many(events)
    rows = memory.events()
    head = rows[-1] if rows else None
    counts = dict(Counter(e["event_type"] for e in events))
    log.info("seeded %d events (%s)", len(seqs), counts)
    return SeedSummary(counts, first_contact(store, scenario), len(rows),
                       head["seq"] if head else None, head["hash"] if head else None,
                       time.perf_counter() - t0)  # fmt: skip
