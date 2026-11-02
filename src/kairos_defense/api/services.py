"""The API's composition root (CLAUDE.md rule 6, D-104, D-110): the only place outside the CLI
that constructs adapters.

``Services`` opens the main database **read-only** (CLI reads keep working while the API runs),
LanceDB, the matcher and report recall when their models and indexes are present (otherwise the
API serves the replay without matches and says why in ``/api/health``), the ``live_*`` sink in
its own file, the result cache, and the ledger wrapped so every append is broadcast. Locks: one
re-entrant lock for the main store, LanceDB, the matcher and recall; the ledger and the sink keep
their own. When two are held, the store lock is taken first. No DuckDB connection is used by two
threads at once.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from kairos_defense import __version__
from kairos_defense.live.broadcast import Broadcaster, PublishingMemory
from kairos_defense.live.loop import LiveLoop
from kairos_defense.live.precompute import fingerprint
from kairos_defense.live.replay import (
    LiveIncident,
    live_incident_ids,
    load_incident,
    scaled_clock,
)
from kairos_defense.live.session import Session

log = logging.getLogger(__name__)


class ServiceError(RuntimeError):
    """The API cannot start (missing data, a locked file): the message says how to fix it."""


class Services:
    def __init__(self, cfg, *, memory_path: Path | str | None = None,
                 live_path: Path | str | None = None, reseed: bool = False,
                 exports_path: Path | str | None = None,
                 time_scale: float = 1.0, live_mode_path: Path | str | None = None,
                 live_threaded: bool = True, sim_command=None,
                 config_dir: Path | str | None = None) -> None:  # fmt: skip
        import duckdb

        from kairos_defense.store.duck import DuckTrackStore
        from kairos_defense.store.lance import LanceVectorStore
        from kairos_defense.store.live_cache import FileResultCache
        from kairos_defense.store.live_duck import DuckLiveSink

        self.cfg, self.app = cfg, cfg.app
        self.lock = threading.RLock()
        self.problems: list[str] = []
        db = Path(self.app.paths.duckdb)
        if not db.exists():
            raise ServiceError(f"no data: {db} is missing; run `make data index models`")
        try:
            self.store = DuckTrackStore(db, self.app)
        except duckdb.IOException as exc:
            raise ServiceError(f"{db} is in use by a writing process (`make index`?): "
                               f"{exc}") from exc  # fmt: skip
        self.lance = LanceVectorStore(self.app.paths.lancedb)
        self.matcher, self.recall, self.model = self._matching()
        self.cache = FileResultCache(Path(self.app.paths.cache) / "live")
        self.exports = Path(exports_path or self.app.paths.exports)  # e2e: a scratch folder
        scaled_clock(time_scale)  # validate early: [0.05, 1]
        self.time_scale = float(time_scale)  # < 1: slow-motion replays for capture (D-168)
        self.live_path = Path(live_path or self.app.paths.live)
        try:
            self.sink = DuckLiveSink(self.live_path, self.app)
        except duckdb.IOException as exc:
            raise ServiceError(f"{self.live_path} is in use by another process: {exc}") from exc
        self.bus = Broadcaster()
        self.memory_path = Path(memory_path or self.app.paths.memory)
        self.memory = PublishingMemory(self._open_memory(reseed), self.bus)
        self.incident_ids = live_incident_ids(self.store)
        self._incidents: dict[str, LiveIncident] = {}
        self._loops: dict[str, LiveLoop] = {}
        self.swarm_matcher = None  # match.swarm.SwarmMatcher, built on first use (routes_swarm)
        self.swarm_cache: dict[tuple, dict] = {}
        self.live = None  # live mode (phase 11, D-172): api.live_services.LiveServices
        try:
            from kairos_defense.api.live_services import LiveServices

            self.live = LiveServices(self, live_mode_path, threaded=live_threaded,
                                     sim_command=sim_command, config_dir=config_dir)  # fmt: skip
        except duckdb.IOException as exc:
            raise ServiceError(f"the live-mode folder is in use by another process: "
                               f"{exc}") from exc  # fmt: skip

    # --- construction -----------------------------------------------------------------------
    def _matching(self):
        from kairos_defense.match.candidates import IndexStale
        from kairos_defense.match.dtw_rerank import DtwUnavailable
        from kairos_defense.match.fusion import MODEL_FILE, ModelError
        from kairos_defense.match.matcher import DtwMatcher
        from kairos_defense.memory.actions import file_sha256
        from kairos_defense.recall.embed import EmbedderUnavailable, make_embedder
        from kairos_defense.recall.index import ReportIndexStale, check_reports_index
        from kairos_defense.recall.search import ReportRecall
        from kairos_defense.store.lance import REPORTS_TABLE, LanceReportIndex

        try:
            matcher = DtwMatcher(self.store, self.lance, self.cfg.scoring, self.app.paths.models)
        except (ModelError, IndexStale, DtwUnavailable, FileNotFoundError, ValueError) as exc:
            self.problems.append(f"no matching: {type(exc).__name__}: {exc}")
            return None, None, None
        mfile = Path(self.app.paths.models) / MODEL_FILE
        model = {"version": matcher.model_version, "sha256": file_sha256(mfile),
                 "file": mfile.name,
                 "validation": json.loads(mfile.read_text()).get("validation", {})}  # fmt: skip
        recall = None
        try:
            emb = make_embedder(self.app)
            if not self.lance.has(REPORTS_TABLE):
                raise ReportIndexStale("the reports table is missing: run `make index`")
            check_reports_index(self.store, self.lance, emb)
            recall = ReportRecall(self.store, LanceReportIndex(self.app.paths.lancedb),
                                  self.lance, emb, self.cfg.scoring)  # fmt: skip
        except (EmbedderUnavailable, ReportIndexStale) as exc:
            self.problems.append(f"no report recall: {exc}")
        return matcher, recall, model

    def _open_memory(self, reseed: bool):
        from kairos_defense.memory.ledger import LedgerError
        from kairos_defense.memory.seed import seed
        from kairos_defense.store.ledger_duck import DuckCaseMemory, reseed_ledger

        p = self.memory_path
        try:
            if reseed:
                reseed_ledger(p, self.app, self.store, self.cfg.scenario)
            mem = DuckCaseMemory(p, self.app)
            if mem.count() == 0:
                log.info("empty ledger %s: seeding it", p)
                seed(mem, self.store, self.cfg.scenario)
        except LedgerError as exc:
            raise ServiceError(str(exc)) from exc
        return mem

    def close(self) -> None:
        closers = [self.memory.inner.close, self.sink.close, self.store.close]
        if self.live is not None:
            closers.insert(0, self.live.close)
        for closer in closers:
            try:
                closer()
            except Exception:  # closing everything matters more than the first error
                log.exception("close failed")

    # --- live -------------------------------------------------------------------------------
    def incident(self, incident_id: str) -> LiveIncident:
        """A live incident (``KeyError`` for any other id), loaded once."""
        if incident_id not in self.incident_ids:
            raise KeyError(f"no live incident {incident_id!r}")
        with self.lock:
            if incident_id not in self._incidents:
                self._incidents[incident_id] = load_incident(self.store, incident_id)
        return self._incidents[incident_id]

    def loop(self, incident_id: str) -> LiveLoop:
        inc = self.incident(incident_id)
        with self.lock:
            if incident_id not in self._loops:
                fp = fingerprint(self.store, self.cfg.scoring, self.app, incident_id)
                self._loops[incident_id] = LiveLoop(
                    inc, self.store, self.cfg.scoring, matcher=self.matcher, recall=self.recall,
                    cache=self.cache, lock=self.lock, fingerprint=fp)  # fmt: skip
            return self._loops[incident_id]

    def session(self, incident_id: str) -> Session:
        loop = self.loop(incident_id)
        speed = float(self.app.replay.default_speed)
        return Session(loop.incident, loop, sink=self.sink, memory=self.memory,
                       feed=self.bus.subscribe(), model=self.model, speed=speed,
                       now=scaled_clock(self.time_scale))  # fmt: skip

    # --- admin (D-010) ----------------------------------------------------------------------
    def reset_live(self) -> dict[str, int]:
        return self.sink.reset()

    def reseed(self):
        """Close the ledger, rebuild it from seed, reopen it (under the memory lock, so no
        append lands in the file being replaced). Returns the ``SeedSummary``."""
        from kairos_defense.store.ledger_duck import DuckCaseMemory, reseed_ledger

        with self.lock, self.memory.lock:  # lock order everywhere: store, then memory
            self.memory.inner.close()
            try:
                summary = reseed_ledger(self.memory_path, self.app, self.store, self.cfg.scenario)
            finally:
                self.memory.replace(DuckCaseMemory(self.memory_path, self.app))
        return summary

    def health(self) -> dict:
        head = self.memory.head()
        return {"status": "ok" if not self.problems else "degraded", "version": __version__,
                "live_incidents": self.incident_ids, "matching": self.matcher is not None,
                "live_mode": self.live is not None,
                "problems": self.problems, "ledger_rows": self.memory.count(),
                "ledger_head_seq": head.seq if head else None}  # fmt: skip
