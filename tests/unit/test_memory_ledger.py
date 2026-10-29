"""SPEC §15.1–§15.3: the append-only, hash-chained ledger and its single writer.

The tamper tests come first (phase 6 manual prompt): raw SQL edits one row behind the writer's back
and ``verify_chain`` must name exactly that seq. Tests may mutate the table directly; library code
never does (``test_memory_append_only.py``).
"""

from __future__ import annotations

import itertools
import threading
from datetime import datetime, timedelta

import numpy as np
import pytest

from kairos_defense.memory.canonical import GENESIS, row_hash
from kairos_defense.memory.ledger import InvalidEvent, active_rows
from kairos_defense.store.guard import TruthAccessError
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import assessment, ev, incident, numbered, proposal


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        yield m


def _ten(mem) -> None:
    mem.append_many(numbered(10))


# --- tampering is caught at exactly the edited seq (written first) ---------------------------
def test_tamper_object_json_caught_at_that_seq(mem) -> None:
    _ten(mem)
    assert mem.verify_chain() is None
    mem.con.execute("""UPDATE ledger SET object_json = '{"base":"BRAVO"}' WHERE seq = 6""")
    assert mem.verify_chain() == 6


def test_tamper_recorded_at_caught_at_that_seq(mem) -> None:
    _ten(mem)
    mem.con.execute("UPDATE ledger SET recorded_at = recorded_at + INTERVAL 1 SECOND WHERE seq = 3")
    assert mem.verify_chain() == 3


def test_tamper_hash_caught_at_that_seq(mem) -> None:
    _ten(mem)
    mem.con.execute("UPDATE ledger SET hash = repeat('a', 64) WHERE seq = 8")
    assert mem.verify_chain() == 8


def test_deleted_row_caught_at_missing_seq(mem) -> None:
    _ten(mem)
    mem.con.execute("DELETE FROM ledger WHERE seq = 5")
    assert mem.verify_chain() == 5


def test_intact_and_empty_chains_verify_none(mem) -> None:
    assert mem.verify_chain() is None and mem.count() == 0 and mem.head() is None
    _ten(mem)
    assert mem.verify_chain() is None and mem.count() == 10


# --- the chain ---------------------------------------------------------------------------------
def test_seq_contiguous_from_1_and_prev_hash_links(mem) -> None:
    seqs = mem.append_many(numbered(5))
    seqs.append(mem.append(numbered(6)[-1]))
    assert seqs == [1, 2, 3, 4, 5, 6]
    rows = mem.events()
    assert [r["seq"] for r in rows] == seqs
    assert rows[0]["prev_hash"] == GENESIS == "0" * 64
    for a, b in itertools.pairwise(rows):
        assert b["prev_hash"] == a["hash"]
    for r in rows:
        assert r["hash"] == row_hash(r["prev_hash"], r)
    head = mem.head()
    assert (head.seq, head.hash, head.recorded_at) == (6, rows[-1]["hash"], rows[-1]["recorded_at"])


def test_recorded_at_never_goes_backwards(mem) -> None:
    """D-010: a clock earlier than the head (a replay re-run or seek back) is stamped with the
    head's time."""
    t = datetime(2026, 8, 29, 2, 41, 36)
    mem.append(incident("INC-A", "BRAVO", t - timedelta(minutes=13)))
    head_t = mem.head().recorded_at
    seq = mem.append(incident("INC-B", "BRAVO", t - timedelta(hours=3)))
    row = mem.events()[-1]
    assert seq == 2 and row["recorded_at"] == head_t
    assert mem.verify_chain() is None


