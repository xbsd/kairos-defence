"""Hand-built ledger events for the memory tests (not a test module).

Times are naive UTC. ``LOCAL`` is DELTA's (COASTAL) offset, so ``local(2026, 4, 20, 9, 10)`` is the
planted assessment's recorded time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

LOCAL = -5  # COASTAL, no daylight saving


def local(*args: int) -> datetime:
    """A local COASTAL wall time as naive UTC."""
    return datetime(*args) - timedelta(hours=LOCAL)


ACTORS = {
    "incident_recorded": "generator",
    "report_recorded": "generator",
    "assessment_asserted": "generator",
    "case_opened": "generator",
    "decision_recorded": "generator",
    "match_proposed": "matcher@test",
    "link_approved": "analyst:test",
    "link_rejected": "analyst:test",
    "claim_retracted": "analyst:test",
    "evidence_exported": "system",
    "model_registered": "system",
}


def ev(event_type: str, t: datetime, **kw) -> dict:
    """One event with the actor its type allows by default."""
    return {
        "event_type": event_type,
        "recorded_at": t,
        "actor": ACTORS.get(event_type, "generator"),
        **kw,
    }


def incident(inc: str, base: str, start: datetime, end: datetime | None = None) -> dict:
    end = end or start + timedelta(minutes=8)
    return ev("incident_recorded", end + timedelta(minutes=5), subject_id=inc,
              valid_from=start, valid_to=end,
              object_json={"base": base, "region_id": "COASTAL", "n_tracks": 1,
                           "is_swarm": False})  # fmt: skip


def report(rid: str, inc: str, base: str, event_t: datetime, t: datetime, text: str = "") -> dict:
    return ev("report_recorded", t, subject_id=rid, valid_from=event_t,
              source_type="security_forces", source_id=rid, source_grade="B2",
              object_json={"incident_id": inc, "base": base, "source": "security_forces",
                           "text": text or f"report about {inc}"})  # fmt: skip


def assessment(inc: str, label: str, t: datetime, valid_from: datetime, author: str = "DELTA BDOC",
               actor: str = "generator") -> dict:  # fmt: skip
    return ev("assessment_asserted", t, subject_id=inc, predicate="assessment",
              valid_from=valid_from, source_type="assessment", source_id=f"A-{inc}",
              actor=actor, object_json={"label": label, "rationale": f"assessed {label}",
                                        "author": author, "assessment_id": f"A-{inc}"})  # fmt: skip


def case_opened(inc: str, base: str, t: datetime) -> dict:
    return ev("case_opened", t, case_id=f"CASE-{inc}", subject_id=inc, valid_from=t,
              object_json={"base": base, "opened_by": "DELTA BDOC"})  # fmt: skip


def decision(case_id: str, inc: str, what: str, t: datetime, actor: str = "generator") -> dict:
    return ev(
        "decision_recorded",
        t,
        case_id=case_id,
        subject_id=inc,
        predicate="decision",
        valid_from=t,
        actor=actor,
        object_json={"decision": what, "rationale": f"assessed {what}", "by": "DELTA BDOC"},
    )


def proposal(case_id: str, inc: str, query: str, score: float, t: datetime, rank: int = 1) -> dict:
    return ev("match_proposed", t, case_id=case_id, subject_id=inc, predicate="member_of",
              valid_from=t, source_type="matcher", source_id="test", confidence=score,
              object_json={"query_incident": query, "score": score, "rank": rank,
                           "model_version": "test", "top3": [inc]})  # fmt: skip


def delta_story() -> list[dict]:
    """The planted DELTA night as Kairos Defense learned it, then two later facts."""
    d0 = local(2026, 4, 19, 21, 35)
    a0 = local(2026, 3, 3, 21, 52)
    return [
        incident("P1-ALPHA-260303", "ALPHA", a0),
        incident("P1-DELTA-260419", "DELTA", d0),
        report(
            "R-P1-DELTA-260419-1",
            "P1-DELTA-260419",
            "DELTA",
            local(2026, 4, 19, 21, 20),
            local(2026, 4, 19, 22, 40),
            "white pickup on County Rd 12",
        ),
        case_opened("P1-DELTA-260419", "DELTA", local(2026, 4, 20, 9, 10)),
        assessment("P1-DELTA-260419", "hobbyist", local(2026, 4, 20, 9, 10), d0),
        decision("CASE-P1-DELTA-260419", "P1-DELTA-260419", "close", local(2026, 4, 20, 9, 10)),
        incident("P1-ALPHA-260502", "ALPHA", local(2026, 5, 2, 22, 5)),
    ]


def numbered(n: int, t0: datetime | None = None) -> list[dict]:
    """``n`` distinct incident events one minute apart."""
    t0 = t0 or datetime(2026, 1, 1)
    return [incident(f"INC-{i:04d}", "ALPHA", t0 + timedelta(minutes=i)) for i in range(n)]
