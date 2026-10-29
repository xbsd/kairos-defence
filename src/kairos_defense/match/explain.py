"""Explanations (SPEC §10.7): the top three fused contributions, as plain reasons.

A reason is shown when its §10.7 condition holds and its contribution ``coef_i × x_i`` is positive;
reasons are ordered by contribution, at most three. The warp reason ranks with ``shape_sim``'s
contribution. Values in the text are the past flight's own signature values: its RF family, its
approach bearing rounded to 5°, its orbit radius rounded to 10 m (D-074).
"""

from __future__ import annotations

import math

from kairos_defense.match.dtw_rerank import warp_text
from kairos_defense.match.fusion import FusionModel

MAX_REASONS = 3


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def reasons(
    features: dict[str, float], model: FusionModel, warp_ratio: float, csig: dict
) -> list[str]:
    """Up to three reasons for one match, strongest contribution first."""
    contrib = model.contributions(features)
    found: list[tuple[float, int, str]] = []

    def add(feature: str, text: str) -> None:
        found.append((contrib.get(feature, 0.0), len(found), text))

    if features.get("rf_match", 0.0) == 1.0:
        add("rf_match", f"Same RF family ({csig.get('rf_family')})")
    brg = _num(csig.get("approach_bearing_deg"))
    if features.get("bearing_sim", 0.0) > 0.9 and brg is not None:
        add("bearing_sim", f"Same approach bearing ({round(brg / 5) * 5 % 360:.0f}°)")
    rad = _num(csig.get("loiter_radius_m"))
    if features.get("radius_sim", 0.0) > 0.8 and rad is not None:
        add("radius_sim", f"Same orbit radius (~{round(rad / 10) * 10:.0f} m)")
    if features.get("launch_sim", 0.0) > 0.7:
        add("launch_sim", "Same launch area")
    if features.get("tod_sim", 0.0) > 0.9:
        add("tod_sim", "Same time of night")
    pace = warp_text(warp_ratio)
    if pace is not None:
        add("shape_sim", f"Same shape, {pace}")
    found = [r for r in found if r[0] > 0]
    found.sort(key=lambda r: (-r[0], r[1]))
    return [text for _, _, text in found[:MAX_REASONS]]
