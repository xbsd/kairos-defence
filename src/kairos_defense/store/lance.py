"""LanceDB adapter for the ``VectorStore`` port (SPEC §4.1, §7.5).

All LanceDB calls live here (D-014). Searches always pre-filter (``prefilter=True``) so the filter
is applied before the nearest-neighbour cut, and return ``_distance`` (squared L2; vectors are
unit-length, so ranking equals cosine). Filters use plain columns only; times are int64 epoch
milliseconds (``*_ts_ms``), never timestamps (§7.5).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd
import pyarrow as pa
from lancedb.index import Bitmap, BTree

log = logging.getLogger(__name__)

KEYS = {"flight_windows": "window_id", "swarm_windows": "incident_id", "reports": "report_id"}
SCALAR_INDEXES = {  # column -> index kind, created after a full rewrite
    "flight_windows": {"window_s": Bitmap, "start_ts_ms": BTree, "incident_id": BTree},
}


class LanceVectorStore:
    """``VectorStore`` over a LanceDB directory (``data/lancedb``)."""

    def __init__(self, uri: Path | str) -> None:
        self.uri = Path(uri)
        self.uri.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.uri))

    def tables(self) -> list[str]:
        return list(self.db.list_tables().tables)

    def has(self, table: str) -> bool:
        return table in self.tables()

    def replace(self, table: str, data: pa.Table | pd.DataFrame) -> int:
        """Drop ``table`` and write ``data`` as its full contents (index build); returns rows.
        Creates the scalar indexes listed in ``SCALAR_INDEXES`` for faster filters."""
        self.db.drop_table(table, ignore_missing=True)
        tbl = self.db.create_table(table, data)
        if tbl.count_rows() > 0:
            for col, kind in SCALAR_INDEXES.get(table, {}).items():
                tbl.create_index(col, config=kind())
        log.info("wrote LanceDB %s (%d rows)", table, tbl.count_rows())
        return tbl.count_rows()

    def upsert(self, table: str, rows: Sequence[dict]) -> None:
        """Insert or update ``rows`` by the table's key column (``KEYS``); creates the table."""
        if not rows:
            return
        data = pa.Table.from_pylist(list(rows))
        if not self.has(table):
            self.db.create_table(table, data)
            return
        key = KEYS.get(table)
        if key is None:
            raise ValueError(f"no key column known for LanceDB table {table!r}")
        tbl = self.db.open_table(table)
        tbl.merge_insert(key).when_matched_update_all().when_not_matched_insert_all().execute(data)

    def search(self, table: str, vector: np.ndarray, where: str | None, k: int) -> pd.DataFrame:
        """``k`` nearest rows to ``vector`` among rows matching ``where`` (pre-filtered), nearest
        first, with ``_distance``; the vector column is dropped."""
        q = self.db.open_table(table).search(np.asarray(vector, dtype=np.float32))
        if where:
            q = q.where(where, prefilter=True)
        df = q.limit(k).to_pandas()
        return df.drop(columns=["vector"], errors="ignore").reset_index(drop=True)

    def count(self, table: str, where: str | None = None) -> int:
        return int(self.db.open_table(table).count_rows(where))

    def to_pandas(self, table: str, columns: Sequence[str] | None = None) -> pd.DataFrame:
        """Whole table (tests and summaries)."""
        df = self.db.open_table(table).to_pandas()
        return df if columns is None else df[list(columns)]
