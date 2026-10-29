"""LanceDB adapters for the ``VectorStore`` and ``ReportIndex`` ports (SPEC §4.1, §7.5, §12).

All LanceDB calls live here (D-014). Searches always pre-filter (``prefilter=True``) so the filter
is applied before the nearest-neighbour cut, and return ``_distance`` (squared L2; vectors are
unit-length, so ranking equals cosine). Filters use plain columns only; times are int64 epoch
milliseconds (``*_ts_ms``), never timestamps (§7.5).

``reports`` gets a full-text index on ``text`` with token positions, so quoted phrases match
exactly (``create_index(..., config=FTS(with_position=True))``: 0.40's replacement for the
deprecated ``create_fts_index``, D-085). ``LanceReportIndex.hybrid`` uses LanceDB's native hybrid
search with ``RRFReranker`` (K = 60, ties by ``report_id``); if the installed LanceDB cannot run
it, it raises ``NotImplementedError`` and ``recall.search`` fuses the two searches itself (§12.5).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd
import pyarrow as pa
from lancedb.index import FTS, Bitmap, BTree
from lancedb.rerankers import RRFReranker

log = logging.getLogger(__name__)

KEYS = {"flight_windows": "window_id", "swarm_windows": "incident_id", "reports": "report_id"}
SCALAR_INDEXES = {  # column -> index kind, created after a full rewrite
    "flight_windows": {"window_s": Bitmap, "start_ts_ms": BTree, "incident_id": BTree},
}
FTS_COLUMNS = {"reports": "text"}  # table -> full-text indexed column (§7.5)
REPORTS_TABLE = "reports"
# §7.5 ``reports`` columns without the vector
REPORT_COLUMNS = ["report_id", "incident_id", "installation_id", "source", "source_grade",
                  "event_ts_ms", "report_ts_ms", "x_m", "y_m", "text"]  # fmt: skip


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
            if table in FTS_COLUMNS:
                tbl.create_index(FTS_COLUMNS[table], config=FTS(with_position=True))
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


class ReportRRF(RRFReranker):
    """LanceDB's ``RRFReranker`` (K = 60) with equal scores ordered by ``report_id``. LanceDB sorts
    the fused rows by score alone and then cuts to k, so a tie at the cut would follow merge order;
    this keeps the cut deterministic and equal to ``recall.search.rrf_fuse`` (D-085)."""

    def rerank_hybrid(self, query, vector_results, fts_results):
        out = super().rerank_hybrid(query, vector_results, fts_results)
        return out.sort_by([("_relevance_score", "descending"), ("report_id", "ascending")])


def _report_rows(df: pd.DataFrame, score: str) -> pd.DataFrame:
    """``REPORT_COLUMNS`` plus ``score`` (also when empty), best first as LanceDB returned them."""
    if score not in df.columns:
        df = df.assign(**{score: pd.Series(dtype="float64")})
    return df.reindex(columns=[*REPORT_COLUMNS, score]).reset_index(drop=True)


class LanceReportIndex:
    """``ReportIndex`` over the LanceDB ``reports`` table (native FTS and hybrid search)."""

    def __init__(self, uri: Path | str, table: str = REPORTS_TABLE) -> None:
        self.db = lancedb.connect(str(uri))
        self.table = table

    def _tbl(self):
        return self.db.open_table(self.table)

    def hybrid(self, text: str, vector: np.ndarray, where: str | None, k: int) -> pd.DataFrame:
        """Vector and keyword search with the same pre-filter, fused by RRF (K = 60); rows with
        ``_relevance_score``. Raises ``NotImplementedError`` when LanceDB cannot run it (§12.5)."""
        try:
            q = (self._tbl().search(query_type="hybrid")
                 .vector(np.asarray(vector, dtype=np.float32)).text(text))  # fmt: skip
            if where:
                q = q.where(where, prefilter=True)
            df = q.rerank(ReportRRF(K=60)).limit(k).to_pandas()
        except (AttributeError, TypeError, ValueError) as exc:
            raise NotImplementedError(f"LanceDB hybrid search unavailable: {exc}") from exc
        return _report_rows(df, "_relevance_score")

    def fts(self, text: str, where: str | None, k: int) -> pd.DataFrame:
        """Keyword (BM25) search over ``text``, pre-filtered; rows with ``_score``."""
        q = self._tbl().search(text, query_type="fts")
        if where:
            q = q.where(where, prefilter=True)
        return _report_rows(q.limit(k).to_pandas(), "_score")
