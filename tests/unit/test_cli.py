from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from kairos_defense.cli import STUBS, app

COMMANDS = [
    "gen", "index", "models", "eval", "match", "recall", "forecast", "replay",
    "memory", "export", "verify-evidence", "fetch-models", "api", "mcp",
]  # fmt: skip

runner = CliRunner()


def test_help_lists_every_command() -> None:
    res = runner.invoke(app, ["--help"], terminal_width=200)
    assert res.exit_code == 0
    listed = set(re.findall(r"^│ ([a-z-]+)\s", res.output, flags=re.M))
    assert set(COMMANDS) <= listed
    assert list(STUBS) == COMMANDS


@pytest.mark.parametrize("name", COMMANDS)
def test_stub_names_its_phase(name: str) -> None:
    res = runner.invoke(app, [name, "--incident", "DEMO-BRAVO-0828", "--at", "90"])
    assert res.exit_code == 0, res.output
    assert f"phase {STUBS[name][0]} implements it" in res.output


def test_version() -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "kairos-defense 0.0.1" in res.output
