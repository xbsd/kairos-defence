"""``kairos-defense`` command-line entry point (Typer).

Phase 0 ships stubs: each command says which build phase (SPEC §20) implements it. Stubs accept and
ignore any options, so Makefile targets such as ``make data`` already run end to end.
"""

from __future__ import annotations

import typer
from rich.console import Console

from kairos_defense import __version__

console = Console(stderr=True)

app = typer.Typer(
    name="kairos-defense",
    help="Kairos Defense: cross-installation drone pattern memory (demo; synthetic data only).",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

# name -> (phase that implements it, one-line help)
STUBS: dict[str, tuple[str, str]] = {
    "gen": ("1", "Generate the synthetic world, flights, sensors and truth (seeded)."),
    "index": ("3", "Build features, signatures and LanceDB indexes (reports from phase 5)."),
    "models": ("4", "Train the fusion model and calibrate DTW."),
    "eval": ("3", "Run the evaluation harness and write reports/eval_<date>.md."),
    "match": ("3", "Match an incident against history (euclidean in phase 3, dtw in phase 4)."),
    "recall": ("5", "Retrieve past reports for an incident's matches (hybrid search)."),
    "forecast": ("5", "Forecast the recovery area of an incident from its analogs."),
    "replay": ("7", "Replay a live incident; --precompute and --reset."),
    "memory": ("6", "Case memory: seed, verify or reseed the ledger."),
    "export": ("6", "Export a signed evidence package for a case (needs approval)."),
    "verify-evidence": ("6", "Verify an evidence package's hashes, signature and chain."),
    "fetch-models": ("5", "Download optional embedding models for offline use."),
    "api": ("7", "Serve the FastAPI backend (REST and WebSocket); --dump-openapi."),
    "mcp": ("9", "Run the MCP server over stdio."),
}

_PASS_THROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}


def _make_stub(name: str, phase: str) -> typer.models.CommandFunctionType:
    def stub(ctx: typer.Context) -> None:
        extra = f" (ignored: {' '.join(ctx.args)})" if ctx.args else ""
        console.print(f"[bold]{name}[/bold] is not built yet: phase {phase} implements it.{extra}")

    stub.__name__ = name.replace("-", "_")
    return stub


for _name, (_phase, _help) in STUBS.items():
    app.command(name=_name, help=f"{_help} (phase {_phase})", context_settings=_PASS_THROUGH)(
        _make_stub(_name, _phase)
    )


def _version(value: bool) -> None:
    if value:
        console.print(f"kairos-defense {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    """Kairos Defense command line."""


if __name__ == "__main__":
    app()
