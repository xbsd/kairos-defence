"""Case diffs (SPEC §15.4, D-101): what changed about a case between two transaction times.

``case_diff(rows, case_id, t1, t2)`` lists rows recorded in ``(t1, t2]`` that touch the case's
subjects as known at ``t2``, so facts about an incident linked later ("it had not happened yet at
t1") are included. Each item carries its seq and evidence references (``views.item``) in one of
``GROUPS``; approvals carry ``new_member`` (False when the incident was already a member at t1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from kairos_defense.memory.asof import members_at, snapshot, touching_rows
from kairos_defense.memory.ledger import known_at
from kairos_defense.memory.views import item, obj

GROUPS = ("members_added", "proposals", "claims_added", "claims_retracted", "contradictions",
          "decisions", "exports", "facts")  # fmt: skip
GROUP_OF = {
    "link_approved": "members_added",
    "match_proposed": "proposals",
    "assessment_asserted": "claims_added",
    "claim_retracted": "claims_retracted",
    "case_opened": "decisions",
    "decision_recorded": "decisions",
    "evidence_exported": "exports",
    "incident_recorded": "facts",
    "report_recorded": "facts",
    "link_rejected": "facts",
    "model_registered": "facts",
}


def _key(c: Mapping) -> tuple:
    return c["subject_id"], c["predicate"], tuple(c["values"])


def case_diff(rows: Sequence[Mapping], case_id: str, t1: datetime, t2: datetime) -> list[dict]:
    """Items for the case's changes in ``(t1, t2]``, in seq order."""
    known = known_at(rows, t2)
    before = set(members_at(known, case_id, t1))
    after = members_at(known, case_id, t2)
    window = [r for r in touching_rows(known, case_id, after) if t1 < r["recorded_at"] <= t2]
    out, added = [], set()
    versions = {obj(r).get("model_version") for r in window if r["event_type"] == "match_proposed"}
    for r in window:
        g = GROUP_OF[r["event_type"]]
        if g == "members_added":
            inc = r["subject_id"]
            out.append(item(r, g, new_member=inc not in before and inc not in added))
            added.add(inc)
        else:
            out.append(item(r, g))
    out += [item(r, "facts") for r in known
            if r["event_type"] == "model_registered" and t1 < r["recorded_at"] <= t2
            and obj(r).get("version") in versions]  # fmt: skip
    old = {_key(c) for c in snapshot(known, case_id, t1).contradictions}
    for c in snapshot(known, case_id, t2).contradictions:
        if _key(c) not in old:
            out.append({"group": "contradictions", "seq": c["opened_seq"],
                        "event_type": "contradiction", "recorded_at": c["opened_at"],
                        "subject_id": c["subject_id"], "case_id": case_id,
                        "supersedes_seq": None, "source_id": None, "values": c["values"],
                        "claims": [x["seq"] for x in c["claims"]],
                        "summary": f"{c['subject_id']} {c['predicate']}: "
                                   + " vs ".join(map(str, c["values"]))})  # fmt: skip
    return sorted(out, key=lambda i: (i["seq"], i["group"]))


def group(items: Sequence[Mapping]) -> dict[str, list[dict]]:
    """Items by group, every group present (empty lists included), in ``GROUPS`` order."""
    out: dict[str, list[dict]] = {g: [] for g in GROUPS}
    for i in items:
        out.setdefault(i["group"], []).append(dict(i))
    return out
