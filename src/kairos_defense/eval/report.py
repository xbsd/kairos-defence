"""Evaluation outputs (SPEC §19.4): ``reports/eval_<date>.md``, ``.json`` and a figure, plus the
``--baseline`` regression gate.

``eval --baseline`` writes ``reports/baseline.json``; a later run without the flag fails if a gated
metric is more than 5% worse (relative) than the baseline, or a demo assertion fails. Phase 3
reports the Euclidean baseline numbers only; the first ``baseline.json`` is written in phase 4
(D-056).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from kairos_defense.eval.harness import T_GRID, EvalRun
from kairos_defense.eval.metrics import (
    Outcome,
    copycat_first_rate,
    mrr,
    percentiles,
    recall_at_k,
    time_to_match_share,
    times_to_match,
)

TOLERANCE = 0.05  # §19.4: fail when a metric worsens by more than 5% relative
GATED = {  # metric -> +1 higher is better, -1 lower is better
    "recall_at_5_t120": 1, "mrr_t120": 1, "time_to_match_t90": 1, "copycat_first_t120": -1,
    "recall_at_5_t120_copycats": 1, "latency_prefilter_p95_ms": -1,
    "latency_end_to_end_p95_ms": -1,
}  # fmt: skip
PENDING = {
    "dtw_lift": "phase 4 (needs DTW + fusion)",
    "report_linkage": "phase 5",
    "forecast_error_t90": "phase 5",
    "swarm_top1": "phase 9",
    "latency_dtw": "phase 4",
}
LATENCY_STAGES = (("query_build", "query_ms"), ("prefilter", "prefilter_ms"),
                  ("end_to_end", "total_ms"))  # fmt: skip
BUDGET_MS = {"prefilter": 50, "end_to_end": 1500}  # §10.9 p95 (end to end includes DTW later)


def _actor_table(outcomes: list[Outcome], at_s: int = 120) -> dict[str, dict]:
    out = {}
    for actor in sorted({o.actor_id for o in outcomes}):
        rows = [o for o in outcomes if o.actor_id == actor and o.at_s == at_s]
        ranks = [o.true_rank for o in rows if o.ran and o.true_rank is not None]
        r5, n = recall_at_k(rows, 5, at_s)
        out[actor] = {"queries": n, "recall_at_5": r5,
                      "median_best_rank": float(np.median(ranks)) if ranks else None,
                      "found_in_candidates": len(ranks)}  # fmt: skip
    return out


def summarize(run: EvalRun) -> dict:
    """Flat metric dict plus breakdowns, JSON-serializable."""
    p, c = run.outcomes["probers"], run.outcomes["copycats"]
    ran = [o for o in p + c if o.ran]
    lat = {stage: percentiles([getattr(o, f) for o in ran]) for stage, f in LATENCY_STAGES}
    ttm = [v for v in times_to_match(p).values() if v is not None]
    metrics = {
        "recall_at_5_t120": recall_at_k(p, 5, 120)[0],
        "mrr_t120": mrr(p, 120)[0],
        "time_to_match_t90": time_to_match_share(p, 90)[0],
        "copycat_first_t120": copycat_first_rate(p, 120)[0],
        "recall_at_5_t120_copycats": recall_at_k(c, 5, 120)[0],
        "median_time_to_match_s": float(np.median(ttm)) if ttm else None,
    }
    for stage, (p50, p95) in lat.items():
        metrics[f"latency_{stage}_p50_ms"] = p50
        metrics[f"latency_{stage}_p95_ms"] = p95
    sets = run.sets
    counts = {
        "prober_queries": len(sets.probers),
        "prober_unanswerable": sum(not q.answerable for q in sets.probers),
        "copycat_queries": len(sets.copycats),
        "copycat_unanswerable": sum(not q.answerable for q in sets.copycats),
        "swarm_incidents": len(sets.swarm_incidents),
        "searches": len(ran),
    }
    by_t = {
        str(t): {
            "recall_at_5_probers": recall_at_k(p, 5, t)[0],
            "top3_probers": recall_at_k(p, 3, t)[0],
            "recall_at_5_copycats": recall_at_k(c, 5, t)[0],
            "window_s": sorted({o.window_s for o in p + c if o.at_s == t and o.window_s}),
            "ran": any(o.ran for o in p + c if o.at_s == t),
        }
        for t in T_GRID
    }
    return {
        "method": run.method,
        "created_at": run.created_at.isoformat(timespec="seconds"),
        "elapsed_s": round(run.elapsed_s, 1),
        "metrics": metrics,
        "counts": counts,
        "recall_by_t": by_t,
        "per_actor": _actor_table(p + c),
        "pending": PENDING,
        "demo": [asdict(r) for r in run.demo],
    }


def regressions(metrics: dict, baseline: dict, tol: float = TOLERANCE) -> list[str]:
    """Gated metrics more than ``tol`` (relative) worse than ``baseline``."""
    out = []
    for key, sign in GATED.items():
        v, b = metrics.get(key), baseline.get(key)
        if v is None or b is None:
            continue
        worse = v < b * (1 - tol) if sign > 0 else v > b * (1 + tol)
        if worse:
            out.append(f"{key}: {v:.4g} vs baseline {b:.4g}")
    return out


def _fmt(v, pct: bool = False) -> str:
    if v is None:
        return "-"
    return f"{v:.0%}" if pct else f"{v:.3f}"


def _ms(v) -> str:
    return "-" if v is None else f"{v:.0f}"


def markdown(s: dict, figure: str) -> str:
    m, n = s["metrics"], s["counts"]
    day = s["created_at"][:10]
    lines = [
        f"# Evaluation · {s['method']} baseline · {day}",
        "",
        f"`kairos-defense eval` (phase 3): the Euclidean baseline (§10.2) on the §19 protocol. "
        "No targets apply yet; these numbers are the reference for phase 4's DTW lift. "
        f"Run time {s['elapsed_s']:.0f} s.",
        "",
        "## Query sets (§19.1)",
        "",
        "| Set | Queries | Unanswerable (no earlier same-actor track, D-009) |",
        "|---|---:|---:|",
        f"| Probers (nights 2026-03-01 to 08-31) | {n['prober_queries']} | "
        f"{n['prober_unanswerable']} |",
        f"| Copycats | {n['copycat_queries']} | {n['copycat_unanswerable']} |",
        f"| Swarm incidents | {n['swarm_incidents']} | matched in phase 9 |",
        "",
        f"Each answerable query runs at T = {', '.join(map(str, T_GRID))} s after its first radar "
        f"point ({n['searches']} searches). T = 30 s is below `min_track_s` (45 s): the matcher "
        "waits, which counts as a miss.",
        "",
        "## Headline metrics (§19.3, probers unless noted)",
        "",
        "| Metric | Value | v1 target (from phase 4) |",
        "|---|---:|---|",
        f"| Recall@5 at T = 120 s | {_fmt(m['recall_at_5_t120'])} | ≥ 0.80 |",
        f"| MRR at T = 120 s | {_fmt(m['mrr_t120'])} | report only |",
        f"| Time to match: top 3 by T = 90 s | {_fmt(m['time_to_match_t90'], True)} | ≥ 70% |",
        f"| Copycat-first rate at T = 120 s | {_fmt(m['copycat_first_t120'], True)} | ≤ 5% |",
        f"| Recall@5 at T = 120 s, copycat queries | {_fmt(m['recall_at_5_t120_copycats'])} "
        "| report only |",
        "| DTW lift | - | ≥ +0.10 (phase 4) |",
        "| Report linkage | - | ≥ 0.70 (phase 5) |",
        "| Forecast error at T = 90 s | - | median ≤ 400 m (phase 5) |",
        "| Swarm top-1 | - | ≥ 0.80 (phase 9) |",
        "",
        "## Recall by time since first contact",
        "",
        "| T (s) | Window W (s) | Recall@5 probers | Top-3 probers | Recall@5 copycats |",
        "|---:|---|---:|---:|---:|",
    ]
    for t, r in s["recall_by_t"].items():
        w = ", ".join(map(str, r["window_s"])) if r["ran"] else "not run"
        cells = [t, w, _fmt(r["recall_at_5_probers"]), _fmt(r["top3_probers"]),
                 _fmt(r["recall_at_5_copycats"])]  # fmt: skip
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", f"![Recall@5 against T]({figure})", "",
              "## Per actor (Recall@5 at T = 120 s)", "",
              "| Actor | Queries | Recall@5 | Found in top 50 | Median best rank |",
              "|---|---:|---:|---:|---:|"]  # fmt: skip
    for actor, a in s["per_actor"].items():
        med = "-" if a["median_best_rank"] is None else f"{a['median_best_rank']:.0f}"
        lines.append(f"| {actor} | {a['queries']} | {_fmt(a['recall_at_5'])} | "
                     f"{a['found_in_candidates']} | {med} |")  # fmt: skip
    lines += ["", "## Latency (§10.9)", "", "| Stage | p50 (ms) | p95 (ms) | p95 budget (ms) |",
              "|---|---:|---:|---:|"]  # fmt: skip
    names = {
        "query_build": "Query build (resample, target, PAA)",
        "prefilter": "Prefilter (LanceDB search + grouping)",
        "end_to_end": "End to end",
    }
    for stage, label in names.items():
        budget = BUDGET_MS.get(stage)
        lines.append(f"| {label} | {_ms(m[f'latency_{stage}_p50_ms'])} | "
                     f"{_ms(m[f'latency_{stage}_p95_ms'])} | {budget or '-'} |")  # fmt: skip
    lines += ["| DTW re-rank (50 candidates) | - | - | 800 (phase 4) |", "",
              "## Demo assertions (`scenario_demo.yaml`)", "",
              "| Expectation | Expected | Observed | Status |", "|---|---|---|---|"]  # fmt: skip
    for r in s["demo"]:
        lines.append(f"| `{r['key']}` | {r['expected']} | {r['observed']} | {r['status']} |")
    lines += ["", "Truth is read only by `kairos_defense.eval` to label outcomes (CLAUDE.md "
              "rule 2); every search is filtered to tracks that started before the query "
              "(rule 3).", ""]  # fmt: skip
    return "\n".join(lines)


def plot_recall(s: dict, path: Path) -> Path:
    """Recall@5 against T for prober and copycat queries (one axis, two series)."""
    from kairos_defense.sim.figures import INK, INK_2, MUTED, SERIES_PATH, SERIES_RADAR, SURFACE
    from kairos_defense.sim.figures import _plt as plt_

    plt = plt_()
    ts = [int(t) for t, r in s["recall_by_t"].items() if r["ran"]]
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=110, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    n = s["counts"]
    np_, nc = (
        n["prober_queries"] - n["prober_unanswerable"],
        n["copycat_queries"] - n["copycat_unanswerable"],
    )
    series = (("recall_at_5_probers", f"probers ({np_})", SERIES_PATH),
              ("recall_at_5_copycats", f"copycats ({nc})", SERIES_RADAR))  # fmt: skip
    for key, label, color in series:
        ys = [s["recall_by_t"][str(t)][key] for t in ts]
        if any(y is None for y in ys):  # no answerable queries in this set
            continue
        ax.plot(ts, ys, color=color, lw=2, marker="o", ms=8, mec=SURFACE, mew=2, label=label)
        ax.annotate(label, (ts[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=INK_2, fontsize=9)  # fmt: skip
    ax.set_xlim(min(ts) - 10, max(ts) + 40)
    ax.set_ylim(0, 1.02)
    ax.set_xticks(ts)
    ax.set_xlabel("T, seconds after first radar contact", color=INK_2, fontsize=9)
    ax.set_ylabel("Recall@5", color=INK_2, fontsize=9)
    ax.set_title(f"{s['method'].title()} baseline: same actor in the top 5", color=INK,
                 fontsize=10, loc="left")  # fmt: skip
    ax.grid(axis="y", color=MUTED, lw=0.5, alpha=0.4)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2, loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return path


def write_reports(run: EvalRun, reports_dir: Path | str) -> tuple[Path, Path, dict]:
    """Write ``eval_<date>.md``, ``eval_<date>.json`` and the figure; returns paths and summary."""
    out = Path(reports_dir)
    s = summarize(run)
    day = run.created_at.date().isoformat()
    fig = plot_recall(s, out / "figures" / "eval_recall_by_t.png")
    md = out / f"eval_{day}.md"
    md.write_text(markdown(s, f"figures/{fig.name}"), encoding="utf-8")
    js = out / f"eval_{day}.json"
    payload = {**s, "outcomes": [asdict(o) for name in ("probers", "copycats")
                                 for o in run.outcomes[name]]}  # fmt: skip
    js.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")
    return md, js, s


def gate(s: dict, baseline_path: Path) -> list[str]:
    """Problems that make ``eval`` exit non-zero: regressions against ``baseline.json`` (if it
    exists) and failed demo assertions."""
    problems = [f"demo assertion failed: {r['key']} ({r['observed']})" for r in s["demo"]
                if r["status"] == "fail"]  # fmt: skip
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
        problems += regressions(s["metrics"], base.get("metrics", {}))
    return problems
