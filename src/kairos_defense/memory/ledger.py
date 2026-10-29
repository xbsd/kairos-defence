"""The ledger's store-free core (SPEC §15.1–§15.3, D-092 to D-095).

Adapters (``store.ledger_duck.DuckCaseMemory``) call these under their single-writer lock:

- ``normalize_event`` checks fields and converts times to naive UTC and values to canonical form;
- ``validate`` checks the event type, the actor's permission (rule 8), ids (rule 9) and what a
  ``supersedes_seq`` may point to;
- ``seal`` assigns ``seq``, stamps ``recorded_at = max(clock, head)`` (D-010) and hashes the row;
- ``verify_rows`` walks the chain and returns the first broken seq (D-014).

Corrections are new events that supersede earlier ones (rule 7); nothing here edits a stored row.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import NamedTuple

from kairos_defense.memory.canonical import GENESIS, normalize, round_float, row_hash, utc_naive

ROW_FIELDS = ("seq", "recorded_at", "event_type", "case_id", "subject_id", "predicate",
              "object_json", "valid_from", "valid_to", "source_type", "source_id",
              "source_grade", "confidence", "actor", "supersedes_seq", "prev_hash",
              "hash")  # fmt: skip
EVENT_FIELDS = tuple(f for f in ROW_FIELDS if f not in ("seq", "prev_hash", "hash"))
TIME_FIELDS = ("recorded_at", "valid_from", "valid_to")
TEXT_FIELDS = ("event_type", "case_id", "subject_id", "predicate", "source_type", "source_id",
               "source_grade", "actor")  # fmt: skip

# event_type -> actor kinds that may write it (§15.2 "Written by", rule 8: matcher and agents
# only ever propose)
WRITERS: dict[str, frozenset[str]] = {
    "incident_recorded": frozenset({"generator", "system"}),
    "report_recorded": frozenset({"generator", "system"}),
    "assessment_asserted": frozenset({"generator", "analyst"}),
    "case_opened": frozenset({"generator", "analyst"}),
    "match_proposed": frozenset({"matcher", "agent"}),
    "link_approved": frozenset({"analyst"}),
    "link_rejected": frozenset({"analyst"}),
    "claim_retracted": frozenset({"analyst", "generator"}),
    "decision_recorded": frozenset({"analyst", "generator"}),
    "evidence_exported": frozenset({"system"}),
    "model_registered": frozenset({"system"}),
}
EVENT_TYPES = tuple(WRITERS)
# event_type -> what its supersedes_seq must point to (and it must have one)
SUPERSEDES: dict[str, frozenset[str]] = {
    "link_rejected": frozenset({"match_proposed"}),
    "claim_retracted": frozenset({"assessment_asserted", "link_approved", "decision_recorded"}),
}
NEEDS_CASE = frozenset({"case_opened", "match_proposed", "link_approved", "link_rejected",
                        "decision_recorded", "evidence_exported"})  # fmt: skip
NEEDS_SUBJECT = frozenset(EVENT_TYPES) - {"model_registered", "evidence_exported"}
DECISIONS = ("close", "reopen", "escalate", "notify_law_enforcement")

ACTOR = re.compile(r"^(generator|system|matcher@[A-Za-z0-9._-]{1,64}|agent:[A-Za-z0-9._-]{1,64}"
                   r"|analyst:[a-z0-9_.-]{1,32})$")  # fmt: skip
ID = re.compile(r"^[A-Z0-9][A-Z0-9-]*$")  # incident, track and report ids; never a name (rule 9)
CASE_ID = re.compile(r"^CASE-[A-Z0-9][A-Z0-9-]*$")
HANDLE = re.compile(r"^[a-z0-9_.-]{1,32}$")


class LedgerError(RuntimeError):
    """The ledger cannot be used as asked (missing, locked, wrong schema, read-only)."""


class InvalidEvent(ValueError):
    """An event the ledger refuses to append."""


class Head(NamedTuple):
    seq: int
    hash: str
    recorded_at: datetime


class Ref(NamedTuple):
    """What ``validate`` needs to know about an earlier row."""

    event_type: str
    case_id: str | None
    superseded: bool


Lookup = Callable[[int], Ref | None]


def actor_kind(actor: str) -> str:
    """``generator``, ``system``, ``matcher``, ``agent`` or ``analyst``."""
    if not isinstance(actor, str) or not ACTOR.match(actor):
        raise InvalidEvent(f"bad actor {actor!r}: generator, system, matcher@<version>, "
                           "agent:<model> or analyst:<handle>")  # fmt: skip
    return re.split(r"[@:]", actor, maxsplit=1)[0]


def analyst(handle: str) -> str:
    """``analyst:<handle>``; handles are lowercase tokens, never a person's name (rule 9)."""
    if not HANDLE.match(handle or ""):
        raise InvalidEvent(f"bad analyst handle {handle!r}: 1-32 of a-z 0-9 _ . -")
    return f"analyst:{handle}"


