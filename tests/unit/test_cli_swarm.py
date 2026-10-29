"""`kairos-defense swarm` (phase 9, SPEC §14, D-152) on the swarm nights."""

from __future__ import annotations

from typer.testing import CliRunner

from kairos_defense.cli import app

runner = CliRunner()


def test_swarm_cli_ranks_s1_golf_first(swarm_index, monkeypatch) -> None:
    import kairos_defense.cli as cli

    c, _ = swarm_index
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    res = runner.invoke(app, ["swarm", "--incident", "DEMO-SWARM-ECHO-0614"], terminal_width=200)
    assert res.exit_code == 0, res.output
    assert "S1-GOLF-260503" in res.output and "detected yes" in res.output
    first = next(line for line in res.output.splitlines() if "│ 1 " in line or "│  1 " in line)
    assert "S1-GOLF-260503" in first


def test_swarm_cli_refuses_unknown_and_single_track_incidents(swarm_index, monkeypatch) -> None:
    import kairos_defense.cli as cli

    c, _ = swarm_index
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    res = runner.invoke(app, ["swarm", "--incident", "NO-SUCH"], terminal_width=200)
    assert res.exit_code == 1 and "unknown incident" in res.output
    res = runner.invoke(app, ["swarm", "--incident", "P1-DELTA-260419"], terminal_width=200)
    assert res.exit_code == 1 and "not a swarm" in res.output
