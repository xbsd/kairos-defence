"""``kairos-defense simulate`` and ``kairos-defense live check|reset|status`` (phase 11, D-169).

``simulate`` is the separate simulator process: it plans and flies one scenario on the live
clock, records who flew through the sim writer (before the first detection leaves), and streams
only sensor detections to the app's ``/ws/ingest``. It names the actor only on an interactive
terminal or with ``--show-actor`` (D-182): a launched child's log never holds it. ``live check``
flies the scenarios headless against an in-process API and scores them (``eval.live_check``).
``live reset`` empties the live-mode folder (through ``POST /api/live/reset`` while the API holds
it); ``live status`` shows its incidents.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

import typer

from kairos_defense.cli_memory import API_DEFAULT, call_api

CONFIG_HELP = "Folder with the five YAML files."
live_app = typer.Typer(help="Live mode: score the scenarios, reset or inspect live data.",
                       no_args_is_help=True)  # fmt: skip


def _base():
    from kairos_defense import cli

    return cli


def _say(text: str) -> None:
    """One line of the simulator's report on stdout (its own terminal, or a launcher's log)."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _watch_parent(parent_pid: int, stop) -> None:
    def run() -> None:
        while True:
            if os.getppid() != parent_pid:
                stop()
                return
            time.sleep(1.0)

    threading.Thread(target=run, daemon=True, name="parent-watch").start()


