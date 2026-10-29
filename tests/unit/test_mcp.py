"""The MCP server (SPEC §18.2, §20 phase 9 tests): the read-only tools are registered by default,
the proposal tools only with --allow-proposals, calls return JSON, and a real MCP client lists the
tools over stdio (with a deadline that kills the server, so a gate never hangs)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import anyio
import pytest
from typer.testing import CliRunner

from kairos_defense.agent import probe
from kairos_defense.agent.context import ToolContext
from kairos_defense.agent.mcp_server import build_server
from kairos_defense.agent.tools import PROPOSALS, READ_ONLY
from kairos_defense.cli import app

LIVE = "DEMO-BRAVO-0828"


def server_command() -> list[str]:
    """The installed ``kairos-defense mcp`` (the console script next to this Python)."""
    script = Path(sys.executable).with_name("kairos-defense")
    if script.exists():
        return [str(script), "mcp"]
    return [sys.executable, "-m", "kairos_defense.cli", "mcp"]


def tool_names(server) -> list[str]:
    return [t.name for t in anyio.run(server.list_tools)]


def no_context():
    raise AssertionError("listing tools must not build the ToolContext")


def test_mcp_server_registers_every_read_only_tool() -> None:
    """SPEC §20 phase 9: the server registers every read-only tool, and nothing else."""
    assert tool_names(build_server(no_context)) == list(READ_ONLY)


def test_mcp_allow_proposals_adds_the_two_proposal_tools() -> None:
    names = tool_names(build_server(no_context, allow_proposals=True))
    assert names == list(READ_ONLY + PROPOSALS) and len(names) == 8


def test_mcp_tools_carry_read_only_hints() -> None:
    tools = anyio.run(build_server(no_context, allow_proposals=True).list_tools)
    hints = {t.name: t.annotations.read_only_hint for t in tools}
    assert all(hints[n] for n in READ_ONLY) and not any(hints[n] for n in PROPOSALS)
    schema = next(t for t in tools if t.name == "find_similar_flights").input_schema
    assert schema["required"] == ["incident_id"] and "window_s" in schema["properties"]


@pytest.fixture
def mcp_ctx(live_kit, ledger_copy):
    made = []

    def factory():
        made.append(1)
        return ToolContext(live_kit.cfg, store=live_kit.store, vstore=live_kit.lance,
                           matcher=live_kit.matcher, recall=live_kit.recall, memory=ledger_copy,
                           lock=live_kit.lock, agent="mcp-test",
                           clock=lambda: datetime(2026, 8, 29, 2, 0))  # fmt: skip

    return factory, made


def _json(result) -> dict:
    assert not result.is_error
    return json.loads(result.content[0].text)


def test_mcp_call_tool_returns_json(mcp_ctx, ledger_copy) -> None:
    factory, made = mcp_ctx
    server = build_server(factory)
    n = ledger_copy.count()
    out = _json(anyio.run(server.call_tool, "find_similar_flights",
                          {"incident_id": LIVE, "window_s": 90}))  # fmt: skip
    assert out["incident_id"] == LIVE and out["matches"] and made == [1]
    bad = {"case_id": "CASE-P1-DELTA-260419", "as_of_ts": "2026-04-20"}  # no Z or offset
    err = _json(anyio.run(server.call_tool, "as_of_view", bad))
    assert "bad time" in err["error"]
    assert ledger_copy.count() == n and made == [1]  # one context, built once; nothing written


def test_mcp_proposal_appends_one_match_proposed(mcp_ctx, ledger_copy) -> None:
    factory, _ = mcp_ctx
    server = build_server(factory, allow_proposals=True)
    n = ledger_copy.count()
    out = _json(anyio.run(server.call_tool, "propose_link",
                          {"case_id": "CASE-P1-DELTA-260419", "incident_id": LIVE,
                           "rationale": "same orbit and approach"}))  # fmt: skip
    assert out["appended"] == 1 and ledger_copy.count() == n + 1
    row = ledger_copy.events()[-1]
    assert row["event_type"] == "match_proposed" and row["actor"] == "agent:mcp-test"


def test_mcp_stdio_client_lists_tools() -> None:
    """A real MCP client over stdio: ``kairos-defense mcp`` answers with the six read-only tools.
    The 60 s deadline kills the server process if it hangs."""
    names = anyio.run(probe.list_tools, server_command(), 60.0)
    assert names == list(READ_ONLY)


def test_probe_main_prints_names_and_checks_the_count(capsys) -> None:
    assert probe.main(["--timeout", "60", "--expect", "6", "--", *server_command()]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:6] == list(READ_ONLY) and out[-1].startswith("6 tools from")
    assert probe.main(["--timeout", "60", "--expect", "8", "--", *server_command(),
                       "--allow-proposals"]) == 0  # fmt: skip
    assert probe.main(["--timeout", "60", "--expect", "7", "--", *server_command()]) == 1
    assert probe.main(["--timeout", "20", "--", sys.executable, "-c", "pass"]) == 1
    with pytest.raises(SystemExit):
        probe.main(["--timeout", "5"])  # no command after --


def test_mcp_cli_help() -> None:
    res = CliRunner().invoke(app, ["mcp", "--help"], terminal_width=200)
    assert res.exit_code == 0, res.output
    assert "--allow-proposals" in res.output and "--agent" in res.output
    bad = CliRunner().invoke(app, ["mcp", "--agent", "no spaces"], terminal_width=200)
    assert bad.exit_code == 1 and "bad --agent" in bad.output
