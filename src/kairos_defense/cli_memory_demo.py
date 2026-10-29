"""``memory demo``, ``export`` and ``verify-evidence`` (phase 6, SPEC §15.6, §15.7, D-098 to D-100).

``memory demo`` copies the seeded ledger to a scratch file (the real ledger stays at seed state),
records tonight's incident, registers the model, proposes the **real** matcher's top 3 at T as
links into the planted case and, only with ``--approve`` (rule 8), approves them as
``analyst:<handle>``. It prints "known then" (when the case was closed) and "known now" (the
scratch head) side by side, then the grouped diff.
"""

from __future__ import annotations

from pathlib import Path

import typer

from kairos_defense.cli_memory import (
    CONFIG_HELP,
    LEDGER_HELP,
    _base,
    _case_offset,
    _models_validation,
    _open,
    _remove,
    parse_time,
)


def _default_case(cfg) -> str:
    from kairos_defense.memory.seed import planted_cases

    planted = planted_cases(cfg.scenario)
    return f"CASE-{planted[0]}" if planted else ""


def _scratch_copy(cfg, scratch: Path):
    """A verified copy of the seeded ledger at ``scratch`` (writable), or exit 1."""
    from kairos_defense.memory.ledger import LedgerError

    cli = _base()
    with _open(cfg, None, read_only=True) as src:
        src_head = src.head()
    if src_head is None:
        cli.console.print("[red]empty ledger:[/red] run `kairos-defense memory seed` first.")
        raise typer.Exit(1)
    _remove(scratch, Path(f"{scratch}.wal"))
    mem = _open(cfg, str(scratch), read_only=False, must_exist=False)
    try:
        mem.copy_from(cfg.app.paths.memory)
    except LedgerError as exc:
        mem.close()
        cli._fail(exc)
    if mem.verify_chain() is not None or mem.head() != src_head:
        mem.close()
        cli.console.print("[red]the scratch copy does not match the ledger[/red]")
        raise typer.Exit(1)
    return mem


