"""``kairos-defense recall``, ``forecast`` and ``fetch-models`` (phase 5, SPEC §12, §13).

Registered on the Typer app by ``cli.py`` (``register(app)``). Shared helpers (config loading,
fix-it exits, the console) are looked up on ``kairos_defense.cli`` at call time, so tests that
patch ``cli._load_config`` cover these commands too. Every failure a user can fix exits 1 with
the command that fixes it (D-075, D-091). Nothing here reads truth: the CLI prints no error.
"""

from __future__ import annotations

import math
from datetime import timedelta

import typer

from kairos_defense import geo

CONFIG_HELP = "Folder with the five YAML files."
METHOD_HELP = "dtw (DTW + fusion, phase 4) or euclidean (the §10.2 baseline)."


def _base():
    from kairos_defense import cli

    return cli


def _query_and_matches(store, lance, cfg, incident: str, track: str | None, at: int, method):
    """Resolve the incident's track, build the query at T and rank its matches; exits 1 on an
    unknown incident or track, missing models, a stale index or no DTW."""
    from kairos_defense.match.baseline import euclidean_matches
    from kairos_defense.match.candidates import IndexStale
    from kairos_defense.match.dtw_rerank import DtwUnavailable
    from kairos_defense.match.fusion import ModelError
    from kairos_defense.match.matcher import DtwMatcher, MatchResult
    from kairos_defense.match.query import load_query

    cli = _base()
    if method not in ("dtw", "euclidean"):
        cli.console.print(f"[red]unknown method {method!r}:[/red] use dtw or euclidean.")
        raise typer.Exit(1)
    tracks = store.sql(
        "SELECT DISTINCT track_id FROM track_points WHERE incident_id = $i ORDER BY track_id",
        {"i": incident},
    ).track_id.tolist()
    if not tracks or (track is not None and track not in tracks):
        cli.console.print(f"[red]unknown incident or track:[/red] {track or incident}")
        raise typer.Exit(1)
    try:
        matcher = (DtwMatcher(store, lance, cfg.scoring, cfg.app.paths.models)
                   if method == "dtw" else None)  # fmt: skip
    except (ModelError, IndexStale, DtwUnavailable) as exc:
        cli._fail(exc)
    q = load_query(store, track or tracks[0], at, cfg.scoring)
    if matcher is None:
        ms = euclidean_matches(q, lance, cfg.scoring)
        return q, MatchResult(ms, ms, {})
    return q, matcher.match(q)


def _offsets(store) -> dict[str, int]:
    rows = store.sql("SELECT installation_id, utc_offset_hours FROM installations "
                     "JOIN regions USING (region_id)")  # fmt: skip
    return dict(rows.itertuples(index=False))


def describe_center(fc, q) -> str:
    """Where the center lies from tonight's target centroid, e.g. "2,164 m at 320° (northwest)
    of BRAVO-fuel_farm"."""
    from kairos_defense.sim.lexicon import compass8

    c = q.target.centroid
    d = math.hypot(fc.center_x_m - c[0], fc.center_y_m - c[1])
    brg = float(geo.bearing(c, [fc.center_x_m, fc.center_y_m]))
    return f"{d:,.0f} m at {brg:.0f}° ({compass8(brg)}) of {q.target.asset_id}"


