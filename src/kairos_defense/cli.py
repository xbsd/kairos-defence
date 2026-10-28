"""``kairos-defense`` command-line entry point (Typer).

Commands not built yet are stubs: each says which build phase (SPEC §20) implements it. Stubs accept
and ignore any options, so every Makefile target already runs end to end.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kairos_defense import __version__

console = Console(stderr=True, width=None if sys.stderr.isatty() else 120)

app = typer.Typer(
    name="kairos-defense",
    help="Kairos Defense: cross-installation drone pattern memory (demo; synthetic data only).",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

# name -> (phase that implements it, one-line help)
STUBS: dict[str, tuple[str, str]] = {
    "models": ("4", "Train the fusion model and calibrate DTW."),
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


def _load_config(config: str):
    """Load and validate the config folder; print a readable error and exit 1 if it is bad."""
    from kairos_defense.config import ConfigError, load_config

    try:
        return load_config(config)
    except ConfigError as exc:
        console.print(f"[red]config error:[/red] {exc}")
        raise typer.Exit(1) from exc


def _need_data(cfg) -> None:
    if not Path(cfg.app.paths.duckdb).exists():
        console.print(f"[red]no data:[/red] {cfg.app.paths.duckdb} is missing; run `make data`.")
        raise typer.Exit(1)


@app.command()
def gen(
    seed: int | None = typer.Option(None, help="Global seed (default: the seed in world.yaml)."),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
    figures: bool = typer.Option(True, "--figures/--no-figures", help="Write sample figures."),
) -> None:
    """Generate the synthetic world, flights, swarms, sensors, paperwork and truth (seeded)."""
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
    swarms = sum(i.is_swarm for i in g.incidents)
    table.add_row("remote_id", f"{len(g.tables['remote_id']):,}", "")
    table.add_row("swarm incidents", f"{swarms:,}", "")
    table.add_row("drones flown", f"{len(g.results):,}", "")
    table.add_row("drones not tracked", f"{missed:,}", "")
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


@app.command()
def index(config: str = typer.Option("config", help="Folder with the five YAML files.")) -> None:
    """Build features, signatures and LanceDB windows for every history track (reports: phase 5)."""
    from kairos_defense.features.build import build_index

    cfg = _load_config(config)
    _need_data(cfg)
    s = build_index(cfg)
    table = Table(title="kairos-defense index", title_justify="left")
    table.add_column("Item")
    table.add_column("Value", justify="right")
    table.add_row("tracks", f"{s.tracks:,}")
    table.add_row("history tracks indexed", f"{s.history_tracks - len(s.failed):,}")
    table.add_row("live tracks skipped", f"{s.live_tracks_skipped:,}")
    table.add_row("track_features rows", f"{s.feature_rows:,}")
    table.add_row(
        "gap seconds", f"{s.gap_seconds:,} ({s.gap_seconds / max(s.feature_rows, 1):.1%})"
    )
    table.add_row("track_signatures rows", f"{s.signatures:,}")
    for size, n in s.windows_by_size.items():
        table.add_row(f"flight_windows {size} s", f"{n:,}")
    table.add_row("targets", ", ".join(f"{k} {v:,}" for k, v in s.target_kinds.items()))
    table.add_row("loiter direction", ", ".join(f"{k} {v:,}" for k, v in s.loiter_dirs.items()))
    table.add_row("RF family unknown", f"{s.rf_unknown:,}")
    table.add_row("Remote ID present", f"{s.rid_present:,}")
    if s.failed:
        table.add_row("[red]failed[/red]", ", ".join(s.failed))
    table.add_row("elapsed", f"{s.elapsed_s:.1f} s")
    console.print(table)
    console.print(f"wrote track_features and track_signatures to {cfg.app.paths.duckdb}, "
                  f"flight_windows to {cfg.app.paths.lancedb}")  # fmt: skip


@app.command()
def match(
    incident: str = typer.Option(..., help="Incident to match, e.g. DEMO-BRAVO-0828."),
    at: int = typer.Option(..., help="Seconds after the track's first radar point (T)."),
    method: str = typer.Option("euclidean", help="euclidean (phase 3) or dtw (phase 4)."),
    track: str | None = typer.Option(None, help="Track of the incident (default: its first)."),
    top: int = typer.Option(10, help="How many matches to show."),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
) -> None:
    """Match an incident's track, seen T seconds in, against every earlier track (no look-ahead)."""
    from datetime import timedelta

    from kairos_defense.match.baseline import euclidean_matches
    from kairos_defense.match.query import load_query
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceVectorStore

    if method != "euclidean":
        console.print(f"[red]method {method!r} is not built yet:[/red] phase 4 adds dtw.")
        raise typer.Exit(1)
    cfg = _load_config(config)
    _need_data(cfg)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        tracks = store.sql(
            "SELECT DISTINCT track_id FROM track_points WHERE incident_id = $i ORDER BY track_id",
            {"i": incident},
        ).track_id.tolist()
        if not tracks or (track is not None and track not in tracks):
            console.print(f"[red]unknown incident or track:[/red] {track or incident}")
            raise typer.Exit(1)
        if at < cfg.scoring.live.min_track_s:
            wait = cfg.scoring.live.min_track_s
            console.print(f"[yellow]T+{at} s is below min_track_s ({wait:g} s): "
                          "the live matcher would wait.[/yellow]")  # fmt: skip
        offsets = dict(
            store.sql(
                "SELECT installation_id, utc_offset_hours FROM installations "
                "JOIN regions USING (region_id)"
            ).itertuples(index=False)
        )
        t0 = time.perf_counter()
        q = load_query(store, track or tracks[0], at, cfg.scoring)
        matches = euclidean_matches(q, LanceVectorStore(cfg.app.paths.lancedb), cfg.scoring)
        elapsed = time.perf_counter() - t0

    def local(ts, inst: str) -> str:
        return f"{ts + timedelta(hours=offsets[inst]):%Y-%m-%d %H:%M}"

    console.print(
        f"query {q.track_id} at T+{q.at_s} s · {len(q.features)} s seen · window {q.window_s} s"
        f" ({q.rows_used} s used) · target {q.target.asset_id} · first contact "
        f"{local(q.start_ts, q.installation_id)} local · {len(matches)} candidates · "
        f"{elapsed * 1000:.0f} ms"
    )
    table = Table(title=f"euclidean matches for {incident}", title_justify="left")
    for col in ("#", "track", "base", "start (local)", "score", "d²", "window"):
        table.add_column(col, justify="right" if col in ("#", "score", "d²") else "left")
    for i, m in enumerate(matches[:top], 1):
        table.add_row(str(i), m.track_id, m.installation_id, local(m.start_ts, m.installation_id),
                      f"{m.score:.3f}", f"{m.features['euclidean_d2']:.3f}",
                      f"{int(m.features['window_s'])} s @ {m.window_offset_s} s")  # fmt: skip
    console.print(table)
    if not matches:
        console.print("no earlier track to match (nothing started before this one)")


