"""SPEC §12.2, §7.5: the LanceDB ``reports`` table, its full-text index, filters, ``report_clues``
and the stale-index guard."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.resample import epoch_ms
from kairos_defense.recall.clues import extract_clues
from kairos_defense.recall.embed import HashingEmbedder
from kairos_defense.recall.index import (
    ReportIndexStale,
    check_reports_index,
    history_reports,
    reports_table,
)
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import REPORT_COLUMNS, LanceReportIndex, LanceVectorStore

T0 = pd.Timestamp("2026-04-20 02:00:00")
TEXTS = [
    ("A", 0, "A white pickup was parked on County Rd 12 from 21:20 to 22:05."),
    ("A", 1, "A WHITE PICKUP WAS PARKED ON COUNTY RD 12 FROM 21:20 TO 22:05."),
    ("A", 2, "A black SUV was seen on County Road 12 near the gate."),
    ("A", 3, "Drone departed over Rd 12 County at night."),
    ("B", 0, "A white pickup was parked on County Rd 12 near Installation B."),
    ("A", 30, "Six hours later a white pickup was seen on County Rd 12 again."),
]


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    """A six-row ``reports`` table: two bases, three times, one exact phrase in four rows."""
    rows = pd.DataFrame([{"report_id": f"R{i}", "incident_id": f"INC-{base}",
                          "installation_id": base, "source": "security_forces",
                          "source_grade": "B2", "event_ts": T0 + pd.Timedelta(hours=h / 5),
                          "report_ts": T0 + pd.Timedelta(hours=h / 5 + 1), "x_m": 100.0 * i,
                          "y_m": -50.0 * i, "text": text}
                         for i, (base, h, text) in enumerate(TEXTS)])  # fmt: skip
    emb = HashingEmbedder(384)
    uri = tmp_path_factory.mktemp("reports") / "lancedb"
    lance = LanceVectorStore(uri)
    lance.replace("reports", reports_table(rows, emb.embed(rows.text.tolist()), 384))
    return rows, emb, lance, LanceReportIndex(uri)


def test_reports_table_holds_history_reports_only(p1_index) -> None:
    cfg = p1_index.cfg
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    tbl = lance.db.open_table("reports")
    schema = {f.name: str(f.type) for f in tbl.schema}
    assert list(schema) == [*REPORT_COLUMNS, "vector"]
    assert schema["event_ts_ms"] == schema["report_ts_ms"] == "int64"
    assert schema["x_m"] == "double" and schema["vector"] == "fixed_size_list<item: float>[384]"
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as duck:
        hist = history_reports(duck)
        live = duck.sql("SELECT incident_id FROM incidents WHERE status = 'live'").incident_id
    got = lance.to_pandas("reports").sort_values("report_id").reset_index(drop=True)
    assert len(got) == len(hist) == p1_index.reports.reports > 0
    assert got.report_id.tolist() == hist.report_id.tolist()
    assert not set(got.incident_id) & set(live)
    assert got.event_ts_ms.tolist() == [epoch_ms(t) for t in hist.event_ts]
    assert got.report_ts_ms.tolist() == [epoch_ms(t) for t in hist.report_ts]
    assert p1_index.reports.embedder == "hashing-v1-384"


def test_fts_finds_an_exact_phrase(small) -> None:
    _, _, _, index = small
    hits = index.fts(
        '"County Rd 12"', "installation_id = 'A' AND event_ts_ms < 9000000000000000", 10
    )
    assert sorted(hits.report_id) == ["R0", "R1", "R5"]  # the blotter capitals match too
    assert {"R2", "R3"}.isdisjoint(hits.report_id)  # "County Road 12", "Rd 12 County"
    assert list(hits.columns) == [*REPORT_COLUMNS, "_score"]
    empty = index.fts('"County Rd 12"', "installation_id = 'Z'", 10)
    assert len(empty) == 0 and list(empty.columns) == [*REPORT_COLUMNS, "_score"]


def test_filters_exclude_other_bases_and_times(small) -> None:
    _, emb, lance, index = small
    t0, t1 = epoch_ms(T0) - 1, epoch_ms(T0 + pd.Timedelta(hours=1))
    flt = f"installation_id = 'A' AND event_ts_ms BETWEEN {t0} AND {t1}"
    v = emb.embed(["white pickup County Rd 12"])[0]
    for got in (index.hybrid("white pickup county rd 12", v, flt, 10),
                index.fts("white pickup", flt, 10),
                lance.search("reports", v, flt, 10)):  # fmt: skip
        assert set(got.report_id) <= {"R0", "R1", "R2", "R3"} and len(got)
        assert "R4" not in set(got.report_id) and "R5" not in set(got.report_id)
    hyb = index.hybrid("white pickup county rd 12", v, flt, 10)
    assert list(hyb.columns) == [*REPORT_COLUMNS, "_relevance_score"]


def test_report_clues_are_written(p1_index) -> None:
    cfg = p1_index.cfg
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as duck:
        clues = duck.sql("SELECT * FROM report_clues ORDER BY report_id, clue_type, clue_value")
        reports = history_reports(duck)
        roads = duck.sql("SELECT name FROM roads").name.tolist()
    want = sorted({(r, c.type, c.value) for r, t in zip(reports.report_id, reports.text,
                                                        strict=True)
                   for c in extract_clues(t, roads)})  # fmt: skip
    assert sorted(map(tuple, clues.to_numpy().tolist())) == want
    delta = set(map(tuple, clues[clues.report_id == "R-P1-DELTA-260419-1"]
                    [["clue_type", "clue_value"]].to_numpy().tolist()))  # fmt: skip
    assert delta == {("vehicle", "white pickup"), ("road", "County Rd 12")}
    assert p1_index.reports.clue_rows == len(clues)


class OtherEmbedder(HashingEmbedder):
    """Same dimension, different vectors (another provider)."""

    def embed(self, texts):
        return np.roll(super().embed(texts), 1, axis=1)


def test_stale_reports_index_is_refused(p1_index, tmp_path) -> None:
    cfg = p1_index.cfg
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as duck:
        probe = check_reports_index(duck, lance, HashingEmbedder(384))
        assert probe == history_reports(duck).report_id.iloc[0]
        with pytest.raises(ReportIndexStale, match="another embedder"):
            check_reports_index(duck, lance, OtherEmbedder(384))
        # a count mismatch: an index missing its last report
        rows = history_reports(duck).iloc[:-1]
        short = LanceVectorStore(tmp_path / "short")
        emb = HashingEmbedder(384)
        short.replace("reports", reports_table(rows, emb.embed(rows.text.tolist()), 384))
        with pytest.raises(ReportIndexStale, match="make index"):
            check_reports_index(duck, short, emb)
        with pytest.raises(ReportIndexStale, match="make index"):
            check_reports_index(duck, LanceVectorStore(tmp_path / "none"), emb)


def test_reports_rebuild_is_deterministic(p1_index) -> None:
    from kairos_defense.recall.index import build_reports_index

    cfg = p1_index.cfg
    lance = LanceVectorStore(cfg.app.paths.lancedb)

    def snapshot():
        with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as duck:
            clues = duck.sql("SELECT * FROM report_clues")
        rep = lance.to_pandas("reports")
        return clues, rep.drop(columns="vector"), np.stack(rep.vector.to_numpy())

    before = snapshot()
    again = build_reports_index(cfg)
    after = snapshot()
    assert before[0].equals(after[0]) and before[1].equals(after[1])
    assert before[2].tobytes() == after[2].tobytes()
    assert again.reports == p1_index.reports.reports
