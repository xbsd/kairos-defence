"""Snapshots, contradictions and valid-time views (SPEC §15.4, D-094).

Pure functions over ledger rows in seq order (``CaseMemory.events()``), with naive-UTC times.

- **Members** of a case: its founder (``case_opened``) and then the subjects of active
  ``link_approved`` rows.
- **Pending**: active, undecided ``match_proposed`` rows for the case about an incident that is
  not already a member. A proposal is decided once a ``link_approved`` names it
  (``object_json.proposal_seq``) or a ``link_rejected`` supersedes it.
- **Claims**: active ``assessment_asserted`` rows about members, valued by ``label``. A
  **contradiction** is two or more active claims with the same subject and predicate and
  different values; both stay listed until one is retracted. Nothing resolves them.
- **Status**: ``unknown`` before ``case_opened``; then ``closed`` after an active ``close``
  decision unless a later ``reopen``; otherwise ``open``. Escalations do not change it.
- A row **touches** a case when its ``case_id`` is the case, its incident is a member (the
  ``subject_id``, or ``object_json.incident_id`` for reports), or it supersedes a row that does.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from kairos_defense.memory.ledger import active_rows, known_at, superseded_seqs
from kairos_defense.memory.views import (
    claim_view,
    decision_view,
    dedupe,
    export_view,
    link_view,
    obj,
    proposal_view,
    report_view,
)
from kairos_defense.ports import CaseSnapshot


def founder_row(active: Iterable[Mapping], case_id: str) -> Mapping | None:
    return next((r for r in active if r["event_type"] == "case_opened"
                 and r["case_id"] == case_id), None)  # fmt: skip


def members_at(rows: Sequence[Mapping], case_id: str, t: datetime) -> list[str]:
    """Member incident ids of the case as known at ``t`` (founder first)."""
    active = active_rows(rows, t)
    f = founder_row(active, case_id)
    if f is None:
        return []
    links = [r["subject_id"] for r in active
             if r["event_type"] == "link_approved" and r["case_id"] == case_id]  # fmt: skip
    return dedupe([f["subject_id"], *links])


def touches(r: Mapping, case_id: str, members: Iterable[str], touching: set[int]) -> bool:
    if r["case_id"] == case_id:
        return True
    if r["event_type"] == "report_recorded":
        return obj(r).get("incident_id") in members
    if r["subject_id"] is not None and r["subject_id"] in members:
        return True
    return r["supersedes_seq"] is not None and r["supersedes_seq"] in touching


def touching_rows(rows: Iterable[Mapping], case_id: str, members: Sequence[str]) -> list[dict]:
    """Rows (superseded ones included) that touch the case, in seq order."""
    out, seqs, mem = [], set(), set(members)
    for r in rows:
        if touches(r, case_id, mem, seqs):
            out.append(r)
            seqs.add(r["seq"])
    return out


def contradictions(claims: Sequence[Mapping]) -> list[dict]:
    """Groups of active claims (views from ``claim_view``) with the same subject and predicate
    but different values. ``opened_seq`` is the claim that first made the group disagree."""
    groups: dict[tuple, list[Mapping]] = {}
    for c in sorted(claims, key=lambda c: c["seq"]):
        groups.setdefault((c["subject_id"], c["predicate"]), []).append(c)
    out = []
    for (subject, predicate), cs in groups.items():
        values = sorted({c["value"] for c in cs}, key=str)
        if len(values) < 2:
            continue
        seen: set = set()
        opened = None
        for c in cs:
            seen.add(c["value"])
            if len(seen) == 2 and opened is None:
                opened = c
        out.append({"subject_id": subject, "predicate": predicate, "values": values,
                    "claims": [dict(c) for c in cs], "opened_seq": opened["seq"],
                    "opened_at": opened["recorded_at"]})  # fmt: skip
    return out


def case_status(decisions: Sequence[Mapping], exists: bool) -> str:
    if not exists:
        return "unknown"
    status = "open"
    for d in decisions:
        if d["decision"] == "close":
            status = "closed"
        elif d["decision"] == "reopen":
            status = "open"
    return status


def is_decided(known: Sequence[Mapping]) -> set[int]:
    """Proposal seqs an analyst has approved or rejected."""
    approved = {obj(r).get("proposal_seq") for r in known if r["event_type"] == "link_approved"}
    rejected = {r["supersedes_seq"] for r in known if r["event_type"] == "link_rejected"}
    return {s for s in approved | rejected if s is not None}


def snapshot(rows: Sequence[Mapping], case_id: str, t: datetime) -> CaseSnapshot:
    """The case as known at ``t`` (transaction time)."""
    known = known_at(rows, t)
    gone = superseded_seqs(known)
    active = [r for r in known if r["seq"] not in gone]
    head = known[-1] if known else None
    heads = {"head_seq": head["seq"] if head else None, "head_hash": head["hash"] if head else None}
    f = founder_row(active, case_id)
    if f is None:
        return CaseSnapshot(case_id, t, **heads)
    links = [link_view(r) for r in active
             if r["event_type"] == "link_approved" and r["case_id"] == case_id]  # fmt: skip
    members = dedupe([f["subject_id"], *(lk["incident_id"] for lk in links)])
    mem, decided = set(members), is_decided(known)
    pending = [proposal_view(r) for r in active
               if r["event_type"] == "match_proposed" and r["case_id"] == case_id
               and r["seq"] not in decided and r["subject_id"] not in mem]  # fmt: skip
    claims = [claim_view(r) for r in active if r["event_type"] == "assessment_asserted"
              and (r["subject_id"] in mem or r["case_id"] == case_id)]  # fmt: skip
    decisions = [
        decision_view(r)
        for r in active
        if r["event_type"] == "decision_recorded" and r["case_id"] == case_id
    ]
    return CaseSnapshot(
        case_id, t, exists=True, status=case_status(decisions, True), founder=f["subject_id"],
        members=members, links=links, pending=pending, claims=claims,
        contradictions=contradictions(claims), decisions=decisions,
        exports=[export_view(r) for r in active
                 if r["event_type"] == "evidence_exported" and r["case_id"] == case_id],
        reports=[report_view(r) for r in active if r["event_type"] == "report_recorded"
                 and obj(r).get("incident_id") in mem],
        events=[dict(r) for r in touching_rows(known, case_id, members)], **heads,
    )  # fmt: skip


def valid_at(rows: Sequence[Mapping], case_id: str, t_valid: datetime,
             known: datetime) -> dict:  # fmt: skip
    """Valid time (§15.4): what the ledger, as known at ``known``, says was true in the world at
    ``t_valid``: active rows touching the case with ``valid_from <= t_valid < valid_to`` (an open
    ``valid_to`` never ends). Separate from transaction-time ``snapshot``."""
    active = active_rows(rows, known)
    members = members_at(rows, case_id, known)
    facts = [r for r in touching_rows(active, case_id, members)
             if r["valid_from"] is not None and r["valid_from"] <= t_valid
             and (r["valid_to"] is None or t_valid < r["valid_to"])]  # fmt: skip
    return {"case_id": case_id, "valid_at": t_valid, "known_at": known, "members": members,
            "claims": [claim_view(r) for r in facts if r["event_type"] == "assessment_asserted"],
            "rows": [dict(r) for r in facts]}  # fmt: skip


def case_summaries(rows: Sequence[Mapping], t: datetime) -> list[dict]:
    """One line per case known at ``t`` (the Case board's list): ``case_id``, ``founder``,
    ``base`` (the founder's installation), ``status``, ``opened_at``, ``members``,
    ``pending`` (undecided proposals), ``contradictions``, ``claims`` (active labels),
    ``last_decision`` and ``exports``. Ordered by ``opened_at``, then ``case_id``."""
    known = known_at(rows, t)
    bases = {r["subject_id"]: obj(r).get("base") for r in known
             if r["event_type"] == "incident_recorded"}  # fmt: skip
    out = []
    for r in known:
        if r["event_type"] != "case_opened":
            continue
        s = snapshot(known, r["case_id"], t)
        if not s.exists:  # opened, then retracted
            continue
        last = s.decisions[-1] if s.decisions else None
        out.append({"case_id": s.case_id, "founder": s.founder,
                    "base": bases.get(s.founder) or obj(r).get("base"), "status": s.status,
                    "opened_at": r["recorded_at"], "members": list(s.members),
                    "pending": len(s.pending), "contradictions": len(s.contradictions),
                    "claims": sorted({str(c["value"]) for c in s.claims if c["value"]}),
                    "last_decision": last["decision"] if last else None,
                    "exports": len(s.exports)})  # fmt: skip
    return sorted(out, key=lambda c: (c["opened_at"], c["case_id"]))
