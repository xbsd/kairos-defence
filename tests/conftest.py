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
    """``cfg`` with every data path under ``folder`` (app, truth, memory, live, LanceDB, models,
    exports, cache) and the signing key there too."""
    paths = cfg.app.paths.model_copy(
        update={"duckdb": str(folder / "kd.duckdb"), "truth": str(folder / "gt.duckdb"),
                "memory": str(folder / "mem.duckdb"), "live": str(folder / "live.duckdb"),
                "live_mode": str(folder / "live_mode"), "lancedb": str(folder / "lancedb"),
                "reports": str(folder / "reports"), "models": str(folder / "models"),
                "exports": str(folder / "exports"), "cache": str(folder / "cache")}
    )  # fmt: skip
    signing = cfg.app.signing.model_copy(update={"key_path": folder / "keys" / "ed25519.pem"})
    app = cfg.app.model_copy(update={"paths": paths, "signing": signing})
    return cfg.model_copy(update={"app": app})


def with_paths(cfg, folder: Path, *names: str):
    """``cfg`` with the named ``paths`` (and ``key`` for the signing key) moved under ``folder``,
    keeping the others (for example the data and models of ``p1_index``)."""
    moved = {"memory": "mem.duckdb", "exports": "exports", "cache": "cache", "reports": "reports",
             "live": "live.duckdb", "live_mode": "live_mode"}  # fmt: skip
    paths = cfg.app.paths.model_copy(update={n: str(folder / moved[n]) for n in names
                                             if n in moved})  # fmt: skip
    signing = cfg.app.signing
    if "key" in names:
        signing = signing.model_copy(update={"key_path": folder / "keys" / "ed25519.pem"})
    app = cfg.app.model_copy(update={"paths": paths, "signing": signing})
    return cfg.model_copy(update={"app": app})


def with_models(cfg, folder: Path):
    """``cfg`` with ``paths.models`` set to ``folder``."""
    paths = cfg.app.paths.model_copy(update={"models": str(folder)})
    return cfg.model_copy(update={"app": cfg.app.model_copy(update={"paths": paths})})


TOY_COEF = {"shape_sim": 4.0, "rf_match": 3.0, "bearing_sim": 1.5, "tod_sim": 2.0,
            "launch_sim": 1.0, "radius_sim": 1.0, "alt_sim": 1.0}  # fmt: skip
TOY_TAU = 1.6


def write_toy_models(cfg, folder: Path) -> Path:
    """Hand-set fusion model and DTW calibration (no truth, no training) in ``folder``."""
    from kairos_defense.match.fusion import (
        CALIBRATION_FILE,
        MODEL_FILE,
        DtwCalibration,
        FusionModel,
    )

    feats = tuple(cfg.scoring.fusion.features)
    FusionModel("fusion-v1", feats, tuple(TOY_COEF[f] for f in feats), -9.0, TOY_TAU,
                "toy").save(folder / MODEL_FILE)  # fmt: skip
    q = {"p10": 1.4, "p50": TOY_TAU, "p90": 1.9}
    DtwCalibration("dtw-calibration-v1", TOY_TAU, 0, 0, q, q, cfg.scoring.dtw.band_fraction,
                   [0.5, 1.5], "toy").save(folder / CALIBRATION_FILE)  # fmt: skip
    return folder


@pytest.fixture(scope="session")
def toy_models(p1_index, tmp_path_factory):
    """``p1_index.cfg`` with a hand-set model folder (matcher tests; training is tested apart)."""
    folder = write_toy_models(p1_index.cfg, tmp_path_factory.mktemp("toy_models"))
    return with_models(p1_index.cfg, folder)


@dataclass
class Indexed:
    cfg: object  # Config with temporary paths
    gen: object  # Generated
    summary: object  # IndexSummary
    reports: object = None  # ReportsSummary (phase 5)


@pytest.fixture(scope="session")
def p1_index(cfg, tmp_path_factory) -> Indexed:
    """The nights of all six P1 flights (live included) generated, written and indexed, report
    index included (what `make index` builds)."""
    from kairos_defense.features.build import build_index
    from kairos_defense.recall.index import build_reports_index
    from kairos_defense.sim.generate import generate
    from kairos_defense.sim.writers import write_all

    c = tmp_config(cfg, tmp_path_factory.mktemp("p1"))
    g = generate(cfg, 42, nights=P1_NIGHTS)
    write_all(c.app, g.tables, g.truth)
    summary = build_index(c)
    return Indexed(c, g, summary, build_reports_index(c))


@dataclass
class Seeded:
    path: Path  # a closed, seeded ledger file: copy it, never write it
    summary: object  # SeedSummary
    cfg: object  # p1_index.cfg


@pytest.fixture(scope="session")
def seeded_p1(p1_index, tmp_path_factory) -> Seeded:
    """The six P1 nights seeded once into a ledger of their own (not p1_index's memory path)."""
    from kairos_defense.memory.seed import seed
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.ledger_duck import DuckCaseMemory

    path = tmp_path_factory.mktemp("seeded") / "seeded.duckdb"
    c = p1_index.cfg
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store, DuckCaseMemory(path, c.app) as mem:
        summary = seed(mem, store, c.scenario)
    return Seeded(path, summary, c)


