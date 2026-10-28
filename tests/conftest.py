from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def cfg():
    from kairos_defense.config import load_config

    return load_config(ROOT / "config")


@pytest.fixture(scope="session")
def world(cfg):
    from kairos_defense.sim.world import build_world

    return build_world(cfg, 42)


@pytest.fixture(scope="session")
def cal(cfg, world):
    from kairos_defense.sim.calendar import build_calendar

    return build_calendar(cfg, world, 42)


@dataclass
class Sample:
    plans: list
    paths: list


@pytest.fixture(scope="session")
def sample(cfg, world, cal) -> Sample:
    """One flight per actor and base (P1-P6, C1, C2) plus 30 hobbyists, flown at seed 42."""
    from kairos_defense.rng import rng_for
    from kairos_defense.sim.actors import actor_specs, hobbyist_plans, make_flight
    from kairos_defense.sim.kinematics import fly_plans

    plans = []
    night = date(2025, 10, 7)
    for spec in actor_specs(cfg):
        for i, base in enumerate(spec.bases):
            key = f"TEST/{spec.actor_id}/{base}"
            launch = datetime.combine(night, datetime.min.time()) + timedelta(hours=21, minutes=i)
            plans.append(make_flight(cfg, world, spec, key, base, launch, rng_for(7, key)))
    plans += hobbyist_plans(cfg, world, cal, 42)[:30]
    return Sample(plans, fly_plans(plans, world, cal, 42))


WINDOW = (date(2026, 8, 11), date(2026, 8, 31))  # three weeks, ending with the live night


@pytest.fixture(scope="session")
def g42(cfg):
    """The generator's in-memory output for a three-week window at seed 42."""
    from kairos_defense.sim.generate import generate

    return generate(cfg, 42, window=WINDOW)
