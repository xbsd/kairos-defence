"""``kairos-defense mcp`` (phase 9, SPEC §18.2): the MCP server over stdio.

Registered on the Typer app by ``cli.py``. Stdout carries only the MCP protocol: nothing here
prints to it (the CLI console writes to stderr), and ``make mcp`` runs this silently. Read-only by
default; ``--allow-proposals`` adds ``propose_link`` (appends one ``match_proposed``, actor
``agent:<name>``) and ``propose_evidence_export`` (appends nothing). Data, models and the ledger
are opened on the first tool call, so a client can list the tools on a machine with no data.
"""

from __future__ import annotations

import typer

from kairos_defense.agent.context import API_DEFAULT

CONFIG_HELP = "Folder with the five YAML files."


def mcp_cmd(
    allow_proposals: bool = typer.Option(
        False, "--allow-proposals",
        help="Also offer propose_link and propose_evidence_export (a human still approves)."),
    agent: str = typer.Option("mcp", help="Name in the actor agent:<name> of proposals."),
    memory: str | None = typer.Option(None, help="Ledger file (default: paths.memory)."),
    api: str = typer.Option(API_DEFAULT, help="Running API the ledger tools ask while it holds "
                                              "the ledger (loopback only, D-010)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Run the MCP server over stdio (read-only tools unless --allow-proposals)."""
    import logging
    import re

    from kairos_defense import cli
    from kairos_defense.agent.context import ToolContext
    from kairos_defense.agent.mcp_server import serve

    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", agent):
        cli.console.print(f"[red]bad --agent {agent!r}:[/red] 1-64 of A-Z a-z 0-9 . _ -")
        raise typer.Exit(1)
    logging.basicConfig(level=logging.WARNING)  # logging goes to stderr; stdout is the protocol
    cfg = cli._load_config(config)
    serve(lambda: ToolContext(cfg, memory_path=memory, agent=agent, api_base=api),
          allow_proposals=allow_proposals)  # fmt: skip


def register(app: typer.Typer) -> None:
    app.command(name="mcp")(mcp_cmd)
