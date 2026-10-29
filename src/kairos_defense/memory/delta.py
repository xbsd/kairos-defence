"""The shift delta (SPEC §15.8, D-101): what the memory learned during a shift.

``delta(rows, since, until, installation_id)`` groups the rows recorded in ``(since, until]``. Each
item carries its seq and evidence references (``views.item``). ``contradictions_opened`` lists
contradictions present at ``until`` and absent at ``since`` (any subject), keyed to the claim
that opened them.

The installation filter keeps a row when the installation is the base of its incident (subject or
query incident), of its report, or of its case's founder. Rows with no installation
(``model_registered``) are dropped when filtering.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from kairos_defense.memory.asof import contradictions
from kairos_defense.memory.ledger import active_rows, known_at
from kairos_defense.memory.views import claim_view, item, obj
from kairos_defense.ports import _jsonable

GROUPS = ("incidents", "reports", "proposals", "links_approved", "links_rejected",
          "assessments_added", "assessments_retracted", "retractions", "contradictions_opened",
          "decisions", "exports", "models")  # fmt: skip
_GROUP_OF = {
    "incident_recorded": "incidents",
    "report_recorded": "reports",
    "match_proposed": "proposals",
    "link_approved": "links_approved",
    "link_rejected": "links_rejected",
    "assessment_asserted": "assessments_added",
    "case_opened": "decisions",
    "decision_recorded": "decisions",
    "evidence_exported": "exports",
    "model_registered": "models",
}


@dataclass(frozen=True)
class ShiftDelta:
    since: datetime
    until: datetime
    installation_id: str | None
    groups: dict[str, list[dict]] = field(default_factory=dict)
    head_seq: int | None = None
    head_hash: str | None = None

    @property
    def count(self) -> int:
        return sum(len(v) for v in self.groups.values())

    def to_dict(self) -> dict:
        return _jsonable({"since": self.since, "until": self.until,
                          "installation_id": self.installation_id, "groups": self.groups,
                          "count": self.count, "head_seq": self.head_seq,
                          "head_hash": self.head_hash})  # fmt: skip


def _bases(known: Sequence[Mapping]) -> tuple[dict[str, str], dict[str, str]]:
    """Incident -> base, and case -> its founder's base."""
    inc = {r["subject_id"]: obj(r).get("base") for r in known
           if r["event_type"] == "incident_recorded"}  # fmt: skip
    case = {r["case_id"]: obj(r).get("base") or inc.get(r["subject_id"]) for r in known
            if r["event_type"] == "case_opened"}  # fmt: skip
    return inc, case


def _row_bases(r: Mapping, inc: Mapping, case: Mapping) -> set[str]:
    o = obj(r)
    found = {o.get("base") if r["event_type"] in ("report_recorded", "incident_recorded")
             else None, inc.get(r["subject_id"]), inc.get(o.get("query_incident")),
             inc.get(o.get("incident_id")), case.get(r["case_id"])}  # fmt: skip
    return {b for b in found if b}


def _claim_contradictions(rows: Sequence[Mapping], t: datetime) -> dict[tuple, dict]:
    claims = [claim_view(r) for r in active_rows(rows, t) if r["event_type"] ==
              "assessment_asserted"]  # fmt: skip
    return {(c["subject_id"], c["predicate"], tuple(c["values"])): c
            for c in contradictions(claims)}  # fmt: skip


def delta(rows: Sequence[Mapping], since: datetime, until: datetime,
          installation_id: str | None = None) -> ShiftDelta:  # fmt: skip
    """Rows recorded in ``(since, until]``, grouped (``GROUPS``), optionally for one base."""
    known = known_at(rows, until)
    by_seq = {r["seq"]: r for r in known}
    inc, case = _bases(known)
    groups: dict[str, list[dict]] = {g: [] for g in GROUPS}

    def keep(r: Mapping) -> bool:
        return installation_id is None or installation_id in _row_bases(r, inc, case)

    for r in known:
        if not since < r["recorded_at"] <= until or not keep(r):
            continue
        if r["event_type"] == "claim_retracted":
            target = by_seq.get(r["supersedes_seq"], {})
            g = ("assessments_retracted" if target.get("event_type") == "assessment_asserted"
                 else "retractions")  # fmt: skip
            groups[g].append(item(r, g, retracts=target.get("event_type")))
        else:
            g = _GROUP_OF[r["event_type"]]
            groups[g].append(item(r, g))
    old = _claim_contradictions(known, since)
    for key, c in _claim_contradictions(known, until).items():
        if key in old:
            continue
        if installation_id is not None and inc.get(c["subject_id"]) != installation_id:
            continue
        groups["contradictions_opened"].append({
            "group": "contradictions_opened", "seq": c["opened_seq"],
            "event_type": "contradiction", "recorded_at": c["opened_at"],
            "subject_id": c["subject_id"], "case_id": None, "supersedes_seq": None,
            "source_id": None, "values": c["values"], "claims": [x["seq"] for x in c["claims"]],
            "summary": f"{c['subject_id']} {c['predicate']}: " + " vs ".join(map(str, c["values"])),
        })  # fmt: skip
    head = known[-1] if known else None
    return ShiftDelta(since, until, installation_id, groups,
                      head["seq"] if head else None, head["hash"] if head else None)  # fmt: skip
