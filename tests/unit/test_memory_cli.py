"""The phase 6 commands (D-100): ``memory seed|reseed|verify|show|delta|demo``, ``export`` and
``verify-evidence``, on the P1 nights. Every test points the ledger, exports, cache and signing key
at its own folder, so none writes the session-scoped ``p1_index`` ledger."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import kairos_defense.cli as cli
from kairos_defense.cli import app
from kairos_defense.store.guard import connect_app_db
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.conftest import tmp_config, with_paths

runner = CliRunner()
CASE = "CASE-P1-DELTA-260419"


def _run(*args: str):
    return runner.invoke(app, list(args), terminal_width=250)


@pytest.fixture
def p1(p1_index, tmp_path, monkeypatch):
    c = with_paths(p1_index.cfg, tmp_path, "memory", "exports", "cache", "key")
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    return c


@pytest.fixture
def toy(toy_models, tmp_path, monkeypatch):
    c = with_paths(toy_models, tmp_path, "memory", "exports", "cache", "key")
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    return c


def _head(c, path=None):
    with DuckCaseMemory(path or c.app.paths.memory, c.app, read_only=True) as m:
        return m.head()


def test_memory_seed_then_refuse_second_seed(p1) -> None:
    res = _run("memory", "seed")
    assert res.exit_code == 0, res.output
    assert "incident_recorded" in res.output and "case_opened" in res.output
    assert Path(p1.app.paths.memory).exists()
    again = _run("memory", "seed")
    assert again.exit_code == 1 and "reseed" in again.output


def test_memory_reseed_gives_same_head_hash(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    first = _head(p1)
    res = _run("memory", "reseed")
    assert res.exit_code == 0, res.output and "verified" in res.output
    assert _head(p1) == first
    folder = Path(p1.app.paths.memory).parent
    assert not [p for p in folder.iterdir() if "reseed.tmp" in p.name]


def test_memory_verify_intact_and_broken(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    res = _run("memory", "verify")
    assert res.exit_code == 0 and "chain intact" in res.output, res.output
    con = connect_app_db(p1.app.paths.memory, p1.app)
    con.execute("UPDATE ledger SET subject_id = 'TAMPERED' WHERE seq = 7")
    con.close()
    res = _run("memory", "verify")
    assert res.exit_code == 1 and "chain broken at seq 7" in res.output


def test_memory_show_delta_known_at_1000_local(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    res = _run("memory", "show", CASE, "--as-of", "2026-04-20T10:00-05:00")
    assert res.exit_code == 0, res.output
    assert "hobbyist" in res.output and "closed" in res.output
    assert "1: P1-DELTA-260419" in res.output and "10:00 local (15:00Z)" in res.output
    early = _run("memory", "show", CASE, "--as-of", "2026-04-20T14:00Z")
    assert "unknown" in early.output


def test_memory_times_need_an_offset(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    for args in (("memory", "show", CASE, "--as-of", "2026-04-20T10:00"),
                 ("memory", "delta", "--since", "yesterday")):  # fmt: skip
        res = _run(*args)
        assert res.exit_code == 1 and "offset" in res.output, res.output


def test_memory_demo_leaves_real_ledger_untouched(toy) -> None:
    assert _run("memory", "seed").exit_code == 0
    before = _head(toy)
    res = _run("memory", "demo")
    assert res.exit_code == 0, res.output
    assert "known then" in res.output and "known now" in res.output
    assert "pending" in res.output and "--approve" in res.output
    assert _head(toy) == before
    scratch = Path(toy.app.paths.cache) / "memory_demo.duckdb"
    with DuckCaseMemory(scratch, toy.app, read_only=True) as m:
        s = m.as_of(CASE, m.head().recorded_at)
        assert s.links == [] and m.verify_chain() is None
        assert {r["event_type"] for r in m.events(after=before.recorded_at)} == {
            "incident_recorded", "model_registered", "match_proposed"}  # fmt: skip


def test_memory_demo_approve_adds_members(toy) -> None:
    assert _run("memory", "seed").exit_code == 0
    res = _run("memory", "demo", "--approve", "--analyst", "duty")
    assert res.exit_code == 0, res.output
    scratch = Path(toy.app.paths.cache) / "memory_demo.duckdb"
    with DuckCaseMemory(scratch, toy.app, read_only=True) as m:
        proposed = [r["subject_id"] for r in m.events() if r["event_type"] == "match_proposed"]
        s = m.as_of(CASE, m.head().recorded_at)
    assert len(proposed) == 3
    assert set(s.members) == {"P1-DELTA-260419", *proposed} and s.pending == []
    assert {lk["actor"] for lk in s.links} == {"analyst:duty"}
    assert f"{len(s.members)}: P1-DELTA-260419" in res.output and "members_added" in res.output


def test_export_needs_approve_flag(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    n = _head(p1).seq
    res = _run("export", "--case", CASE)
    assert res.exit_code == 1 and "approval required" in res.output
    assert not Path(p1.app.paths.exports).exists() and _head(p1).seq == n


def test_export_and_verify_evidence_cli(p1) -> None:
    assert _run("memory", "seed").exit_code == 0
    res = _run("export", "--case", CASE, "--approve", "--at", "2026-08-28T12:00Z")
    assert res.exit_code == 0, res.output
    assert "manifest sha256" in res.output and "signed, key" in res.output
    (folder,) = Path(p1.app.paths.exports).iterdir()
    assert folder.name == f"{CASE}_20260828T120000"
    ok = _run("verify-evidence", str(folder))
    assert ok.exit_code == 0 and "PASS" in ok.output and "FAIL" not in ok.output, ok.output
    page = folder / "case.html"
    page.write_text(page.read_text() + "<!-- edited -->")
    bad = _run("verify-evidence", str(folder))
    assert bad.exit_code == 1 and "case.html" in bad.output and "FAIL" in bad.output
    missing = _run("verify-evidence", str(folder), "--ledger", str(folder / "none.duckdb"))
    assert "SKIP" in missing.output
    assert _run("verify-evidence", str(folder / "nope")).exit_code == 1


def test_memory_delta_cli(toy) -> None:
    assert _run("memory", "seed").exit_code == 0
    assert _run("memory", "demo", "--approve").exit_code == 0
    scratch = str(Path(toy.app.paths.cache) / "memory_demo.duckdb")
    res = _run("memory", "delta", "--since", "2026-08-28T00:00-05:00", "--ledger", scratch)
    assert res.exit_code == 0, res.output
    for g in ("incidents", "proposals", "links_approved", "models"):
        assert g in res.output, g
    bravo = _run("memory", "delta", "--since", "2026-08-28T00:00-05:00", "--ledger", scratch,
                 "--installation", "BRAVO")  # fmt: skip
    assert bravo.exit_code == 0 and "DEMO-BRAVO-0828" in bravo.output and "models" not in (
        bravo.output)  # fmt: skip


def test_memory_commands_need_a_ledger_or_data(cfg, tmp_path, monkeypatch) -> None:
    c = tmp_config(cfg, tmp_path)
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    for args in (("memory", "verify"), ("memory", "show", CASE, "--as-of", "2026-04-20T15:00Z"),
                 ("memory", "delta", "--since", "2026-04-20T15:00Z"),
                 ("export", "--case", CASE, "--approve")):  # fmt: skip
        res = _run(*args)
        assert res.exit_code == 1 and "memory seed" in res.output, (args, res.output)
    for args in (("memory", "seed"), ("memory", "reseed"), ("memory", "demo")):
        res = _run(*args)
        assert res.exit_code == 1 and "make data" in res.output, (args, res.output)
