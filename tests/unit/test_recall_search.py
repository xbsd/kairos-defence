"""SPEC §12.3, §12.5: the per-match query (text, filter), hybrid search, the RRF fallback and the
planted DELTA report at rank 1 for the DELTA match."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.resample import epoch_ms
from kairos_defense.recall.embed import HashingEmbedder
from kairos_defense.recall.index import reports_table
from kairos_defense.recall.search import (
    TARGET_WORDS,
    ReportRecall,
    fts_text,
    hybrid_search,
    query_text,
    recall_filter,
    rrf_fuse,
    signature_words,
)
from kairos_defense.sim.facts import ASSET_NAMES
from kairos_defense.store.guard import connect_app_db
from kairos_defense.store.lance import REPORT_COLUMNS, LanceReportIndex, LanceVectorStore

START = pd.Timestamp("2026-08-29 02:40:06")


def _q(at_s: int = 120, incident: str = "DEMO-BRAVO-0828"):
    """The fields of a ``Query`` that the text and filter read."""
    return SimpleNamespace(start_ms=epoch_ms(START), at_s=at_s, incident_id=incident,
                           until=(START + pd.Timedelta(seconds=at_s)).to_pydatetime())  # fmt: skip


MSIG = {"installation_id": "DELTA", "start_ts": pd.Timestamp("2026-04-20 02:35:00"),
        "end_ts": pd.Timestamp("2026-04-20 02:46:00"), "launch_x_rel_m": -1500.0,
        "launch_y_rel_m": 1200.0}  # fmt: skip


def test_recall_filter_known_answer(cfg) -> None:
    flt = recall_filter(_q(), MSIG, np.array([9000.0, -24000.0]), cfg.scoring)
    s = epoch_ms(MSIG["start_ts"]) - 3 * 3_600_000
    e = epoch_ms(MSIG["end_ts"]) + 3 * 3_600_000
    assert flt == (
        f"installation_id = 'DELTA' AND event_ts_ms BETWEEN {s} AND {e} "
        "AND x_m BETWEEN 2500.000 AND 14000.000 AND y_m BETWEEN -29000.000 AND -17800.000 "
        f"AND event_ts_ms < {epoch_ms(START)} AND report_ts_ms <= {epoch_ms(START) + 120_000}"
    )
    no_launch = recall_filter(_q(), {**MSIG, "launch_x_rel_m": None}, np.array([0.0, 0.0]),
                              cfg.scoring)  # fmt: skip
    assert "x_m BETWEEN -5000.000 AND 5000.000 AND y_m BETWEEN -5000.000 AND 5000.000" in no_launch
    with pytest.raises(ValueError, match="unsafe"):
        recall_filter(_q(), {**MSIG, "installation_id": "X' OR '1'='1"}, np.zeros(2), cfg.scoring)


def test_query_text_from_signature() -> None:
    sig = {"loiter_radius_m": 187.0, "target_kind": "fuel_farm", "approach_bearing_deg": 316.0}
    assert signature_words(sig) == "drone orbit fuel farm vehicle road launch northwest"
    unknown = {"loiter_radius_m": float("nan"), "target_kind": "fence",
               "approach_bearing_deg": None}  # fmt: skip
    assert signature_words(unknown) == "drone fence vehicle road launch"
    assert signature_words({}) == "drone vehicle road launch"


class SqlStore:
    """A ``TrackStore`` stand-in whose ``sql`` runs on an in-memory DuckDB ``reports`` table."""

    def __init__(self, cfg, rows: list[dict]) -> None:
        self.con = connect_app_db(":memory:", cfg.app)
        self.con.execute("CREATE TABLE reports (report_id VARCHAR, incident_id VARCHAR, "
                         "report_ts TIMESTAMP, text VARCHAR)")  # fmt: skip
        for r in rows:
            self.con.execute("INSERT INTO reports VALUES ($report_id, $incident_id, $report_ts, "
                             "$text)", r)  # fmt: skip

    def sql(self, query, params=None):
        return self.con.execute(query, params or {}).df()


def test_query_text_prefers_tonights_filed_report(cfg) -> None:
    sig = {"target_kind": "fuel_farm"}
    rows = [
        {"report_id": "R1", "incident_id": "DEMO-BRAVO-0828", "text": "first report",
         "report_ts": START + pd.Timedelta(seconds=30)},
        {"report_id": "R2", "incident_id": "DEMO-BRAVO-0828", "text": "second report",
         "report_ts": START + pd.Timedelta(seconds=100)},
        {"report_id": "R3", "incident_id": "DEMO-BRAVO-0828", "text": "not filed yet",
         "report_ts": START + pd.Timedelta(seconds=500)},
        {"report_id": "R4", "incident_id": "OTHER", "text": "another incident",
         "report_ts": START + pd.Timedelta(seconds=110)},
    ]  # fmt: skip
    store = SqlStore(cfg, rows)
    assert query_text(store, _q(120), sig) == "second report"
    assert query_text(store, _q(60), sig) == "first report"
    assert query_text(store, _q(20), sig) == "drone fuel farm vehicle road launch"


def test_target_words_agree_with_report_vocabulary() -> None:
    assert TARGET_WORDS == {**ASSET_NAMES, "fence": "fence"}


def test_fts_text_is_sanitized() -> None:
    assert (
        fts_text('21:35 BDOC: "UAS" near (fuel) farm; AND OR*')
        == "21 35 bdoc uas near fuel farm and or"
    )
    assert fts_text(":::") == ""


def _frame(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{c: (rid if c == "report_id" else 0) for c in REPORT_COLUMNS}
                         for rid in ids], columns=REPORT_COLUMNS)  # fmt: skip


def test_rrf_fuse_known_answer() -> None:
    out = rrf_fuse(_frame(["a", "b", "c"]), _frame(["b", "d"]), k=5)
    assert out.report_id.tolist() == ["b", "a", "d", "c"]
    assert np.allclose(out._relevance_score, [1 / 61 + 1 / 62, 1 / 61, 1 / 62, 1 / 63], atol=0)
    assert rrf_fuse(_frame(["a", "b", "c"]), _frame(["b", "d"]), k=2).report_id.tolist() == [
        "b", "a"]  # fmt: skip
    tie = rrf_fuse(_frame(["y"]), _frame(["x"]), k=5)  # both 1/61: ties sort by report_id
    assert tie.report_id.tolist() == ["x", "y"]
    empty = rrf_fuse(_frame([]), _frame([]), k=5)
    assert len(empty) == 0 and list(empty.columns) == [*REPORT_COLUMNS, "_relevance_score"]


@pytest.fixture(scope="module")
def forty(tmp_path_factory):
    """40 reports with random word salad over the recall vocabulary, two bases."""
    rng = np.random.default_rng(1)
    words = ["drone", "fuel", "farm", "white", "pickup", "county", "rd", "orbit", "fence", "night"]
    n = 40
    rows = pd.DataFrame({
        "report_id": [f"R{i:02d}" for i in range(n)], "incident_id": "INC",
        "installation_id": ["A" if i % 2 == 0 else "B" for i in range(n)],
        "source": "local_pd", "source_grade": "C4",
        "event_ts": [START - pd.Timedelta(days=1, minutes=i) for i in range(n)],
        "report_ts": [START - pd.Timedelta(hours=20, minutes=i) for i in range(n)],
        "x_m": 0.0, "y_m": 0.0, "text": [" ".join(rng.choice(words, size=6)) for _ in range(n)],
    })  # fmt: skip
    emb = HashingEmbedder(384)
    uri = tmp_path_factory.mktemp("forty") / "lancedb"
    lance = LanceVectorStore(uri)
    lance.replace("reports", reports_table(rows, emb.embed(rows.text.tolist()), 384))
    return emb, lance, LanceReportIndex(uri)


class NoHybrid:
    """A ``ReportIndex`` whose backend has no hybrid search (§12.5)."""

    def __init__(self, inner: LanceReportIndex) -> None:
        self.inner = inner

    def hybrid(self, text, vector, where, k):
        raise NotImplementedError("no hybrid here")

    def fts(self, text, where, k):
        return self.inner.fts(text, where, k)


def test_fallback_equals_native_hybrid(forty) -> None:
    emb, lance, index = forty
    texts = ("white pickup county rd", "drone fuel farm", "night orbit", "fence", "rd pickup")
    for text in texts:
        v = emb.embed([text])[0]
        native = hybrid_search(index, lance, text, v, "installation_id = 'A'", 5)
        fused = hybrid_search(NoHybrid(index), lance, text, v, "installation_id = 'A'", 5)
        assert native.report_id.tolist() == fused.report_id.tolist(), text
        assert np.array_equal(native._relevance_score.to_numpy(np.float64),
                              fused._relevance_score.to_numpy(np.float64))  # fmt: skip
        assert list(native.columns) == list(fused.columns) == [*REPORT_COLUMNS,
                                                               "_relevance_score"]  # fmt: skip
        assert set(native.installation_id) == {"A"}


def test_hybrid_unsupported_falls_back(forty) -> None:
    emb, lance, index = forty
    v = emb.embed(["white pickup"])[0]
    got = hybrid_search(NoHybrid(index), lance, "white pickup", v, None, 5)
    vec = lance.search("reports", v, None, 5)
    fts = index.fts("white pickup", None, 5)
    want = rrf_fuse(vec, fts, 5)
    assert got.report_id.tolist() == want.report_id.tolist() and len(got) == 5
    # no keyword left after sanitizing: the vector list alone, RRF-scored
    only = hybrid_search(index, lance, "!!!", v, None, 3)
    assert only.report_id.tolist() == vec.report_id.tolist()[:3]
    assert np.allclose(only._relevance_score, [1 / 61, 1 / 62, 1 / 63])


def test_delta_report_is_rank1_for_the_delta_match(toy_models) -> None:
    """§20 test: the planted DELTA report is rank 1 for the DELTA match using tonight's default
    query (live query at T+120), with its two clues marked by span."""
    from kairos_defense.forecast.analog import forecast
    from kairos_defense.match.matcher import DtwMatcher, MatchResult
    from kairos_defense.match.query import load_query
    from kairos_defense.store.duck import DuckTrackStore

    cfg = toy_models
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as duck:
        q = load_query(duck, "DEMO-BRAVO-0828-T1", 120, cfg.scoring)
        res = DtwMatcher(duck, lance, cfg.scoring, cfg.app.paths.models).match(q)
        delta = next(m for m in res.matches if m.incident_id == "P1-DELTA-260419")
        only = MatchResult([delta], [], {}, res.signature, res.signatures)
        fc = forecast(duck, q, res, cfg.scoring)
        rr = ReportRecall(duck, LanceReportIndex(cfg.app.paths.lancedb), lance,
                          HashingEmbedder(384), cfg.scoring)  # fmt: skip
        out = rr.for_matches(q, only, fc.roads if fc else (), n=1)
    assert out.query_text.startswith("drone")  # no report filed tonight: built from the signature
    (mr,) = out.matches
    top = mr.reports[0]
    assert top.rank == 1 and top.report_id == "R-P1-DELTA-260419-1"
    assert top.event_ts_ms < q.start_ms and top.report_ts_ms <= q.start_ms + 120_000
    spans = {c.value: top.text[c.start : c.end] for c in top.clues}
    assert spans == {"white pickup": "white pickup", "County Rd 12": "County Rd 12"}
    d = out.to_dict()
    assert d["matches"][0]["reports"][0]["clues"][1]["value"] == "County Rd 12"
