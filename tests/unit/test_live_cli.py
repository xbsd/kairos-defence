"""D-111: ``kairos-defense replay`` (list, --precompute, --reset) and the D-010 fallbacks of
``replay --reset`` and ``memory reseed`` while another process holds the file."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import kairos_defense.cli as cli
import kairos_defense.cli_live as cli_live
import kairos_defense.cli_memory as cli_memory
from kairos_defense.cli import app
from kairos_defense.live.loop import LiveLoop
from kairos_defense.store.live_duck import DuckLiveSink
from tests.conftest import with_paths

runner = CliRunner()


def _run(*args: str):
    return runner.invoke(app, list(args), terminal_width=250)


@pytest.fixture
def toy(toy_models, tmp_path, monkeypatch):
    c = with_paths(toy_models, tmp_path, "memory", "live", "cache", "exports", "key")
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    return c


def test_replay_lists_live_incidents(toy) -> None:
    res = _run("replay")
    assert res.exit_code == 0, res.output
    assert "DEMO-BRAVO-0828" in res.output and "0/95 stale" in res.output
    assert _run("replay", "--incident", "NOPE").exit_code == 1


def test_replay_precompute_then_fresh(toy, monkeypatch) -> None:
    real = LiveLoop.__init__

    def short(self, *a, **kw):  # two reruns keep the fast test fast (the full sweep is slow)
        real(self, *a, **kw)
        self.schedule = [45, 90]
        self.save_features = lambda: 0

    monkeypatch.setattr(LiveLoop, "__init__", short)
    res = _run("replay", "--precompute")
    assert res.exit_code == 0, res.output
    assert "2 computed, 0 cached" in res.output and "2/2 fresh" in res.output
    again = _run("replay", "--precompute")
    assert "0 computed, 2 cached" in again.output


def test_replay_reset_empties_live_tables(toy) -> None:
    from tests.unit.test_live_recorder import _pt

    with DuckLiveSink(toy.app.paths.live, toy.app) as sink:
        sink.append("live_points", [_pt(1), _pt(2)])
    res = _run("replay", "--reset")
    assert res.exit_code == 0, res.output
    assert "live_points (2 rows)" in res.output and "ledger is untouched" in res.output


def test_replay_reset_calls_api_when_locked(toy, monkeypatch) -> None:
    import duckdb

    def locked(*a, **kw):
        raise duckdb.IOException("Could not set lock on file: Conflicting lock is held")

    calls = []
    monkeypatch.setattr("kairos_defense.store.live_duck.DuckLiveSink", locked)

    def fake(base, path):
        calls.append(path)
        return {"reset": {"live_points": 7}}

    monkeypatch.setattr(cli_live, "call_api", fake)
    res = _run("replay", "--reset")
    assert res.exit_code == 0, res.output
    assert calls == ["/api/admin/reset"] and "through http://127.0.0.1:8000" in res.output
    monkeypatch.setattr(cli_live, "call_api", lambda base, path: None)
    res = _run("replay", "--reset")
    assert res.exit_code == 1 and "no API answers" in res.output


def test_memory_reseed_calls_api_when_locked(toy, monkeypatch) -> None:
    from kairos_defense.store.ledger_duck import LedgerLocked

    def locked(*a, **kw):
        raise LedgerLocked("in use")

    monkeypatch.setattr("kairos_defense.store.ledger_duck.check_unlocked", locked)
    doc = {"rows": 10, "head_seq": 10, "head_hash": "ab"}
    monkeypatch.setattr(cli_memory, "call_api", lambda base, path: doc)
    res = _run("memory", "reseed")
    assert res.exit_code == 0, res.output
    out = " ".join(res.output.split())
    assert "POST /api/admin/reseed" in out and "head seq 10" in out


def test_memory_reseed_exits_1_when_locked_and_no_api(toy, monkeypatch) -> None:
    from kairos_defense.store.ledger_duck import LedgerLocked

    def locked(*a, **kw):
        raise LedgerLocked("in use")

    monkeypatch.setattr("kairos_defense.store.ledger_duck.check_unlocked", locked)
    monkeypatch.setattr(cli_memory, "call_api", lambda base, path: None)
    res = _run("memory", "reseed")
    assert res.exit_code == 1 and "ledger in use" in res.output


def test_call_api_refuses_non_loopback() -> None:
    import typer

    with pytest.raises(typer.BadParameter):
        cli_memory.call_api("http://example.com", "/api/admin/reset")
    assert cli_memory.call_api("http://127.0.0.1:9", "/api/admin/reset", 0.5) is None


def test_api_exports_option_reaches_services_and_reload_env(toy, monkeypatch) -> None:
    import os

    import uvicorn

    import kairos_defense.api.app as app_mod

    seen: dict = {}

    def fake_create(cfg=None, **kw):
        seen.update(kw)
        return object()

    monkeypatch.setattr(app_mod, "create_app", fake_create)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: seen.__setitem__("run", (a, k)))
    for k in ("KD_CONFIG", "KD_STATIC", "KD_MEMORY", "KD_LIVE_DB", "KD_EXPORTS"):
        monkeypatch.setenv(k, "")  # the CLI writes them; monkeypatch restores them afterwards
    r = _run("api", "--exports", "data/cache/e2e/exports", "--port", "8799")
    assert r.exit_code == 0, r.output
    assert seen["exports_path"] == "data/cache/e2e/exports"
    r = _run("api", "--reload", "--exports", "scratch/exports")
    assert r.exit_code == 0, r.output
    assert os.environ["KD_EXPORTS"] == "scratch/exports"
    assert seen["run"][0][0] == "kairos_defense.api.app:factory"


def test_api_time_scale_option_reaches_create_app(toy, monkeypatch) -> None:
    """D-168: `api --time-scale` slows replays for screen capture; outside [0.05, 1] it exits 2."""
    import os

    import uvicorn

    import kairos_defense.api.app as app_mod

    seen: dict = {}

    def fake_create(cfg=None, **kw):
        seen.update(kw)
        return object()

    monkeypatch.setattr(app_mod, "create_app", fake_create)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: seen.__setitem__("run", (a, k)))
    for k in ("KD_CONFIG", "KD_STATIC", "KD_MEMORY", "KD_LIVE_DB", "KD_EXPORTS", "KD_TIME_SCALE"):
        monkeypatch.setenv(k, "")
    r = _run("api", "--time-scale", "0.2", "--port", "8799")
    assert r.exit_code == 0, r.output
    assert seen["time_scale"] == pytest.approx(0.2)
    assert "slow motion" in r.output
    r = _run("api", "--port", "8799")
    assert r.exit_code == 0 and seen["time_scale"] == 1.0 and "slow motion" not in r.output
    r = _run("api", "--reload", "--time-scale", "0.25")
    assert r.exit_code == 0, r.output
    assert os.environ["KD_TIME_SCALE"] == "0.25"
    assert _run("api", "--time-scale", "0.01").exit_code == 2
