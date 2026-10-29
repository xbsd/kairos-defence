"""DuckDB adapter for the ``CaseMemory`` port (SPEC §15, D-092, D-093): ``data/memory.duckdb``.

One process writes (DuckDB's file lock enforces it: while a process holds the file read-write, no
other process can open it, even read-only). Within the process one connection sits behind a lock,
so seq assignment, sealing and the insert of a batch happen atomically (§15.1). Rows are only
ever inserted; snapshots, diffs and verification are the pure functions in ``kairos_defense.memory``
over ``events()``. The connection goes through ``connect_app_db``, so it can never open truth.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa

from kairos_defense.config import AppConfig
from kairos_defense.memory.asof import snapshot
from kairos_defense.memory.canonical import canonical_json
from kairos_defense.memory.diff import case_diff
from kairos_defense.memory.ledger import (
    Head,
    LedgerError,
    Ref,
    head_of,
    normalize_event,
    seal,
    validate,
    verify_rows,
)
from kairos_defense.ports import CaseSnapshot
from kairos_defense.store.ddl import LEDGER_ASOF_MACRO, LEDGER_COLUMNS, LEDGER_DDL
from kairos_defense.store.guard import connect_app_db, refuse_truth

log = logging.getLogger(__name__)

_TS = pa.timestamp("us")
ARROW_SCHEMA = pa.schema([
    ("seq", pa.int64()), ("recorded_at", _TS), ("event_type", pa.string()),
    ("case_id", pa.string()), ("subject_id", pa.string()), ("predicate", pa.string()),
    ("object_json", pa.string()), ("valid_from", _TS), ("valid_to", _TS),
    ("source_type", pa.string()), ("source_id", pa.string()), ("source_grade", pa.string()),
    ("confidence", pa.float64()), ("actor", pa.string()), ("supersedes_seq", pa.int64()),
    ("prev_hash", pa.string()), ("hash", pa.string()),
])  # fmt: skip
assert ARROW_SCHEMA.names == LEDGER_COLUMNS


class LedgerLocked(LedgerError):
    """Another process holds the ledger file (DuckDB allows one writer per file)."""


def _open(path: Path, app: AppConfig, read_only: bool) -> duckdb.DuckDBPyConnection:
    try:
        return connect_app_db(path, app, read_only=read_only)
    except duckdb.IOException as exc:
        if "lock" in str(exc).lower():
            raise LedgerLocked(f"{path} is in use by another process (stop `make demo` or the "
                               f"API first, D-010): {exc}") from exc  # fmt: skip
        raise LedgerError(f"cannot open {path}: {exc}") from exc


class DuckCaseMemory:
    """``CaseMemory`` over one DuckDB file. ``read_only=True`` never creates or writes it."""

    def __init__(self, path: Path | str, app: AppConfig, *, read_only: bool = False) -> None:
        self.path, self.app, self.read_only = Path(path), app, read_only
        refuse_truth(self.path, app)
        if read_only and not self.path.exists():
            raise LedgerError(f"no ledger at {self.path}: run `kairos-defense memory seed`")
        self.con = _open(self.path, app, read_only)
        self._lock = threading.RLock()
        self._has_table = self._check_schema()
        if not self._has_table and not read_only:
            self.con.execute(LEDGER_DDL)
            self._has_table = True
        if self._has_table and not read_only:
            self.con.execute(LEDGER_ASOF_MACRO)

    def _check_schema(self) -> bool:
        cols = [c for (c,) in self.con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ledger' "
            "ORDER BY ordinal_position").fetchall()]  # fmt: skip
        if cols and cols != LEDGER_COLUMNS:
            self.con.close()
            raise LedgerError(f"{self.path} has a different ledger schema: run "
                              "`kairos-defense memory reseed`")  # fmt: skip
        return bool(cols)

    # --- lifecycle -------------------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self.con.close()

    def __enter__(self) -> DuckCaseMemory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def checkpoint(self) -> None:
        with self._lock:
            if not self.read_only:
                self.con.execute("CHECKPOINT")

    # --- reads -----------------------------------------------------------------------------------
    def _select(self, where: str = "", params: dict | None = None) -> list[dict]:
        if not self._has_table:
            return []
        with self._lock:
            cur = self.con.execute(f"SELECT * FROM ledger {where} ORDER BY seq", params or {})
            names = [d[0] for d in cur.description]
            out = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        for r in out:
            if r["object_json"] is not None:
                r["object_json"] = json.loads(r["object_json"])
        return out

    def events(self, after: datetime | None = None, until: datetime | None = None) -> list[dict]:
        """Rows with ``after < recorded_at <= until`` (either bound optional), in seq order, with
        ``object_json`` parsed. Times are naive UTC."""
        return self._select("WHERE ($a IS NULL OR recorded_at > $a) "
                            "AND ($u IS NULL OR recorded_at <= $u)",
                            {"a": after, "u": until})  # fmt: skip

    def rows_for_seqs(self, seqs: Sequence[int]) -> list[dict]:
        return self._select("WHERE list_contains($s, seq)", {"s": [int(s) for s in seqs]})

    def head(self) -> Head | None:
        rows = self._select("WHERE seq = (SELECT max(seq) FROM ledger)")
        return head_of(rows[0]) if rows else None

    def count(self) -> int:
        if not self._has_table:
            return 0
        with self._lock:
            return int(self.con.execute("SELECT count(*) FROM ledger").fetchone()[0])

    # --- port ------------------------------------------------------------------------------------
    def as_of(self, case_id: str, t: datetime) -> CaseSnapshot:
        return snapshot(self.events(until=t), case_id, t)

    def diff(self, case_id: str, t1: datetime, t2: datetime) -> list[dict]:
        return case_diff(self.events(until=t2), case_id, t1, t2)

    def verify_chain(self) -> int | None:
        return verify_rows(self.events())

    def append(self, event: dict) -> int:
        return self.append_many([event])[0]

    def append_many(self, events: Sequence[dict]) -> list[int]:
        """Validate, seal and insert ``events`` in one transaction (all or nothing)."""
        if self.read_only:
            raise PermissionError(f"{self.path} is open read-only")
        with self._lock:
            head = self.head()
            batch: dict[int, dict] = {}

            def lookup(seq: int) -> Ref | None:
                if seq in batch:
                    r = batch[seq]
                    return Ref(r["event_type"], r["case_id"], _superseded_in(batch, seq))
                if head is None or not isinstance(seq, int) or not 1 <= seq <= head.seq:
                    return None
                et, case = self.con.execute(
                    "SELECT event_type, case_id FROM ledger WHERE seq = $s", {"s": seq}
                ).fetchone()  # fmt: skip
                gone = self.con.execute("SELECT count(*) FROM ledger WHERE supersedes_seq = $s",
                                        {"s": seq}).fetchone()[0] > 0  # fmt: skip
                return Ref(et, case, gone or _superseded_in(batch, seq))

            rows = []
            for ev in events:
                e = normalize_event(ev)
                validate(e, lookup)
                row = seal(head, e)
                batch[row["seq"]] = row
                rows.append(row)
                head = head_of(row)
            if rows:
                self._insert(rows)
        return [r["seq"] for r in rows]

    def _insert(self, rows: list[dict]) -> None:
        cols = {c: [r[c] for r in rows] for c in LEDGER_COLUMNS}
        cols["object_json"] = [
            None if o is None else canonical_json(o) for o in cols["object_json"]
        ]
        tbl = pa.table(cols, schema=ARROW_SCHEMA)
        self.con.execute("BEGIN TRANSACTION")
        try:
            self.con.register("rows_in", tbl)
            self.con.execute("INSERT INTO ledger SELECT * FROM rows_in")
            self.con.unregister("rows_in")
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        log.debug("appended seqs %d-%d", rows[0]["seq"], rows[-1]["seq"])

    def copy_from(self, source: Path | str) -> int:
        """Copy every row of another ledger file into this empty one, unchanged (the demo's
        scratch copy). The source must be closed by its writer. Returns the row count."""
        src = Path(source)
        refuse_truth(src, self.app)
        if self.read_only or self.count():
            raise LedgerError("copy_from needs an empty, writable ledger")
        quoted = str(src.resolve()).replace("'", "''")
        with self._lock:
            try:
                self.con.execute(f"ATTACH '{quoted}' AS src_ledger (READ_ONLY)")
            except duckdb.IOException as exc:
                raise LedgerLocked(f"cannot read {src}: {exc}") from exc
            try:
                self.con.execute("INSERT INTO ledger SELECT * FROM src_ledger.ledger ORDER BY seq")
            finally:
                self.con.execute("DETACH src_ledger")
        return self.count()


def _superseded_in(batch: dict[int, dict], seq: int) -> bool:
    return any(r["supersedes_seq"] == seq for r in batch.values())


def _remove(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            p.unlink()


def check_unlocked(path: Path | str, app: AppConfig) -> None:
    """Raise ``LedgerLocked`` if another process holds ``path`` (DuckDB's file lock)."""
    p = Path(path)
    if p.exists():
        _open(p, app, read_only=False).close()


def reseed_ledger(path: Path | str, app: AppConfig, store, scenario):
    """Rebuild the ledger at ``path`` from seed (D-010): seed a temporary file next to it, verify
    the chain, close it, remove stale WAL files, then ``os.replace``. Returns the ``SeedSummary``.
    Raises ``LedgerLocked`` when another process holds ``path`` (the caller closes its own
    connection first), ``LedgerError`` when the new chain does not verify (``path`` unchanged).
    Used by ``memory reseed`` and ``POST /api/admin/reseed``."""
    import os

    from kairos_defense.memory.seed import seed

    p = Path(path)
    check_unlocked(p, app)
    tmp = p.with_name(p.name + ".reseed.tmp")
    _remove(tmp, Path(f"{tmp}.wal"))
    with DuckCaseMemory(tmp, app) as mem:
        summary = seed(mem, store, scenario)
        broken = mem.verify_chain()
    if broken is not None:
        _remove(tmp)
        raise LedgerError(f"reseed failed: the new chain is broken at seq {broken}; {p} is "
                          "unchanged")  # fmt: skip
    _remove(Path(f"{p}.wal"))
    os.replace(tmp, p)
    log.info("reseeded %s (%d rows)", p, summary.rows)
    return summary
