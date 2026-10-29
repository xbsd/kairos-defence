"""Report recall per match (SPEC §12.3, §12.5, D-082, D-085).

For tonight's query ``q`` and a matched past track ``m``:

- text: tonight's most recent report filed by ``q.until``, else words built from tonight's
  partial signature ("drone orbit fuel farm vehicle road launch northwest");
- vector: the embedder's vector of that text;
- filter: ``m``'s base, ``m.start − 3 h`` to ``m.end + 3 h``, a 5 km box around ``m``'s loiter
  and launch points, and no look-ahead: the event started before tonight's first contact and the
  report was filed by the replay time (rule 3);
- search: hybrid (vector + keyword) fused by reciprocal rank, k = 5. When the backend has no
  native hybrid search the two searches run apart and ``rrf_fuse`` fuses them with the same
  formula, Σ 1/(60 + rank) (§12.5). Ties sort by ``report_id``.

Only the ports are used (rule 6). Truth is never read.
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Collection
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SiteGeometry, load_site
from kairos_defense.features.resample import epoch_ms
from kairos_defense.match.live_signature import query_signature
from kairos_defense.match.query import Query
from kairos_defense.ports import Embedder, ReportIndex, TrackStore, VectorStore
from kairos_defense.recall.clues import Clue, LinkedClue, extract_clues, link_clues
from kairos_defense.recall.embed import TOKEN_RE
from kairos_defense.sim.lexicon import compass8
from kairos_defense.store.lance import REPORT_COLUMNS, REPORTS_TABLE

RRF_K = 60
SCORE = "_relevance_score"
HOUR_MS = 3_600_000
# report wording of each target kind (sim.facts.ASSET_NAMES plus the fence pseudo-asset)
TARGET_WORDS = {"fuel_farm": "fuel farm", "flight_line": "flight line",
                "munitions": "munitions area", "hq": "headquarters", "housing": "housing area",
                "fence": "fence"}  # fmt: skip
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _known(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def signature_words(qsig: dict) -> str:
    """§12.3's query built from a (partial) signature; unknown fields drop their words."""
    words = ["drone"]
    if _known(qsig.get("loiter_radius_m")):
        words.append("orbit")
    if qsig.get("target_kind") in TARGET_WORDS:
        words.append(TARGET_WORDS[qsig["target_kind"]])
    words.append("vehicle road launch")
    if _known(qsig.get("approach_bearing_deg")):
        words.append(compass8(float(qsig["approach_bearing_deg"])))
    return " ".join(words)


def query_text(store: TrackStore, q: Query, qsig: dict) -> str:
    """Tonight's most recent report filed by ``q.until``, else ``signature_words``."""
    r = store.sql(
        "SELECT text FROM reports WHERE incident_id = $i AND report_ts <= $u "
        "ORDER BY report_ts DESC, report_id DESC LIMIT 1",
        {"i": q.incident_id, "u": q.until},
    )
    return str(r["text"].iloc[0]) if len(r) else signature_words(qsig)


def fts_text(text: str) -> str:
    """Keyword text safe for the FTS parser: lowercase ``[a-z0-9]+`` tokens joined by spaces."""
    return " ".join(TOKEN_RE.findall(text.lower()))


def recall_filter(q: Query, msig: dict, centroid: np.ndarray, scoring: ScoringConfig) -> str:
    """The §12.3 filter for match ``msig`` (a stored signature) plus no look-ahead (D-082).
    ``centroid``: the match's target centroid, region meters; the box spans it and the launch
    point (centroid + launch offset, when known), widened by ``recall.radius_m``."""
    inst = str(msig["installation_id"])
    if not _SAFE_ID.match(inst):
        raise ValueError(f"unsafe installation id in a filter: {inst!r}")
    rc = scoring.recall
    pts = [np.asarray(centroid, dtype=np.float64)]
    if _known(msig.get("launch_x_rel_m")) and _known(msig.get("launch_y_rel_m")):
        pts.append(pts[0] + [float(msig["launch_x_rel_m"]), float(msig["launch_y_rel_m"])])
    xy = np.vstack(pts)
    lo, hi = xy.min(axis=0) - rc.radius_m, xy.max(axis=0) + rc.radius_m
    w = round(rc.hours_window * HOUR_MS)
    t0, t1 = epoch_ms(msig["start_ts"]) - w, epoch_ms(msig["end_ts"]) + w
    until_ms = q.start_ms + 1000 * int(q.at_s)
    return (f"installation_id = '{inst}' AND event_ts_ms BETWEEN {t0} AND {t1} "
            f"AND x_m BETWEEN {lo[0]:.3f} AND {hi[0]:.3f} "
            f"AND y_m BETWEEN {lo[1]:.3f} AND {hi[1]:.3f} "
            f"AND event_ts_ms < {q.start_ms} AND report_ts_ms <= {until_ms}")  # fmt: skip


