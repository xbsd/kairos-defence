"""Evaluation outputs (SPEC §19.4): ``reports/eval_<date>.md``, ``.json`` and a figure, plus the
``--baseline`` regression gate.

``eval --baseline`` writes ``reports/baseline.json``; a later run without the flag fails if a gated
metric is more than 5% worse (relative) than the baseline, or a demo assertion fails. Phase 4's exit
check writes the first ``baseline.json`` from the DTW matcher (D-056, D-076). The Markdown writer is
in ``report_md.py``.
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
    dtw_lift,
    forecast_summary,
    mrr,
    percentiles,
    recall_at_k,
    report_linkage,
    time_to_match_share,
    times_to_match,
)
from kairos_defense.eval.report_md import markdown

TOLERANCE = 0.05  # §19.4: fail when a metric worsens by more than 5% relative
# Latency is timing noise at the 5% level, so it regresses only when more than 50% plus 2 ms worse
# (D-060); the absolute §10.9 latency targets are enforced separately by scripts/check_targets.py.
LATENCY_TOLERANCE = 0.5
LATENCY_SLACK_MS = 2.0
GATED = {  # metric -> +1 higher is better, -1 lower is better
    "recall_at_5_t120": 1, "mrr_t120": 1, "time_to_match_t90": 1, "copycat_first_t120": -1,
    "recall_at_5_t120_copycats": 1, "dtw_lift": 1, "latency_prefilter_p95_ms": -1,
    "latency_dtw_p95_ms": -1, "latency_end_to_end_p95_ms": -1,
    "report_linkage": 1, "forecast_median_t90_m": -1,
}  # fmt: skip
PENDING = {"swarm_top1": "phase 9"}
LATENCY_STAGES = (("query_build", "query_ms"), ("prefilter", "prefilter_ms"), ("dtw", "dtw_ms"),
                  ("end_to_end", "total_ms"))  # fmt: skip
# §10.9 p95 budgets. The DTW budget is for 50 candidates; phase 4 re-ranks 500 (D-068, D-076).
BUDGET_MS = {"prefilter": 50, "dtw": 800, "end_to_end": 1500}


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


def downstream_metrics(probers: list[Outcome]) -> dict:
    """Phase 5 keys (D-088): forecast error at T = 90 and 120 s, report linkage at 120 s, and
    the forecast and recall timings (report only, outside the timed matcher span)."""
    med90, p80_90, n90, miss90 = forecast_summary(probers, 90)
    med120, p80_120, _, miss120 = forecast_summary(probers, 120)
    link, hits, total = report_linkage(probers, 120)
    out = {
        "forecast_median_t90_m": med90,
        "forecast_p80_t90_m": p80_90,
        "forecast_queries_t90": n90,
        "forecast_missing_t90": miss90,
        "forecast_median_t120_m": med120,
        "forecast_p80_t120_m": p80_120,
        "forecast_missing_t120": miss120,
        "report_linkage": link,
        "report_linkage_retrieved": hits,
        "report_linkage_relevant": total,
    }
    for stage in ("forecast", "recall"):
        p50, p95 = percentiles([getattr(o, f"{stage}_ms") for o in probers])
        out[f"latency_{stage}_p50_ms"], out[f"latency_{stage}_p95_ms"] = p50, p95
    return out


def summarize(run: EvalRun) -> dict:
    """Flat metric dict plus breakdowns, JSON-serializable."""
    p, c = run.outcomes["probers"], run.outcomes["copycats"]
    ran = [o for o in p + c if o.ran]
    lat = {stage: percentiles([getattr(o, f) for o in ran]) for stage, f in LATENCY_STAGES}
    ttm = [v for v in times_to_match(p).values() if v is not None]
    lift, _, base_r5 = dtw_lift(p, 5, 120)
    metrics = {
        "recall_at_5_t120": recall_at_k(p, 5, 120)[0],
        "recall_at_5_t120_baseline": base_r5,
        "dtw_lift": lift,
        "mrr_t120": mrr(p, 120)[0],
        "time_to_match_t90": time_to_match_share(p, 90)[0],
        "copycat_first_t120": copycat_first_rate(p, 120)[0],
        "recall_at_5_t120_copycats": recall_at_k(c, 5, 120)[0],
        "median_time_to_match_s": float(np.median(ttm)) if ttm else None,
    }
    for stage, (p50, p95) in lat.items():
        metrics[f"latency_{stage}_p50_ms"] = p50
        metrics[f"latency_{stage}_p95_ms"] = p95
    metrics.update(downstream_metrics(p))
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
        "model_version": run.model_version,
        "candidate_tracks": run.candidate_tracks,
        "created_at": run.created_at.isoformat(timespec="seconds"),
        "elapsed_s": round(run.elapsed_s, 1),
        "metrics": metrics,
        "counts": counts,
        "recall_by_t": by_t,
        "per_actor": _actor_table(p + c),
        "pending": PENDING if run.reports_indexed else {**PENDING, "report_linkage": "no index"},
        "demo": [asdict(r) for r in run.demo],
    }


def regressions(metrics: dict, baseline: dict, tol: float = TOLERANCE) -> list[str]:
    """Gated metrics more than ``tol`` (relative) worse than ``baseline``.

    Latency uses the looser
    ``LATENCY_TOLERANCE`` and ``LATENCY_SLACK_MS`` bound (D-060)."""
    out = []
    for key, sign in GATED.items():
        v, b = metrics.get(key), baseline.get(key)
        if v is None or b is None:
            continue
        if key.startswith("latency_"):
            worse = v > b * (1 + LATENCY_TOLERANCE) + LATENCY_SLACK_MS
        else:
            worse = v < b * (1 - tol) if sign > 0 else v > b * (1 + tol)
        if worse:
            out.append(f"{key}: {v:.4g} vs baseline {b:.4g}")
    return out


def plot_recall(s: dict, path: Path) -> Path:
    """Recall@5 against T for prober and copycat queries (one axis, two series)."""
    from kairos_defense.sim.figures import INK, INK_2, MUTED, SERIES_PATH, SERIES_RADAR, SURFACE
    from kairos_defense.sim.figures import _plt as plt_

    plt = plt_()
    with plt.rc_context({"font.family": "DejaVu Sans"}):  # bundled with matplotlib (D-077)
        _draw_recall(plt, s, path, (INK, INK_2, MUTED, SERIES_PATH, SERIES_RADAR, SURFACE))
    return path


def _draw_recall(plt, s: dict, path: Path, colors: tuple) -> None:
    INK, INK_2, MUTED, SERIES_PATH, SERIES_RADAR, SURFACE = colors
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
    title = "DTW + fusion" if s["method"] == "dtw" else f"{s['method'].title()} baseline"
    ax.set_title(f"{title}: same actor in the top 5", color=INK, fontsize=10, loc="left")
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
