"""Ports: the only interfaces business logic may depend on (SPEC §4.1, CLAUDE.md rule 6).

Adapters in ``kairos_defense.store`` implement them for DuckDB and LanceDB now, and for KDB-X and
Kairos later (SPEC §22).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Protocol

import numpy as np
import pandas as pd


def _jsonable(v: object) -> object:
    """JSON-safe copy: times as ISO 8601 UTC with ``Z``, NaN and infinities as None."""
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            v = v.astimezone(UTC).replace(tzinfo=None)
        return v.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


@dataclass(frozen=True)
class CaseSnapshot:
    """What the case memory knew about one case at ``as_of`` (transaction time, SPEC §15.4).

    ``members`` are incident ids: the founder, then incidents of approved links. Lists hold plain
    dicts (summaries of ledger rows, each with its ``seq``); ``events`` are the full rows touching
    the case, hashes included. Times are naive UTC; ``to_dict`` is JSON-safe (ISO ``Z``).
    """

    case_id: str
    as_of: datetime
    exists: bool = False
    status: str = "unknown"  # unknown (not opened by as_of) | open | closed
    founder: str | None = None
    members: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)  # active link_approved
    pending: list[dict] = field(default_factory=list)  # undecided proposals, not yet members
    claims: list[dict] = field(default_factory=list)  # active assessments about members
    contradictions: list[dict] = field(default_factory=list)  # never auto-resolved
    decisions: list[dict] = field(default_factory=list)
    exports: list[dict] = field(default_factory=list)
    reports: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    head_seq: int | None = None  # chain head at as_of
    head_hash: str | None = None

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


class TrackStore(Protocol):
    def track_points(self, track_id: str) -> pd.DataFrame: ...
    def features(self, track_id: str) -> pd.DataFrame: ...  # 1 Hz rows, §9
    def features_many(self, track_ids: Sequence[str]) -> pd.DataFrame: ...  # by track, t_s (D-072)
    # RF family, Remote ID serials and operator from what was heard up to ``until`` (D-071, D-072)
    def sensor_context_until(self, track_id: str, until: datetime) -> dict: ...
    def signature(self, track_id: str) -> dict: ...  # §9.4
    def tracks_before(self, ts: datetime, exclude_incident: str | None = None) -> pd.DataFrame: ...
    def context_asof(self, track_id: str) -> pd.DataFrame: ...  # weather and events per point, §11
    def sql(self, query: str, params: dict | None = None) -> pd.DataFrame: ...


class VectorStore(Protocol):
    def upsert(self, table: str, rows: Sequence[dict]) -> None: ...
    def search(self, table: str, vector: np.ndarray, where: str | None, k: int) -> pd.DataFrame: ...


class ReportIndex(Protocol):
    def hybrid(self, text: str, vector: np.ndarray, where: str | None, k: int) -> pd.DataFrame: ...
    def fts(self, text: str, where: str | None, k: int) -> pd.DataFrame: ...


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...  # (n, dim) float32, L2-normalized


class CaseMemory(Protocol):
    def append(self, event: dict) -> int: ...  # returns ledger seq
    def append_many(self, events: Sequence[dict]) -> list[int]: ...  # one transaction (D-093)
    # rows with after < recorded_at <= until, seq order, object_json parsed (D-093)
    def events(
        self, after: datetime | None = None, until: datetime | None = None
    ) -> list[dict]: ...
    def as_of(self, case_id: str, t: datetime) -> CaseSnapshot: ...
    def diff(self, case_id: str, t1: datetime, t2: datetime) -> list[dict]: ...
    def verify_chain(self) -> int | None: ...  # first broken seq; None if intact (D-014)


@dataclass(frozen=True)
class IngestStat:
    """One real write batch into a ``live_*`` scratch table (SPEC §16.2): the §16.3 ``ingest``
    message's fields. ``write_ms`` is the measured insert time."""

    table: str
    rows: int
    total_rows: int
    write_ms: float
    statement: str  # e.g. "INSERT INTO live_points … 3 rows"

    def to_dict(self) -> dict:
        return asdict(self)


class LiveSink(Protocol):
    """Where a replay records the detections it makes visible (``live_points``, ``live_rf``,
    ``live_rid``; D-103, D-104)."""

    def append(self, table: str, rows: Sequence[dict]) -> IngestStat: ...  # one batch
    def count(self, table: str) -> int: ...
    def reset(self) -> dict[str, int]: ...  # empties every live_* table; rows removed per table


class ResultCache(Protocol):
    """Precomputed live-loop results per incident (D-013, D-105): JSON documents by name
    (``manifest``, ``features``, ``t0045`` …)."""

    def get(self, incident_id: str, name: str) -> dict | None: ...
    def put(self, incident_id: str, name: str, doc: dict) -> None: ...
    def clear(self, incident_id: str) -> int: ...  # documents removed


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...


class LiveFeed(Protocol):
    """Live mode's own store (D-172): ingested detections, the app's live incidents and tracks,
    learned live history and the matches each rerun showed. Separate from the history so
    ``live reset`` removes all of it; the ledger is never part of it (rule 7)."""

    def append(self, table: str, rows: Sequence[dict]) -> IngestStat: ...  # live_points, …
    def put_incident(self, row: dict) -> None: ...  # insert or replace one live incident
    def put_track(self, row: dict) -> None: ...  # app track id <-> the sensor's track id
    # learned tracks' track_features and track_signatures rows (closed incidents only, D-176)
    def learn(self, features: pd.DataFrame, signatures: pd.DataFrame) -> int: ...
    def add_result(self, row: dict) -> None: ...  # one rerun's shown matches
    def results(self, incident_id: str) -> list[dict]: ...
    def reset(self) -> dict[str, int]: ...  # rows removed per table
