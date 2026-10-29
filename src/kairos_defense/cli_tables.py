"""Rich tables printed by ``kairos-defense match``, ``models``, ``eval``, ``forecast`` and
``recall`` (outside ``cli.py``).

Missing numbers print as ``-``: a warp ratio is NaN beyond the explained top 20 or when it is not
credible (D-069), and the Euclidean baseline has no warp or reasons (D-054).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from rich.table import Table
from rich.text import Text


def _num(v, fmt: str = "{:.3f}") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "-"
    return fmt.format(v)


def match_table(title: str, matches: list, method: str, local: Callable) -> Table:
    """One row per match: rank, track, base, local start, score; for DTW also shape, warp and
    reasons."""
    t = Table(title=title, title_justify="left")
    cols = ["#", "track", "base", "start (local)", "score"]
    cols += ["shape", "warp", "reasons"] if method == "dtw" else ["d²", "window"]
    for c in cols:
        t.add_column(c, justify="right" if c in ("#", "score", "shape", "warp", "d²") else "left")
    for i, m in enumerate(matches, 1):
        row = [str(i), m.track_id, m.installation_id, local(m.start_ts, m.installation_id),
               f"{m.score:.3f}"]  # fmt: skip
        if method == "dtw":
            row += [f"{m.shape_sim:.3f}", _num(m.warp_ratio, "{:.2f}"), "; ".join(m.reasons) or "-"]
        else:
            row += [f"{m.features['euclidean_d2']:.3f}",
                    f"{int(m.features['window_s'])} s @ {m.window_offset_s} s"]  # fmt: skip
        t.add_row(*row)
    return t


def models_table(s) -> Table:
    """``kairos-defense models``: training set, τ, coefficients, validation (``TrainSummary``)."""
    m, cal, v = s.model, s.calibration, s.model.validation
    t = Table(title="kairos-defense models", title_justify="left")
    t.add_column("Item")
    t.add_column("Value", justify="right")
    split = m.train_split
    t.add_row("training nights", f"{split['train_first']} to {split['train_last']}")
    t.add_row("T grid (s)", ", ".join(map(str, split["t_grid"])))
    t.add_row("training queries", f"{s.train['queries']:,}")
    t.add_row("training pairs (same actor)", f"{s.train['pairs']:,} ({s.train['positives']:,})")
    same, other = cal.d_norm_same, cal.d_norm_other
    t.add_row("τ (median same-actor d_norm)", f"{cal.tau:.4f}")
    t.add_row("d_norm p10/p50/p90 same actor",
              f"{same['p10']:.3f} / {same['p50']:.3f} / {same['p90']:.3f}")  # fmt: skip
    t.add_row("d_norm p10/p50/p90 others",
              f"{other['p10']:.3f} / {other['p50']:.3f} / {other['p90']:.3f}")  # fmt: skip
    for f, c in zip(m.features, m.coefficients, strict=True):
        t.add_row(f"coefficient {f}", f"{c:+.3f}")
    t.add_row("intercept", f"{m.intercept:+.3f}")
    t.add_row("training Recall@5 T=120 s (probers)", _num(v.get("train_recall_at_5_t120_probers")))
    t.add_row("validation nights", f"{split['valid_first']} to {split['valid_last']}")
    counts = f"{v.get('queries', 0):,} / {v.get('pairs', 0):,} ({v.get('positives', 0):,})"
    t.add_row("validation queries / pairs (same actor)", counts)
    t.add_row("validation ROC AUC", _num(v.get("roc_auc")))
    t.add_row("validation log loss", _num(v.get("log_loss")))
    t.add_row("validation Recall@5 T=120 s (probers)", _num(v.get("recall_at_5_t120_probers")))
    t.add_row("training hash", m.training_hash[:16])
    t.add_row("elapsed", f"{s.elapsed_s:.1f} s")
    return t


def eval_table(s: dict, method: str) -> Table:
    """``kairos-defense eval``: headline metrics, latency, demo rows (the ``summarize`` dict)."""
    m, n = s["metrics"], s["counts"]

    def f(v, pct: bool = False) -> str:
        return "-" if v is None else (f"{v:.0%}" if pct else f"{v:.3f}")

    t = Table(title=f"kairos-defense eval · {method}", title_justify="left")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("prober queries (unanswerable)",
              f"{n['prober_queries']} ({n['prober_unanswerable']})")  # fmt: skip
    t.add_row("copycat queries (unanswerable)",
              f"{n['copycat_queries']} ({n['copycat_unanswerable']})")  # fmt: skip
    t.add_row("model · candidates per query", f"{s['model_version']} · {s['candidate_tracks']}")
    t.add_row("Recall@5 at T=120 s", f(m["recall_at_5_t120"]))
    t.add_row("Recall@5 at T=120 s, Euclidean order (same run)",
              f(m.get("recall_at_5_t120_baseline")))  # fmt: skip
    t.add_row("DTW lift", f(m.get("dtw_lift")))
    t.add_row("MRR at T=120 s", f(m["mrr_t120"]))
    t.add_row("time to match (top 3 by T=90 s)", f(m["time_to_match_t90"], True))
    t.add_row("copycat-first at T=120 s", f(m["copycat_first_t120"], True))
    t.add_row("Recall@5 at T=120 s, copycats", f(m["recall_at_5_t120_copycats"]))
    t.add_row("report linkage (T=120 s, top 3, k=5)",
              f"{f(m.get('report_linkage'))} ({m.get('report_linkage_retrieved', 0)} of "
              f"{m.get('report_linkage_relevant', 0)})")  # fmt: skip
    for key, label in (("t90", "T=90 s"), ("t120", "T=120 s")):
        med, p80 = m.get(f"forecast_median_{key}_m"), m.get(f"forecast_p80_{key}_m")
        t.add_row(f"forecast error {label} median / P80",
                  "-" if med is None else f"{med:,.0f} / {p80:,.0f} m")  # fmt: skip
    for stage in ("query_build", "prefilter", "dtw", "end_to_end", "forecast", "recall"):
        p50, p95 = m.get(f"latency_{stage}_p50_ms"), m.get(f"latency_{stage}_p95_ms")
        t.add_row(f"latency {stage.replace('_', ' ')} p50 / p95",
                  "-" if p50 is None else f"{p50:.0f} / {p95:.0f} ms")  # fmt: skip
    for r in s["demo"]:
        t.add_row(f"demo {r['key']}", f"{r['status']}: {r['observed']}")
    t.add_row("elapsed", f"{s['elapsed_s']:.1f} s")
    return t


def analogs_table(fc) -> Table:
    """``kairos-defense forecast``: one row per analog (§13 steps 1-4)."""
    t = Table(title="analogs (top matches with a known recovery point)", title_justify="left")
    for c in ("#", "incident", "score", "recovery rel. (m)", "rotation", "anchor", "j* (s)",
              "mapped recovery (m)"):  # fmt: skip
        t.add_column(c, justify="right" if c in ("#", "score", "rotation", "j* (s)") else "left")
    for i, a in enumerate(fc.analogs, 1):
        rx, ry = a.recovery_rel_m
        t.add_row(str(i), a.incident_id, f"{a.score:.3f}", f"({rx:,.0f}, {ry:,.0f})",
                  f"{a.rotation_deg:+.0f}°", a.anchor_asset_id, str(a.aligned_t_s),
                  f"({a.recovery_x_m:,.0f}, {a.recovery_y_m:,.0f})")  # fmt: skip
    return t


def marked_text(text: str, clues) -> Text:
    """Report text with clue spans underlined; linked clues also bold (§12.4, §17.8)."""
    out = Text(text)
    for c in clues:
        out.stylize("bold underline" if c.linked else "underline", c.start, c.end)
    return out


def recall_table(mr, local: Callable) -> Table:
    """``kairos-defense recall``: the reports recalled for one matched incident."""
    t = Table(title=f"match #{mr.match_rank} {mr.incident_id} (score {mr.match_score:.3f})",
              title_justify="left")  # fmt: skip
    for c in ("#", "report", "source", "grade", "event (local)", "score", "text"):
        t.add_column(c, justify="right" if c in ("#", "score") else "left",
                     overflow="fold")  # fmt: skip
    for r in mr.reports:
        t.add_row(str(r.rank), r.report_id, r.source, r.source_grade,
                  local(r.event_ts_ms, mr.installation_id), f"{r.score:.4f}",
                  marked_text(r.text, r.clues))  # fmt: skip
    return t
