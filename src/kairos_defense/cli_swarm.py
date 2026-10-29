"""``kairos-defense swarm`` (phase 9, SPEC §14): rank the earlier swarms like one swarm incident.

Registered on the Typer app by ``cli.py`` (``register(app)``). Shared helpers are looked up on
``kairos_defense.cli`` at call time (as in ``cli_recall``). Fix-it exits (exit 1): missing data, a
missing swarm index (`make index`), an unknown incident or one that is not a swarm. Reads no truth
and writes nothing.
"""

from __future__ import annotations

import typer
from rich.table import Table

CONFIG_HELP = "Folder with the five YAML files."


def _base():
    from kairos_defense import cli

    return cli


def swarm_table(res) -> Table:
    """The ranked swarms of a ``SwarmResult``, one row per match."""
    q = res.query
    title = (f"kairos-defense swarm · {q.incident_id} · {q.n_drones} drones · "
             f"{len(q.descriptors)} s described · detected {'yes' if q.is_swarm else 'no'} "
             f"(together {q.together_s} s)")  # fmt: skip
    t = Table(title=title, title_justify="left")
    for col, just in (("#", "right"), ("Incident", "left"), ("Base", "left"),
                      ("Start (UTC)", "left"), ("Drones", "right"), ("Similarity", "right"),
                      ("Distance", "right"), ("Pace", "right")):  # fmt: skip
        t.add_column(col, justify=just)
    for m in res.matches:
        t.add_row(str(m.rank), m.incident_id, m.installation_id,
                  m.start_ts.strftime("%Y-%m-%d %H:%M"), str(m.n_drones), f"{m.similarity:.3f}",
                  f"{m.distance:.3f}", f"{m.warp_ratio:.2f}")  # fmt: skip
    return t


def swarm_cmd(
    incident: str = typer.Option(..., "--incident", help="A swarm incident id."),
    at: float | None = typer.Option(
        None, "--at", min=0, help="Seconds after first contact (default: the whole flight)."
    ),
    k: int = typer.Option(5, "--k", min=1, max=50, help="Matches to show."),
    config: str = typer.Option("config", "--config", help=CONFIG_HELP),
) -> None:
    """Rank earlier swarms by choreography (§14): descriptors, prefilter and DTW."""
    from kairos_defense.match.swarm import SwarmIndexMissing, SwarmMatcher
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceVectorStore

    cli = _base()
    cfg = cli._load_config(config)
    cli._need_data(cfg)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        inc = store.sql("SELECT is_swarm FROM incidents WHERE incident_id = $i", {"i": incident})
        if len(inc) != 1:
            cli.console.print(f"[red]unknown incident:[/red] {incident}")
            raise typer.Exit(1)
        if not bool(inc.iloc[0]["is_swarm"]):
            cli.console.print(f"[red]not a swarm incident:[/red] {incident} (use `match`)")
            raise typer.Exit(1)
        try:
            res = SwarmMatcher(store, LanceVectorStore(cfg.app.paths.lancedb), cfg.scoring).match(
                incident, at_s=at, k=k
            )
        except SwarmIndexMissing as exc:
            cli._fail(exc)
    cli.console.print(swarm_table(res))
    if not res.matches:
        cli.console.print("no earlier swarm to compare with (or too few seconds described)")


def register(app: typer.Typer) -> None:
    app.command("swarm")(swarm_cmd)
