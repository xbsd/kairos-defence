"""Evaluation metrics (SPEC §19.3) as pure functions over per-query outcomes.

An outcome is one query track at one protocol time T: whether the matcher ran, the 1-based rank of
the best same-actor track (``true_rank``, None if absent) and of the best copycat track
(``copycat_rank``), and latencies in milliseconds. Unanswerable queries (no earlier same-actor
track, D-009) are excluded before these functions are called.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Outcome:
    track_id: str
    actor_id: str
    actor_type: str
    at_s: int
    ran: bool
    true_rank: int | None = None
    copycat_rank: int | None = None
    window_s: int | None = None
    query_ms: float | None = None
    prefilter_ms: float | None = None
    total_ms: float | None = None
    top: tuple[str, ...] = ()


def _at(outcomes: Iterable[Outcome], at_s: int) -> list[Outcome]:
    return [o for o in outcomes if o.at_s == at_s]


def recall_at_k(outcomes: Iterable[Outcome], k: int, at_s: int) -> tuple[float | None, int]:
    """Share of queries with a same-actor track in the top ``k`` at ``at_s``; ``(value, n)``.
    A query whose matcher did not run counts as a miss."""
    rows = _at(outcomes, at_s)
    if not rows:
        return None, 0
    hits = sum(o.ran and o.true_rank is not None and o.true_rank <= k for o in rows)
    return hits / len(rows), len(rows)


def mrr(outcomes: Iterable[Outcome], at_s: int) -> tuple[float | None, int]:
    """Mean reciprocal rank of the first same-actor track at ``at_s`` (0 when absent)."""
    rows = _at(outcomes, at_s)
    if not rows:
        return None, 0
    rr = [1.0 / o.true_rank if o.ran and o.true_rank else 0.0 for o in rows]
    return float(np.mean(rr)), len(rows)


def times_to_match(outcomes: Iterable[Outcome], top: int = 3) -> dict[str, int | None]:
    """Per query: the earliest protocol T with a same-actor track in the top ``top`` (None if
    never)."""
    first: dict[str, int | None] = {}
    for o in sorted(outcomes, key=lambda o: (o.track_id, o.at_s)):
        first.setdefault(o.track_id, None)
        hit = o.ran and o.true_rank is not None and o.true_rank <= top
        if hit and first[o.track_id] is None:
            first[o.track_id] = o.at_s
    return first


def time_to_match_share(
    outcomes: Iterable[Outcome], by_s: int = 90, top: int = 3
) -> tuple[float | None, int]:
    """Share of queries with a same-actor track in the top ``top`` by T = ``by_s`` (D-055)."""
    t = times_to_match(outcomes, top)
    if not t:
        return None, 0
    return sum(v is not None and v <= by_s for v in t.values()) / len(t), len(t)


def copycat_first_rate(outcomes: Iterable[Outcome], at_s: int) -> tuple[float | None, int]:
    """Share of queries where a copycat ranks above every same-actor track at ``at_s``."""
    rows = [o for o in _at(outcomes, at_s) if o.ran]
    if not rows:
        return None, 0
    first = [
        o.copycat_rank is not None and (o.true_rank is None or o.copycat_rank < o.true_rank)
        for o in rows
    ]
    return sum(first) / len(rows), len(rows)


def percentiles(
    values: Sequence[float | None], qs: Sequence[float] = (50, 95)
) -> list[float | None]:
    """Percentiles of the non-missing values (None when there are none)."""
    v = np.asarray([x for x in values if x is not None], dtype=np.float64)
    return [float(np.percentile(v, q)) if len(v) else None for q in qs]
