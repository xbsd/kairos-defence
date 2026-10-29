"""Flight phase of a live track for the ``features`` message (D-115): approach, loiter, egress.

On the 1 Hz features seen up to second s (``(n, …)`` frame from ``track_features``):

- ``loiter`` when at least 7 of the last 10 seconds pass ``signatures.loiter_mask`` (slower than
  1.2 × the median speed, within 600 m of the target) **and** the chosen target is an asset, not
  the fence. A partial track's target is the fence until the drone settles over an asset (D-081),
  and the fence pseudo-target is near every inbound drone, so the asset condition keeps an inbound
  drone at the fence in ``approach``.
- Once a loiter run of 10 s or more has happened: ``egress`` when ``dist_target_m`` is above
  600 m and has risen over the last 5 s, else still ``loiter`` (radar noise makes single seconds
  of an orbit fail the mask; the phase does not flicker back to approach).
- ``approach`` otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense.features.signatures import loiter_mask

PHASES = ("approach", "loiter", "egress")
RECENT_S, RECENT_MIN = 10, 7
RUN_MIN_S = 10
EGRESS_M, RISE_S = 600.0, 5


def loiter_seconds(features: pd.DataFrame, target_kind: str) -> np.ndarray:
    """Per second: whether 7 of the 10 seconds ending there pass the loiter mask; ``(n,)``."""
    if target_kind == "fence" or len(features) == 0:
        return np.zeros(len(features), dtype=bool)
    m = loiter_mask(features).astype(np.int64)
    c = np.concatenate([[0], np.cumsum(m)])
    n = len(m)
    lo = np.maximum(np.arange(1, n + 1) - RECENT_S, 0)
    return (c[1:] - c[lo]) >= RECENT_MIN


def _longest_run(b: np.ndarray) -> int:
    best = run = 0
    for v in b:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def flight_phase(features: pd.DataFrame, target_kind: str) -> str:
    """The phase at the last row of ``features`` (seen up to that second only, rule 3)."""
    if len(features) == 0:
        return "approach"
    loit = loiter_seconds(features, target_kind)
    if _longest_run(loit) < RUN_MIN_S:
        return "loiter" if loit[-1] else "approach"
    d = features["dist_target_m"].to_numpy(dtype=np.float64)
    if len(d) > RISE_S and np.isfinite(d[-1]) and d[-1] > EGRESS_M:
        past = d[-1 - RISE_S]
        if np.isfinite(past) and d[-1] > past:
            return "egress"
    return "loiter"


def first_loiter_s(features: pd.DataFrame, target_kind: str) -> int | None:
    """The first second (``t_s``) classed ``loiter`` in ``features``, or None."""
    loit = loiter_seconds(features, target_kind)
    idx = np.flatnonzero(loit)
    return int(features["t_s"].iloc[idx[0]]) if len(idx) else None
