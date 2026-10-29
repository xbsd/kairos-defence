"""The agent's composition root (SPEC §18): the ports and services the tools run on.

D-104 names ``api/services.py`` and the CLI as the places that build adapters; the agent is the
third (it extends D-104). ``ToolContext(cfg)`` (the MCP server) builds the DuckDB and LanceDB
adapters lazily, on the first tool call that needs them, so listing the tools needs no data;
``ToolContext(cfg, store=…, memory=…, lock=…)`` (the API's chat route) reuses the API's handles.

- Track data and indexes open read-only and stay open (DuckDB lets several read-only processes
  share a file).
- The ledger opens per call (read-only for the read tools, read-write for ``propose_link``) and
  closes after, so an MCP server never holds ``data/memory.duckdb`` between calls. While another
  process holds it (the API: DuckDB allows one writer per file, D-010), ``ledger()`` raises
  ``LedgerBusy``; the read tools then ask the API's REST routes on ``api_base`` (loopback only,
  rule 5), and a proposal is refused with the cause.
- ``lock`` serializes tool calls: the MCP server may run sync tools on worker threads, and one
  DuckDB connection is never used by two threads at once (D-110).
- Nothing here opens the ground-truth file (rule 2).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

API_DEFAULT = "http://127.0.0.1:8000"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class ToolError(ValueError):
    """A tool call that cannot be answered as asked (bad input, unknown id); the message says
    what to change."""


class ToolUnavailable(ToolError):
    """The data, index or models a tool needs are missing (run ``make data index models``)."""


class LedgerBusy(ToolError):
    """Another process (usually the API) holds the ledger file."""


def utc_now() -> datetime:
    """The wall clock as naive UTC (an agent proposal's transaction time, §15.1)."""
    return datetime.now(UTC).replace(tzinfo=None)


class ToolContext:
    """What the tools need, built lazily from ``cfg`` unless injected."""

    def __init__(self, cfg, *, store=None, vstore=None, matcher=None, recall=None, memory=None,
                 memory_path: Path | str | None = None, agent: str = "mcp",
                 api_base: str = API_DEFAULT, lock: threading.RLock | None = None,
                 clock: Callable[[], datetime] = utc_now) -> None:  # fmt: skip
        self.cfg = cfg
        self.agent = agent  # actor agent:<agent> on proposals (D-094)
        self._store, self._vstore = store, vstore
        self._matcher, self._recall = matcher, recall
        self._memory = memory  # an injected CaseMemory (the API's); None: open per call
        self.memory_path = Path(memory_path or cfg.app.paths.memory)
        self.api_base = api_base
        self.lock = lock or threading.RLock()
        self.clock = clock
        self._owned: list = []

    # --- adapters (lazy) ----------------------------------------------------------------------
    @property
    def store(self):
        """The ``TrackStore`` (DuckDB, read-only)."""
        if self._store is None:
            import duckdb

            from kairos_defense.store.duck import DuckTrackStore

            path = Path(self.cfg.app.paths.duckdb)
            if not path.exists():
                raise ToolUnavailable(f"no data: {path} is missing; run `make data index models`")
            try:
                self._store = DuckTrackStore(path, self.cfg.app)
            except duckdb.IOException as exc:
                raise ToolUnavailable(f"{path} is in use by a writing process (`make index`?): "
                                      f"{exc}") from exc  # fmt: skip
            self._owned.append(self._store)
        return self._store

    @property
    def vstore(self):
        """The ``VectorStore`` (LanceDB)."""
        if self._vstore is None:
            from kairos_defense.store.lance import LanceVectorStore

            self._vstore = LanceVectorStore(self.cfg.app.paths.lancedb)
        return self._vstore

    @property
    def matcher(self):
        """The phase 4 DTW matcher (needs ``make index models``)."""
        if self._matcher is None:
            from kairos_defense.match.candidates import IndexStale
            from kairos_defense.match.dtw_rerank import DtwUnavailable
            from kairos_defense.match.fusion import ModelError
            from kairos_defense.match.matcher import DtwMatcher

            try:
                self._matcher = DtwMatcher(self.store, self.vstore, self.cfg.scoring,
                                           self.cfg.app.paths.models)  # fmt: skip
            except (ModelError, IndexStale, DtwUnavailable, FileNotFoundError, ValueError) as exc:
                raise ToolUnavailable(f"no matching ({type(exc).__name__}): {exc}; run "
                                      "`make index models`") from exc  # fmt: skip
        return self._matcher

    @property
    def recall(self):
        """Report recall (§12; needs the reports index from ``make index``)."""
        if self._recall is None:
            from kairos_defense.recall.embed import EmbedderUnavailable, make_embedder
            from kairos_defense.recall.index import ReportIndexStale, check_reports_index
            from kairos_defense.recall.search import ReportRecall
            from kairos_defense.store.lance import REPORTS_TABLE, LanceReportIndex

            try:
                emb = make_embedder(self.cfg.app)
                if not self.vstore.has(REPORTS_TABLE):
                    raise ReportIndexStale("the reports table is missing")
                check_reports_index(self.store, self.vstore, emb)
            except (EmbedderUnavailable, ReportIndexStale) as exc:
                raise ToolUnavailable(f"no report recall: {exc}; run `make index`") from exc
            self._recall = ReportRecall(self.store, LanceReportIndex(self.cfg.app.paths.lancedb),
                                        self.vstore, emb, self.cfg.scoring)  # fmt: skip
        return self._recall

    @contextmanager
    def ledger(self, write: bool = False) -> Iterator:
        """The ``CaseMemory`` for one call: the injected one, or the ledger file opened now
        (read-only unless ``write``) and closed after. ``LedgerBusy`` when another process holds
        it; ``ToolUnavailable`` when it does not exist."""
        if self._memory is not None:
            yield self._memory
            return
        from kairos_defense.memory.ledger import LedgerError
        from kairos_defense.store.ledger_duck import DuckCaseMemory, LedgerLocked

        try:
            mem = DuckCaseMemory(self.memory_path, self.cfg.app, read_only=not write)
        except LedgerLocked as exc:
            raise LedgerBusy(f"the ledger {self.memory_path} is held by another process "
                             "(the API, `make demo`?)") from exc  # fmt: skip
        except LedgerError as exc:
            raise ToolUnavailable(str(exc)) from exc
        try:
            yield mem
        finally:
            mem.close()

    # --- the API fallback (D-010) -------------------------------------------------------------
    def remote(self, path: str, params: dict | None = None, timeout_s: float = 30.0) -> dict:
        """``GET {api_base}{path}`` on a loopback API: the JSON reply. ``ToolError`` with the API's
        message on an HTTP error, ``LedgerBusy`` when nothing answers."""
        import urllib.error
        import urllib.parse
        import urllib.request

        host = urllib.parse.urlparse(self.api_base).hostname
        if host not in LOOPBACK:
            raise ToolError(f"api_base must be a loopback URL, not {self.api_base!r}")
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = self.api_base.rstrip("/") + path + (f"?{query}" if query else "")
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode()).get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise ToolError(f"the API answered {exc.code}: {detail or exc.reason}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise LedgerBusy(f"the ledger {self.memory_path} is held by another process and no "
                             f"API answers at {self.api_base}") from exc  # fmt: skip

    def close(self) -> None:
        for a in self._owned:
            with suppress(Exception):  # closing everything matters more than the first error
                a.close()
        self._owned.clear()
