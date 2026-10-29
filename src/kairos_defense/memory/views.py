"""Compact, readable views of ledger rows, shared by snapshots, diffs, the shift delta and the CLI.

Every view keeps the row's ``seq`` (its evidence reference) and its transaction time.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta


def obj(row: Mapping) -> dict:
    return row.get("object_json") or {}


def claim_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "subject_id": r["subject_id"], "predicate": r["predicate"],
            "value": o.get("label"), "rationale": o.get("rationale"), "author": o.get("author"),
            "source_type": r["source_type"], "source_id": r["source_id"],
            "source_grade": r["source_grade"], "actor": r["actor"],
            "recorded_at": r["recorded_at"], "valid_from": r["valid_from"]}  # fmt: skip


def link_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "incident_id": r["subject_id"], "proposal_seq": o.get("proposal_seq"),
            "query_incident": o.get("query_incident"), "rationale": o.get("rationale"),
            "actor": r["actor"], "recorded_at": r["recorded_at"]}  # fmt: skip


def proposal_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "incident_id": r["subject_id"], "case_id": r["case_id"],
            "query_incident": o.get("query_incident"), "rank": o.get("rank"),
            "score": o.get("score"), "reasons": o.get("reasons", []),
            "model_version": o.get("model_version"), "t_s": o.get("t_s"), "actor": r["actor"],
            "recorded_at": r["recorded_at"]}  # fmt: skip


def decision_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "decision": o.get("decision"), "rationale": o.get("rationale"),
            "by": o.get("by"), "actor": r["actor"], "recorded_at": r["recorded_at"]}  # fmt: skip


def export_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "manifest_sha256": o.get("manifest_sha256"), "path": o.get("path"),
            "approved_by": o.get("approved_by"), "recorded_at": r["recorded_at"]}  # fmt: skip


def report_view(r: Mapping) -> dict:
    o = obj(r)
    return {"seq": r["seq"], "report_id": r["subject_id"], "incident_id": o.get("incident_id"),
            "source": o.get("source"), "grade": r["source_grade"], "event_at": r["valid_from"],
            "recorded_at": r["recorded_at"], "text": o.get("text")}  # fmt: skip


def describe(r: Mapping) -> str:
    """One line a person can read, e.g. ``P1-ALPHA-260303 proposed for CASE-… (rank 2, 0.913)``."""
    o, et, s = obj(r), r["event_type"], r["subject_id"]
    if et == "incident_recorded":
        return f"incident {s} at {o.get('base')} ({o.get('n_tracks')} track(s))"
    if et == "report_recorded":
        return f"report {s} ({o.get('source')}, {r['source_grade']}) about {o.get('incident_id')}"
    if et == "assessment_asserted":
        return f"{s} assessed {o.get('label')!r} by {o.get('author') or r['actor']}"
    if et == "case_opened":
        return f"{r['case_id']} opened on {s}"
    if et == "decision_recorded":
        return f"{r['case_id']}: {o.get('decision')} ({o.get('rationale')})"
    if et == "match_proposed":
        score = o.get("score")
        sc = "-" if score is None else f"{score:.3f}"
        return (f"{s} proposed for {r['case_id']} from {o.get('query_incident')} "
                f"(rank {o.get('rank')}, score {sc})")  # fmt: skip
    if et == "link_approved":
        return f"{s} linked to {r['case_id']} by {r['actor']} (proposal {o.get('proposal_seq')})"
    if et == "link_rejected":
        return f"proposal {r['supersedes_seq']} ({s}) rejected by {r['actor']}"
    if et == "claim_retracted":
        return f"seq {r['supersedes_seq']} retracted by {r['actor']} ({o.get('rationale')})"
    if et == "evidence_exported":
        return f"{r['case_id']} exported ({str(o.get('manifest_sha256'))[:12]}…)"
    if et == "model_registered":
        return f"model {o.get('version')} registered ({str(o.get('sha256'))[:12]}…)"
    return et


def item(r: Mapping, group: str, **extra: object) -> dict:
    """A diff or delta item: the row's evidence references plus a readable summary."""
    return {"group": group, "seq": r["seq"], "event_type": r["event_type"],
            "recorded_at": r["recorded_at"], "subject_id": r["subject_id"],
            "case_id": r["case_id"], "supersedes_seq": r["supersedes_seq"],
            "source_id": r["source_id"], "summary": describe(r), **extra}  # fmt: skip


def dedupe(xs: Iterable[str | None]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x is not None and x not in out:
            out.append(x)
    return out


def incident_statuses(rows: list[Mapping], at: datetime,
                      offsets: Mapping[str, int]) -> dict[str, str]:  # fmt: skip
    """§17.8 memory status per incident as known at ``at`` (D-116), for every incident in a case;
    callers default the rest to ``"Open, unattributed"``. ``offsets``: installation → UTC offset
    (hours), for the local date of a close.

    - In a closed case: "Closed as <label> on <Mon D>" (label: the case's active assessment of
      the incident, else the close rationale; date: the close decision, local to the case's base).
    - In an open case: "Open case, <n> linked" (n: approved links).
    """
    from kairos_defense.memory.asof import snapshot
    from kairos_defense.memory.ledger import known_at

    known = known_at(rows, at)
    out: dict[str, str] = {}
    for f in (r for r in known if r["event_type"] == "case_opened"):
        snap = snapshot(known, f["case_id"], at)
        if not snap.exists:
            continue
        base = obj(f).get("base")
        for inc in snap.members:
            if snap.status == "closed":
                closes = [d for d in snap.decisions if d["decision"] == "close"]
                last = closes[-1]
                label = next((c["value"] for c in reversed(snap.claims)
                              if c["subject_id"] == inc and c["value"]), None)  # fmt: skip
                when = last["recorded_at"] + timedelta(hours=offsets.get(base, 0))
                out[inc] = f"Closed as {label or last['rationale']} on {when:%b} {when.day}"
            else:
                out.setdefault(inc, f"Open case, {len(snap.links)} linked")
    return out


UNATTRIBUTED = "Open, unattributed"
