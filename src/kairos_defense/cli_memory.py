"""``kairos-defense memory …``, ``export`` and ``verify-evidence`` (phase 6, SPEC §15, D-100).

Registered on the Typer app by ``cli.py`` (``register(app)``); shared helpers are looked up on
``kairos_defense.cli`` at call time, so tests that patch ``cli._load_config`` cover these too.
Times given on the command line need ``Z`` or an offset (``2026-04-20T10:00-05:00``): a naive
time is ambiguous across three regions. Every failure a user can fix exits 1 with the fix.
Nothing here reads truth.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from kairos_defense.memory.canonical import utc_naive

CONFIG_HELP = "Folder with the five YAML files."
LEDGER_HELP = "Ledger file (default: paths.memory)."
API_DEFAULT = "http://127.0.0.1:8000"

memory_app = typer.Typer(help="Case memory (Kairos-lite): seed, reseed, verify, show, delta, "
                         "and the known-then / known-now demo.", no_args_is_help=True)  # fmt: skip


def _base():
    from kairos_defense import cli

    return cli


def parse_time(s: str) -> datetime:
    """Naive UTC from an ISO 8601 time with ``Z`` or an offset; exit 1 otherwise."""
    cli = _base()
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        t = None
    if t is None or t.tzinfo is None:
        cli.console.print(f"[red]bad time {s!r}:[/red] give an ISO 8601 time with Z or an offset, "
                          "e.g. 2026-04-20T10:00-05:00 or 2026-04-20T15:00Z")  # fmt: skip
        raise typer.Exit(1)
    return utc_naive(t)


def call_api(base: str, path: str, timeout_s: float = 30.0) -> dict | None:
    """``POST {base}{path}`` on a loopback API (D-010); the JSON reply, or None when nothing
    answers. Only 127.0.0.1 and localhost are allowed (offline, rule 5)."""
    import urllib.error
    import urllib.parse
    import urllib.request

    host = urllib.parse.urlparse(base).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise typer.BadParameter(f"--api must be a loopback URL, not {base!r}")
    req = urllib.request.Request(base.rstrip("/") + path, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode() or "{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _offsets(cfg) -> dict[str, int]:
    return {i.id: r.utc_offset_hours for r in cfg.world.regions for i in r.installations}


def _case_offset(rows: list[dict], case_id: str, cfg) -> int:
    f = next((r for r in rows if r["event_type"] == "case_opened" and r["case_id"] == case_id),
             None)  # fmt: skip
    base = (f["object_json"] or {}).get("base") if f else None
    return _offsets(cfg).get(base, 0)


def _open(cfg, ledger: str | None, *, read_only: bool, must_exist: bool = True):
    """The ledger adapter, or exit 1 (missing, locked, wrong schema)."""
    from kairos_defense.memory.ledger import LedgerError
    from kairos_defense.store.ledger_duck import DuckCaseMemory

    cli = _base()
    path = Path(ledger or cfg.app.paths.memory)
    if must_exist and not path.exists():
        cli.console.print(f"[red]no ledger:[/red] {path} is missing; run "
                          "`kairos-defense memory seed`.")  # fmt: skip
        raise typer.Exit(1)
    try:
        return DuckCaseMemory(path, cfg.app, read_only=read_only)
    except LedgerError as exc:
        cli._fail(exc)


def _seed_into(cfg, path: Path):
    from kairos_defense.memory.seed import SeedError, seed
    from kairos_defense.store.duck import DuckTrackStore

    cli = _base()
    cli._need_data(cfg)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        mem = _open(cfg, str(path), read_only=False, must_exist=False)
        try:
            return seed(mem, store, cfg.scenario), mem
        except SeedError as exc:
            mem.close()
            cli._fail(exc)


@memory_app.command("seed")
def seed_cmd(config: str = typer.Option("config", help=CONFIG_HELP)) -> None:
    """Seed an empty ledger with history as Kairos Defense would have learned it (§15.5)."""
    from kairos_defense.cli_memory_view import seed_table

    cli = _base()
    cfg = cli._load_config(config)
    s, mem = _seed_into(cfg, Path(cfg.app.paths.memory))
    mem.close()
    cli.console.print(seed_table(s, f"kairos-defense memory seed → {cfg.app.paths.memory}"))


def _remove(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            p.unlink()


@memory_app.command("reseed")
def reseed_cmd(
    api: str = typer.Option(API_DEFAULT, help="Running API to reset through when the ledger is "
                            "in use (D-010)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:  # fmt: skip
    """Rebuild the ledger from scratch (reset between demo runs, D-010): seed a temporary file,
    verify it, then replace the ledger. While the API holds the file, reseed through it."""
    from kairos_defense.cli_memory_view import seed_table
    from kairos_defense.memory.ledger import LedgerError
    from kairos_defense.memory.seed import SeedError
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.ledger_duck import LedgerLocked, check_unlocked, reseed_ledger

    cli = _base()
    cfg = cli._load_config(config)
    path = Path(cfg.app.paths.memory)
    try:
        check_unlocked(path, cfg.app)
    except LedgerLocked as exc:
        doc = call_api(api, "/api/admin/reseed")
        if doc is None:
            cli.console.print(f"[red]ledger in use:[/red] {path} is held by another process and "
                              f"no API answers at {api}. Stop `make demo` (or the API) and rerun, "
                              f"or reset through the running API (D-010). {exc}")  # fmt: skip
            raise typer.Exit(1) from exc
        cli.console.print(f"{path} is held by the running API: reseeded through {api} "
                          f"(POST /api/admin/reseed, D-010): {doc.get('rows', 0):,} rows, "
                          f"head seq {doc.get('head_seq')} hash {doc.get('head_hash')} "
                          "(verified)")  # fmt: skip
        return
    cli._need_data(cfg)
    try:
        with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
            s = reseed_ledger(path, cfg.app, store, cfg.scenario)
    except (LedgerError, SeedError) as exc:
        cli._fail(exc)
    cli.console.print(seed_table(s, f"kairos-defense memory reseed → {path} (verified)"))


@memory_app.command("verify")
def verify_cmd(ledger: str | None = typer.Option(None, help=LEDGER_HELP),
               config: str = typer.Option("config", help=CONFIG_HELP)) -> None:  # fmt: skip
    """Recompute every hash in seq order (§15.3); exit 1 at the first broken seq."""
    cli = _base()
    cfg = cli._load_config(config)
    with _open(cfg, ledger, read_only=True) as mem:
        n, broken, head = mem.count(), mem.verify_chain(), mem.head()
    where = ledger or cfg.app.paths.memory
    if broken is not None:
        cli.console.print(f"[red]chain broken at seq {broken}[/red] in {where} ({n:,} rows)")
        raise typer.Exit(1)
    if head is None:
        cli.console.print(f"chain intact: 0 rows in {where} (empty: run `memory seed`)")
        return
    cli.console.print(f"chain intact: {n:,} rows in {where}, head seq {head.seq:,} hash "
                      f"{head.hash} recorded {head.recorded_at:%Y-%m-%d %H:%M:%S}Z")  # fmt: skip


@memory_app.command("show")
def show_cmd(case: str = typer.Argument(..., help="Case id, e.g. CASE-P1-DELTA-260419."),
             as_of: str = typer.Option(..., "--as-of", help="Transaction time (Z or offset)."),
             ledger: str | None = typer.Option(None, help=LEDGER_HELP),
             config: str = typer.Option("config", help=CONFIG_HELP)) -> None:  # fmt: skip
    """Print a case as Kairos Defense knew it at a moment (transaction time, §15.4)."""
    from kairos_defense.cli_memory_view import snapshot_table
    from kairos_defense.memory.asof import snapshot

    cli = _base()
    cfg = cli._load_config(config)
    t = parse_time(as_of)
    with _open(cfg, ledger, read_only=True) as mem:
        rows = mem.events()
    cli.console.print(snapshot_table(snapshot(rows, case, t), _case_offset(rows, case, cfg)))


@memory_app.command("delta")
def delta_cmd(since: str = typer.Option(..., help="Start of the shift, exclusive (Z or offset)."),
              until: str | None = typer.Option(None, help="End, inclusive (default: the head)."),
              installation: str | None = typer.Option(None, help="Only this base, e.g. BRAVO."),
              ledger: str | None = typer.Option(None, help=LEDGER_HELP),
              config: str = typer.Option("config", help=CONFIG_HELP)) -> None:  # fmt: skip
    """What the memory learned during a shift, grouped, with seqs (§15.8)."""
    from kairos_defense.cli_memory_view import items_table
    from kairos_defense.memory.delta import delta

    cli = _base()
    cfg = cli._load_config(config)
    t0 = parse_time(since)
    with _open(cfg, ledger, read_only=True) as mem:
        rows, head = mem.events(), mem.head()
    t1 = parse_time(until) if until else (head.recorded_at if head else t0)
    d = delta(rows, t0, t1, installation)
    off = _offsets(cfg).get(installation, 0) if installation else None
    tz = f"local, UTC{off:+d}" if off is not None else "UTC"
    cli.console.print(
        items_table(
            f"shift delta {installation or 'all bases'} ({tz}): "
            f"{d.count} items, head seq {d.head_seq}",
            d.groups,
            off,
        )
    )


def register(app: typer.Typer) -> None:
    from kairos_defense import cli_memory_demo

    app.add_typer(memory_app, name="memory")
    memory_app.command("demo")(cli_memory_demo.demo_cmd)
    app.command(name="export")(cli_memory_demo.export_cmd)
    app.command(name="verify-evidence")(cli_memory_demo.verify_evidence_cmd)


def _models_validation(models_dir: Path) -> tuple[Path, dict]:
    from kairos_defense.match.fusion import MODEL_FILE

    path = Path(models_dir) / MODEL_FILE
    return path, json.loads(path.read_text()).get("validation", {})
