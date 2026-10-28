"""Synthetic tracks and sites with known answers, shared by the phase 3 feature tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from kairos_defense.features.channels import SiteGeometry, Target

T0 = datetime(2026, 5, 3, 2, 0, 0)  # naive UTC


def points(t_s, x, y, alt=None, quality=None, t0: datetime = T0) -> pd.DataFrame:
    """A track_points-like frame from per-point seconds and coordinates."""
    t_s = np.asarray(t_s, dtype=np.float64)
    n = len(t_s)
    return pd.DataFrame(
        {
            "ts": [t0 + timedelta(seconds=float(s)) for s in t_s],
            "x_m": np.asarray(x, dtype=np.float64),
            "y_m": np.asarray(y, dtype=np.float64),
            "alt_m": np.full(n, 100.0) if alt is None else np.asarray(alt, dtype=np.float64),
            "quality": np.full(n, 0.9) if quality is None else np.asarray(quality),
        }
    )


def straight(n: int = 121, speed: float = 12.0, bearing_deg: float = 45.0, **kw) -> pd.DataFrame:
    t = np.arange(n, dtype=np.float64)
    b = np.radians(bearing_deg)
    return points(t, speed * t * np.sin(b), speed * t * np.cos(b), **kw)


def circle(
    n: int = 361,
    radius: float = 180.0,
    rate_dps: float = 3.0,
    ccw: bool = True,
    center=(0.0, 0.0),
    start_bearing: float = 0.0,
    **kw,
) -> pd.DataFrame:
    """Orbit at ``rate_dps`` around ``center``; ccw means the bearing from the center decreases."""
    t = np.arange(n, dtype=np.float64)
    brg = np.radians(start_bearing + (-1 if ccw else 1) * rate_dps * t)
    return points(t, center[0] + radius * np.sin(brg), center[1] + radius * np.cos(brg), **kw)


def square(cx: float, cy: float, half: float) -> Polygon:
    return Polygon([(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half),
                    (cx - half, cy + half)])  # fmt: skip


def site(fence_half: float = 1000.0) -> SiteGeometry:
    """Two 50 m square assets inside a square fence centered on the origin."""
    a = Target("TEST-fuel_farm", "fuel_farm", square(400, 300, 25), np.array([400.0, 300.0]))
    b = Target("TEST-hq", "hq", square(-300, -200, 25), np.array([-300.0, -200.0]))
    fence = square(0, 0, fence_half)
    f = Target("TEST-fence", "fence", fence, np.array([0.0, 0.0]))
    return SiteGeometry("TEST", "COASTAL", -5, (a, b, f), fence)
