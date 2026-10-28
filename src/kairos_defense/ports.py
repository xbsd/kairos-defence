"""Ports: the only interfaces business logic may depend on (SPEC §4.1, CLAUDE.md rule 6).

Adapters in ``kairos_defense.store`` implement them for DuckDB and LanceDB now, and for KDB-X and
Kairos later (SPEC §22).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CaseSnapshot:
    """What the case memory believed about one case at ``as_of`` (filled in by phase 6, §15)."""

    case_id: str
    as_of: datetime
    events: list[dict] = field(default_factory=list)
    state: dict = field(default_factory=dict)


class TrackStore(Protocol):
    def track_points(self, track_id: str) -> pd.DataFrame: ...
    def features(self, track_id: str) -> pd.DataFrame: ...  # 1 Hz rows, §9
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
    def as_of(self, case_id: str, t: datetime) -> CaseSnapshot: ...
    def diff(self, case_id: str, t1: datetime, t2: datetime) -> list[dict]: ...
    def verify_chain(self) -> int | None: ...  # first broken seq; None if intact (D-014)


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
