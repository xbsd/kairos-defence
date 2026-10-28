"""``kairos-defense`` command-line entry point (Typer).

Commands not built yet are stubs: each says which build phase (SPEC §20) implements it. Stubs accept
and ignore any options, so every Makefile target already runs end to end.
"""

from __future__ import annotations

import time

import typer
from rich.console import Console
from rich.table import Table

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


@app.command()
def gen(
    seed: int | None = typer.Option(None, help="Global seed (default: the seed in world.yaml)."),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
    figures: bool = typer.Option(True, "--figures/--no-figures", help="Write sample figures."),
) -> None:
    """Generate the synthetic world, flights, radar and truth from scratch (seeded)."""
    from kairos_defense.config import ConfigError, load_config
    from kairos_defense.sim.datacard import EXPECTED, volumes, write_data_card
    from kairos_defense.sim.generate import generate
    from kairos_defense.sim.writers import write_all

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        console.print(f"[red]config error:[/red] {exc}")
        raise typer.Exit(1) from exc
    t0 = time.perf_counter()
    g = generate(cfg, seed)
    write_all(cfg.app, g.tables, g.truth)
    card = write_data_card(cfg, g, figures=figures)
    elapsed = time.perf_counter() - t0

    table = Table(title=f"kairos-defense gen --seed {g.seed}", title_justify="left")
    table.add_column("Item")
    table.add_column("Value", justify="right")
    table.add_column("Expected (§8.11)", justify="right")
    for k, v in volumes(g).items():
        table.add_row(k, f"{v:,}", f"≈{EXPECTED[k]:,}")
    missed = sum(not r.detected for r in g.results)
    table.add_row("flights flown", f"{len(g.results):,}", "")
    table.add_row("flights not detected", f"{missed:,}", "")
    if g.live is not None:
        lt = g.live
        est = "never" if lt.orbit_established_s is None else f"T+{lt.orbit_established_s:.0f} s"
        table.add_row(
            "live first contact", f"{lt.first_contact_local:%H:%M:%S}", "21:39:30-21:40:30"
        )
        table.add_row("live orbit established", est, "T+65-100 s")
    table.add_row("elapsed", f"{elapsed:.1f} s", "")
    console.print(table)
    console.print(f"wrote {cfg.app.paths.duckdb}, the truth file and {card}")


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
