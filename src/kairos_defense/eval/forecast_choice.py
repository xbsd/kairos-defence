"""The pre-registered forecast-anchor comparison (D-090): ``target`` (§13 as written) against
``match_kind`` on the training nights only.

Prober queries of nights 2025-03-01 to 2026-02-28 (answerable, months 1 to 12), T = 90 s, the
shipped model. ``match_kind`` is adopted if and only if its median error is at least 50 m lower
and its P80 is not higher. Run ``uv run python -m kairos_defense.eval.forecast_choice``; it prints
both modes and writes ``reports/forecast_choice.json``. Months 13 to 18 and the demo are never
consulted here.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np

from kairos_defense.config import Config, load_config
from kairos_defense.eval.downstream import forecast_error
from kairos_defense.eval.harness import labelled_tracks, query_cases, track_list
from kairos_defense.eval.metrics import inf_percentile
from kairos_defense.eval.training import TrainSplit
from kairos_defense.eval.truth import track_truth
from kairos_defense.forecast.analog import forecast
from kairos_defense.match.matcher import DtwMatcher
from kairos_defense.match.query import load_query
from kairos_defense.ports import TrackStore, VectorStore

log = logging.getLogger(__name__)

MODES = ("target", "match_kind")
AT_S = 90
MIN_GAIN_M = 50.0
OUT_FILE = "forecast_choice.json"


def verdict(stats: dict[str, dict]) -> str:
    """The D-090 rule: ``match_kind`` when its median is ≥ 50 m lower and its P80 no higher."""
    t, m = stats["target"], stats["match_kind"]
    ok = m["median_m"] <= t["median_m"] - MIN_GAIN_M and m["p80_m"] <= t["p80_m"]
    return "match_kind" if ok else "target"


def compare_anchors(
    cfg: Config,
    store: TrackStore,
    vstore: VectorStore,
    truth,
    first: date,
    last: date,
    models_dir: Path | str | None = None,
    at_s: int = AT_S,
) -> dict:
    """Forecast error per anchor mode on answerable prober queries of nights ``first``..``last``
    at ``at_s``; returns both modes' median, P80 and count, the per-query errors and the
    verdict."""
    matcher = DtwMatcher(store, vstore, cfg.scoring, models_dir or cfg.app.paths.models)
    cases = [c for c in query_cases(labelled_tracks(track_list(store), truth), ("prober",),
                                    first, last) if c.answerable]  # fmt: skip
    rec = truth.set_index("track_id")[["recovery_x_m", "recovery_y_m"]]
    scorings = {m: cfg.scoring.model_copy(update={"forecast": cfg.scoring.forecast.model_copy(
        update={"anchor": m})}) for m in MODES}  # fmt: skip
    errors: dict[str, list[float]] = {m: [] for m in MODES}
    rows = []
    for c in cases:
        q = load_query(store, c.track_id, at_s, cfg.scoring)
        res = matcher.match(q)
        row = {"track_id": c.track_id, "target": q.target.asset_id}
        for m in MODES:
            e = forecast_error(forecast(store, q, res, scorings[m]), rec.loc[c.track_id])
            errors[m].append(e)
            row[m] = e
        rows.append(row)
    stats = {}
    for m in MODES:
        v = np.sort(np.asarray(errors[m], dtype=np.float64))
        stats[m] = {"median_m": inf_percentile(v, 50) if len(v) else float("nan"),
                    "p80_m": inf_percentile(v, 80) if len(v) else float("nan"), "queries": len(v),
                    "missing": int(np.isinf(v).sum())}  # fmt: skip
    return {"nights": [first.isoformat(), last.isoformat()], "at_s": at_s,
            "rule": f"match_kind iff median at least {MIN_GAIN_M:g} m lower and P80 not higher",
            "modes": stats, "verdict": verdict(stats) if cases else "target",
            "queries": rows}  # fmt: skip


def main(argv: list[str] | None = None, split: TrainSplit | None = None) -> dict:
    """Run the comparison on the config folder ``argv[0]`` (default ``config``), print it and
    write ``reports/forecast_choice.json``; returns the result."""
    from rich.console import Console

    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceVectorStore

    logging.basicConfig(level=logging.WARNING)
    args = sys.argv[1:] if argv is None else argv
    cfg = load_config(args[0] if args else "config")
    sp = split or TrainSplit()
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        lance = LanceVectorStore(cfg.app.paths.lancedb)
        out = compare_anchors(cfg, store, lance, track_truth(cfg.app), sp.train_first,
                              sp.train_last)  # fmt: skip
    path = Path(cfg.app.paths.reports) / OUT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    con = Console(highlight=False)
    con.print(f"forecast anchor on nights {out['nights'][0]} to {out['nights'][1]}, T = {AT_S} s")
    for m, st in out["modes"].items():
        con.print(f"  {m:<10} median {st['median_m']:7.0f} m  P80 {st['p80_m']:7.0f} m  "
                  f"queries {st['queries']}  missing {st['missing']}")  # fmt: skip
    con.print(f"rule: {out['rule']}\nverdict: {out['verdict']} (current forecast.anchor: "
              f"{cfg.scoring.forecast.anchor})\nwrote {path}")  # fmt: skip
    return out


if __name__ == "__main__":
    main()
