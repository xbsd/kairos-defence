"""``kairos-defense simulate`` and ``live check|reset|status`` (D-182, D-183)."""

from __future__ import annotations

from typer.testing import CliRunner

from kairos_defense.cli import app

runner = CliRunner()


def run(*args: str):
    return runner.invoke(app, list(args))


def test_simulate_dry_run_never_names_the_actor_off_a_terminal(tmp_path) -> None:
    r = run(
        "simulate",
        "--scenario",
        "returning-prober",
        "--actor",
        "P3",
        "--base",
        "ECHO",
        "--seed",
        "5",
        "--dry-run",
        "--live-mode-dir",
        str(tmp_path),
    )
    assert r.exit_code == 0, r.output
    first = r.output.splitlines()[0]
    assert first.startswith("live scenario returning-prober at ECHO: seed 5, launch 2026-09-01")
    assert "P3" not in r.output and "Munitions" not in r.output
    assert "dry run: nothing sent, no ground truth written, the clock not moved" in r.output
    assert not (tmp_path / "clock.json").exists()


def test_simulate_show_actor_names_it(tmp_path) -> None:
    r = run(
        "simulate",
        "--scenario",
        "returning-prober",
        "--actor",
        "P3",
        "--base",
        "ECHO",
        "--seed",
        "5",
        "--dry-run",
        "--show-actor",
        "--live-mode-dir",
        str(tmp_path),
    )
    assert r.exit_code == 0 and "flown by P3 (Munitions figure-eight)" in r.output


def test_simulate_refusals_hide_the_actor_off_a_terminal(tmp_path) -> None:
    r = run(
        "simulate",
        "--scenario",
        "returning-prober",
        "--actor",
        "P3",
        "--base",
        "BRAVO",
        "--dry-run",
        "--live-mode-dir",
        str(tmp_path),
    )
    assert r.exit_code == 2 and "scenario refused" in r.output and "P3" not in r.output
    r = run("simulate", "--scenario", "nope", "--dry-run", "--live-mode-dir", str(tmp_path))
    assert r.exit_code == 2


def test_live_reset_and_status_on_a_scratch_folder(tmp_path) -> None:
    r = run("live", "status", "--live-mode-dir", str(tmp_path))
    assert r.exit_code == 0 and "no live incidents" in r.output
    r = run("live", "reset", "--live-mode-dir", str(tmp_path))
    assert r.exit_code == 0 and "the history and the ledger are untouched" in r.output


def test_live_check_help_and_bad_scenarios() -> None:
    r = run("live", "check", "--help")
    assert r.exit_code == 0 and "--scenarios" in r.output and "--speed" in r.output
    r = run("live", "check", "--scenarios", "bogus")
    assert r.exit_code == 2 and "unknown scenario" in r.output