@pytest.fixture
def ledger_copy(seeded_p1, tmp_path):
    """A fresh, writable copy of the seeded P1 ledger for one test."""
    from kairos_defense.store.ledger_duck import DuckCaseMemory

    with DuckCaseMemory(tmp_path / "copy.duckdb", seeded_p1.cfg.app) as mem:
        mem.copy_from(seeded_p1.path)
        yield mem


@dataclass
class LiveKit:
    cfg: object  # toy_models config
    store: object  # DuckTrackStore (read-only)
    lance: object
    matcher: object
    recall: object
    incident: object  # LiveIncident DEMO-BRAVO-0828
    lock: object


@pytest.fixture(scope="module")
def live_kit(toy_models):
    """The P1 nights' live incident with the hand-set models: what a live loop needs. Module
    scope: its read-only connection must close before other modules write the P1 file."""
    import threading

    from kairos_defense.live.replay import load_incident
    from kairos_defense.match.matcher import DtwMatcher
    from kairos_defense.recall.embed import make_embedder
    from kairos_defense.recall.search import ReportRecall
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceReportIndex, LanceVectorStore

    c = toy_models
    store = DuckTrackStore(c.app.paths.duckdb, c.app)
    lance = LanceVectorStore(c.app.paths.lancedb)
    matcher = DtwMatcher(store, lance, c.scoring, c.app.paths.models)
    recall = ReportRecall(store, LanceReportIndex(c.app.paths.lancedb), lance,
                          make_embedder(c.app), c.scoring)  # fmt: skip
    yield LiveKit(c, store, lance, matcher, recall, load_incident(store, "DEMO-BRAVO-0828"),
                  threading.RLock())  # fmt: skip
    store.close()


def make_loop(kit: LiveKit, cache=None, fingerprint=None, incident=None):
    from kairos_defense.live.loop import LiveLoop

    return LiveLoop(incident or kit.incident, kit.store, kit.cfg.scoring, matcher=kit.matcher,
                    recall=kit.recall, cache=cache, lock=kit.lock,
                    fingerprint=fingerprint)  # fmt: skip


@pytest.fixture(scope="module")
def live_loop(live_kit):
    """One shared loop (its in-memory results are reused across tests: read, never mutate)."""
    return make_loop(live_kit)


def api_config(base_cfg, seeded_path: Path, folder: Path):
    """``base_cfg`` with the ledger (a copy of ``seeded_path``), live tables, cache, exports and
    signing key under ``folder``."""
    import shutil

    c = with_paths(
        base_cfg, folder, "memory", "live", "live_mode", "cache", "exports", "key", "reports"
    )
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seeded_path, c.app.paths.memory)
    return c


@pytest.fixture(scope="module")
def api(toy_models, seeded_p1, tmp_path_factory):
    """A TestClient on ``create_app`` over the P1 nights, the hand-set models and a copy of the
    seeded ledger (module-scoped: tests that need a clean ledger POST /api/admin/reseed)."""
    from fastapi.testclient import TestClient

    from kairos_defense.api.app import create_app

    c = api_config(toy_models, seeded_p1.path, tmp_path_factory.mktemp("api"))
    with TestClient(create_app(c)) as client:
        client.cfg = c
        yield client


SWARM_NIGHTS = (date(2025, 3, 25), date(2026, 3, 16), date(2026, 4, 19), date(2026, 5, 3),
                date(2026, 5, 10), date(2026, 6, 14), date(2026, 8, 6),
                date(2026, 8, 28))  # fmt: skip


@pytest.fixture(scope="session")
def swarm_index(cfg, tmp_path_factory):
    """Both planted swarm events, three more S1 and three S2 events (and the planted DELTA and live
    BRAVO nights, so the ledger can be seeded), generated, written and indexed in a temporary
    folder."""
    from kairos_defense.features.build import build_index
    from kairos_defense.sim.generate import generate
    from kairos_defense.sim.writers import write_all

    c = tmp_config(cfg, tmp_path_factory.mktemp("swarm"))
    g = generate(cfg, 42, nights=SWARM_NIGHTS)
    write_all(c.app, g.tables, g.truth)
    return c, build_index(c)


@pytest.fixture(scope="module")
def live_services(toy_models, seeded_p1, tmp_path_factory):
    """A ``Services`` with live mode over the P1 nights and the hand-set models: a copy of the
    seeded ledger, a scratch live-mode folder, reruns every 20 s (fewer reruns, fast tests) and
    the worker run on submit (``live_threaded=False``: no thread, no waiting)."""
    from kairos_defense.api.services import Services
    from tests.unit.live_kit import fast_scoring

    c = api_config(fast_scoring(toy_models), seeded_p1.path, tmp_path_factory.mktemp("livemode"))
    svc = Services(c, live_threaded=False)
    yield svc
    svc.close()
