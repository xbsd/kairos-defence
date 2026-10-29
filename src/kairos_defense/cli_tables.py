"""Rich tables printed by ``kairos-defense match``, ``models`` and ``eval`` (outside ``cli.py``).

Missing numbers print as ``-``: a warp ratio is NaN beyond the explained top 20 or when it is not
credible (D-069), and the Euclidean baseline has no warp or reasons (D-054).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from rich.table import Table


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
    for stage in ("query_build", "prefilter", "dtw", "end_to_end"):
        p50, p95 = m.get(f"latency_{stage}_p50_ms"), m.get(f"latency_{stage}_p95_ms")
        t.add_row(f"latency {stage.replace('_', ' ')} p50 / p95",
                  "-" if p50 is None else f"{p50:.0f} / {p95:.0f} ms")  # fmt: skip
    for r in s["demo"]:
        t.add_row(f"demo {r['key']}", f"{r['status']}: {r['observed']}")
    t.add_row("elapsed", f"{s['elapsed_s']:.1f} s")
    return t
