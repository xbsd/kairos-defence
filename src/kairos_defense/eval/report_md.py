"""``reports/eval_<date>.md`` from the ``report.summarize`` dict (SPEC §19.4)."""

from __future__ import annotations

T_GRID_TEXT = "30, 45, 60, 90, 120, 180"


def _fmt(v, pct: bool = False) -> str:
    if v is None:
        return "-"
    return f"{v:.0%}" if pct else f"{v:.3f}"


def _ms(v) -> str:
    return "-" if v is None else f"{v:.0f}"


def _intro(s: dict) -> list[str]:
    day = s["created_at"][:10]
    if s["method"] == "dtw":
        return [
            f"# Evaluation · DTW + fusion · {day}",
            "",
            f"`kairos-defense eval` (phase 4): the DTW matcher with fusion model "
            f"`{s.get('model_version', '-')}` on the §19 protocol, {s.get('candidate_tracks', '-')}"
            " candidate tracks per query. The Euclidean baseline is the prefilter order of the "
            "same candidates on the same run (D-076). "
            f"Run time {s['elapsed_s']:.0f} s.",
        ]
    return [
        f"# Evaluation · {s['method']} baseline · {day}",
        "",
        f"`kairos-defense eval --method {s['method']}`: the Euclidean baseline (§10.2) on the §19 "
        f"protocol. Run time {s['elapsed_s']:.0f} s.",
    ]


def markdown(s: dict, figure: str) -> str:
    m, n = s["metrics"], s["counts"]
    lines = [
        *_intro(s),
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
        f"Each answerable query runs at T = {T_GRID_TEXT} s after its first radar point "
        f"({n['searches']} searches). T = 30 s is below `min_track_s` (45 s): the matcher waits, "
        "which counts as a miss.",
        "",
        "## Headline metrics (§19.3, probers unless noted)",
        "",
        "| Metric | Value | v1 target |",
        "|---|---:|---|",
        f"| Recall@5 at T = 120 s | {_fmt(m['recall_at_5_t120'])} | ≥ 0.80 |",
        f"| Recall@5 at T = 120 s, Euclidean order of the same candidates | "
        f"{_fmt(m.get('recall_at_5_t120_baseline'))} | reference |",
        f"| DTW lift | {_fmt(m.get('dtw_lift'))} | ≥ +0.10 |",
        f"| MRR at T = 120 s | {_fmt(m['mrr_t120'])} | report only |",
        f"| Time to match: top 3 by T = 90 s | {_fmt(m['time_to_match_t90'], True)} | ≥ 70% |",
        f"| Copycat-first rate at T = 120 s | {_fmt(m['copycat_first_t120'], True)} | ≤ 5% |",
        f"| Recall@5 at T = 120 s, copycat queries | {_fmt(m['recall_at_5_t120_copycats'])} "
        "| report only |",
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
    k = s.get("candidate_tracks", "-")
    lines += ["", f"![Recall@5 against T]({figure})", "",
              "## Per actor (Recall@5 at T = 120 s)", "",
              f"| Actor | Queries | Recall@5 | Found in top {k} | Median best rank |",
              "|---|---:|---:|---:|---:|"]  # fmt: skip
    for actor, a in s["per_actor"].items():
        med = "-" if a["median_best_rank"] is None else f"{a['median_best_rank']:.0f}"
        lines.append(f"| {actor} | {a['queries']} | {_fmt(a['recall_at_5'])} | "
                     f"{a['found_in_candidates']} | {med} |")  # fmt: skip
    lines += ["", "## Latency (§10.9)", "", "| Stage | p50 (ms) | p95 (ms) | p95 budget (ms) |",
              "|---|---:|---:|---:|"]  # fmt: skip
    names = {
        "query_build": ("Query build (resample, target, PAA)", "-"),
        "prefilter": ("Prefilter (LanceDB search + grouping)", "50"),
        "dtw": (f"DTW re-rank ({k} candidates)", "800 (for 50)"),
        "end_to_end": ("End to end", "1,500"),
    }
    for stage, (label, budget) in names.items():
        lines.append(f"| {label} | {_ms(m.get(f'latency_{stage}_p50_ms'))} | "
                     f"{_ms(m.get(f'latency_{stage}_p95_ms'))} | {budget} |")  # fmt: skip
    lines += ["", "Latency is reported, never gating (D-060).", "",
              "## Demo assertions (`scenario_demo.yaml`)", "",
              "| Expectation | Expected | Observed | Status |", "|---|---|---|---|"]  # fmt: skip
    for r in s["demo"]:
        lines.append(f"| `{r['key']}` | {r['expected']} | {r['observed']} | {r['status']} |")
    lines += ["", "Truth is read only by `kairos_defense.eval` to label outcomes (CLAUDE.md "
              "rule 2); every search is filtered to tracks that started before the query "
              "(rule 3).", ""]  # fmt: skip
    return "\n".join(lines)
