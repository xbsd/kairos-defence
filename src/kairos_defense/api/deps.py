"""Shared helpers for the routes: the services, time parsing and lookups (D-108)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Request

from kairos_defense.api.services import Services
from kairos_defense.live.replay import iso_z
from kairos_defense.memory.canonical import utc_naive


def services(request: Request) -> Services:
    return request.app.state.services


def parse_time(value: str | None, name: str, default: datetime | None = None) -> datetime:
    """Naive UTC from an ISO 8601 time with ``Z`` or an offset; 422 otherwise (a naive time is
    ambiguous across three regions, as in the CLI)."""
    if value is None:
        if default is None:
            raise HTTPException(422, f"{name} is required")
        return default
    try:
        t = datetime.fromisoformat(value.replace("z", "Z"))
    except ValueError:
        t = None
    if t is None or t.tzinfo is None:
        raise HTTPException(422, f"bad time {name}={value!r}: give an ISO 8601 time with Z or an "
                                 "offset, e.g. 2026-04-20T15:00Z")  # fmt: skip
    return utc_naive(t)


def block(r: dict) -> dict:
    """A ledger row as a chain block (``LedgerBlock``)."""
    return {"seq": int(r["seq"]), "event_type": r["event_type"], "actor": r["actor"],
            "recorded_at": iso_z(r["recorded_at"]), "hash": r["hash"],
            "prev_hash": r["prev_hash"], "case_id": r["case_id"],
            "subject_id": r["subject_id"]}  # fmt: skip


def record(r: dict) -> dict:
    """A full ledger row (``LedgerRecord``)."""
    out = block(r)
    for k in ("predicate", "object_json", "source_type", "source_id", "source_grade",
              "confidence", "supersedes_seq"):  # fmt: skip
        out[k] = r[k]
    for k in ("valid_from", "valid_to"):
        out[k] = iso_z(r[k]) if r[k] is not None else None
    return out