def simulate_cmd(
    scenario: str = typer.Option(..., help="returning-prober, copycat, hobbyist, swarm-repeat "
                                           "or new-operator-twice."),
    base: str | None = typer.Option(None, help="Installation to fly at (default: the actor's)."),
    actor: str | None = typer.Option(None, help="Prober P1-P6 (or random), copycat C1-C2, "
                                                "swarm team S1-S2."),
    second_base: str | None = typer.Option(None, "--second-base",
                                           help="new-operator-twice: where flight 2 flies."),
    speed: float = typer.Option(1.0, min=1.0, max=50.0, help="Feed time per wall second."),
    seed: int | None = typer.Option(None, help="Seed (default: derived from the world seed and "
                                               "the launch counter, rule 4)."),
    url: str = typer.Option("ws://127.0.0.1:8000/ws/ingest", help="The app's ingest WebSocket."),
    live_mode_dir: str | None = typer.Option(None, "--live-mode-dir",
                                             help="Live-mode folder (its clock.json)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan and fly, print, send nothing."),
    show_actor: bool = typer.Option(False, "--show-actor",
                                    help="Name the actor even when output is not a terminal."),
    parent_pid: int | None = typer.Option(None, "--parent-pid", hidden=True,
                                          help="Stop when this process is gone (the API)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Fly one live scenario and stream its sensor detections to the app (D-169)."""
    from kairos_defense.sim import live_scenarios as ls
    from kairos_defense.sim import writers
    from kairos_defense.sim.live_clock import CLOCK_FILE, LiveClock
    from kairos_defense.sim.live_feed import FeedClient, FeedError
    from kairos_defense.sim.world import build_world

    cli = _base()
    cfg = cli._load_config(config)
    visible = show_actor or sys.stdout.isatty()
    folder = Path(live_mode_dir or cfg.app.paths.live_mode)
    clock = LiveClock(folder / CLOCK_FILE, cfg.world.calendar.end_local)
    seed = seed or clock.default_seed(cfg.world.seed)
    world = build_world(cfg, cfg.world.seed)
    try:
        sc = ls.build(cfg, world, clock, scenario, seed=seed, actor=actor, base=base,
                      second_base=second_base)  # fmt: skip
    except ls.ScenarioError as exc:
        cli.console.print(f"[red]scenario refused:[/red] {exc}" if visible else
                          "[red]scenario refused:[/red] its arguments do not fit (run it in a "
                          "terminal or with --show-actor for the reason)")  # fmt: skip
        raise typer.Exit(2) from exc
    det = sc.detections()
    site = world.sites[sc.bases[0]]
    local = ls.utc_ms_to_local(sc.start_ms, site.utc_offset_hours)
    _say(
        f"live scenario {sc.name} at {', '.join(sc.bases)}: seed {sc.seed}, launch "
        f"{local:%Y-%m-%d %H:%M:%S} local ({ls.iso_ms(sc.start_ms)}), speed {speed:g}x; "
        f"{len(sc.flights)} flight(s), {len(det)} detections over "
        f"{(sc.end_ms - sc.start_ms) / 1000:.0f} s of feed time",
    )
    if visible:
        _say(
            f"flown by {sc.actor_id} ({sc.nickname}): shown in this terminal only; the app "
            "receives sensor detections only",
        )
    if dry_run:
        _say("dry run: nothing sent, no ground truth written, the clock not moved")
        return
    clock.reserve(ls.reserve_until(sc, cfg))
    writers.record_live_flights(cfg.app, sc.truth_rows())  # before the first detection leaves
    client = FeedClient(url, det, start_ms=sc.start_ms, installations=list(sc.bases),
                        idle_close_s=cfg.scoring.live.idle_close_s, speed=speed)  # fmt: skip
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: client.stop())
    if parent_pid:
        _watch_parent(parent_pid, client.stop)
    try:
        s = client.run()
    except FeedError as exc:
        _say(f"feed failed: {exc}")
        raise typer.Exit(1) from exc
    _say(
        f"sent {s.sent} detections in {s.frames} frames over {s.wall_s:.1f} s "
        f"({s.feed_s:.0f} s of feed time): {s.accepted} accepted, {s.rejected} rejected"
        + (f" ({'; '.join(s.reasons)})" if s.reasons else "")
        + (f", {s.reconnects} reconnect(s)" if s.reconnects else "")
        + (" (stopped)" if s.stopped else ""),
    )


@live_app.command("check")
def check_cmd(
    scenarios: str = typer.Option("all", help="all, or a comma-separated list of scenarios."),
    speed: float = typer.Option(50.0, min=1.0, max=50.0, help="Simulator speed."),
    timeout: float = typer.Option(900.0, help="Seconds allowed per scenario."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Fly every scenario headless against an in-process API and score it (exit 0 all pass, 1
    only expectations missed, 2 crash or timeout)."""
    from kairos_defense.eval.live_check import SCENARIOS, run_live_check

    cli = _base()
    cfg = cli._load_config(config)
    names = list(SCENARIOS) if scenarios == "all" else [s.strip() for s in scenarios.split(",")]
    bad = [n for n in names if n not in SCENARIOS]
    if bad:
        cli.console.print(f"[red]unknown scenario(s):[/red] {', '.join(bad)}; use "
                          f"{', '.join(SCENARIOS)}")  # fmt: skip
        raise typer.Exit(2)
    raise typer.Exit(run_live_check(cfg, Path(config), names, speed, timeout))


@live_app.command("reset")
def reset_cmd(
    api: str = typer.Option(API_DEFAULT, help="Running API to reset through (D-010)."),
    live_mode_dir: str | None = typer.Option(None, "--live-mode-dir", help="Live-mode folder."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Remove every live-mode row: detections, live incidents, learned live history, results and
    vectors. The history and the ledger are untouched."""
    import duckdb

    from kairos_defense.store.lance import LanceVectorStore
    from kairos_defense.store.live_feed import VECTORS_DIR, DuckFeedStore

    cli = _base()
    cfg = cli._load_config(config)
    folder = Path(live_mode_dir or cfg.app.paths.live_mode)
    try:
        with DuckFeedStore(folder, cfg.app) as feed:
            out = feed.reset()
        n = LanceVectorStore(folder / VECTORS_DIR).drop("flight_windows")
    except duckdb.IOException as exc:
        doc = call_api(api, "/api/live/reset")
        if doc is None:
            cli.console.print(f"[red]live-mode store in use:[/red] {folder} is held by another "
                              f"process and no API answers at {api}. {exc}")  # fmt: skip
            raise typer.Exit(1) from exc
        cli.console.print(f"{folder} is held by the running API: reset through {api} "
                          "(POST /api/live/reset)")  # fmt: skip
        out, n = doc.get("reset", {}), doc.get("vectors", 0)
    cli.console.print("removed " + ", ".join(f"{t} ({k:,})" for t, k in out.items() if k)
                      + (", " if any(out.values()) else "nothing from the tables; ")
                      + f"{n:,} live window vector(s); the history and the ledger are "
                        "untouched")  # fmt: skip


@live_app.command("status")
def status_cmd(
    live_mode_dir: str | None = typer.Option(None, "--live-mode-dir", help="Live-mode folder."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """List the live incidents since the last reset and the learned live history."""
    import duckdb

    from kairos_defense.store.live_feed import DuckFeedStore

    cli = _base()
    cfg = cli._load_config(config)
    folder = Path(live_mode_dir or cfg.app.paths.live_mode)
    try:
        with DuckFeedStore(folder, cfg.app) as feed:
            inc = feed.incidents()
            learned = feed.count("track_signatures")
    except duckdb.IOException:
        cli.console.print(f"{folder} is held by the running API: see GET /api/live/status")
        return
    if inc.empty:
        cli.console.print(f"no live incidents in {folder}")
    for r in inc.itertuples():
        cli.console.print(f"{r.incident_id}  {r.installation_id}  {r.state:<7}  "
                          f"{r.n_tracks} track(s){'  swarm' if r.is_swarm else ''}")  # fmt: skip
    cli.console.print(f"{learned} learned live track(s)")


def register(app: typer.Typer) -> None:
    app.command(name="simulate")(simulate_cmd)
    app.add_typer(live_app, name="live")
