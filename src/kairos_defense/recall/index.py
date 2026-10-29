"""The ``reports`` index (SPEC §12.2, §7.5) and ``report_clues`` (§7.2, §12.4).

``build_reports_index`` runs inside ``kairos-defense index`` after the track index. It reads the
history reports (live incidents' reports, if any, are appended at replay time, D-041), extracts
their clues into DuckDB ``report_clues``, embeds their text and writes the LanceDB ``reports``
table with its full-text index. Like the track index build it uses the adapters directly (D-053);
it is deterministic (reports sorted by id, no random draws).

``check_reports_index`` refuses an index that does not hold today's history reports or was
embedded with another embedder (D-084), the way ``match.candidates.check_index`` guards windows.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyarrow as pa

from kairos_defense.config import Config
from kairos_defense.features.resample import epoch_ms
from kairos_defense.ports import Embedder, TrackStore, VectorStore
from kairos_defense.recall.clues import extract_clues
from kairos_defense.recall.embed import make_embedder
from kairos_defense.store.ddl import DERIVED_COLUMNS
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import REPORTS_TABLE, LanceVectorStore

log = logging.getLogger(__name__)

STALE_TOLERANCE = 1e-6  # squared L2 between a stored report vector and the same text embedded now
HISTORY_REPORTS = (
    "SELECT r.* FROM reports r JOIN incidents i USING (incident_id) "
    "WHERE i.status = 'history' ORDER BY r.report_id"
)


class ReportIndexStale(RuntimeError):
    """The LanceDB ``reports`` table is missing, incomplete or from another embedder."""


@dataclass
class ReportsSummary:
    reports: int = 0
    live_reports_skipped: int = 0
    clue_rows: int = 0
    clues_by_type: dict[str, int] = field(default_factory=dict)
    reports_with_clues: int = 0
    embedder: str = ""
    dim: int = 0
    elapsed_s: float = 0.0


def history_reports(store: TrackStore) -> pd.DataFrame:
    """Reports of history incidents, ordered by ``report_id`` (§7.1 columns)."""
    return store.sql(HISTORY_REPORTS)


def clue_rows(reports: pd.DataFrame, road_names: list[str]) -> pd.DataFrame:
    """``report_clues`` rows: one per distinct (report, type, value), in report and text order."""
    rows = []
    for rid, text in zip(reports["report_id"], reports["text"], strict=True):
        found: dict[tuple[str, str], None] = {}
        for c in extract_clues(str(text), road_names):
            found.setdefault((c.type, c.value))
        rows += [(rid, t, v) for t, v in found]
    return pd.DataFrame(rows, columns=DERIVED_COLUMNS["report_clues"])


def reports_table(rows: pd.DataFrame, vectors: np.ndarray, dim: int) -> pa.Table:
    """Arrow table for LanceDB ``reports`` (§7.5): times as int64 epoch ms, ``vector`` float32."""
    flat = np.asarray(vectors, dtype=np.float32).reshape(-1)
    ms = [pa.array([epoch_ms(t) for t in rows.get(c, [])], pa.int64())
          for c in ("event_ts", "report_ts")]  # fmt: skip
    return pa.table(
        {
            "report_id": pa.array(rows.get("report_id", []), pa.string()),
            "incident_id": pa.array(rows.get("incident_id", []), pa.string()),
            "installation_id": pa.array(rows.get("installation_id", []), pa.string()),
            "source": pa.array(rows.get("source", []), pa.string()),
            "source_grade": pa.array(rows.get("source_grade", []), pa.string()),
            "event_ts_ms": ms[0],
            "report_ts_ms": ms[1],
            "x_m": pa.array(rows.get("x_m", []), pa.float64()),
            "y_m": pa.array(rows.get("y_m", []), pa.float64()),
            "text": pa.array(rows.get("text", []), pa.string()),
            "vector": pa.FixedSizeListArray.from_arrays(pa.array(flat, pa.float32()), dim),
        }
    )


def build_reports_index(cfg: Config) -> ReportsSummary:
    """Rebuild ``report_clues`` and LanceDB ``reports`` from the history reports."""
    t0 = time.perf_counter()
    out = ReportsSummary()
    embedder = make_embedder(cfg.app)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app, read_only=False) as store:
        reports = history_reports(store)
        out.live_reports_skipped = int(store.sql("SELECT count(*) AS n FROM reports").n[0]) - len(
            reports
        )
        roads = sorted(store.sql("SELECT DISTINCT name FROM roads")["name"].astype(str))
        clues = clue_rows(reports, roads)
        out.clue_rows = store.write_table("report_clues", clues)
    out.reports = len(reports)
    out.clues_by_type = clues["clue_type"].value_counts().sort_index().to_dict()
    out.reports_with_clues = int(clues["report_id"].nunique())
    vectors = embedder.embed(reports["text"].astype(str).tolist())
    LanceVectorStore(cfg.app.paths.lancedb).replace(
        REPORTS_TABLE, reports_table(reports, vectors, embedder.dim)
    )
    out.embedder = str(getattr(embedder, "name", type(embedder).__name__))
    out.dim = embedder.dim
    out.elapsed_s = time.perf_counter() - t0
    return out


def check_reports_index(store: TrackStore, vstore: VectorStore, embedder: Embedder) -> str:
    """Raise ``ReportIndexStale`` unless LanceDB ``reports`` holds exactly the history reports and
    the lowest ``report_id``'s stored vector equals its text embedded now (``STALE_TOLERANCE``).
    Uses only the ports (rule 6). Returns the probe report id."""
    reports = history_reports(store)
    if len(reports) == 0:
        raise ReportIndexStale("no history report to index: run `make data` then `make index`")
    probe = reports.iloc[0]
    v = embedder.embed([str(probe["text"])])[0]
    try:
        hits = vstore.search(REPORTS_TABLE, v, None, len(reports) + 1)
        own = vstore.search(REPORTS_TABLE, v, f"report_id = '{probe['report_id']}'", 1)
    except (ValueError, FileNotFoundError, OSError, RuntimeError) as exc:
        raise ReportIndexStale(f"no reports index: run `make index` ({exc})") from exc
    if len(hits) != len(reports):
        raise ReportIndexStale(f"reports index is stale: run `make index` ({len(hits)} indexed, "
                               f"{len(reports)} history reports)")  # fmt: skip
    if len(own) == 0 or float(own["_distance"].iloc[0]) > STALE_TOLERANCE:
        name = getattr(embedder, "name", type(embedder).__name__)
        raise ReportIndexStale(f"reports index is stale: run `make index` (report "
                               f"{probe['report_id']} was embedded with another embedder than "
                               f"{name})")  # fmt: skip
    return str(probe["report_id"])