def forecast_cmd(
    incident: str = typer.Option(..., help="Incident to forecast, e.g. DEMO-BRAVO-0828."),
    at: int = typer.Option(..., help="Seconds after the track's first radar point (T)."),
    track: str | None = typer.Option(None, help="Track of the incident (default: its first)."),
    method: str = typer.Option("dtw", help=METHOD_HELP),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Forecast where an incident's drone will be recovered, from its analogs (§13)."""
    from kairos_defense.cli_tables import analogs_table
    from kairos_defense.forecast.analog import forecast
    from kairos_defense.store.duck import DuckTrackStore

    cli = _base()
    cfg = cli._load_config(config)
    cli._need_data(cfg)
    lance = cli._need_index(cfg)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        q, res = _query_and_matches(store, lance, cfg, incident, track, at, method)
        fc = forecast(store, q, res, cfg.scoring)
    cli.console.print(f"query {q.track_id} at T+{q.at_s} s · target {q.target.asset_id} · "
                      f"method {method} · {len(res.matches)} candidates")  # fmt: skip
    if fc is None:
        cli.console.print("no forecast: no match has a known recovery point (§9.4)")
        return
    cli.console.print(f"center ({fc.center_x_m:,.0f}, {fc.center_y_m:,.0f}) m region frame · "
                      f"{describe_center(fc, q)} · radius {fc.radius_m:,.0f} m · anchor "
                      f"{fc.anchor}")  # fmt: skip
    cli.console.print(analogs_table(fc))
    (x0, y0), (x1, y1) = fc.path[0], fc.path[-1]
    cli.console.print(f"exit path: {len(fc.path)} points from ({x0:,.0f}, {y0:,.0f}) to "
                      f"({x1:,.0f}, {y1:,.0f}) m")  # fmt: skip
    cli.console.print(f"roads crossing the zone: {', '.join(fc.roads) or 'none'}")


def recall_cmd(
    incident: str = typer.Option(..., help="Incident whose matches to look up."),
    at: int = typer.Option(..., help="Seconds after the track's first radar point (T)."),
    track: str | None = typer.Option(None, help="Track of the incident (default: its first)."),
    matches: int = typer.Option(3, help="How many matched incidents (best first)."),
    k: int | None = typer.Option(None, help="Reports per match (default: recall.k)."),
    query: str | None = typer.Option(None, help="Keyword text (default: tonight's, §12.3)."),
    method: str = typer.Option("dtw", help=METHOD_HELP),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Retrieve past reports for an incident's matches (hybrid search) with linked clues."""
    from kairos_defense.cli_tables import recall_table
    from kairos_defense.forecast.analog import forecast
    from kairos_defense.recall.embed import make_embedder
    from kairos_defense.recall.search import ReportRecall
    from kairos_defense.store.duck import DuckTrackStore

    cli = _base()
    cfg = cli._load_config(config)
    cli._need_data(cfg)
    lance = cli._need_index(cfg)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        index = cli._need_reports_index(cfg, store, lance)
        q, res = _query_and_matches(store, lance, cfg, incident, track, at, method)
        fc = forecast(store, q, res, cfg.scoring)
        rr = ReportRecall(store, index, lance, make_embedder(cfg.app), cfg.scoring)
        out = rr.for_matches(q, res, fc.roads if fc else (), n=matches, k=k, query=query)
        offsets = _offsets(store)
    cli.console.print(f"query {q.track_id} at T+{q.at_s} s · keyword text: {out.query_text!r}")
    zone = ("none" if fc is None else f"center ({fc.center_x_m:,.0f}, {fc.center_y_m:,.0f}) m, "
            f"radius {fc.radius_m:,.0f} m, roads: {', '.join(fc.roads) or 'none'}")  # fmt: skip
    cli.console.print(f"forecast zone: {zone}")

    def local(ms: int, inst: str) -> str:
        from kairos_defense.match.baseline import _ts

        return f"{_ts(ms) + timedelta(hours=offsets[inst]):%Y-%m-%d %H:%M}"

    for mr in out.matches:
        cli.console.print(recall_table(mr, local))
        sentences = sorted({s for r in mr.reports for c in r.clues for s in c.links})
        for s in sentences:
            cli.console.print(f"  link: {s}")
        if not mr.reports:
            cli.console.print("  no report in the filter window")


def fetch_models_cmd(
    model: str | None = typer.Option(None, help="Model (default: embeddings.fastembed_model)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Download the optional FastEmbed model into paths.cache (the only command that downloads)."""
    from kairos_defense.recall.embed import EmbedderUnavailable, fetch_model

    cli = _base()
    cfg = cli._load_config(config)
    try:
        path = fetch_model(cfg.app, model)
    except EmbedderUnavailable as exc:
        cli._fail(exc)
    cli.console.print(f"fetched {model or cfg.app.embeddings.fastembed_model} into {path}; set "
                      "embeddings.provider: fastembed and run `make index`")  # fmt: skip


def register(app: typer.Typer) -> None:
    app.command(name="forecast")(forecast_cmd)
    app.command(name="recall")(recall_cmd)
    app.command(name="fetch-models")(fetch_models_cmd)
