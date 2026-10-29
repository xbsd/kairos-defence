"""The §15.6 writes: what the live loop, the API (phase 7), the agent (phase 9) and the CLI append.

Every function takes the ``CaseMemory`` port and an explicit ``clock`` (naive UTC; the replay
clock live). The writer stamps ``max(clock, head)`` (D-010). Rules (D-097):

- ``record_incident`` and ``register_model`` write once (per incident; per version and sha256).
- ``propose_matches`` appends one ``match_proposed`` per top-3 match as a batch sharing ``top3``
  and ``recorded_at``, unless an earlier batch for the same query and case has the same top-3
  set with every score within 0.05: a re-run or a seek back appends nothing.
- ``decide_link`` is the analyst's approve or reject of any active, undecided proposal for the
  case (whether or not its incident is already a member). Only ``analyst:<handle>`` may (rule 8).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

import numpy as np

from kairos_defense.memory.asof import is_decided
from kairos_defense.memory.ledger import analyst, superseded_seqs
from kairos_defense.memory.views import obj
from kairos_defense.ports import CaseMemory

SCORE_TOLERANCE = 0.05  # §15.6: a score must move by more than this to propose again


class ActionError(ValueError):
    """A write the case memory refuses (the message says why)."""


class ProposalNotFound(ActionError):
    pass


class ProposalAlreadyDecided(ActionError):
    pass


class WrongCase(ActionError):
    pass


class CaseExists(ActionError):
    pass


def json_safe(v: object) -> object:
    """NaN and infinities become None, numpy scalars Python numbers, tuples lists (recursively)."""
    if isinstance(v, (float, np.floating)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, Mapping):
        return {k: json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [json_safe(x) for x in v]
    return v


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _first(rows: Iterable[Mapping], **match: object) -> Mapping | None:
    return next((r for r in rows if all(r[k] == v for k, v in match.items())), None)


def record_incident(memory: CaseMemory, incident: Mapping, clock: datetime,
                    actor: str = "system") -> int:  # fmt: skip
    """``incident_recorded`` for a live incident (``incident_id``, ``installation_id``,
    ``region_id``, ``start_ts``, ``n_tracks``, ``is_swarm``); valid from its start, open-ended.
    Returns the existing seq if the incident is already recorded."""
    inc = str(incident["incident_id"])
    old = _first(memory.events(), event_type="incident_recorded", subject_id=inc)
    if old is not None:
        return int(old["seq"])
    return memory.append({
        "event_type": "incident_recorded", "actor": actor, "recorded_at": clock,
        "subject_id": inc, "valid_from": incident["start_ts"],
        "object_json": json_safe({"base": incident["installation_id"],
                                  "region_id": incident.get("region_id"),
                                  "n_tracks": incident.get("n_tracks"),
                                  "is_swarm": incident.get("is_swarm")})})  # fmt: skip


def register_model(memory: CaseMemory, version: str, sha256: str, clock: datetime,
                   file: str = "", validation: Mapping | None = None) -> int:  # fmt: skip
    """``model_registered`` once per (version, sha256); returns the existing seq otherwise."""
    for r in memory.events():
        o = obj(r)
        if r["event_type"] == "model_registered" and (o.get("version"), o.get("sha256")) == (
            version, sha256):  # fmt: skip
            return int(r["seq"])
    return memory.append({
        "event_type": "model_registered", "actor": "system", "recorded_at": clock,
        "object_json": json_safe({"version": version, "sha256": sha256, "file": file,
                                  "validation": dict(validation or {})})})  # fmt: skip


def _as_dict(m: object) -> dict:
    return m.to_dict() if hasattr(m, "to_dict") else dict(m)  # Match or a plain dict


def propose_matches(memory: CaseMemory, case_id: str, query_incident: str, matches: Sequence,
                    clock: datetime, *, query_track: str | None = None, t_s: int | None = None,
                    model_version: str | None = None, actor: str | None = None,
                    top: int = 3) -> list[int]:  # fmt: skip
    """Propose the ``top`` best matches (``Match`` or dicts with ``incident_id``, ``score`` …) for
    ``case_id``. Returns the new seqs, or ``[]`` when deduplicated (see module)."""
    ms = [json_safe(_as_dict(m)) for m in list(matches)[:top]]
    if not ms:
        return []
    version = model_version or ms[0].get("model_version") or "unknown"
    top3 = [m["incident_id"] for m in ms]
    scores = {m["incident_id"]: m["score"] for m in ms}
    batches: dict[tuple, dict[str, float]] = {}
    for r in memory.events():
        o = obj(r)
        if (r["event_type"] == "match_proposed" and r["case_id"] == case_id
                and o.get("query_incident") == query_incident):  # fmt: skip
            batches.setdefault((r["recorded_at"], tuple(o.get("top3") or ())), {})[
                r["subject_id"]] = o.get("score")  # fmt: skip
    for (_t, t3), old in batches.items():
        if set(t3) == set(top3) and all(
            old.get(i) is not None and abs(old[i] - scores[i]) <= SCORE_TOLERANCE for i in top3
        ):
            return []
    events = [{
        "event_type": "match_proposed", "actor": actor or f"matcher@{version}",
        "recorded_at": clock, "case_id": case_id, "subject_id": m["incident_id"],
        "predicate": "member_of", "valid_from": clock, "source_type": "matcher",
        "source_id": version, "confidence": m["score"],
        "object_json": {"query_incident": query_incident, "query_track": query_track,
                        "match_track": m.get("track_id"), "rank": rank, "score": m["score"],
                        "shape_sim": m.get("shape_sim"), "features": m.get("features", {}),
                        "reasons": m.get("reasons", []), "warp_ratio": m.get("warp_ratio"),
                        "model_version": version, "t_s": t_s, "top3": top3},
    } for rank, m in enumerate(ms, 1)]  # fmt: skip
    return memory.append_many(events)


def decide_link(memory: CaseMemory, case_id: str, proposal_seq: int, decision: str,
                handle: str, clock: datetime, rationale: str = "") -> int:  # fmt: skip
    """An analyst approves (``link_approved``) or rejects (``link_rejected``, superseding the
    proposal) one proposal. Raises ``ProposalNotFound``, ``WrongCase`` or
    ``ProposalAlreadyDecided``."""
    if decision not in ("approve", "reject"):
        raise ActionError(f"decision must be approve or reject, not {decision!r}")
    actor = analyst(handle)
    rows = memory.events()
    p = _first(rows, seq=int(proposal_seq))
    if p is None or p["event_type"] != "match_proposed":
        raise ProposalNotFound(f"seq {proposal_seq} is not a match proposal")
    if p["case_id"] != case_id:
        raise WrongCase(f"proposal {proposal_seq} is for {p['case_id']}, not {case_id}")
    if p["seq"] in superseded_seqs(rows) or p["seq"] in is_decided(rows):
        raise ProposalAlreadyDecided(f"proposal {proposal_seq} is already decided")
    base = {"actor": actor, "recorded_at": clock, "case_id": case_id,
            "subject_id": p["subject_id"], "predicate": "member_of"}  # fmt: skip
    if decision == "approve":
        return memory.append({**base, "event_type": "link_approved", "valid_from": clock,
                              "object_json": {"proposal_seq": p["seq"],
                                              "query_incident": obj(p).get("query_incident"),
                                              "rationale": rationale}})  # fmt: skip
    return memory.append({**base, "event_type": "link_rejected", "supersedes_seq": p["seq"],
                          "object_json": {"rationale": rationale}})  # fmt: skip


def open_case(memory: CaseMemory, incident_id: str, actor: str, clock: datetime,
              base: str | None = None) -> int:  # fmt: skip
    """``case_opened`` for ``CASE-<incident_id>``; raises ``CaseExists`` if that id is taken."""
    case_id = f"CASE-{incident_id}"
    if _first(memory.events(), event_type="case_opened", case_id=case_id) is not None:
        raise CaseExists(f"{case_id} already exists")
    return memory.append({"event_type": "case_opened", "actor": actor, "recorded_at": clock,
                          "case_id": case_id, "subject_id": incident_id, "valid_from": clock,
                          "object_json": {"base": base, "opened_by": actor}})  # fmt: skip


def record_decision(memory: CaseMemory, case_id: str, decision: str, actor: str,
                    clock: datetime, rationale: str = "") -> int:  # fmt: skip
    """``decision_recorded`` (close, reopen, escalate, notify_law_enforcement) on a case."""
    f = _first(memory.events(), event_type="case_opened", case_id=case_id)
    if f is None:
        raise ActionError(f"no case {case_id}")
    return memory.append({"event_type": "decision_recorded", "actor": actor,
                          "recorded_at": clock, "case_id": case_id,
                          "subject_id": f["subject_id"], "predicate": "decision",
                          "valid_from": clock,
                          "object_json": {"decision": decision, "rationale": rationale,
                                          "by": actor}})  # fmt: skip


def retract(memory: CaseMemory, seq: int, actor: str, clock: datetime,
            rationale: str = "") -> int:  # fmt: skip
    """``claim_retracted`` superseding an assessment, a link or a decision (rule 7: the
    original row stays; the retraction is a new event)."""
    target = _first(memory.events(), seq=int(seq))
    if target is None:
        raise ActionError(f"no row {seq}")
    return memory.append({"event_type": "claim_retracted", "actor": actor, "recorded_at": clock,
                          "case_id": target["case_id"], "subject_id": target["subject_id"],
                          "predicate": target["predicate"], "supersedes_seq": int(seq),
                          "object_json": {"rationale": rationale}})  # fmt: skip
