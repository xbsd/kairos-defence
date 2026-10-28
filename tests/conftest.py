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


@dataclass
class Swarms:
    plans: list  # center plans, one per swarm event
    centers: list  # flown center paths
    drones: list  # per event: list of drone paths


@pytest.fixture(scope="session")
def swarms(cfg, world, cal) -> Swarms:
    """Every swarm event at seed 42 (random and planted), flown with its drones."""
    from kairos_defense.sim.kinematics import fly_plans
    from kairos_defense.sim.swarm import drone_paths, swarm_plans

    plans = swarm_plans(cfg, world, cal, 42)
    centers = fly_plans(plans, world, cal, 42)
    drones = [drone_paths(p, c, 42) for p, c in zip(plans, centers, strict=True)]
    return Swarms(plans, centers, drones)


PLANTED_NIGHTS = (date(2026, 3, 3), date(2026, 4, 19), date(2026, 5, 3), date(2026, 6, 14))


@pytest.fixture(scope="session")
def planted(cfg):
    """The nights of the planted ALPHA and DELTA flights and both planted swarm events."""
    from kairos_defense.sim.generate import generate

    return generate(cfg, 42, nights=PLANTED_NIGHTS)


@pytest.fixture(scope="session")
def world_names(world) -> list[str]:
    """Road, park and installation names: world vocabulary the guardrail scan allows."""
    from kairos_defense.sim.lexicon import park_name

    names = [r.name for r in world.roads] + [park_name(p.park_id) for p in world.parks]
    return names + [f"Installation {s.title()}" for s in world.sites]


P1_NIGHTS = (date(2025, 11, 14), date(2026, 3, 3), date(2026, 4, 19), date(2026, 5, 2),
             date(2026, 7, 10), date(2026, 8, 28))  # fmt: skip


def tmp_config(cfg, folder: Path):
    """``cfg`` with every data path under ``folder`` (app, truth, memory, LanceDB)."""
    paths = cfg.app.paths.model_copy(
        update={"duckdb": str(folder / "kd.duckdb"), "truth": str(folder / "gt.duckdb"),
                "memory": str(folder / "mem.duckdb"), "lancedb": str(folder / "lancedb"),
                "reports": str(folder / "reports")}
    )  # fmt: skip
    return cfg.model_copy(update={"app": cfg.app.model_copy(update={"paths": paths})})


@dataclass
class Indexed:
    cfg: object  # Config with temporary paths
    gen: object  # Generated
    summary: object  # IndexSummary


@pytest.fixture(scope="session")
def p1_index(cfg, tmp_path_factory) -> Indexed:
    """The nights of all six P1 flights (live included) generated, written and indexed."""
    from kairos_defense.features.build import build_index
    from kairos_defense.sim.generate import generate
    from kairos_defense.sim.writers import write_all

    c = tmp_config(cfg, tmp_path_factory.mktemp("p1"))
    g = generate(cfg, 42, nights=P1_NIGHTS)
    write_all(c.app, g.tables, g.truth)
    return Indexed(c, g, build_index(c))