@app.command(name="eval")
def eval_(
    baseline: bool = typer.Option(False, "--baseline", help="Write reports/baseline.json."),
    method: str = typer.Option("euclidean", help="Matching method (euclidean in phase 3)."),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
) -> None:
    """Run the evaluation harness (§19) and write reports/eval_<date>.md and .json."""
    from kairos_defense.eval.harness import METHODS, evaluate
    from kairos_defense.eval.report import gate, write_reports
    from kairos_defense.eval.truth import track_truth
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceVectorStore

    if method not in METHODS:
        console.print(f"[red]method {method!r} is not built yet:[/red] phase 4 adds dtw.")
        raise typer.Exit(1)
    cfg = _load_config(config)
    _need_data(cfg)
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    if not lance.has("flight_windows"):
        console.print("[red]no index:[/red] flight_windows is missing; run `make index`.")
        raise typer.Exit(1)
    truth = track_truth(cfg.app)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        run = evaluate(cfg, store, lance, truth, method)
    md, js, s = write_reports(run, cfg.app.paths.reports)
    m, n = s["metrics"], s["counts"]

    def f(v, pct: bool = False) -> str:
        return "-" if v is None else (f"{v:.0%}" if pct else f"{v:.3f}")

    table = Table(title=f"kairos-defense eval · {method}", title_justify="left")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row(
        "prober queries (unanswerable)", f"{n['prober_queries']} ({n['prober_unanswerable']})"
    )
    table.add_row("copycat queries (unanswerable)",
                  f"{n['copycat_queries']} ({n['copycat_unanswerable']})")  # fmt: skip
    table.add_row("Recall@5 at T=120 s", f(m["recall_at_5_t120"]))
    table.add_row("MRR at T=120 s", f(m["mrr_t120"]))
    table.add_row("time to match (top 3 by T=90 s)", f(m["time_to_match_t90"], True))
    table.add_row("copycat-first at T=120 s", f(m["copycat_first_t120"], True))
    table.add_row("Recall@5 at T=120 s, copycats", f(m["recall_at_5_t120_copycats"]))
    for stage in ("query_build", "prefilter", "end_to_end"):
        p50, p95 = m[f"latency_{stage}_p50_ms"], m[f"latency_{stage}_p95_ms"]
        table.add_row(f"latency {stage.replace('_', ' ')} p50 / p95",
                      "-" if p50 is None else f"{p50:.0f} / {p95:.0f} ms")  # fmt: skip
    for r in s["demo"]:
        table.add_row(f"demo {r['key']}", f"{r['status']}: {r['observed']}")
    table.add_row("elapsed", f"{s['elapsed_s']:.1f} s")
    console.print(table)
    console.print(f"wrote {md} and {js}")
    reports = Path(cfg.app.paths.reports)
    if baseline:
        import json

        (reports / "baseline.json").write_text(json.dumps(s, indent=1, default=str) + "\n")
        console.print(f"wrote {reports / 'baseline.json'}")
        return
    problems = gate(s, reports / "baseline.json")
    for p in problems:
        console.print(f"[red]{p}[/red]")
    if problems:
        raise typer.Exit(1)


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
