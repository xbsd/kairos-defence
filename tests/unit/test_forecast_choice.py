"""D-090: the pre-registered forecast-anchor comparison runs on a training split and applies its
rule (median at least 50 m lower and P80 not higher)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import kairos_defense.eval.forecast_choice as fcmod
from kairos_defense.eval.training import TrainSplit


def test_verdict_rule() -> None:
    def stats(t, m):
        return {"target": {"median_m": t[0], "p80_m": t[1]},
                "match_kind": {"median_m": m[0], "p80_m": m[1]}}  # fmt: skip

    assert fcmod.verdict(stats((500, 1000), (311, 492))) == "match_kind"
    assert fcmod.verdict(stats((500, 1000), (451, 900))) == "target"  # only 49 m better
    assert fcmod.verdict(stats((500, 1000), (450, 1000))) == "match_kind"  # exactly 50 m, P80 tie
    assert fcmod.verdict(stats((500, 1000), (300, 1001))) == "target"  # P80 worse


def test_forecast_choice_runs(toy_models, monkeypatch) -> None:
    monkeypatch.setattr(fcmod, "load_config", lambda _c: toy_models)
    split = TrainSplit(train_first=date(2026, 3, 1), train_last=date(2026, 7, 31))
    out = fcmod.main(["config"], split)
    assert set(out["modes"]) == {"target", "match_kind"}
    assert out["nights"] == ["2026-03-01", "2026-07-31"] and out["at_s"] == 90
    for s in out["modes"].values():
        assert s["queries"] == len(out["queries"]) > 0
        assert s["median_m"] >= 0 and s["p80_m"] >= s["median_m"]
    assert out["verdict"] == fcmod.verdict(out["modes"])
    assert {q["track_id"] for q in out["queries"]} <= {
        "P1-ALPHA-260303-T1",
        "P1-DELTA-260419-T1",
        "P1-ALPHA-260502-T1",
        "P1-CHARLIE-260710-T1",
    }
    path = Path(toy_models.app.paths.reports) / fcmod.OUT_FILE
    assert json.loads(path.read_text())["verdict"] == out["verdict"]
