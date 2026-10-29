"""Shared helpers of the agent tools: JSON safety, argument and time checks, the query loader and
the ledger reads. Every check raises ``ToolError`` with a message a person can act on."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import numpy as np

from kairos_defense.agent.context import ToolContext, ToolError
from kairos_defense.memory.ledger import CASE_ID, ID

DEFAULT_WINDOW_S = 120  # the replay second the tools look at by default (§1.2's T+120)
MAX_RATIONALE = 2000
INSTALLATION = re.compile(r"^[A-Z][A-Z0-9-]{0,31}$")


# --- JSON and arguments ---------------------------------------------------------------------------
def to_json(v: object) -> object:
    """A JSON-safe copy: numpy scalars as Python numbers, NaN and infinities as None, times as ISO
    8601 UTC with ``Z``, tuples and arrays as lists."""
    from kairos_defense.memory.canonical import utc_naive

    if isinstance(v, Mapping):
        return {str(k): to_json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [to_json(x) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, datetime):
        return utc_naive(v).strftime("%Y-%m-%dT%H:%M:%SZ")
    if v is None or isinstance(v, str):
        return v
    return str(v)


def iso_ms(ms: int | float | None) -> str | None:
    """Epoch milliseconds (LanceDB ``*_ts_ms``) as ISO 8601 UTC with ``Z``."""
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: object, name: str) -> datetime:
    """Naive UTC from an ISO 8601 string with ``Z`` or an offset; ``ToolError`` otherwise."""
    from kairos_defense.memory.canonical import utc_naive

    t = None
    if isinstance(value, str):
        try:
            t = datetime.fromisoformat(value.replace("z", "Z"))
        except ValueError:
            t = None
    if t is None or t.tzinfo is None:
        raise ToolError(f"bad time {name}={value!r}: give an ISO 8601 time with Z or an offset, "
                        "e.g. 2026-04-20T15:00Z or 2026-04-20T10:00-05:00")  # fmt: skip
    return utc_naive(t)


def int_arg(v: object, name: str, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise ToolError(f"{name} must be a number from {lo} to {hi}, not {v!r}")
    return int(v)


def id_arg(v: object, name: str) -> str:
    if not isinstance(v, str) or not ID.match(v):
        raise ToolError(f"bad {name} {v!r}: incident ids are uppercase letters, digits and dashes")
    return v


def case_id_arg(v: object) -> str:
    if not isinstance(v, str) or not CASE_ID.match(v):
        raise ToolError(f"bad case_id {v!r}: case ids are CASE-<first member incident_id>")
    return v


# --- flights --------------------------------------------------------------------------------------
def incident_row(ctx: ToolContext, incident_id: str) -> dict:
    df = ctx.store.sql("SELECT * FROM incidents WHERE incident_id = $i", {"i": incident_id})
    if len(df) != 1:
        raise ToolError(f"unknown incident {incident_id!r}")
    return df.iloc[0].to_dict()


def tracks_of(ctx: ToolContext, incident_id: str) -> list[str]:
    return [str(t) for t in ctx.store.sql(
        "SELECT DISTINCT track_id FROM track_points WHERE incident_id = $i ORDER BY track_id",
        {"i": incident_id})["track_id"]]  # fmt: skip


def track_of(ctx: ToolContext, incident_id: str, track_id: str | None) -> str:
    """The incident's track: ``track_id`` when given, else its only track (a swarm has several)."""
    tracks = tracks_of(ctx, incident_id)
    if track_id is not None:
        if track_id not in tracks:
            raise ToolError(f"{track_id!r} is not a track of {incident_id}")
        return track_id
    if len(tracks) != 1:
        raise ToolError(f"{incident_id} has {len(tracks)} tracks (a swarm?): name one with "
                        "track_id, or use the Swarm view for swarm matching")  # fmt: skip
    return tracks[0]


def tool_query(ctx: ToolContext, incident_id: str, at_s: object, track_id: str | None = None):
    """The incident's track as seen ``at_s`` seconds after its first radar point (rule 3: points
    up to then only), with ``live.min_track_s`` as the smallest ``at_s``."""
    from kairos_defense.match.query import load_query

    inc = id_arg(incident_id, "incident_id")
    incident_row(ctx, inc)
    lo = int(ctx.cfg.scoring.live.min_track_s)
    at = int_arg(at_s, "the seconds after first contact", lo, 3600)
    return load_query(ctx.store, track_of(ctx, inc, track_id), at, ctx.cfg.scoring)


def match_dict(m, rank: int) -> dict:
    d = m.to_dict()
    return to_json({"rank": rank, "incident_id": m.incident_id, "track_id": m.track_id,
                    "installation_id": m.installation_id, "start_ts": m.start_ts,
                    "score": d["score"], "shape_sim": d["shape_sim"],
                    "warp_ratio": d["warp_ratio"], "reasons": list(m.reasons),
                    "window_offset_s": m.window_offset_s})  # fmt: skip


def query_info(q) -> dict:
    return to_json({"incident_id": q.incident_id, "track_id": q.track_id,
                    "query_start": q.start_ts, "at_s": int(q.at_s),
                    "search_window_s": int(q.window_s)})  # fmt: skip


# --- ledger ---------------------------------------------------------------------------------------
def ledger_rows(ctx: ToolContext) -> list[dict]:
    """Every ledger row (seq order); ``LedgerBusy`` while another process holds the file."""
    with ctx.ledger() as mem:
        return mem.events()


def need_case(rows: list[dict], case_id: str) -> None:
    if not any(r["event_type"] == "case_opened" and r["case_id"] == case_id for r in rows):
        raise ToolError(f"no case {case_id}")


def head_time(rows: list[dict]) -> datetime:
    if not rows:
        raise ToolError("the ledger is empty: run `kairos-defense memory seed`")
    return rows[-1]["recorded_at"]