def demo_cmd(
    at: int | None = typer.Option(None, help="T in seconds (default: live_top3_at_s, 90)."),
    approve: bool = typer.Option(False, "--approve", help="Approve the proposals (rule 8)."),
    analyst: str = typer.Option("demo", help="Analyst handle that approves."),
    case: str | None = typer.Option(None, help="Case the proposals target (default: DELTA's)."),
    scratch: str | None = typer.Option(None, help="Scratch ledger (default: cache folder)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Terminal demo: the planted case "known then" and "known now", side by side (§15.6)."""
    from kairos_defense.cli_memory_view import items_table, side_by_side
    from kairos_defense.cli_recall import _query_and_matches
    from kairos_defense.memory.actions import (
        decide_link,
        file_sha256,
        propose_matches,
        record_incident,
        register_model,
    )
    from kairos_defense.memory.diff import group
    from kairos_defense.memory.ledger import InvalidEvent
    from kairos_defense.store.duck import DuckTrackStore

    cli = _base()
    cfg = cli._load_config(config)
    cli._need_data(cfg)
    lance = cli._need_index(cfg)
    at = int(at if at is not None else cfg.scenario.expectations.live_top3_at_s)
    case = case or _default_case(cfg)
    live = cfg.scenario.live_incident
    path = Path(scratch or Path(cfg.app.paths.cache) / "memory_demo.duckdb")
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        q, res = _query_and_matches(store, lance, cfg, live, None, at, "dtw")
        inc = store.sql("SELECT * FROM incidents WHERE incident_id = $i", {"i": live})
        inc = inc.iloc[0].to_dict()
    mem = _scratch_copy(cfg, path)
    with mem:
        rows = mem.events()
        founder = next((r for r in rows if r["event_type"] == "case_opened"
                        and r["case_id"] == case), None)  # fmt: skip
        if founder is None:
            cli.console.print(f"[red]unknown case {case}[/red] in the seeded ledger")
            raise typer.Exit(1)
        then = founder["recorded_at"]
        clock = q.until
        try:
            record_incident(mem, inc, inc["start_ts"])
            model_file, validation = _models_validation(cfg.app.paths.models)
            register_model(mem, res.matches[0].model_version, file_sha256(model_file), clock,
                           model_file.as_posix(), validation)  # fmt: skip
            seqs = propose_matches(mem, case, live, res.matches, clock, query_track=q.track_id,
                                   t_s=at)  # fmt: skip
            if approve:
                for s in seqs:
                    decide_link(mem, case, s, "approve", analyst, clock,
                                "approved in the terminal demo")  # fmt: skip
        except (InvalidEvent, ValueError) as exc:
            cli._fail(exc)
        now = mem.head().recorded_at
        rows = mem.events()
        before, after = mem.as_of(case, then), mem.as_of(case, now)
        items = mem.diff(case, then, now)
        broken = mem.verify_chain()
    off = _case_offset(rows, case, cfg)
    top = ", ".join(f"{m.incident_id} {m.score:.3f}" for m in res.matches[:3])
    cli.console.print(f"query {q.track_id} at T+{at} s · model {res.matches[0].model_version} · "
                      f"real top 3: {top}")  # fmt: skip
    cli.console.print(side_by_side(before, after, off))
    cli.console.print(items_table(f"diff {case}: (known then, known now]", group(items), off))
    state = "approved" if approve else "pending (rerun with --approve to link them)"
    cli.console.print(f"{len(seqs)} proposals {state}; scratch ledger {path} "
                      f"({len(rows):,} rows, chain {'intact' if broken is None else 'BROKEN'}); "
                      f"{cfg.app.paths.memory} is unchanged")  # fmt: skip


def export_cmd(
    case: str = typer.Option(..., help="Case id, e.g. CASE-P1-DELTA-260419."),
    approve: bool = typer.Option(False, "--approve", help="Explicit approval (rule 8)."),
    analyst: str = typer.Option("demo", help="Analyst handle that approves."),
    at: str | None = typer.Option(None, help="Export clock (Z or offset; default: the head)."),
    ledger: str | None = typer.Option(None, help=LEDGER_HELP),
    out: str | None = typer.Option(None, help="Output folder (default: paths.exports)."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Export a signed evidence package for a case (needs --approve, §15.7)."""
    from kairos_defense.memory.evidence import EvidenceError, export_evidence, signer_for
    from kairos_defense.memory.evidence import fingerprint as fp
    from kairos_defense.memory.ledger import InvalidEvent
    from kairos_defense.memory.ledger import analyst as as_analyst
    from kairos_defense.store.duck import DuckTrackStore

    cli = _base()
    if not approve:
        cli.console.print("[red]approval required (rule 8):[/red] an export needs an explicit "
                          "human approval; rerun with --approve. Nothing was written.")  # fmt: skip
        raise typer.Exit(1)
    cfg = cli._load_config(config)
    try:
        who = as_analyst(analyst)
    except InvalidEvent as exc:
        cli._fail(exc)
    clock = parse_time(at) if at else None
    store = (DuckTrackStore(cfg.app.paths.duckdb, cfg.app)
             if Path(cfg.app.paths.duckdb).exists() else None)  # fmt: skip
    try:
        with _open(cfg, ledger, read_only=False) as mem:
            head = mem.head()
            if head is None:
                cli.console.print("[red]empty ledger:[/red] run `kairos-defense memory seed`.")
                raise typer.Exit(1)
            signer = signer_for(cfg.app)
            res = export_evidence(mem, case, approve=True, approved_by=who,
                                  clock=clock or head.recorded_at,
                                  out_root=out or cfg.app.paths.exports, signer=signer,
                                  store=store)  # fmt: skip
    except EvidenceError as exc:
        cli._fail(exc)
    finally:
        if store is not None:
            store.close()
    key = f"signed, key {fp(signer.public_pem())}" if signer else "UNSIGNED (signing disabled)"
    cli.console.print(f"exported {res.path}/ · manifest sha256 {res.manifest_sha256} · {key} · "
                      f"records head seq {res.head_seq:,} · appended evidence_exported seq "
                      f"{res.seq:,}")  # fmt: skip


def verify_evidence_cmd(
    folder: str = typer.Argument(..., help="Package folder under exports/."),
    ledger: str | None = typer.Option(None, help=LEDGER_HELP),
    pubkey: str | None = typer.Option(None, help="Expected public key (PEM) to pin."),
    config: str = typer.Option("config", help=CONFIG_HELP),
) -> None:
    """Verify an evidence package: file hashes, the Ed25519 signature, chain continuity and the
    rows against the ledger; prints a PASS/FAIL/SKIP table, exit 1 on any FAIL."""
    from kairos_defense.cli_memory_view import checks_table
    from kairos_defense.memory.evidence import passed, verify_evidence
    from kairos_defense.memory.ledger import LedgerError
    from kairos_defense.store.ledger_duck import DuckCaseMemory

    cli = _base()
    cfg = cli._load_config(config)
    if not Path(folder).is_dir():
        cli.console.print(f"[red]no package:[/red] {folder} is not a folder")
        raise typer.Exit(1)
    pem = Path(pubkey).read_bytes() if pubkey else None
    path = Path(ledger or cfg.app.paths.memory)
    mem, note = None, f"no ledger at {path}"
    if path.exists():
        try:
            mem = DuckCaseMemory(path, cfg.app, read_only=True)
        except LedgerError as exc:
            note = f"ledger not readable ({type(exc).__name__}): {exc}"
    try:
        checks = verify_evidence(folder, mem, pem, ledger_note=note)
    finally:
        if mem is not None:
            mem.close()
    cli.console.print(checks_table(folder, checks))
    ok = passed(checks)
    cli.console.print("[green]PASS[/green]: the package verifies" if ok
                      else "[red]FAIL[/red]: the package does not verify")  # fmt: skip
    if not ok:
        raise typer.Exit(1)
