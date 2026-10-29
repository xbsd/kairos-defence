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
    "replay": ("7", "Replay a live incident; --precompute and --reset."),
    "memory": ("6", "Case memory: seed, verify or reseed the ledger."),
    "export": ("6", "Export a signed evidence package for a case (needs approval)."),
    "verify-evidence": ("6", "Verify an evidence package's hashes, signature and chain."),
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


def _need_index(cfg):
    """The LanceDB store, or exit 1 when ``flight_windows`` is missing."""
    from kairos_defense.store.lance import LanceVectorStore

    lance = LanceVectorStore(cfg.app.paths.lancedb)
    if not lance.has("flight_windows"):
        console.print("[red]no index:[/red] flight_windows is missing; run `make index`.")
        raise typer.Exit(1)
    return lance


def _need_reports_index(cfg, store, lance):
    """The ``ReportIndex``, or exit 1 when LanceDB ``reports`` is missing or stale (D-084)."""
    from kairos_defense.recall.embed import EmbedderUnavailable, make_embedder
    from kairos_defense.recall.index import ReportIndexStale, check_reports_index
    from kairos_defense.store.lance import REPORTS_TABLE, LanceReportIndex

    if not lance.has(REPORTS_TABLE):
        console.print(
            "[red]no reports index:[/red] the reports table is missing; run `make index`."
        )
        raise typer.Exit(1)
    try:
        check_reports_index(store, lance, make_embedder(cfg.app))
    except (EmbedderUnavailable, ReportIndexStale) as exc:
        _fail(exc)
    return LanceReportIndex(cfg.app.paths.lancedb)


def _fail(exc: Exception) -> None:
    """Print a model, index or DTW error readably and exit 1 (D-075)."""
    console.print(f"[red]{type(exc).__name__}:[/red] {exc}")
    raise typer.Exit(1) from exc


METHOD_HELP = "dtw (DTW + fusion, phase 4) or euclidean (the §10.2 baseline)."


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
    """Build features, signatures and LanceDB windows for every history track, then the report
    index (LanceDB reports with full-text search) and report_clues."""
    from kairos_defense.features.build import build_index
    from kairos_defense.recall.embed import EmbedderUnavailable
    from kairos_defense.recall.index import build_reports_index

    cfg = _load_config(config)
    _need_data(cfg)
    s = build_index(cfg)
    try:
        r = build_reports_index(cfg)
    except EmbedderUnavailable as exc:
        _fail(exc)
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
    table.add_row("reports indexed (live skipped)", f"{r.reports:,} ({r.live_reports_skipped:,})")
    table.add_row("report_clues rows", ", ".join(f"{k} {v:,}" for k, v in r.clues_by_type.items())
                  + f" ({r.clue_rows:,}, in {r.reports_with_clues:,} reports)")  # fmt: skip
    table.add_row("embedder", f"{r.embedder} ({r.dim} dims); full-text index on text")
    table.add_row("elapsed", f"{s.elapsed_s:.1f} s + reports {r.elapsed_s:.1f} s")
    console.print(table)
    console.print(f"wrote track_features, track_signatures and report_clues to "
                  f"{cfg.app.paths.duckdb}, flight_windows and reports to "
                  f"{cfg.app.paths.lancedb}")  # fmt: skip


