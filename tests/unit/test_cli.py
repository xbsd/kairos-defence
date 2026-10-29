from __future__ import annotations

import re
from datetime import date

import pytest
from typer.testing import CliRunner

from kairos_defense.cli import STUBS, app

COMMANDS = [
    "gen", "index", "models", "eval", "match", "recall", "forecast", "replay",
    "memory", "export", "verify-evidence", "fetch-models", "api", "mcp",
]  # fmt: skip

runner = CliRunner()


BUILT = ["gen", "index", "models", "match", "eval", "recall", "forecast", "fetch-models"]


def test_help_lists_every_command() -> None:
    res = runner.invoke(app, ["--help"], terminal_width=200)
    assert res.exit_code == 0
    listed = set(re.findall(r"^│ ([a-z-]+)\s", res.output, flags=re.M))
    assert set(COMMANDS) <= listed
    assert [c for c in COMMANDS if c not in BUILT] == list(STUBS)


def test_gen_help() -> None:
    res = runner.invoke(app, ["gen", "--help"], terminal_width=200)
    assert res.exit_code == 0
    assert "--seed" in res.output and "--config" in res.output


def test_gen_reports_config_errors(tmp_path) -> None:
    res = runner.invoke(app, ["gen", "--config", str(tmp_path)])
    assert res.exit_code == 1
    assert "config error" in res.output


@pytest.mark.parametrize("name", list(STUBS))
def test_stub_names_its_phase(name: str) -> None:
    res = runner.invoke(app, [name, "--incident", "DEMO-BRAVO-0828", "--at", "90"])
    assert res.exit_code == 0, res.output
    assert f"phase {STUBS[name][0]} implements it" in res.output


def test_version() -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "kairos-defense 0.0.1" in res.output


def test_index_needs_data(cfg, tmp_path, monkeypatch) -> None:
    import kairos_defense.cli as cli
    from tests.conftest import tmp_config

    monkeypatch.setattr(cli, "_load_config", lambda _c: tmp_config(cfg, tmp_path))
    res = runner.invoke(app, ["index"])
    assert res.exit_code == 1 and "make data" in res.output


def test_match_dtw_needs_models(p1_index, monkeypatch) -> None:
    """Replaces the phase 3 stub check: without models, ``match --method dtw`` (the default)
    exits 1 and says how to make them."""
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: p1_index.cfg)
    for args in (["--method", "dtw"], []):
        res = runner.invoke(app, ["match", *args, "--incident", "DEMO-BRAVO-0828", "--at", "90"],
                            terminal_width=200)  # fmt: skip
        assert res.exit_code == 1 and "make models" in res.output, res.output
    res = runner.invoke(app, ["match", "--method", "cosine", "--incident", "X", "--at", "90"])
    assert res.exit_code == 1 and "unknown method" in res.output


def test_match_runs_on_the_p1_nights(p1_index, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: p1_index.cfg)
    res = runner.invoke(app, ["match", "--method", "euclidean", "--incident", "DEMO-BRAVO-0828",
                              "--at", "90"], terminal_width=200)  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "query DEMO-BRAVO-0828-T1 at T+90 s" in res.output and "P1-" in res.output


def test_match_dtw_runs_on_the_p1_nights(toy_models, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: toy_models)
    res = runner.invoke(app, ["match", "--incident", "DEMO-BRAVO-0828", "--at", "90", "--top",
                              "5"], terminal_width=250)  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "model fusion-v1" in res.output and "reasons" in res.output
    assert "P1-" in res.output and "Same RF family (FAM-07)" in res.output


def test_models_needs_index(cfg, tmp_path, monkeypatch) -> None:
    import kairos_defense.cli as cli
    from tests.conftest import tmp_config

    c = tmp_config(cfg, tmp_path)
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    res = runner.invoke(app, ["models"])
    assert res.exit_code == 1 and "make data" in res.output
    from kairos_defense.store.guard import connect_app_db

    connect_app_db(c.app.paths.duckdb, c.app).close()  # an empty database, no index
    res = runner.invoke(app, ["models"])
    assert res.exit_code == 1 and "make index" in res.output


def test_models_cli_trains_on_the_p1_nights(p1_index, tmp_path, monkeypatch) -> None:
    import kairos_defense.cli as cli
    import kairos_defense.eval.training as training
    from tests.conftest import with_models

    c = with_models(p1_index.cfg, tmp_path / "models")
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    split = training.TrainSplit(train_last=date(2026, 5, 31), valid_first=date(2026, 6, 1),
                                t_grid=(60, 120))  # fmt: skip
    monkeypatch.setattr(training, "TrainSplit", lambda: split)
    res = runner.invoke(app, ["models"], terminal_width=200)
    assert res.exit_code == 0, res.output
    assert (tmp_path / "models" / "fusion_v1.json").exists()
    assert (tmp_path / "models" / "dtw_calibration.json").exists()
    assert "coefficient shape_sim" in res.output and "validation ROC AUC" in res.output


