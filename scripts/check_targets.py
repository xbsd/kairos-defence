#!/usr/bin/env python3
"""Autopilot target gate: fail unless the newest eval report meets the targets for phase N.

Run by scripts/autopilot.py after `make eval` (see docs/phases/gates.json). Edited by humans only.
Targets come from SPEC §19.3, §10.9 and the phase exit checks in §20. Checks are cumulative: phase N
must also meet every target of the earlier phases, so later work cannot quietly lose an earlier win.

Usage: python3 scripts/check_targets.py N
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
FRESH_HOURS = 3  # the gate runs `make eval` just before this script

# phase -> list of (metric key in eval JSON "metrics", operator, target, label)
METRICS: dict[int, list[tuple[str, str, float, str]]] = {
    4: [
        ("recall_at_5_t120", ">=", 0.80, "Recall@5 at T=120 s (§19.3)"),
        ("dtw_lift", ">=", 0.10, "DTW lift over the Euclidean baseline (§19.3)"),
        ("copycat_first_t120", "<=", 0.05, "Copycat-first rate (§19.3)"),
        ("latency_prefilter_p95_ms", "<=", 50.0, "Prefilter p95 ms (§10.9)"),
        ("latency_dtw_p95_ms", "<=", 800.0, "DTW re-rank of 50 candidates p95 ms (§10.9)"),
        ("latency_end_to_end_p95_ms", "<=", 1500.0, "End-to-end live update p95 ms (§10.9)"),
    ],
    5: [
        ("report_linkage", ">=", 0.70, "Report linkage (§19.3)"),
        ("forecast_median_t90_m", "<=", 400.0, "Forecast median error at T=90 s, m (§19.3)"),
    ],
    9: [
        ("time_to_match_t90", ">=", 0.70, "Time to match: top 3 by T=90 s (§19.3)"),
        ("swarm_top1", ">=", 0.80, "Swarm top-1 (§19.3)"),
    ],
}

# Measured and printed, never failing: the user asked on 2026-10-28 not to let latency block the
# run (D-060). A missing key still fails, so the numbers are always produced.
REPORT_ONLY = {"latency_prefilter_p95_ms", "latency_dtw_p95_ms", "latency_end_to_end_p95_ms"}

# phase -> demo assertion keys (eval JSON "demo" rows) that must have status "pass"
DEMO: dict[int, list[str]] = {
    4: ["live_first_contact_local", "live_orbit_established_s", "live_top3_incidents"],
    5: ["live_rank1_report_for", "forecast_error_max_m"],
    8: [],  # phase 8: every demo row except swarm_top1 (added below)
    9: ["*"],  # phase 9: every demo row
}


def newest_eval() -> Path | None:
    files = sorted(REPORTS.glob("eval_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def check(n: int) -> list[str]:
    problems: list[str] = []
    f = newest_eval()
    if f is None:
        return ["no reports/eval_*.json found (run `make eval`)"]
    age_h = (time.time() - f.stat().st_mtime) / 3600
    if age_h > FRESH_HOURS:
        problems.append(f"{f.name} is {age_h:.1f} h old; `make eval` did not write a fresh report")
    d = json.loads(f.read_text(encoding="utf-8"))
    metrics = d.get("metrics", {})
    if n >= 4:
        if str(d.get("method", "")).lower() == "euclidean":
            problems.append(
                "eval ran the Euclidean baseline; from phase 4 `make eval` must run DTW"
            )
        if not (REPORTS / "baseline.json").exists():
            problems.append(
                "reports/baseline.json missing (phase 4 runs `kairos-defense eval --baseline`)"
            )
    for phase, rows in METRICS.items():
        if phase > n:
            continue
        for key, op, target, label in rows:
            v = metrics.get(key)
            if not isinstance(v, (int, float)):
                problems.append(f"{label}: metrics.{key} missing from {f.name}")
                continue
            ok = v >= target if op == ">=" else v <= target
            warn_only = key in REPORT_ONLY
            word = "PASS" if ok else ("WARN" if warn_only else "FAIL")
            print(f"{word}  {label}: {v:.4g} (target {op} {target:g})")
            if not ok and not warn_only:
                problems.append(f"{label}: {v:.4g}, target {op} {target:g}")
    rows = {r.get("key"): r for r in d.get("demo", [])}
    want: set[str] = set()
    for phase, keys in DEMO.items():
        if phase <= n:
            want |= set(rows) if "*" in keys else set(keys)
    if n >= 8:
        want |= set(rows) - ({"swarm_top1"} if n < 9 else set())
    for key in sorted(want):
        r = rows.get(key)
        status = (r or {}).get("status", "missing")
        print(f"{'PASS' if status == 'pass' else 'FAIL'}  demo {key}: {status}")
        if status != "pass":
            observed = (r or {}).get("observed", "-")
            problems.append(f"demo assertion {key}: status {status!r}, observed {observed}")
    return problems


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("usage: check_targets.py N")
    problems = check(int(sys.argv[1]))
    if problems:
        print("\nTargets not met:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("\nAll targets met.")


if __name__ == "__main__":
    main()