def normalize_event(event: Mapping) -> dict:
    """The event with every field present, times as naive UTC, ``object_json`` and
    ``confidence`` in canonical form. Raises ``InvalidEvent``."""
    unknown = set(event) - set(EVENT_FIELDS)
    if unknown:
        raise InvalidEvent(f"unknown or writer-owned fields: {sorted(unknown)}")
    e = {f: event.get(f) for f in EVENT_FIELDS}
    try:
        for f in TIME_FIELDS:
            e[f] = utc_naive(e[f])
    except (TypeError, ValueError) as exc:
        raise InvalidEvent(f"bad time: {exc}") from exc
    if e["recorded_at"] is None:
        raise InvalidEvent("every event needs a recorded_at clock (§15.6)")
    for f in TEXT_FIELDS:
        if e[f] is not None and not isinstance(e[f], str):
            raise InvalidEvent(f"{f} must be text, got {type(e[f]).__name__}")
    obj = e["object_json"]
    if obj is not None and not isinstance(obj, Mapping):
        raise InvalidEvent("object_json must be an object (a dict) or None")
    try:
        e["object_json"] = None if obj is None else normalize(obj)
        e["confidence"] = None if e["confidence"] is None else round_float(e["confidence"])
    except (TypeError, ValueError) as exc:
        raise InvalidEvent(str(exc)) from exc
    s = e["supersedes_seq"]
    if s is not None:
        if isinstance(s, bool) or (not isinstance(s, int) and not hasattr(s, "__index__")):
            raise InvalidEvent(f"supersedes_seq must be an integer, got {s!r}")
        e["supersedes_seq"] = int(s)
    return e


def validate(e: Mapping, lookup: Lookup) -> None:
    """Check a normalized event against the §15.2 rules. ``lookup(seq)`` describes an earlier
    row (or returns None)."""
    et = e["event_type"]
    if et not in WRITERS:
        raise InvalidEvent(f"unknown event_type {et!r}; one of {', '.join(EVENT_TYPES)}")
    kind = actor_kind(e["actor"])
    if kind not in WRITERS[et]:
        raise InvalidEvent(f"{e['actor']} may not write {et} (only {sorted(WRITERS[et])})")
    if e["subject_id"] is not None and not ID.match(e["subject_id"]):
        raise InvalidEvent(f"bad subject_id {e['subject_id']!r}: incident, track or report ids "
                           "only (uppercase letters, digits, dashes), never a person")  # fmt: skip
    if et in NEEDS_SUBJECT and e["subject_id"] is None:
        raise InvalidEvent(f"{et} needs a subject_id")
    if e["case_id"] is not None and not CASE_ID.match(e["case_id"]):
        raise InvalidEvent(f"bad case_id {e['case_id']!r}: CASE-<first member incident_id>")
    if et in NEEDS_CASE and e["case_id"] is None:
        raise InvalidEvent(f"{et} needs a case_id")
    if et == "case_opened" and e["case_id"] != f"CASE-{e['subject_id']}":
        raise InvalidEvent("case ids are CASE-<first member incident_id> (§15.2)")
    obj = e["object_json"] or {}
    if et == "decision_recorded" and obj.get("decision") not in DECISIONS:
        raise InvalidEvent(f"decision must be one of {', '.join(DECISIONS)}")
    _check_supersedes(e, lookup)
    if et == "link_approved":
        p = obj.get("proposal_seq")
        ref = lookup(p) if isinstance(p, int) else None
        if ref is None or ref.event_type != "match_proposed":
            raise InvalidEvent("link_approved needs object_json.proposal_seq of a match_proposed")


def _check_supersedes(e: Mapping, lookup: Lookup) -> None:
    et, s = e["event_type"], e["supersedes_seq"]
    allowed = SUPERSEDES.get(et)
    if allowed is None:
        if s is not None:
            raise InvalidEvent(f"{et} cannot supersede anything")
        return
    if s is None:
        raise InvalidEvent(f"{et} needs supersedes_seq")
    ref = lookup(s)
    if ref is None:
        raise InvalidEvent(f"supersedes_seq {s} is not an earlier row")
    if ref.event_type not in allowed:
        raise InvalidEvent(f"{et} cannot supersede a {ref.event_type} (seq {s})")
    if ref.superseded:
        raise InvalidEvent(f"seq {s} is already superseded")


def seal(head: Head | None, e: Mapping) -> dict:
    """The stored row: next seq, ``recorded_at = max(clock, head)`` (D-010), prev_hash and hash."""
    row = {"seq": 1 if head is None else head.seq + 1, **{f: e[f] for f in EVENT_FIELDS}}
    if head is not None and row["recorded_at"] < head.recorded_at:
        row["recorded_at"] = head.recorded_at
    row["prev_hash"] = GENESIS if head is None else head.hash
    row["hash"] = row_hash(row["prev_hash"], row)
    return row


def head_of(row: Mapping) -> Head:
    return Head(int(row["seq"]), row["hash"], row["recorded_at"])


def verify_rows(rows: Iterable[Mapping]) -> int | None:
    """The first expected seq (1, 2, …) whose row is missing, does not link to its predecessor,
    does not recompute to its hash, or is recorded before its predecessor; None if intact.

    A row removed from the middle is reported at its own seq. Rows removed from the tail cannot be
    seen from the chain alone: compare with a head published elsewhere (an evidence package)."""
    expected, prev, prev_t = 1, GENESIS, None
    for r in rows:
        if (r["seq"] != expected or r["prev_hash"] != prev
                or row_hash(r["prev_hash"], r) != r["hash"]
                or (prev_t is not None and r["recorded_at"] < prev_t)):  # fmt: skip
            return expected
        expected, prev, prev_t = expected + 1, r["hash"], r["recorded_at"]
    return None


def superseded_seqs(rows: Iterable[Mapping]) -> set[int]:
    return {r["supersedes_seq"] for r in rows if r["supersedes_seq"] is not None}


def known_at(rows: Iterable[Mapping], t: datetime) -> list[dict]:
    """Rows recorded at or before ``t`` (transaction time), in seq order."""
    return [r for r in rows if r["recorded_at"] <= t]


def active_rows(rows: Iterable[Mapping], t: datetime) -> list[dict]:
    """The Python twin of the §15.1 ``ledger_asof(t)`` macro: rows known at ``t`` minus those
    superseded by rows known at ``t``."""
    known = known_at(rows, t)
    gone = superseded_seqs(known)
    return [r for r in known if r["seq"] not in gone]
