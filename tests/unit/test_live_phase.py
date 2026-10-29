"""D-115: the flight phase of the ``features`` message, on synthetic 1 Hz features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense.live.phase import first_loiter_s, flight_phase


def frame(dist: list[float], speed: list[float]) -> pd.DataFrame:
    n = len(dist)
    return pd.DataFrame({"t_s": np.arange(n), "dist_target_m": dist, "speed_ms": speed})


def test_short_track_is_approach() -> None:
    assert flight_phase(frame([900.0, 880.0], [15.0, 15.0]), "fuel_farm") == "approach"
    assert flight_phase(frame([], []), "fuel_farm") == "approach"


def test_inbound_is_approach() -> None:
    d = list(np.linspace(1500, 700, 60))
    assert flight_phase(frame(d, [15.0] * 60), "fuel_farm") == "approach"


def test_fence_target_is_approach_even_when_close() -> None:
    f = frame([100.0] * 30, [8.0] * 30)
    assert flight_phase(f, "fence") == "approach" and first_loiter_s(f, "fence") is None


def test_orbit_is_loiter() -> None:
    d = list(np.linspace(1500, 600, 40)) + [180.0] * 30
    s = [20.0] * 40 + [12.0] * 30
    f = frame(d, s)
    assert flight_phase(f, "fuel_farm") == "loiter"
    assert 40 <= first_loiter_s(f, "fuel_farm") <= 50


def test_noisy_second_inside_orbit_stays_loiter() -> None:
    d = list(np.linspace(1500, 600, 40)) + [180.0] * 30 + [180.0]
    s = [20.0] * 40 + [12.0] * 30 + [40.0]
    assert flight_phase(frame(d, s), "fuel_farm") == "loiter"


def test_leaving_after_loiter_is_egress() -> None:
    d = list(np.linspace(1500, 600, 40)) + [180.0] * 30 + list(np.linspace(300, 1200, 20))
    s = [20.0] * 40 + [12.0] * 30 + [20.0] * 20
    assert flight_phase(frame(d, s), "fuel_farm") == "egress"