@app.command()
def match(
    incident: str = typer.Option(..., help="Incident to match, e.g. DEMO-BRAVO-0828."),
    at: int = typer.Option(..., help="Seconds after the track's first radar point (T)."),
    method: str = typer.Option("dtw", help=METHOD_HELP),
    track: str | None = typer.Option(None, help="Track of the incident (default: its first)."),
    top: int = typer.Option(10, help="How many matches to show."),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
) -> None:
    """Match an incident's track, seen T seconds in, against every earlier track (no look-ahead)."""
    from datetime import timedelta

    from kairos_defense.match.baseline import euclidean_matches
    from kairos_defense.match.candidates import IndexStale
    from kairos_defense.match.dtw_rerank import DtwUnavailable
    from kairos_defense.match.fusion import ModelError
    from kairos_defense.match.matcher import DtwMatcher
    from kairos_defense.match.query import load_query
    from kairos_defense.store.duck import DuckTrackStore

    if method not in ("dtw", "euclidean"):
        console.print(f"[red]unknown method {method!r}:[/red] use dtw or euclidean.")
        raise typer.Exit(1)
    cfg = _load_config(config)
    _need_data(cfg)
    lance = _need_index(cfg)
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
        try:
            matcher = (DtwMatcher(store, lance, cfg.scoring, cfg.app.paths.models)
                       if method == "dtw" else None)  # fmt: skip
        except (ModelError, IndexStale, DtwUnavailable) as exc:
            _fail(exc)
        t0 = time.perf_counter()
        q = load_query(store, track or tracks[0], at, cfg.scoring)
        if matcher is None:
            matches, timings = euclidean_matches(q, lance, cfg.scoring), {}
        else:
            res = matcher.match(q)
            matches, timings = res.matches, res.timings
        elapsed = time.perf_counter() - t0

    def local(ts, inst: str) -> str:
        return f"{ts + timedelta(hours=offsets[inst]):%Y-%m-%d %H:%M}"

    console.print(
        f"query {q.track_id} at T+{q.at_s} s · {len(q.features)} s seen · window {q.window_s} s"
        f" ({q.rows_used} s used) · target {q.target.asset_id} · first contact "
        f"{local(q.start_ts, q.installation_id)} local · {len(matches)} candidates · "
        f"{elapsed * 1000:.0f} ms"
    )
    if matcher is not None:
        stages = " · ".join(f"{k.removesuffix('_ms')} {v:.0f}" for k, v in timings.items())
        console.print(f"model {matcher.model_version} · τ {matcher.tau:.3f} · ms: {stages}")
    from kairos_defense.cli_tables import match_table

    console.print(match_table(f"{method} matches for {incident}", matches[:top], method, local))
    if not matches:
        console.print("no earlier track to match (nothing started before this one)")


@app.command()
def models(config: str = typer.Option("config", help="Folder with the five YAML files.")) -> None:
    """Train the fusion model and calibrate DTW (§10.6) from history; writes models/*.json."""
    from kairos_defense.eval.training import train_models
    from kairos_defense.eval.truth import track_truth
    from kairos_defense.match.candidates import IndexStale
    from kairos_defense.match.dtw_rerank import DtwUnavailable, require_c
    from kairos_defense.store.duck import DuckTrackStore

    cfg = _load_config(config)
    _need_data(cfg)
    lance = _need_index(cfg)
    try:
        require_c()
        with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
            s = train_models(cfg, store, lance, track_truth(cfg.app))
    except (IndexStale, DtwUnavailable, ValueError) as exc:
        _fail(exc)
    from kairos_defense.cli_tables import models_table

    console.print(models_table(s))
    console.print("wrote " + " and ".join(str(p) for p in s.paths))


@app.command(name="eval")
def eval_(
    baseline: bool = typer.Option(False, "--baseline", help="Write reports/baseline.json."),
    method: str = typer.Option("dtw", help=METHOD_HELP),
    config: str = typer.Option("config", help="Folder with the five YAML files."),
) -> None:
    """Run the evaluation harness (§19) and write reports/eval_<date>.md and .json."""
    from kairos_defense.cli_tables import eval_table
    from kairos_defense.eval.harness import METHODS, evaluate
    from kairos_defense.eval.report import gate, write_reports
    from kairos_defense.eval.truth import track_truth
    from kairos_defense.match.candidates import IndexStale
    from kairos_defense.match.dtw_rerank import DtwUnavailable
    from kairos_defense.match.fusion import ModelError
    from kairos_defense.store.duck import DuckTrackStore

    if method not in METHODS:
        console.print(f"[red]unknown method {method!r}:[/red] use dtw or euclidean.")
        raise typer.Exit(1)
    cfg = _load_config(config)
    _need_data(cfg)
    lance = _need_index(cfg)
    truth = track_truth(cfg.app)
    try:
        with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
            reports = _need_reports_index(cfg, store, lance)
            run = evaluate(cfg, store, lance, truth, method, reports=reports)
    except (ModelError, IndexStale, DtwUnavailable) as exc:
        _fail(exc)
    md, js, s = write_reports(run, cfg.app.paths.reports)
    console.print(eval_table(s, method))
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


from kairos_defense import cli_recall  # noqa: E402  (phase 5 commands; imports cli lazily)

cli_recall.register(app)


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