def test_round_trip_recomputes_same_hash(mem) -> None:
    rng = np.random.default_rng(6)
    words = ["pickup", "é-clair", "Ünïcode ☂", "", "County Rd 12", 'a"quote', "line\nbreak"]
    events = []
    t0 = datetime(2026, 2, 1, 3, 4, 5, 678901)
    for i in range(40):
        obj = {"score": float(rng.random()), "n": int(rng.integers(0, 10**9)),
               "neg": -float(rng.random()) * 1e3, "word": words[i % len(words)],
               "nested": {"z": [1, 2.5, None, {"b": True, "a": float(rng.normal())}]},
               "none": None}  # fmt: skip
        e = proposal("CASE-INC-0001", f"INC-{i:04d}", "Q-1", float(rng.random()),
                     t0 + timedelta(microseconds=int(rng.integers(0, 10**12))))  # fmt: skip
        e["object_json"] = obj
        e["valid_to"] = None if i % 2 else t0 + timedelta(days=1, microseconds=i)
        events.append(e)
    mem.append_many(sorted(events, key=lambda e: e["recorded_at"]))
    rows = mem.events()
    assert len(rows) == 40
    for r in rows:
        assert r["hash"] == row_hash(r["prev_hash"], r)
    assert rows[0]["object_json"]["word"] == "pickup"
    assert mem.verify_chain() is None


def test_append_many_is_atomic(mem) -> None:
    _ten(mem)
    bad = [*numbered(3, datetime(2026, 2, 1)), ev("no_such_event", datetime(2026, 2, 2))]
    with pytest.raises(InvalidEvent):
        mem.append_many(bad)
    assert mem.count() == 10 and mem.verify_chain() is None


def test_concurrent_appends_are_serialized(mem) -> None:
    def worker(k: int) -> None:
        for i in range(25):
            mem.append(incident(f"INC-{k}-{i:02d}", "ALPHA", datetime(2026, 1, 1, k, i)))

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert [r["seq"] for r in mem.events()] == list(range(1, 101))
    assert mem.verify_chain() is None


# --- validation ----------------------------------------------------------------------------------
def test_validation_rejects_unknown_type_bad_actor_and_bad_ids(mem) -> None:
    t = datetime(2026, 1, 1)
    bad = [
        ev("no_such_event", t),
        {**incident("INC-1", "ALPHA", t), "actor": "Someone"},
        {**incident("INC-1", "ALPHA", t), "actor": "analyst:Has Spaces"},
        {**incident("INC-1", "ALPHA", t), "subject_id": "Person Name Example"},  # rule 9
        {**incident("INC-1", "ALPHA", t), "subject_id": "inc-lowercase"},
        {**proposal("NOT-A-CASE", "INC-1", "Q", 0.5, t)},
        {**incident("INC-1", "ALPHA", t), "recorded_at": None},
        {**incident("INC-1", "ALPHA", t), "colour": "red"},
        {**incident("INC-1", "ALPHA", t), "seq": 7},
        {**incident("INC-1", "ALPHA", t), "object_json": "not an object"},
    ]
    for e in bad:
        with pytest.raises(InvalidEvent):
            mem.append(e)
    assert mem.count() == 0


def test_only_analysts_approve_or_reject_links(mem) -> None:
    """Rule 8: the matcher and agents may only propose."""
    t = datetime(2026, 1, 1)
    p = mem.append(proposal("CASE-INC-1", "INC-2", "Q-1", 0.9, t))
    approve = ev("link_approved", t, case_id="CASE-INC-1", subject_id="INC-2",
                 predicate="member_of", object_json={"proposal_seq": p})  # fmt: skip
    reject = ev("link_rejected", t, case_id="CASE-INC-1", subject_id="INC-2",
                predicate="member_of", supersedes_seq=p, object_json={})  # fmt: skip
    for actor in ("matcher@fusion-v1", "agent:claude", "system", "generator"):
        for e in (approve, reject):
            with pytest.raises(InvalidEvent, match="may not write"):
                mem.append({**e, "actor": actor})
    agent = {**proposal("CASE-INC-1", "INC-3", "Q-1", 0.8, t), "actor": "agent:claude"}
    assert mem.append(agent) == 2
    assert mem.append(approve) == 3


def test_supersedes_must_reference_an_earlier_compatible_event(mem) -> None:
    t = datetime(2026, 1, 1)
    inc = mem.append(incident("INC-1", "ALPHA", t))
    a = mem.append(assessment("INC-1", "hobbyist", t, t))
    retract = ev("claim_retracted", t, subject_id="INC-1", predicate="assessment",
                 object_json={"rationale": "wrong"})  # fmt: skip
    for target in (None, inc, 99):
        with pytest.raises(InvalidEvent):
            mem.append({**retract, "supersedes_seq": target})
    reject = ev("link_rejected", t, case_id="CASE-INC-1", subject_id="INC-1",
                predicate="member_of", supersedes_seq=a, object_json={})  # fmt: skip
    with pytest.raises(InvalidEvent):
        mem.append(reject)
    with pytest.raises(InvalidEvent):
        mem.append({**incident("INC-2", "ALPHA", t), "supersedes_seq": a})
    assert mem.append({**retract, "supersedes_seq": a}) == 3
    with pytest.raises(InvalidEvent, match="already superseded"):
        mem.append({**retract, "supersedes_seq": a})