def test_forecast_cli_runs_on_the_p1_nights(toy_models, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: toy_models)
    res = runner.invoke(app, ["forecast", "--incident", "DEMO-BRAVO-0828", "--at", "105"],
                        terminal_width=250)  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "query DEMO-BRAVO-0828-T1 at T+105 s" in res.output
    assert re.search(
        r"center \(.+\) m region frame · [\d,]+ m at \d+° \(\w+\) of BRAVO-", res.output
    )
    assert "radius" in res.output and "analogs" in res.output and "P1-" in res.output
    assert "exit path: 60 points" in res.output and "roads crossing the zone:" in res.output
    res = runner.invoke(app, ["forecast", "--incident", "DEMO-BRAVO-0828", "--at", "105",
                              "--method", "euclidean"], terminal_width=250)  # fmt: skip
    assert res.exit_code == 0, res.output


def test_recall_cli_runs_on_the_p1_nights(toy_models, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: toy_models)
    res = runner.invoke(app, ["recall", "--incident", "DEMO-BRAVO-0828", "--at", "120",
                              "--matches", "5"], terminal_width=250)  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "keyword text: 'drone" in res.output and "forecast zone:" in res.output
    assert "R-P1-DELTA-260419-1" in res.output and "security_forces" in res.output
    args = ["--incident", "DEMO-BRAVO-0828", "--at", "120", "--query", "white pickup", "--k", "1"]
    res = runner.invoke(app, ["recall", *args], terminal_width=250)
    assert res.exit_code == 0 and "keyword text: 'white pickup'" in res.output


def test_recall_needs_reports_index(p1_index, tmp_path, monkeypatch) -> None:
    import shutil

    import kairos_defense.cli as cli
    from kairos_defense.store.lance import LanceVectorStore

    lance_dir = tmp_path / "lancedb"
    shutil.copytree(p1_index.cfg.app.paths.lancedb, lance_dir)
    paths = p1_index.cfg.app.paths.model_copy(update={"lancedb": str(lance_dir)})
    c = p1_index.cfg.model_copy(
        update={"app": p1_index.cfg.app.model_copy(update={"paths": paths})}
    )
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    LanceVectorStore(lance_dir).db.drop_table("reports")
    for cmd in (["recall", "--incident", "DEMO-BRAVO-0828", "--at", "120"], ["eval"]):
        res = runner.invoke(app, cmd, terminal_width=200)
        assert res.exit_code == 1 and "make index" in res.output, (cmd, res.output)


def test_forecast_unknown_incident_exits_1(toy_models, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: toy_models)
    for cmd in ("forecast", "recall"):
        res = runner.invoke(app, [cmd, "--incident", "NOPE-0000", "--at", "105"])
        assert res.exit_code == 1 and "unknown incident or track" in res.output, res.output
    res = runner.invoke(app, ["forecast", "--incident", "DEMO-BRAVO-0828", "--track", "X-T9",
                              "--at", "105"])  # fmt: skip
    assert res.exit_code == 1 and "X-T9" in res.output
    res = runner.invoke(app, ["forecast", "--incident", "DEMO-BRAVO-0828", "--at", "105",
                              "--method", "cosine"])  # fmt: skip
    assert res.exit_code == 1 and "unknown method" in res.output


def test_forecast_needs_models(p1_index, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: p1_index.cfg)
    res = runner.invoke(app, ["forecast", "--incident", "DEMO-BRAVO-0828", "--at", "105"])
    assert res.exit_code == 1 and "make models" in res.output, res.output


def test_fetch_models_without_fastembed_exits_1(cfg, tmp_path, monkeypatch) -> None:
    import sys

    import kairos_defense.cli as cli
    from tests.conftest import tmp_config

    monkeypatch.setattr(cli, "_load_config", lambda _c: tmp_config(cfg, tmp_path))
    monkeypatch.setitem(sys.modules, "fastembed", None)
    res = runner.invoke(app, ["fetch-models"], terminal_width=200)
    assert res.exit_code == 1, res.output
    assert "uv sync --extra fastembed" in res.output
    assert not (tmp_path / "cache").exists()  # nothing downloaded or created
