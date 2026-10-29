"""Nodes and edges of a case as known at a moment, for the Case board (SPEC §16.4, §17.9, D-108).

Pure function over ledger rows. Nodes: the case, its member incidents and the incidents of
pending proposals (each with its base), the members' reports and assessments. Edges:
``member_of`` (founder and approved links), ``proposed`` (pending proposals), ``report_of`` and
``assessed``. Incidents with a contradiction (§15.4) carry ``contradiction: true``; nothing is
resolved here. Every node and edge keeps the ``seq`` of the row behind it and its
``recorded_at``, so the board can add nodes as the scrubber reaches them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from kairos_defense.memory.asof import snapshot
from kairos_defense.memory.ledger import known_at
from kairos_defense.memory.views import obj
from kairos_defense.ports import _jsonable


def case_graph(rows: Sequence[Mapping], case_id: str, t: datetime) -> dict:
    """``{"case_id", "as_of", "exists", "status", "nodes": [...], "edges": [...]}``."""
    known = known_at(rows, t)
    snap = snapshot(known, case_id, t)
    out = {"case_id": case_id, "as_of": t, "exists": snap.exists, "status": snap.status,
           "nodes": [], "edges": []}  # fmt: skip
    if not snap.exists:
        return _jsonable(out)
    bases = {r["subject_id"]: obj(r).get("base") for r in known
             if r["event_type"] == "incident_recorded"}  # fmt: skip
    recorded = {r["subject_id"]: (r["seq"], r["recorded_at"]) for r in known
                if r["event_type"] == "incident_recorded"}  # fmt: skip
    contra = {c["subject_id"] for c in snap.contradictions}
    founder = next(r for r in known if r["event_type"] == "case_opened" and r["case_id"] == case_id)
    nodes = [{"id": case_id, "kind": "case", "status": snap.status, "seq": founder["seq"],
              "recorded_at": founder["recorded_at"]}]  # fmt: skip
    edges = []

    def incident(inc: str, member: bool) -> None:
        seq, at = recorded.get(inc, (None, None))
        nodes.append({"id": inc, "kind": "incident", "base": bases.get(inc), "member": member,
                      "contradiction": inc in contra, "seq": seq, "recorded_at": at})  # fmt: skip

    incident(snap.founder, True)
    edges.append({"source": snap.founder, "target": case_id, "kind": "member_of",
                  "seq": founder["seq"], "recorded_at": founder["recorded_at"]})  # fmt: skip
    for lk in snap.links:
        if lk["incident_id"] != snap.founder:
            incident(lk["incident_id"], True)
        edges.append({"source": lk["incident_id"], "target": case_id, "kind": "member_of",
                      "seq": lk["seq"], "recorded_at": lk["recorded_at"]})  # fmt: skip
    seen = {n["id"] for n in nodes}
    for p in snap.pending:
        if p["incident_id"] not in seen:
            incident(p["incident_id"], False)
            seen.add(p["incident_id"])
        edges.append({"source": p["incident_id"], "target": case_id, "kind": "proposed",
                      "seq": p["seq"], "score": p["score"],
                      "recorded_at": p["recorded_at"]})  # fmt: skip
    for rp in snap.reports:
        nodes.append({"id": rp["report_id"], "kind": "report", "source": rp["source"],
                      "grade": rp["grade"], "seq": rp["seq"],
                      "recorded_at": rp["recorded_at"]})  # fmt: skip
        edges.append({"source": rp["report_id"], "target": rp["incident_id"], "kind": "report_of",
                      "seq": rp["seq"], "recorded_at": rp["recorded_at"]})  # fmt: skip
    for c in snap.claims:
        aid = f"A-{c['seq']}"
        nodes.append({"id": aid, "kind": "assessment", "label": c["value"],
                      "contradiction": c["subject_id"] in contra, "seq": c["seq"],
                      "recorded_at": c["recorded_at"]})  # fmt: skip
        edges.append({"source": aid, "target": c["subject_id"], "kind": "assessed",
                      "seq": c["seq"], "recorded_at": c["recorded_at"]})  # fmt: skip
    out["nodes"], out["edges"] = nodes, edges
    return _jsonable(out)
