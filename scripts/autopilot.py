#!/usr/bin/env python3
"""Kairos Defense autopilot: run the remaining build phases unattended with Claude Code.

Per phase:  plan (fresh session) -> independent plan review, auto-approved when clean (revise up to N rounds)
            -> build (fresh session) -> deterministic gate (make check + the phase's exit-check commands
            + documentation checks) -> fix loop (resumes the build session) -> commit + tag -> next phase.

Everything is logged under docs/phases/: one folder per phase (plan, reviews, report, exit check,
gate logs, compressed transcripts, meta.json with session ids and costs), plus INDEX.md and AUTOPILOT.log.

Usage (from the repository root, in a normal terminal, not inside Claude Code):
  python3 scripts/autopilot.py init                      # one-time checks and setup
  python3 scripts/autopilot.py run                       # first phase not marked done in PROGRESS.md -> 9
  python3 scripts/autopilot.py run --from 4 --to 9
  python3 scripts/autopilot.py run --from 5 --redo       # redo phase 5 from planning
  python3 scripts/autopilot.py status
  python3 scripts/autopilot.py backfill --phases 0-3     # write REPORT.md etc. for phases done by hand
Stdlib only. Needs Claude Code >= 2.1.259, git, and the project's own toolchain (uv, npm).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
MIN_VERSION = (2, 1, 259)  # --permission-prompts none
LIMIT_WORDS = (
    "usage limit",
    "rate limit",
    "rate_limit",
    "limit reached",
    "overloaded",
    "try again later",
)
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["approved", "blocking_issues", "summary"],
}
REQUIRED_DOCS = ("PLAN.md", "REPORT.md", "EXIT_CHECK.md")
CLAUDE_MD_MARKER = "## Autopilot and documentation"
SETTINGS_REL = ".claude/settings.autopilot.json"
LAST_PHASE = 10  # phase 10 (docs/phases/PHASE_10.md): user guide, one-pager, rollback guide
# Files only a human may change. The gate blocks the run if any of them differs from the run's start.
PROTECTED = (
    "scripts/autopilot.py",
    "scripts/check_targets.py",
    "scripts/check_docs.py",
    "docs/phases/PHASE_10.md",
    "docs/phases/gates.json",
    ".claude/settings.autopilot.json",
    ".claude/skills/phase-auto/SKILL.md",
)
# Never passed to child processes: an API key would bill sessions to the API instead of the
# subscription login, a stale GITHUB_TOKEN breaks git, and CLAUDE* variables belong to whatever
# Claude Code session launched this script.
DROP_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")


def child_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k not in DROP_ENV and not k.startswith(("CLAUDECODE", "CLAUDE_CODE_", "CLAUDE_PID"))
    }


# ---------------------------------------------------------------- basics
def _root() -> Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if r.returncode != 0:
        sys.exit("autopilot: run this from inside the project's git repository")
    return Path(r.stdout.strip())


ROOT = _root()
PH = ROOT / "docs" / "phases"
LOG = PH / "AUTOPILOT.log"
SETTINGS = ROOT / SETTINGS_REL


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    PH.mkdir(parents=True, exist_ok=True)
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def head() -> str:
    return git("rev-parse", "HEAD").stdout.strip()


def is_clean(ignore_phase_logs: bool = False) -> bool:
    spec = ["--", ".", ":(exclude)docs/phases"] if ignore_phase_logs else []
    return git("status", "--porcelain", *spec).stdout.strip() == ""


def commit_all(msg: str) -> bool:
    git("add", "-A")
    return git("commit", "-m", msg).returncode == 0


def tag(name: str) -> str:
    if git("rev-parse", "-q", "--verify", f"refs/tags/{name}").returncode == 0:
        name = f"{name}-{dt.datetime.now():%Y%m%d%H%M%S}"
    git("tag", "-a", name, "-m", name)
    return name


def pdir(n: int) -> Path:
    d = PH / f"phase-{n:02d}"
    (d / "transcripts").mkdir(parents=True, exist_ok=True)
    return d


def load_meta(n: int) -> dict:
    f = pdir(n) / "meta.json"
    return (
        json.loads(f.read_text()) if f.exists() else {"phase": n, "status": "pending", "steps": []}
    )


def save_meta(n: int, m: dict) -> None:
    (pdir(n) / "meta.json").write_text(json.dumps(m, indent=2))


def progress_rows() -> dict[int, str]:
    """Phase number -> status, read from the table in docs/PROGRESS.md."""
    p = ROOT / "docs" / "PROGRESS.md"
    rows: dict[int, str] = {}
    if p.exists():
        for line in p.read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0].isdigit():
                rows[int(cells[0])] = cells[2].lower()
    return rows


def is_done(status: str) -> bool:
    """Accepts hand-written forms such as 'done', 'Done (Oct 27)', '✅ done' or 'complete'."""
    return bool(re.match(r"^[^a-z]*(done|complete)", status.strip().lower()))


def first_pending() -> int:
    """First phase not done. The autopilot's own record (meta.json) wins over PROGRESS.md,
    because a build session may mark a phase done before its gate has passed."""
    for n, st in sorted(progress_rows().items()):
        f = PH / f"phase-{n:02d}" / "meta.json"
        if f.exists() and not is_done(str(json.loads(f.read_text()).get("status", ""))):
            return n
        if not is_done(st):
            return n
    return LAST_PHASE + 1


def set_progress_status(n: int, status: str) -> None:
    p = ROOT / "docs" / "PROGRESS.md"
    if not p.exists():
        return
    lines = p.read_text().splitlines()
    for i, line in enumerate(lines):
        cells = line.strip().strip("|").split("|")
        if len(cells) >= 3 and cells[0].strip() == str(n):
            cells[2] = f" {status} "
            lines[i] = "|" + "|".join(cells) + "|"
    p.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- Claude Code sessions
def claude_cmd(
    opts, prompt: str, resume: str | None, schema: dict | None, extra: list[str]
) -> list[str]:
    cmd = [CLAUDE, "-p", prompt, "--permission-mode", opts.mode, "--permission-prompts", "none"]
    if SETTINGS.exists():  # allow/deny rules for autopilot sessions only, not for interactive use
        cmd += ["--settings", str(SETTINGS)]
    if resume:
        cmd += ["--resume", resume]
    if opts.budget:
        cmd += ["--max-budget-usd", str(opts.budget)]
    if opts.model:
        cmd += ["--model", opts.model]
    if schema:
        cmd += ["--output-format", "json", "--json-schema", json.dumps(schema)]
    else:
        cmd += ["--output-format", "stream-json", "--verbose"]
    return cmd + extra


def _tail_hint(out: Path) -> str:
    try:
        lines = out.read_text(errors="replace").splitlines()[-40:]
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        for block in (ev.get("message") or {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                inp = block.get("input") or {}
                detail = inp.get("command") or inp.get("file_path") or inp.get("description") or ""
                return f"last tool: {block.get('name')} {str(detail)[:80]}"
    return ""


def _parse(out: Path, schema: bool) -> dict:
    text = out.read_text(errors="replace") if out.exists() else ""
    res, sid = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        sid = sid or ev.get("session_id")
        if ev.get("type") == "result" or (schema and "structured_output" in ev):
            res = ev
    if schema and not res:
        try:
            res = json.loads(text)
        except ValueError:
            res = {}
    return {
        "session_id": res.get("session_id") or sid,
        "result": res.get("result") or "",
        "is_error": bool(res.get("is_error")),
        "cost": res.get("total_cost_usd"),
        "denials": res.get("permission_denials") or [],
        "structured": res.get("structured_output"),
        "raw_tail": text[-2000:],
    }


def run_claude(
    opts,
    prompt: str,
    out: Path,
    resume: str | None = None,
    schema: dict | None = None,
    extra: list[str] | None = None,
    hours: float = 3.0,
) -> dict:
    """One Claude Code session. Streams the transcript to `out`, retries transient failures, gzips the log."""
    extra = extra or []
    if opts.dry_run:
        log(
            f"  [dry run] claude -p {prompt.splitlines()[0]!r} (resume={resume}, schema={bool(schema)})"
        )
        return {
            "ok": True,
            "session_id": "dry-run",
            "result": "",
            "cost": 0.0,
            "denials": [],
            "minutes": 0,
            "structured": {"approved": True, "blocking_issues": [], "summary": "dry run"},
        }
    waits, limit_waits, attempt = [60, 300], 0, 0
    cur_prompt, cur_resume = prompt, resume
    while True:
        attempt += 1
        t0 = time.time()
        with out.open("w") as fh:
            p = subprocess.Popen(
                claude_cmd(opts, cur_prompt, cur_resume, schema, extra),
                cwd=ROOT,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                env=child_env(),
            )
            last = time.time()
            while p.poll() is None:
                time.sleep(10)
                if time.time() - t0 > hours * 3600:
                    log(f"  session exceeded {hours} h; interrupting")
                    p.send_signal(signal.SIGINT)
                    try:
                        p.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        p.terminate()
                    break
                if time.time() - last > 180:
                    log(f"  … running {int((time.time() - t0) / 60)} min. {_tail_hint(out)}")
                    last = time.time()
            rc = p.wait()
        r = _parse(out, bool(schema))
        r.update(
            rc=rc,
            minutes=round((time.time() - t0) / 60, 1),
            ok=(
                rc == 0 and not r["is_error"] and (r["structured"] is not None if schema else True)
            ),
        )
        if r["ok"]:
            break
        blob = (r["result"] + r["raw_tail"]).lower()
        if any(w in blob for w in LIMIT_WORDS) and limit_waits < opts.limit_retries:
            limit_waits += 1
            log(
                f"  usage/rate limit hit; waiting {opts.limit_wait} min (retry {limit_waits}/{opts.limit_retries})"
            )
            time.sleep(opts.limit_wait * 60)
        elif attempt <= len(waits):
            log(f"  session failed (exit {rc}); retrying in {waits[attempt - 1]} s")
            time.sleep(waits[attempt - 1])
        else:
            break
        if (
            r["session_id"] and not schema
        ):  # continue the same conversation instead of starting over
            cur_resume = r["session_id"]
            cur_prompt = "Continue the task from where you stopped. If it is already complete, verify and say so."
        _gzip(out)
        out = out.with_name(out.stem + f".retry{attempt}" + out.suffix)
    _gzip(out)
    return r


def _gzip(out: Path) -> None:
    """Compress a finished .jsonl transcript in place (every attempt, not only the last)."""
    if out.suffix == ".jsonl" and out.exists():
        with out.open("rb") as src, gzip.open(str(out) + ".gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
        out.unlink()


def record(m: dict, step: str, r: dict) -> None:
    m["steps"].append(
        {
            "step": step,
            "at": now(),
            "ok": r.get("ok"),
            "session_id": r.get("session_id"),
            "cost_usd": r.get("cost"),
            "minutes": r.get("minutes"),
            "permission_denials": len(r.get("denials") or []),
        }
    )


# ---------------------------------------------------------------- gate
def load_gates() -> dict:
    f = PH / "gates.json"
    if not f.exists():
        sys.exit("autopilot: docs/phases/gates.json is missing (run `autopilot.py init`)")
    return json.loads(f.read_text())


def docs_check(n: int) -> list[str]:
    d, missing = pdir(n), []
    for name in REQUIRED_DOCS:
        f = d / name
        if not f.exists() or f.stat().st_size < 300:
            missing.append(f"docs/phases/phase-{n:02d}/{name}")
    pkg = ROOT / "src" / "kairos_defense"
    if pkg.exists():
        for sub in sorted(p for p in pkg.iterdir() if p.is_dir() and any(p.glob("*.py"))):
            if not (sub / "README.md").exists():
                missing.append(str((sub / "README.md").relative_to(ROOT)))
    if (ROOT / "web" / "package.json").exists() and not (ROOT / "web" / "README.md").exists():
        missing.append("web/README.md")
    return missing


def protected_changes(start_sha: str) -> list[str]:
    """Protected files that differ (committed or not) from the commit the run started at."""
    r = git("diff", "--name-only", start_sha, "--", *PROTECTED)
    return [x for x in r.stdout.split() if x]


SKIP_MARK = re.compile(
    r"^\+.*(pytest\.mark\.(skip|xfail)|pytest\.skip\(|\bit\.skip\(|\btest\.skip\(|describe\.skip\()"
)


def run_gate(
    n: int, attempt: int, gates: dict, minutes: int, opts
) -> tuple[bool, str, Path, list[str]]:
    """Run the gate. Returns (passed, hard failure reason, log, target gaps).

    A command prefixed `soft:` that exits 1 reports target shortfalls (its `GAP ...` lines) instead of
    failing the gate outright; any other non-zero exit is a hard failure (D-063)."""
    cmds = list(gates.get("always", [])) + list(gates.get("phases", {}).get(str(n), []))
    logf = pdir(n) / f"gate-{attempt}.log"
    reason = ""
    gaps: list[str] = []
    write_accepted(opts)  # rewritten from memory before every gate, so edits to it never count
    env = {**child_env(), "KD_GATE_STARTED": str(time.time() - 1)}
    with logf.open("w") as f:
        f.write(f"# Gate for phase {n}, attempt {attempt}, {now()}\n")
        # Checked before the commands run: gate commands rewrite tracked outputs (eval reports,
        # figures), which the closing commit records. The build itself must leave nothing uncommitted.
        if not is_clean(ignore_phase_logs=True):
            reason = (
                "uncommitted changes left by the build (commit them with git add -A && git commit)"
            )
            f.write("\n# Git (before gate commands)\n" + git("status", "--short").stdout)
        for c in [] if reason else cmds:
            soft = c.startswith("soft:")
            c = c.removeprefix("soft:").strip()
            f.write(f"\n$ {c}\n")
            f.flush()
            pos = f.tell()
            t0 = time.time()
            try:
                rc = subprocess.run(
                    c,
                    shell=True,
                    cwd=ROOT,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=minutes * 60,
                    env=env,
                ).returncode
            except subprocess.TimeoutExpired:
                rc = 124
                f.write(f"\n[timed out after {minutes} min]\n")
            f.write(f"[exit {rc} after {time.time() - t0:.0f} s]\n")
            f.flush()
            if rc == 1 and soft:
                with logf.open(errors="replace") as rf:
                    rf.seek(pos)
                    found = [x[4:].strip() for x in rf.read().splitlines() if x.startswith("GAP ")]
                gaps += found or [f"{c}: exited 1 without GAP lines"]
                continue
            if rc != 0:
                reason = f"command failed: {c}"
                break
        missing = docs_check(n)
        f.write(
            "\n# Documentation check\n"
            + ("\n".join(f"MISSING {x}" for x in missing) or "ok")
            + "\n"
        )
        if missing and not reason:
            reason = "documentation incomplete: " + "; ".join(missing)
        # Tests must not disappear: passing count of the first pytest run (make check) never drops.
        f.flush()
        counts = re.findall(r"(\d+) passed", logf.read_text(errors="replace"))
        passed = int(counts[0]) if counts else None
        f.write(f"\n# Test count\npassed {passed}, minimum {opts.min_tests}\n")
        if not reason and passed is not None and opts.min_tests and passed < opts.min_tests:
            reason = f"fewer Python tests pass ({passed}) than before this run ({opts.min_tests}); tests were removed or skipped"
        if passed and not reason:
            opts.min_tests = max(opts.min_tests or 0, passed)
        added = [
            x
            for x in git(
                "diff", opts.start_sha, "--", "tests", "web/tests", "web/e2e"
            ).stdout.splitlines()
            if SKIP_MARK.search(x)
        ]
        f.write(
            "\n# Skip or xfail markers added this run (review them)\n"
            + ("\n".join(added) or "none")
            + "\n"
        )
        if gaps:
            f.write("\n# Target gaps\n" + "\n".join(gaps) + "\n")
        result = "FAIL: " + reason if reason else ("GAPS ONLY" if gaps else "PASS")
        f.write(f"\n# Result: {result}\n")
    return (not reason and not gaps), reason, logf, gaps


ACCEPTED_FILE = PH / "accepted_gaps.json"


def gap_key(line: str) -> str:
    """'demo:live_top3_incidents: status ...' -> 'demo:live_top3_incidents'; 'dtw_lift: ...' -> 'dtw_lift'."""
    if line.startswith("demo:"):
        return "demo:" + line[5:].split(":", 1)[0]
    return line.split(":", 1)[0]


def write_accepted(opts) -> None:
    ACCEPTED_FILE.write_text(json.dumps({"keys": sorted(opts.accepted)}, indent=2) + "\n")


def accept_gaps(n: int, m: dict, gaps: list[str], logf: Path, opts) -> None:
    """Record target shortfalls that survived the fix attempts and let the run continue (D-063)."""
    keys = sorted({gap_key(g) for g in gaps})
    opts.accepted |= set(keys)
    write_accepted(opts)
    m["gaps"] = gaps
    with (pdir(n) / "GAPS.md").open("w") as f:
        f.write(
            f"# Phase {n}: targets not met, accepted by the autopilot\n\n"
            f"After {opts.target_attempts} fix attempts these targets were still short. Per the user's "
            "instruction of 2026-10-28 (D-063) the run recorded them and continued; later phases report "
            "them as WARN and do not retry them. Every other check in the gate passed.\n\n"
            + "\n".join(f"- {g}" for g in gaps)
            + f"\n\nLast gate log: `{logf.relative_to(ROOT)}`. Accepted keys: {', '.join(keys)}.\n"
        )
    log(f"phase {n}: accepting {len(gaps)} target gap(s) and continuing: {', '.join(keys)}")


# ---------------------------------------------------------------- index and outcomes
def write_index() -> None:
    rows = [
        "# Phase index",
        "",
        "Generated by scripts/autopilot.py. One folder per phase; start with its REPORT.md.",
        "",
        "| Phase | Status | Started | Finished | Cost (USD, est.) | Steps | Report |",
        "|---|---|---|---|---|---|---|",
    ]
    prog = progress_rows()
    for n in range(0, LAST_PHASE + 1):
        f = PH / f"phase-{n:02d}" / "meta.json"
        m = json.loads(f.read_text()) if f.exists() else {}
        cost = sum((s.get("cost_usd") or 0) for s in m.get("steps", []))
        status = m.get("status") or prog.get(n, "")
        rep = (
            f"[REPORT](phase-{n:02d}/REPORT.md)"
            if (PH / f"phase-{n:02d}" / "REPORT.md").exists()
            else ""
        )
        rows.append(
            f"| {n} | {status} | {m.get('started', '')} | {m.get('finished', '')} | "
            f"{cost:.2f} | {len(m.get('steps', []))} | {rep} |"
        )
    tags = git(
        "for-each-ref",
        "--sort=creatordate",
        "--format=| `%(refname:short)` | `%(objectname:short)` | %(creatordate:iso) |",
        "refs/tags",
    ).stdout
    rows += [
        "",
        "## Rollback points",
        "",
        "Every tag below is a safe point. Inspect with `git diff <tag> HEAD --stat`; roll back on a new",
        "branch with `git switch -c rollback <tag>`, then `make clean data index models eval`.",
        "See docs/ROLLBACK.md.",
        "",
        "| Tag | Commit | Created |",
        "|---|---|---|",
    ]
    rows += [x for x in tags.splitlines() if x.strip()] or ["| (none yet) | | |"]
    (PH / "INDEX.md").write_text("\n".join(rows) + "\n")


def block(n: int, m: dict, reason: str) -> bool:
    d = pdir(n)
    with (d / "BLOCKED.md").open("a") as f:
        f.write(
            f"\n## Autopilot stopped, {now()}\n\n- Reason: {reason}\n"
            f"- Logs: docs/phases/phase-{n:02d}/ (gate-*.log, transcripts/, meta.json)\n"
            f"- Resume the last session to ask what happened: `claude --resume {m.get('build_session') or m.get('plan_session')}`\n"
            f"- After fixing, rerun: `python3 scripts/autopilot.py run --from {n}`\n"
        )
    m.update(status="blocked", blocked_reason=reason, finished=now())
    save_meta(n, m)
    set_progress_status(n, f"blocked (see docs/phases/phase-{n:02d}/BLOCKED.md)")
    write_index()
    commit_all(f"phase {n}: autopilot blocked ({reason[:60]})")
    log(f"!!! Phase {n} BLOCKED: {reason}")
    print("\a", end="", flush=True)
    return False


def review_prompt(n: int) -> str:
    block = (
        "docs/phases/PHASE_10.md (the phase block for phase 10)"
        if n == LAST_PHASE
        else f"the Phase {n} block in docs/SPEC.md §20"
    )
    return (
        f"You are an independent reviewer of a build plan. Do not modify any file.\n"
        f"Read CLAUDE.md, {block} and every SPEC section it lists under "
        f"'Read first', docs/phases/TEMPLATES.md, and docs/phases/phase-{n:02d}/PLAN.md.\n"
        "Approve only if the plan: (1) covers every task checkbox in the phase block; (2) names concrete tests "
        "for every test bullet; (3) maps every exit-check criterion to a command and the evidence it produces; "
        "(4) respects every non-negotiable rule in CLAUDE.md; (5) lists the README and docs/phases files it "
        "will create or update; (6) needs no human decision to proceed.\n"
        "Blocking issues are only problems that would make the phase fail its exit check or break a rule. "
        "Put style preferences in suggestions. Return the JSON verdict."
    )


# ---------------------------------------------------------------- one phase
def run_phase(n: int, opts, gates: dict) -> bool:
    m = load_meta(n)
    if opts.redo:
        m = {"phase": n, "status": "pending", "steps": [], "redo_of": m}
        opts.redo = False
    if m.get("status") == "done":
        log(f"phase {n}: already done by autopilot, skipping")
        return True
    d = pdir(n)
    m.setdefault("started", now())
    m["sha_before"] = m.get("sha_before") or head()
    m["status"] = "running"
    save_meta(n, m)
    write_index()
    log(f"=== Phase {n}: start ({opts.mode} mode) ===")

    if not m.get("plan_approved"):
        if not m.get("plan_session") or not (d / "PLAN.md").exists():
            log(f"phase {n}: planning")
            r = run_claude(
                opts, f"/phase-auto plan {n}", d / "transcripts" / "plan.jsonl", hours=1.5
            )
            record(m, "plan", r)
            m["plan_session"] = r.get("session_id")
            save_meta(n, m)
            if not r["ok"] or (not opts.dry_run and not (d / "PLAN.md").exists()):
                return block(n, m, "planning session failed or wrote no PLAN.md")
        for k in range(1, opts.review_rounds + 1):
            log(f"phase {n}: independent plan review {k}")
            rv = run_claude(
                opts,
                review_prompt(n),
                d / "transcripts" / f"review-{k}.json",
                schema=REVIEW_SCHEMA,
                extra=["--disallowedTools", "Edit,Write,NotebookEdit"],
                hours=0.75,
            )
            verdict = rv.get("structured") or {}
            (d / f"PLAN_REVIEW-{k}.json").write_text(json.dumps(verdict, indent=2))
            record(m, f"review-{k}", rv)
            if verdict.get("approved") and not verdict.get("blocking_issues"):
                m["plan_approved"] = True
                log(f"phase {n}: plan approved on review {k}: {verdict.get('summary', '')[:120]}")
                break
            issues = (
                "\n".join(f"- {i}" for i in verdict.get("blocking_issues", []))
                or "- The reviewer returned no usable verdict; re-check the plan against TEMPLATES.md and the phase block."
            )
            log(f"phase {n}: review {k} found blocking issues; revising the plan")
            rr = run_claude(
                opts,
                f"/phase-auto revise {n}\n\nBlocking issues from independent review {k}:\n{issues}",
                d / "transcripts" / f"revise-{k}.jsonl",
                resume=m.get("plan_session"),
                hours=1.0,
            )
            record(m, f"revise-{k}", rr)
            save_meta(n, m)
        else:
            return block(
                n,
                m,
                f"plan not approved after {opts.review_rounds} review rounds (see PLAN_REVIEW-*.json)",
            )
        save_meta(n, m)

    if not m.get("built"):
        log(f"phase {n}: building in a fresh session")
        r = run_claude(
            opts,
            f"/phase-auto build {n}",
            d / "transcripts" / "build.jsonl",
            hours=opts.build_hours,
        )
        record(m, "build", r)
        m["build_session"] = r.get("session_id")
        m["built"] = bool(r["ok"])
        save_meta(n, m)
        if not r["ok"]:
            return block(n, m, "build session failed (see transcripts/build.jsonl.gz)")

    gaps: list[str] = []
    for a in range(1, max(opts.fix_attempts, opts.target_attempts) + 2):
        changed = [] if opts.dry_run else protected_changes(opts.start_sha)
        if changed:
            return block(
                n,
                m,
                "protected autopilot files were changed: "
                + ", ".join(changed)
                + f" (compare with `git diff {opts.start_sha[:10]} -- <file>`)",
            )
        log(f"phase {n}: gate attempt {a}")
        ok, reason, logf, gaps = (
            (True, "", None, []) if opts.dry_run else run_gate(n, a, gates, opts.gate_minutes, opts)
        )
        if ok:
            log(f"phase {n}: gate passed")
            break
        if reason:
            log(f"phase {n}: gate failed: {reason}")
            if a > opts.fix_attempts:
                return block(
                    n, m, f"gate still failing after {opts.fix_attempts} fix attempts: {reason}"
                )
            note = ""
        else:
            log(
                f"phase {n}: everything else passed; {len(gaps)} target gap(s): "
                + "; ".join(gaps)[:300]
            )
            if a > opts.target_attempts:
                accept_gaps(n, m, gaps, logf, opts)
                break
            note = (
                f"\n\nEverything in the gate passed except target shortfalls (the GAP lines). This is "
                f"attempt {a} of {opts.target_attempts} at them: improve the method honestly (no changes "
                "to the §19 protocol, query sets, truth handling or metric definitions to raise a number). "
                "If they are still short after that, the autopilot records them in GAPS.md and moves on."
            )
        rel = f"docs/phases/phase-{n:02d}/{logf.name}"
        r = run_claude(
            opts,
            f"/phase-auto fix {n} {rel}{note}",
            d / "transcripts" / f"fix-{a}.jsonl",
            resume=m.get("build_session"),
            hours=opts.build_hours / 2,
        )
        if not r["ok"]:
            r = run_claude(
                opts,
                f"/phase-auto fix {n} {rel}{note}",
                d / "transcripts" / f"fix-{a}-fresh.jsonl",
                hours=opts.build_hours / 2,
            )
        record(m, f"fix-{a}", r)
        save_meta(n, m)

    m.update(status="done", finished=now(), sha_after=head())
    if gaps:
        set_progress_status(
            n, f"done with gaps ({dt.date.today()}, see docs/phases/phase-{n:02d}/GAPS.md)"
        )
    else:
        set_progress_status(n, f"done ({dt.date.today()}, autopilot gate passed)")
    (d / "diffstat.txt").write_text(git("diff", "--stat", m["sha_before"], "HEAD").stdout)
    save_meta(n, m)
    write_index()
    commit_all(f"phase {n}: autopilot artifacts (plan reviews, gate logs, transcripts)")
    t = tag(f"phase-{n:02d}-done")
    cost = sum((s.get("cost_usd") or 0) for s in m["steps"])
    log(
        f"=== Phase {n}: done{' with gaps' if gaps else ''}, tagged {t}, estimated cost ${cost:.2f} ==="
    )
    push(opts)
    return True


def push(opts) -> None:
    """Optional: fast-forward push of the current branch and tags (never forced). Failures only log."""
    if not opts.push or opts.dry_run:
        return
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    for args in (["push", "origin", branch], ["push", "origin", "--tags"]):
        r = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True, env=child_env()
        )
        log(
            f"  git {' '.join(args)}: {'ok' if r.returncode == 0 else 'FAILED ' + r.stderr.strip()[-200:]}"
        )


# ---------------------------------------------------------------- commands
def cmd_init(opts) -> None:
    ok = True
    v = subprocess.run([CLAUDE, "--version"], text=True, capture_output=True)
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", v.stdout or "")
    if v.returncode != 0 or not m:
        print("✗ Claude Code CLI not found. Install it, sign in with `claude`, then rerun.")
        ok = False
    elif tuple(map(int, m.groups())) < MIN_VERSION:
        print(
            f"✗ Claude Code {m.group(0)} is too old; need {'.'.join(map(str, MIN_VERSION))}+ (run `claude update`)."
        )
        ok = False
    else:
        print(f"✓ Claude Code {m.group(0)}")
    for tool in ("uv", "npm", "make"):
        print(("✓ " if shutil.which(tool) else "✗ missing: ") + tool)
        ok = ok and bool(shutil.which(tool))
    for f in (
        "CLAUDE.md",
        "docs/SPEC.md",
        "docs/PROGRESS.md",
        "docs/phases/gates.json",
        "docs/phases/TEMPLATES.md",
        ".claude/skills/phase-auto/SKILL.md",
    ):
        exists = (ROOT / f).exists()
        print(("✓ " if exists else "✗ missing: ") + f)
        ok = ok and exists
    cm = ROOT / "CLAUDE.md"
    section = ROOT / "docs" / "phases" / "CLAUDE_SECTION.md"
    if cm.exists() and section.exists() and CLAUDE_MD_MARKER not in cm.read_text():
        cm.write_text(cm.read_text().rstrip() + "\n\n" + section.read_text())
        print("✓ appended the autopilot section to CLAUDE.md")
    print(
        ("✓ " if SETTINGS.exists() else "✗ missing: ")
        + f"{SETTINGS_REL} (passed to every autopilot session with --settings)"
    )
    ok = ok and SETTINGS.exists()
    gi = ROOT / ".gitignore"
    if gi.exists() and ".autopilot/" not in gi.read_text():
        gi.write_text(gi.read_text().rstrip() + "\n.autopilot/\n")
    print(f"• next phase per PROGRESS.md: {first_pending()}")
    if ok and not opts.skip_smoke:
        print("• smoke test: one tiny session in the chosen permission mode …")
        out = ROOT / ".autopilot-smoke.jsonl"
        r = subprocess.run(
            claude_cmd(opts, "Reply with the single word OK.", None, None, []),
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            env=child_env(),
        )
        out.write_text(r.stdout)
        mode = ""
        for line in r.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "system" and ev.get("subtype") == "init":
                mode = ev.get("permissionMode") or ev.get("permission_mode") or ""
        out.unlink(missing_ok=True)
        print(
            ("✓" if r.returncode == 0 else "✗")
            + f" smoke session exit {r.returncode}; permission mode reported: {mode or 'unknown'}"
        )
        if opts.mode == "auto" and mode and mode != "auto":
            print(
                "  ! Auto mode is not available to this session (model, plan or org setting). See docs/AUTOPILOT.md, 'If auto mode is unavailable'."
            )
    print("Ready." if ok else "Fix the items marked ✗, then rerun init.")


def cmd_run(opts) -> None:
    if opts.mode == "bypassPermissions" and not (
        Path("/.dockerenv").exists() or os.environ.get("KD_IN_CONTAINER")
    ):
        sys.exit(
            "autopilot: bypassPermissions is only allowed inside a container or VM (set KD_IN_CONTAINER=1 there)."
        )
    if not opts.dry_run and not is_clean(ignore_phase_logs=True):
        sys.exit(
            "autopilot: commit or stash your changes first; each phase must start from a clean tree."
        )
    gates = load_gates()
    start = opts.from_phase if opts.from_phase is not None else first_pending()
    if opts.dry_run:
        # Print only. Running run_phase in dry-run mode would mark phases done, edit PROGRESS.md,
        # commit and tag, after which a real run finds nothing to do.
        print(
            f"[dry run] phases {start}..{opts.to}, mode {opts.mode}, push {'on' if opts.push else 'off'}"
        )
        for n in range(start, opts.to + 1):
            cmds = list(gates.get("always", [])) + list(gates.get("phases", {}).get(str(n), []))
            print(
                f"[dry run] phase {n}: plan, review (up to {opts.review_rounds}), build, gate: "
                + " && ".join(cmds)
            )
        return
    if start > opts.to:
        log("Nothing to do: every phase up to --to is done.")
        commit_log(opts)
        return
    t = tag(f"autopilot-start-{dt.datetime.now():%Y%m%d-%H%M}")
    opts.start_sha = head()
    try:
        opts.accepted = set(json.loads(ACCEPTED_FILE.read_text()).get("keys", []))
    except (OSError, ValueError):
        opts.accepted = set()
    opts.min_tests = None if opts.dry_run else collected_tests()
    log(
        f"Autopilot run: phases {start}..{opts.to}, mode {opts.mode}, rollback tag {t}, "
        f"fast Python tests at start {opts.min_tests}, push {'on' if opts.push else 'off'}"
    )
    for n in range(start, opts.to + 1):
        if not run_phase(n, opts, gates):
            log("Autopilot stopped. Read the BLOCKED.md named above, fix or decide, then rerun.")
            commit_log(opts)
            sys.exit(2)
    log(f"Autopilot finished: phases {start}..{opts.to} done. See docs/phases/INDEX.md.")
    commit_log(opts)
    print("\a", end="", flush=True)


def collected_tests() -> int | None:
    """Number of fast Python tests (`not slow`) at the start of the run: the floor for every gate."""
    r = subprocess.run(
        ["uv", "run", "pytest", "-m", "not slow", "-q", "--collect-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=child_env(),
    )
    found = re.findall(r"(\d+)(?:/\d+)? tests? collected", r.stdout)
    return int(found[-1]) if found else None


def commit_log(opts) -> None:
    """Commit the run log and index so the next run starts from a clean tree."""
    if opts.dry_run:
        return
    write_index()
    git("add", "docs/phases")
    git("commit", "-m", "autopilot: run log and phase index")
    push(opts)


def cmd_status(opts) -> None:
    write_index()
    print((PH / "INDEX.md").read_text())
    if LOG.exists():
        print("Last log lines:\n" + "\n".join(LOG.read_text().splitlines()[-12:]))


def cmd_backfill(opts) -> None:
    a, _, b = opts.phases.partition("-")
    for n in range(int(a), int(b or a) + 1):
        if (pdir(n) / "REPORT.md").exists():
            log(f"phase {n}: REPORT.md exists, skipping backfill")
            continue
        log(f"phase {n}: backfilling documentation")
        r = run_claude(
            opts, f"/phase-auto backfill {n}", pdir(n) / "transcripts" / "backfill.jsonl", hours=1.5
        )
        m = load_meta(n)
        record(m, "backfill", r)
        m["status"] = (
            m.get("status") if m.get("status") == "done" else "done (manual, docs backfilled)"
        )
        save_meta(n, m)
        commit_all(f"phase {n}: backfilled phase documentation")
    write_index()
    commit_all("docs: phase index")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument(
            "--mode",
            default=os.environ.get("KD_MODE", "auto"),
            choices=["auto", "dontAsk", "acceptEdits", "bypassPermissions"],
        )
        p.add_argument("--model", default=os.environ.get("KD_MODEL"))
        p.add_argument(
            "--budget", type=float, default=None, help="max USD per session (client-side estimate)"
        )
        p.add_argument(
            "--limit-wait", type=int, default=30, help="minutes to wait after a usage/rate limit"
        )
        p.add_argument(
            "--limit-retries", type=int, default=12, help="12 x 30 min covers a 5-hour usage window"
        )
        p.add_argument("--dry-run", action="store_true")
        p.add_argument(
            "--push",
            action="store_true",
            help="after each phase (and on a block), fast-forward push the branch and tags to origin",
        )

    p = sub.add_parser("init")
    common(p)
    p.add_argument("--skip-smoke", action="store_true")
    p = sub.add_parser("run")
    common(p)
    p.add_argument("--from", dest="from_phase", type=int)
    p.add_argument("--to", type=int, default=LAST_PHASE)
    p.add_argument("--redo", action="store_true", help="restart the --from phase from planning")
    p.add_argument("--review-rounds", type=int, default=3)
    p.add_argument("--fix-attempts", type=int, default=3)
    p.add_argument(
        "--target-attempts",
        type=int,
        default=3,
        help="fix attempts for target shortfalls before they are recorded as gaps and the run continues",
    )
    p.add_argument("--gate-minutes", type=int, default=60)
    p.add_argument("--build-hours", type=float, default=6.0)
    p = sub.add_parser("status")
    common(p)
    p = sub.add_parser("backfill")
    common(p)
    p.add_argument("--phases", default="0-3")
    opts = ap.parse_args()
    {"init": cmd_init, "run": cmd_run, "status": cmd_status, "backfill": cmd_backfill}[opts.cmd](
        opts
    )


if __name__ == "__main__":
    main()