def _ranked(df: pd.DataFrame, k: int) -> pd.DataFrame:
    df = df.sort_values([SCORE, "report_id"], ascending=[False, True], kind="stable")
    return df.head(k).reset_index(drop=True)


def rrf_fuse(vec: pd.DataFrame, fts: pd.DataFrame, k: int) -> pd.DataFrame:
    """§12.5: ``score = Σ 1 / (60 + rank)`` over the two ranked lists (1-based ranks); the top
    ``k`` report rows with ``_relevance_score``, ties by ``report_id``. Scores are rounded to
    float32, as LanceDB's native reranker stores them, so both paths order rows identically."""
    score: dict[str, float] = {}
    rows: dict[str, pd.Series] = {}
    for df in (vec, fts):
        for rank, (_, r) in enumerate(df.iterrows(), 1):
            rid = str(r["report_id"])
            score[rid] = score.get(rid, 0.0) + 1.0 / (RRF_K + rank)
            rows.setdefault(rid, r)
    if not score:
        return pd.DataFrame(columns=[*REPORT_COLUMNS, SCORE])
    vals = np.asarray(list(score.values()), dtype=np.float32).astype(np.float64)
    out = pd.DataFrame([rows[r][REPORT_COLUMNS] for r in score]).assign(**{SCORE: vals})
    return _ranked(out, k)


def hybrid_search(
    index: ReportIndex,
    vstore: VectorStore,
    text: str,
    vector: np.ndarray,
    where: str | None,
    k: int,
) -> pd.DataFrame:
    """Hybrid search, native when the backend has it, else the §12.5 fusion; same columns."""
    kw = fts_text(text)
    if kw:
        try:
            return _ranked(index.hybrid(kw, vector, where, k), k)
        except NotImplementedError:
            fts = index.fts(kw, where, k)
    else:
        fts = pd.DataFrame(columns=REPORT_COLUMNS)
    vec = vstore.search(REPORTS_TABLE, vector, where, k)
    return rrf_fuse(vec, fts, k)


@dataclass(frozen=True)
class RecalledReport:
    rank: int
    report_id: str
    incident_id: str
    source: str
    source_grade: str
    event_ts_ms: int
    report_ts_ms: int
    x_m: float
    y_m: float
    text: str
    score: float  # _relevance_score
    clues: tuple[LinkedClue, ...] = ()

    def to_dict(self) -> dict:
        keys = ("rank", "report_id", "incident_id", "source", "source_grade", "event_ts_ms",
                "report_ts_ms", "x_m", "y_m", "text", "score")  # fmt: skip
        return {**{k: getattr(self, k) for k in keys}, "clues": [c.to_dict() for c in self.clues]}


@dataclass(frozen=True)
class MatchRecall:
    """The reports recalled for one matched incident (its best-ranked track)."""

    incident_id: str
    track_id: str
    installation_id: str
    match_rank: int  # 1-based rank of the incident's best track in the fused ranking
    match_score: float
    where: str
    reports: tuple[RecalledReport, ...]
    ms: float  # search time (not in ``to_dict``: the message carries results, not timings)

    def to_dict(self) -> dict:
        keys = ("incident_id", "track_id", "installation_id", "match_rank", "match_score",
                "where")  # fmt: skip
        return {**{k: getattr(self, k) for k in keys},
                "reports": [r.to_dict() for r in self.reports]}  # fmt: skip


@dataclass(frozen=True)
class RecallResult:
    """Recall for tonight's top matched incidents (the §16.3 ``recall`` message's content)."""

    query_text: str
    matches: tuple[MatchRecall, ...]
    zone_roads: tuple[str, ...] = ()
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"query_text": self.query_text, "zone_roads": list(self.zone_roads),
                "matches": [m.to_dict() for m in self.matches]}  # fmt: skip