def test_ledger_asof_macro_matches_python_active_rows(mem) -> None:
    t0 = datetime(2026, 1, 1)
    mem.append_many([incident("INC-1", "ALPHA", t0), assessment("INC-1", "hobbyist", t0, t0)])
    t1 = t0 + timedelta(hours=1)
    mem.append(assessment("INC-1", "probing", t1, t0, actor="analyst:a"))
    t2 = t0 + timedelta(hours=2)
    mem.append(ev("claim_retracted", t2, subject_id="INC-1", predicate="assessment",
                  supersedes_seq=2, object_json={"rationale": "superseded"}))  # fmt: skip
    rows = mem.events()
    for t in (t0 - timedelta(days=1), t0 + timedelta(minutes=14), t1, t1 + timedelta(minutes=1),
              t2 + timedelta(days=1)):  # fmt: skip
        sql = [s for (s,) in mem.con.execute(
            "SELECT seq FROM ledger_asof($t) ORDER BY seq", {"t": t}).fetchall()]  # fmt: skip
        assert sql == [r["seq"] for r in active_rows(rows, t)], t
    assert [r["seq"] for r in active_rows(rows, t2)] == [1, 3, 4]


def test_read_only_memory_refuses_append(cfg, tmp_path) -> None:
    path = tmp_path / "mem.duckdb"
    with DuckCaseMemory(path, cfg.app) as m:
        m.append_many(numbered(2))
    with DuckCaseMemory(path, cfg.app, read_only=True) as ro:
        assert ro.count() == 2 and ro.verify_chain() is None
        with pytest.raises(PermissionError):
            ro.append(numbered(3)[-1])


def test_memory_refuses_truth_path(cfg) -> None:
    with pytest.raises(TruthAccessError):
        DuckCaseMemory(cfg.app.paths.truth, cfg.app, read_only=True)


def test_ledger_ddl_columns_match_row_fields() -> None:
    from kairos_defense.memory.ledger import ROW_FIELDS
    from kairos_defense.store.ddl import LEDGER_COLUMNS, LEDGER_DDL, columns

    assert columns(LEDGER_DDL) == LEDGER_COLUMNS == list(ROW_FIELDS)


def test_wrong_schema_is_refused(cfg, tmp_path) -> None:
    from kairos_defense.memory.ledger import LedgerError
    from kairos_defense.store.guard import connect_app_db

    path = tmp_path / "old.duckdb"
    con = connect_app_db(path, cfg.app)
    con.execute("CREATE TABLE ledger (seq BIGINT, note VARCHAR)")
    con.close()
    with pytest.raises(LedgerError, match="reseed"):
        DuckCaseMemory(path, cfg.app)
    with pytest.raises(LedgerError, match="memory seed"):
        DuckCaseMemory(tmp_path / "missing.duckdb", cfg.app, read_only=True)


def test_copy_from_copies_rows_unchanged(cfg, tmp_path) -> None:
    from kairos_defense.memory.ledger import LedgerError

    src = tmp_path / "src.duckdb"
    with DuckCaseMemory(src, cfg.app) as m:
        m.append_many(numbered(12))
        rows = m.events()
    with DuckCaseMemory(tmp_path / "dst.duckdb", cfg.app) as d:
        assert d.copy_from(src) == 12
        assert d.events() == rows and d.verify_chain() is None
        with pytest.raises(LedgerError, match="empty"):
            d.copy_from(src)
        assert d.append(numbered(13)[-1]) == 13


def test_copy_from_refuses_truth(cfg, tmp_path) -> None:
    with DuckCaseMemory(tmp_path / "dst.duckdb", cfg.app) as d, pytest.raises(TruthAccessError):
        d.copy_from(cfg.app.paths.truth)
