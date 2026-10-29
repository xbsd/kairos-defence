"""``kairos-defense api`` and ``replay`` (phase 7, SPEC §16, D-111).

Registered on the Typer app by ``cli.py``. ``api`` serves the FastAPI app (``--dump-openapi``
writes the schema and exits). ``replay`` lists the live incidents, precomputes their results
(``--precompute``, D-013) or empties the ``live_*`` scratch tables (``--reset``); while the API
holds the live file, ``--reset`` goes through ``POST /api/admin/reset`` (D-010).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from kairos_defense.cli_memory import API_DEFAULT, call_api

CONFIG_HELP = "Folder with the five YAML files."


def _base():
    from kairos_defense import cli

    return cli


def api_cmd(
    host: str = typer.Option("127.0.0.1", help="Interface to bind (loopback by default, §2)."),
    port: int = typer.Option(8000, help="Port."),
    static: str | None = typer.Option(None, "--static", help="Serve this built web app at /."),
    reload: bool = typer.Option(False, "--reload", help="Reload on code changes (make dev)."),
    dump_openapi: str | None = typer.Option(None, "--dump-openapi",
                                            help="Write the OpenAPI JSON here and exit."),
    memory: str | None = typer.Option(None, help="Ledger file (default: paths.memory)."),
    live_db: str | None = typer.Option(None, "--live-db",
                                       help="live_* tables file (default: paths.live)."),
    reseed: bool = typer.Option(False, "--reseed", help="Reseed the ledger before serving."),
    exports: str | None = typer.Option(None, "--exports",
                                       help="Evidence export folder (default: paths.exports)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Serve the FastAPI backend: REST (§16.4), the replay WebSocket (§16.3) and the web app."""
    import os

    import uvicorn

    from kairos_defense.api.app import create_app

    cli = _base()
    if dump_openapi:
        out = Path(dump_openapi)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(create_app().openapi(), indent=1) + "\n")
        cli.console.print(f"wrote {out} ({len(create_app().openapi()['paths'])} paths)")
        return
    cfg = cli._load_config(config)
    cli._need_data(cfg)
    if static and not (Path(static) / "index.html").is_file():
        cli.console.print(f"[red]no web build:[/red] {static}/index.html is missing; run "
                          "`npm --prefix web run build`.")  # fmt: skip
        raise typer.Exit(1)
    if reload:
        os.environ.update({"KD_CONFIG": config, "KD_STATIC": static or "",
                           "KD_MEMORY": memory or "", "KD_LIVE_DB": live_db or "",
                           "KD_EXPORTS": exports or ""})  # fmt: skip
        src = str(Path(__file__).parent)
        uvicorn.run("kairos_defense.api.app:factory", factory=True, host=host, port=port,
                    reload=True, reload_dirs=[src], log_level="info")  # fmt: skip
        return
    app = create_app(
        cfg,
        static_dir=static,
        memory_path=memory,
        live_path=live_db,
        reseed=reseed,
        exports_path=exports,
    )
    cli.console.print(f"Kairos Defense API on http://{host}:{port}"
                      + (f" serving {static}" if static else ""))  # fmt: skip
    uvicorn.run(app, host=host, port=port, log_level="info", ws_ping_interval=20)


def _reset(cfg, api: str) -> None:
    import duckdb

    from kairos_defense.store.live_duck import DuckLiveSink

    cli = _base()
    path = Path(cfg.app.paths.live)
    try:
        with DuckLiveSink(path, cfg.app) as sink:
            out = sink.reset()
    except duckdb.IOException as exc:
        doc = call_api(api, "/api/admin/reset")
        if doc is None:
            cli.console.print(f"[red]live tables in use:[/red] {path} is held by another "
                              f"process and no API answers at {api}. Stop it and rerun "
                              f"(D-010). {exc}")  # fmt: skip
            raise typer.Exit(1) from exc
        cli.console.print(f"{path} is held by the running API: reset through {api} "
                          f"(POST /api/admin/reset, D-010)")  # fmt: skip
        out = doc.get("reset", {})
    cli.console.print("emptied " + ", ".join(f"{t} ({n:,} rows)" for t, n in out.items())
                      + f" in {path}; the ledger is untouched")  # fmt: skip


def replay_cmd(
    incident: str | None = typer.Option(None, help="One live incident (default: all)."),
    precompute: bool = typer.Option(False, "--precompute", help="Fill the result cache (D-013)."),
    force: bool = typer.Option(False, "--force", help="With --precompute: recompute everything."),
    reset: bool = typer.Option(False, "--reset", help="Empty the live_* scratch tables."),
    api: str = typer.Option(API_DEFAULT, help="Running API to reset through (D-010)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Live replays (§16.1): list them, precompute their results, or reset the live tables."""
    from kairos_defense.cli_tables import replay_table
    from kairos_defense.live.loop import LiveLoop
    from kairos_defense.live.precompute import fingerprint
    from kairos_defense.live.precompute import precompute as run_precompute
    from kairos_defense.live.replay import live_incident_ids, load_incident
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.live_cache import FileResultCache

    cli = _base()
    cfg = cli._load_config(config)
    if reset:
        _reset(cfg, api)
        if not precompute:
            return
    cli._need_data(cfg)
    cache = FileResultCache(Path(cfg.app.paths.cache) / "live")
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        ids = live_incident_ids(store)
        if incident is not None and incident not in ids:
            cli.console.print(f"[red]no live incident {incident}[/red]; live: {', '.join(ids)}")
            raise typer.Exit(1)
        matcher = recall = None
        if precompute:
            matcher, recall = _matching(cli, cfg, store)
        rows = []
        for iid in [incident] if incident else ids:
            inc = load_incident(store, iid)
            fp = fingerprint(store, cfg.scoring, cfg.app, iid)
            single = not inc.is_swarm
            loop = LiveLoop(inc, store, cfg.scoring, matcher=matcher, recall=recall,
                            cache=cache if precompute and single else None,
                            fingerprint=fp if precompute and single else None)  # fmt: skip
            summary = None
            if precompute and loop.matching:
                summary = run_precompute(loop, force=force)
            state = _state(cache, iid, fp, loop)
            rows.append((inc, loop, state, summary))
    cli.console.print(replay_table(rows))


def _state(cache, iid: str, fp: str, loop) -> dict:
    from kairos_defense.live.loop import result_name

    man = cache.get(iid, "manifest") or {}
    n = sum(cache.get(iid, result_name(r)) is not None for r in loop.schedule)
    fresh = man.get("fingerprint") == fp
    return {"results": n if fresh else 0, "fresh": fresh and n == len(loop.schedule),
            "features": man.get("features", 0) if fresh else 0}  # fmt: skip


def _matching(cli, cfg, store):
    from kairos_defense.match.candidates import IndexStale
    from kairos_defense.match.dtw_rerank import DtwUnavailable
    from kairos_defense.match.fusion import ModelError
    from kairos_defense.match.matcher import DtwMatcher
    from kairos_defense.recall.embed import make_embedder
    from kairos_defense.recall.search import ReportRecall

    lance = cli._need_index(cfg)
    try:
        matcher = DtwMatcher(store, lance, cfg.scoring, cfg.app.paths.models)
    except (ModelError, IndexStale, DtwUnavailable) as exc:
        cli._fail(exc)
    index = cli._need_reports_index(cfg, store, lance)
    return matcher, ReportRecall(store, index, lance, make_embedder(cfg.app), cfg.scoring)


def register(app: typer.Typer) -> None:
    app.command(name="api")(api_cmd)
    app.command(name="replay")(replay_cmd)
