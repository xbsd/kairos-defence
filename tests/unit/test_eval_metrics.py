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
    bad = {"recall_at_5_t120": 0.75, "copycat_first_t120": 0.2, "latency_prefilter_p95_ms": 60.0}
    assert len(regressions(bad, base)) == 3
    assert regressions({"recall_at_5_t120": None}, base) == []
