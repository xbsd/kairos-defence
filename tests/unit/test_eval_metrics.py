"""SPEC §19.3 metrics on hand-made outcomes with known answers, and the §19.4 regression gate."""

from __future__ import annotations

import pytest

from kairos_defense.eval.metrics import (
    Outcome,
    copycat_first_rate,
    mrr,
    percentiles,
    recall_at_k,
    time_to_match_share,
    times_to_match,
)
from kairos_defense.eval.report import regressions


def o(track: str, at: int, rank: int | None, cc: int | None = None, ran: bool = True) -> Outcome:
    return Outcome(track, "P", "prober", at, ran, rank, cc, 60, 1.0, 2.0, 3.0)


OUT = [
    o("a", 120, 1), o("b", 120, 4), o("c", 120, 9), o("d", 120, None, cc=2),
    o("a", 30, None, ran=False), o("a", 45, 7), o("a", 60, 2), o("a", 90, 1),
    o("b", 45, 3), o("b", 90, 5), o("c", 90, 2, cc=1), o("d", 90, None),
]  # fmt: skip


def test_recall_at_k() -> None:
    assert recall_at_k(OUT, 5, 120) == (0.5, 4)
    assert recall_at_k(OUT, 1, 120) == (0.25, 4)
    assert recall_at_k(OUT, 5, 30) == (0.0, 1)  # not run = miss
    assert recall_at_k(OUT, 5, 999) == (None, 0)


def test_mrr() -> None:
    value, n = mrr(OUT, 120)
    assert n == 4 and value == pytest.approx((1 + 1 / 4 + 1 / 9 + 0) / 4)


def test_time_to_match() -> None:
    t = times_to_match(OUT, top=3)
    assert t == {"a": 60, "b": 45, "c": 90, "d": None}
    assert time_to_match_share(OUT, by_s=90) == (0.75, 4)
    assert time_to_match_share(OUT, by_s=60) == (0.5, 4)


def test_copycat_first() -> None:
    assert copycat_first_rate(OUT, 120) == (0.25, 4)  # d: copycat at 2, no true match
    assert copycat_first_rate(OUT, 90) == (0.25, 4)  # c: copycat 1 above true 2


def test_percentiles() -> None:
    assert percentiles([1.0, 2.0, 3.0, None]) == [2.0, pytest.approx(2.9)]
    assert percentiles([None]) == [None, None]


def test_regressions_respect_direction() -> None:
    base = {"recall_at_5_t120": 0.80, "copycat_first_t120": 0.10, "latency_prefilter_p95_ms": 50.0}
    ok = {"recall_at_5_t120": 0.77, "copycat_first_t120": 0.104, "latency_prefilter_p95_ms": 52.0}
    assert regressions(ok, base) == []
    bad = {"recall_at_5_t120": 0.75, "copycat_first_t120": 0.2, "latency_prefilter_p95_ms": 78.0}
    assert len(regressions(bad, base)) == 3
    # D-060: latency regresses only above 1.5 x baseline + 2 ms (77 ms here); 60 ms is timing noise
    assert regressions({**bad, "latency_prefilter_p95_ms": 77.0}, base) == regressions(
        {**bad, "latency_prefilter_p95_ms": 60.0}, base
    )
    assert len(regressions({**bad, "latency_prefilter_p95_ms": 77.0}, base)) == 2
    assert regressions({"recall_at_5_t120": None}, base) == []


def test_dtw_lift_known_answer() -> None:
    from kairos_defense.eval.metrics import dtw_lift

    def o(tid, at, rank, base):
        return Outcome(tid, "P9", "prober", at, True, true_rank=rank, baseline_rank=base)

    rows = [o("a", 120, 1, 9), o("b", 120, 3, 4), o("c", 120, None, 2), o("d", 120, 2, None),
            o("a", 90, 1, 1), Outcome("e", "P9", "prober", 120, False)]  # fmt: skip
    lift, fused, base = dtw_lift(rows, 5, 120)
    assert fused == pytest.approx(3 / 5) and base == pytest.approx(2 / 5)  # e did not run: a miss
    assert lift == pytest.approx(1 / 5)
    assert dtw_lift([], 5, 120) == (None, None, None)


def test_report_linkage_known_answer() -> None:
    from kairos_defense.eval.metrics import report_linkage

    def lk(tid, hits, total, at=120):
        return Outcome(tid, "P9", "prober", at, True, linkage_hits=hits, linkage_total=total)

    rows = [lk("a", 3, 4), lk("b", 1, 1), lk("c", 0, 0), lk("a", 0, 7, at=90),
            Outcome("d", "P9", "prober", 120, True)]  # fmt: skip
    assert report_linkage(rows, 120) == (pytest.approx(0.8), 4, 5)  # (3 + 1) / (4 + 1 + 0)
    assert report_linkage([lk("c", 0, 0)], 120) == (None, 0, 0)


def test_forecast_summary_known_answer() -> None:
    from kairos_defense.eval.metrics import forecast_summary

    def fe(tid, err, at=90, ran=True):
        return Outcome(tid, "P9", "prober", at, ran, forecast_error_m=err)

    errs = [100.0, 200.0, 300.0, 400.0, 500.0]
    rows = [fe(str(i), e) for i, e in enumerate(errs)] + [fe("x", 9.0, at=120)]
    assert forecast_summary(rows, 90) == (300.0, pytest.approx(420.0), 5, 0)  # numpy's linear P80
    # a missing forecast counts as an infinite error, never as NaN
    rows = [fe("a", 100.0), fe("b", 200.0), fe("c", float("inf"))]
    assert forecast_summary(rows, 90) == (200.0, float("inf"), 3, 1)
    rows = [fe("a", 100.0), fe("b", float("inf")), fe("c", float("inf")), fe("d", 50.0)]
    med, p80, n, missing = forecast_summary(rows, 90)
    assert med == float("inf") and p80 == float("inf") and (n, missing) == (4, 2)
    assert forecast_summary([fe("a", None)], 90) == (None, None, 0, 0)
    assert forecast_summary([fe("a", 5.0, ran=False)], 90) == (None, None, 0, 0)
