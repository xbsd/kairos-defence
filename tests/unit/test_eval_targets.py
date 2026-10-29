"""D-139: the §19.3 and §10.9 targets live in ``eval/targets.py`` and match the gate script.

``scripts/check_targets.py`` is edited by humans only. If this test fails after a human changed
the script, update ``kairos_defense/eval/targets.py`` to match: never edit the script from code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from kairos_defense.eval.report_md import markdown
from kairos_defense.eval.targets import BY_KEY, TARGETS, targets_json

ROOT = Path(__file__).resolve().parents[2]
FIX = "update src/kairos_defense/eval/targets.py (the script is edited by humans only)"


def _script():
    path = ROOT / "scripts" / "check_targets.py"
    spec = importlib.util.spec_from_file_location("check_targets", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_targets_match_check_targets_script() -> None:
    ct = _script()
    script = {key: (op, value, phase) for phase, rows in ct.METRICS.items()
              for key, op, value, _label in rows}  # fmt: skip
    ours = {t.key: (t.op, t.value, t.phase) for t in TARGETS}
    assert ours == script, f"targets differ from scripts/check_targets.py: {FIX}"
    assert {t.key for t in TARGETS if t.report_only} == set(ct.REPORT_ONLY), FIX


def test_targets_met_and_text() -> None:
    assert BY_KEY["recall_at_5_t120"].met(0.8) is True
    assert BY_KEY["recall_at_5_t120"].met(0.79) is False
    assert BY_KEY["forecast_median_t90_m"].met(400.0) is True
    assert BY_KEY["forecast_median_t90_m"].met(None) is None
    texts = {t.key: t.text() for t in TARGETS}
    assert texts["recall_at_5_t120"] == "≥ 0.80" and texts["dtw_lift"] == "≥ +0.10"
    assert texts["copycat_first_t120"] == "≤ 5%" and texts["forecast_median_t90_m"] == "≤ 400 m"
    assert texts["time_to_match_t90"] == "≥ 70%" and texts["latency_end_to_end_p95_ms"] == (
        "≤ 1,500 ms")  # fmt: skip
    assert BY_KEY["swarm_top1"].pending is None  # measured from phase 9 (§14)
    assert all(t.pending is None for t in TARGETS)


def _summary() -> dict:
    m = dict.fromkeys(["recall_at_5_t120", "mrr_t120", "time_to_match_t90",
                       "copycat_first_t120", "recall_at_5_t120_copycats"], 0.5)  # fmt: skip
    return {"method": "dtw", "created_at": "2026-10-29T00:00:00", "elapsed_s": 1.0,
            "model_version": "fusion-v1", "candidate_tracks": 500, "metrics": m,
            "counts": {"prober_queries": 1, "prober_unanswerable": 0, "copycat_queries": 1,
                       "copycat_unanswerable": 0, "swarm_incidents": 0, "searches": 2},
            "recall_by_t": {}, "per_actor": {}, "demo": [],
            "targets": targets_json()}  # fmt: skip


def test_eval_json_writes_targets() -> None:
    from kairos_defense.eval import report

    js = targets_json()
    assert [t["key"] for t in js] == [t.key for t in TARGETS]
    row = next(t for t in js if t["key"] == "latency_dtw_p95_ms")
    assert row == {**row, "op": "<=", "value": 800.0, "report_only": True, "text": "≤ 800 ms"}
    src = Path(report.__file__).read_text()
    assert '"targets": targets_json()' in src  # summarize() writes them into the eval JSON


def test_report_md_target_column_from_targets() -> None:
    md = markdown(_summary(), "figures/x.png")
    for key in ("recall_at_5_t120", "dtw_lift", "copycat_first_t120", "report_linkage",
                "forecast_median_t90_m", "time_to_match_t90"):  # fmt: skip
        assert f"| {BY_KEY[key].text()} |" in md, key
    assert "answerable) | - | ≥ 0.80 |" in md  # the swarm row, no metric in this summary
    assert "| 1,500 |" in md and "| 800 (for 50) |" in md