class ReportRecall:
    """Recall reports for a query's matches through the ports (caches sites and road names)."""

    def __init__(
        self,
        store: TrackStore,
        index: ReportIndex,
        vstore: VectorStore,
        embedder: Embedder,
        scoring: ScoringConfig,
    ) -> None:
        self.store, self.index, self.vstore = store, index, vstore
        self.embedder, self.scoring = embedder, scoring
        self._sites: dict[str, SiteGeometry] = {}
        self._roads: list[str] | None = None

    def site(self, installation_id: str) -> SiteGeometry:
        if installation_id not in self._sites:
            self._sites[installation_id] = load_site(self.store, installation_id)
        return self._sites[installation_id]

    @property
    def road_names(self) -> list[str]:
        if self._roads is None:
            names = self.store.sql("SELECT DISTINCT name FROM roads")["name"].astype(str)
            self._roads = sorted(names)
        return self._roads

    def centroid(self, msig: dict) -> np.ndarray:
        """The match's target centroid (region meters) from its stored target id."""
        return self.site(str(msig["installation_id"])).target(str(msig["target_asset_id"])).centroid

    def for_match(
        self, q: Query, msig: dict, text: str, vector: np.ndarray, k: int | None = None
    ) -> tuple[pd.DataFrame, str]:
        """The top ``k`` reports for one matched track, and the filter used."""
        where = recall_filter(q, msig, self.centroid(msig), self.scoring)
        return hybrid_search(self.index, self.vstore, text, vector, where,
                             k or self.scoring.recall.k), where  # fmt: skip

    def for_matches(
        self,
        q: Query,
        result,
        zone_roads: Collection[str] = (),
        n: int = 3,
        k: int | None = None,
        query: str | None = None,
    ) -> RecallResult:
        """Reports for the top ``n`` distinct matched incidents of ``result`` (a ``MatchResult``),
        with clues linked across them and to ``zone_roads`` (the forecast's roads)."""
        t0 = time.perf_counter()
        qsig = getattr(result, "signature", None) or query_signature(self.store, q)
        text = query or query_text(self.store, q, qsig)
        vector = self.embedder.embed([text])[0]
        t1 = time.perf_counter()
        picked, seen = [], set()
        for rank, m in enumerate(result.matches, 1):
            if m.incident_id not in seen:
                seen.add(m.incident_id)
                picked.append((rank, m))
            if len(picked) == n:
                break
        sigs = getattr(result, "signatures", None)
        found = []
        for rank, m in picked:
            ts = time.perf_counter()
            msig = (sigs.loc[m.track_id].to_dict() | {"track_id": m.track_id}
                    if sigs is not None and m.track_id in sigs.index
                    else self.store.signature(m.track_id))  # fmt: skip
            df, where = self.for_match(q, msig, text, vector, k)
            found.append((rank, m, df, where, (time.perf_counter() - ts) * 1e3))
        clues: dict[str, dict[str, list[Clue]]] = {
            m.incident_id: {str(r["report_id"]): extract_clues(str(r["text"]), self.road_names)
                            for r in df.to_dict("records")}
            for _, m, df, _, _ in found
        }  # fmt: skip
        linked = link_clues(clues, set(zone_roads))
        out = []
        for rank, m, df, where, ms in found:
            reports = tuple(
                RecalledReport(i, str(r["report_id"]), str(r["incident_id"]), str(r["source"]),
                               str(r["source_grade"]), int(r["event_ts_ms"]),
                               int(r["report_ts_ms"]), float(r["x_m"]), float(r["y_m"]),
                               str(r["text"]), float(r[SCORE]),
                               tuple(linked[m.incident_id][str(r["report_id"])]))
                for i, r in enumerate(df.to_dict("records"), 1)
            )  # fmt: skip
            out.append(MatchRecall(m.incident_id, m.track_id, m.installation_id, rank,
                                   float(m.score), where, reports, ms))  # fmt: skip
        t2 = time.perf_counter()
        timings = {"embed_ms": (t1 - t0) * 1e3, "total_ms": (t2 - t0) * 1e3}
        return RecallResult(text, tuple(out), tuple(sorted(zone_roads)), timings)
