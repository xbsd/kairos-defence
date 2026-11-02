"""CLAUDE.md rule 2 and SPEC §7.6: only eval/ reads truth; the guard refuses it everywhere else."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kairos_defense.store.guard import TruthAccessError, connect_app_db, is_truth_path

FORBIDDEN = ("truth.duckdb", "paths.truth", "truth_path", "live_truth")  # D-170, D-179
ALLOWED_DIRS = ("kairos_defense/eval/",)
ALLOWED_FILES = ("kairos_defense/sim/writers.py", "kairos_defense/store/guard.py")  # D-008


def test_source_scan(root: Path) -> None:
    pkg = root / "src" / "kairos_defense"
    files = sorted(pkg.rglob("*.py"))
    assert len(files) > 5, "scan found too few files: wrong path?"
    offenders = []
    for f in files:
        rel = f.relative_to(root / "src").as_posix()
        if rel.startswith(ALLOWED_DIRS) or rel in ALLOWED_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        offenders += [f"{rel}: {s}" for s in FORBIDDEN if s in text]
    assert not offenders, "truth referenced outside eval/: " + ", ".join(offenders)


def test_scan_would_catch_an_offender(tmp_path: Path) -> None:
    bad = "con = duckdb.connect(cfg.app.paths.truth)"
    assert any(s in bad for s in FORBIDDEN)


def test_guard_refuses_truth_however_spelled(cfg, tmp_path: Path, monkeypatch) -> None:
    truth = cfg.app.paths.truth
    monkeypatch.chdir(cfg.root)
    spellings = [
        truth,
        str(truth),
        Path("data/truth.duckdb"),
        Path("data/../data/./truth.duckdb"),
    ]
    for p in spellings:
        assert is_truth_path(p, cfg.app), p
        with pytest.raises(TruthAccessError):
            connect_app_db(p, cfg.app)


def test_guard_refuses_symlink_and_hard_link(cfg, tmp_path: Path) -> None:
    truth = tmp_path / "truth.duckdb"
    truth.write_bytes(b"")
    app = cfg.app.model_copy(update={"paths": cfg.app.paths.model_copy(update={"truth": truth})})
    sym = tmp_path / "innocent.duckdb"
    sym.symlink_to(truth)
    hard = tmp_path / "also_innocent.duckdb"
    os.link(truth, hard)
    for p in (sym, hard):
        with pytest.raises(TruthAccessError):
            connect_app_db(p, app)


def test_guard_allows_app_databases(cfg, tmp_path: Path) -> None:
    con = connect_app_db(":memory:", cfg.app)
    assert con.execute("select 42").fetchone() == (42,)
    con.close()
    con = connect_app_db(tmp_path / "sub" / "app.duckdb", cfg.app)
    con.execute("create table t (x int)")
    con.close()
    assert (tmp_path / "sub" / "app.duckdb").exists()
