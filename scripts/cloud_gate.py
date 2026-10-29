#!/usr/bin/env python3
"""Gate helper for running the remaining phases inside ONE Claude Code session (e.g. on the web),
where `scripts/autopilot.py run` cannot start new sessions with `claude -p`.

The session does the plan, review, build and fix work itself (docs/CLOUD_HANDOFF.md). This script
keeps the parts that must not be Claude's judgement: it runs the same gate as the autopilot
(docs/phases/gates.json, the documentation check, the test-count floor, the target checker with
soft gaps, D-063) and it is the only thing that marks a phase done.

  python3 scripts/cloud_gate.py gate N      # run the gate; exit 0 pass, 1 only target gaps, 2 hard failure
  python3 scripts/cloud_gate.py accept N    # after 3 gap-only attempts: write GAPS.md, record the gaps
  python3 scripts/cloud_gate.py close N     # after a pass (or accept): mark done, index, commit, tag
  python3 scripts/cloud_gate.py status      # phase table

Stdlib only. Reuses scripts/autopilot.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "autopilot", Path(__file__).with_name("autopilot.py")
)
ap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ap)


def _opts(n: int) -> argparse.Namespace:
    m = ap.load_meta(n)
    o = argparse.Namespace()
    try:
        o.accepted = set(json.loads(ap.ACCEPTED_FILE.read_text()).get("keys", []))
    except (OSError, ValueError):
        o.accepted = set()
    # Test floor: the most tests any earlier gate passed, else the count collected now.
    floor = 0
    for k in range(n):
        floor = max(floor, int(ap.load_meta(k).get("tests_passed") or 0))
    o.min_tests = floor or ap.collected_tests()
    o.start_sha = m.get("sha_before") or ap.head()
    o.target_attempts = 3
    return o


def cmd_gate(n: int) -> int:
    m = ap.load_meta(n)
    m.setdefault("started", ap.now())
    m["sha_before"] = m.get("sha_before") or ap.head()
    m["status"] = "running"
    attempt = int(m.get("gate_attempts") or 0) + 1
    o = _opts(n)
    ok, reason, logf, gaps = ap.run_gate(n, attempt, ap.load_gates(), 60, o)
    m["gate_attempts"] = attempt
    m["last_gate"] = {"attempt": attempt, "ok": ok, "reason": reason, "gaps": gaps,
                      "log": str(logf.relative_to(ap.ROOT))}  # fmt: skip
    if ok and o.min_tests:
        m["tests_passed"] = o.min_tests
    m.setdefault("steps", []).append({"step": f"gate-{attempt}", "at": ap.now(), "ok": ok})
    ap.save_meta(n, m)
    ap.log(f"phase {n}: cloud gate attempt {attempt}: "
           + ("PASS" if ok else ("FAIL: " + reason if reason else f"{len(gaps)} target gap(s)")))  # fmt: skip
    print(f"\nGate log: {logf.relative_to(ap.ROOT)}")
    if ok:
        print("PASS. Next: python3 scripts/cloud_gate.py close", n)
        return 0
    if reason:
        print("HARD FAILURE:", reason, "\nFix the cause (read the log), commit, rerun the gate.")
        return 2
    print("ONLY TARGET GAPS:\n" + "\n".join(f"  - {g}" for g in gaps))
    print(
        f"Gap-only attempts so far: {attempt}. After 3, run: python3 scripts/cloud_gate.py accept {n}"
    )
    return 1


def cmd_accept(n: int) -> int:
    m = ap.load_meta(n)
    last = m.get("last_gate") or {}
    if last.get("reason") or not last.get("gaps"):
        print("accept needs a last gate with only target gaps; run the gate first.")
        return 2
    o = _opts(n)
    ap.accept_gaps(n, m, last["gaps"], ap.ROOT / last["log"], o)
    m["gaps"] = last["gaps"]
    m["gaps_accepted"] = True
    ap.save_meta(n, m)
    print(
        "Gaps recorded in",
        f"docs/phases/phase-{n:02d}/GAPS.md. Next: python3 scripts/cloud_gate.py close {n}",
    )
    return 0


def cmd_close(n: int) -> int:
    m = ap.load_meta(n)
    last = m.get("last_gate") or {}
    if not (last.get("ok") or m.get("gaps_accepted")):
        print("close needs a passing gate, or accepted gaps. Run the gate first.")
        return 2
    m.update(status="done", finished=ap.now(), sha_after=ap.head())
    if m.get("gaps_accepted"):
        ap.set_progress_status(
            n, f"done with gaps ({dt.date.today()}, see docs/phases/phase-{n:02d}/GAPS.md)"
        )
    else:
        ap.set_progress_status(
            n, f"done ({dt.date.today()}, gate passed in a single cloud session)"
        )
    (ap.pdir(n) / "diffstat.txt").write_text(
        ap.git("diff", "--stat", m["sha_before"], "HEAD").stdout
    )
    ap.save_meta(n, m)
    ap.write_index()
    ap.commit_all(f"phase {n}: gate artifacts (cloud session)")
    t = ap.tag(f"phase-{n:02d}-done")
    ap.log(
        f"=== Phase {n}: done{' with gaps' if m.get('gaps_accepted') else ''} (cloud), tagged {t} ==="
    )
    print(f"Closed phase {n}, tagged {t}. Push now: git push origin HEAD && git push origin {t}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("cmd", choices=["gate", "accept", "close", "status"])
    p.add_argument("phase", type=int, nargs="?")
    a = p.parse_args()
    if a.cmd == "status":
        ap.write_index()
        print((ap.PH / "INDEX.md").read_text())
        return
    if a.phase is None:
        sys.exit("phase number required")
    sys.exit({"gate": cmd_gate, "accept": cmd_accept, "close": cmd_close}[a.cmd](a.phase))


if __name__ == "__main__":
    main()
