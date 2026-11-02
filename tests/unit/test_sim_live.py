"""Live-mode scenarios (D-178): the five recipes, determinism, no actor in what is sent."""

from __future__ import annotations

import json

import pytest

from kairos_defense.sim import live_scenarios as ls
from kairos_defense.sim.live_clock import LiveClock


@pytest.fixture
def clock(cfg, tmp_path):
    return LiveClock(tmp_path / "clock.json", cfg.world.calendar.end_local)


def _relative(sc) -> list[str]:
    """Detections with times relative to the first launch and the sensor track ids blanked."""
    out = []
    for ms, m in sc.detections():
        d = {k: v for k, v in m.items() if k not in ("ts", "sensor_track_id")}
        out.append(json.dumps({**d, "dt": ms - sc.start_ms}, sort_keys=True))
    return sorted(out)  # same-ms detections of a swarm's drones are ordered by their track ids


def test_scenario_catalog_lists_the_five_scenarios(cfg) -> None:
    cat = {e["name"]: e for e in ls.catalog(cfg)}
    assert tuple(cat) == ls.SCENARIOS
    assert [a["id"] for a in cat["returning-prober"]["actors"]] == ["P1", "P2", "P3", "P4", "P5",
                                                                     "P6"]  # fmt: skip
    assert cat["returning-prober"]["default_actor"] == "P1"
    assert cat["returning-prober"]["allow_random"]
    assert [a["id"] for a in cat["copycat"]["actors"]] == ["C1", "C2"]
    assert [a["id"] for a in cat["swarm-repeat"]["actors"]] == ["S1", "S2"]
    assert cat["new-operator-twice"]["second_base"] and not cat["hobbyist"]["actors"]
    assert cat["returning-prober"]["actors"][0]["nickname"] == "County Rd operator"


def test_resolve_defaults_and_refusals(cfg) -> None:
    assert ls.resolve(cfg, "returning-prober", None, None, None, 1) == ("P1", "BRAVO", None)
    assert ls.resolve(cfg, "swarm-repeat", None, None, None, 1) == ("S1", "GOLF", None)
    assert ls.resolve(cfg, "new-operator-twice", None, "BRAVO", None, 1) == (None, "BRAVO",
                                                                             "CHARLIE")  # fmt: skip
    actor, base, _ = ls.resolve(cfg, "returning-prober", "random", "GOLF", None, 5)
    assert base == "GOLF" and actor in {"P4", "P6"}  # only they fly at GOLF


@pytest.mark.parametrize(("args", "match"), [
    (("nope", None, None, None), "unknown scenario"),
    (("returning-prober", "P9", None, None), "unknown actor"),
    (("returning-prober", "P1", "GOLF", None), "flies only at"),
    (("hobbyist", "P1", None, None), "takes no actor"),
    (("hobbyist", None, "MARS", None), "unknown base"),
    (("new-operator-twice", None, "BRAVO", "BRAVO"), "another installation"),
    (("copycat", None, None, "ALPHA"), "one base only"),
])  # fmt: skip
def test_bad_actor_or_base_is_refused(cfg, args, match) -> None:
    with pytest.raises(ls.ScenarioError, match=match):
        ls.resolve(cfg, *args, 1)


@pytest.mark.parametrize("name", ls.SCENARIOS)
def test_same_seed_same_detections(cfg, world, tmp_path, name) -> None:
    a = LiveClock(tmp_path / "a.json", cfg.world.calendar.end_local)
    b = LiveClock(tmp_path / "b.json", cfg.world.calendar.end_local)
    one = ls.build(cfg, world, a, name, seed=11)
    b.reserve(one.start_ms + 86_400_000)  # one night later: same launch time of night
    two = ls.build(cfg, world, b, name, seed=11)
    again = ls.build(cfg, world, a, name, seed=11)
    assert one.start_ms + 86_400_000 == two.start_ms
    assert _relative(one) == _relative(two)  # the seed, not the date, flies the flight
    assert one.detections() == again.detections()  # same seed and clock: identical messages
    assert len(one.detections()) > 50


@pytest.mark.parametrize("name", ["returning-prober", "hobbyist", "swarm-repeat"])
def test_different_seeds_differ(cfg, world, clock, name) -> None:
    assert _relative(ls.build(cfg, world, clock, name, seed=11)) != _relative(
        ls.build(cfg, world, clock, name, seed=12)
    )


@pytest.mark.parametrize("name", ls.SCENARIOS)
def test_detections_are_time_ordered_and_carry_no_actor(cfg, world, clock, name) -> None:
    sc = ls.build(cfg, world, clock, name, seed=21)
    det = sc.detections()
    times = [ms for ms, _ in det]
    assert times == sorted(times)
    text = json.dumps([m for _, m in det])
    for word in (sc.actor_id, sc.nickname, sc.name, "actor", "nickname", "scenario"):
        assert word not in text, word
    kinds = {m["type"] for _, m in det}
    assert "point" in kinds and kinds <= {"point", "rf", "rid"}
    allowed = {"v", "type", "installation_id", "sensor_id", "sensor_track_id", "ts", "x_m", "y_m",
               "alt_m", "quality", "band", "protocol_family", "bearing_deg", "snr_db", "serial",
               "drone_x_m", "drone_y_m", "op_x_m", "op_y_m"}  # fmt: skip
    assert {k for _, m in det for k in m} <= allowed
    ids = {m["sensor_track_id"] for _, m in det if m["type"] == "point"}
    assert all(i.startswith("TRK-") and sc.actor_id not in i for i in ids)
    rows = sc.truth_rows()
    assert {r["sensor_track_id"] for r in rows} == ids
    assert {r["actor_id"] for r in rows} == {sc.actor_id}


def test_launch_follows_the_actor_window_and_the_clock(cfg, world, clock) -> None:
    p1 = ls.build(cfg, world, clock, "returning-prober", seed=3)
    assert ls.iso_ms(p1.start_ms) == "2026-09-02T02:00:00.000Z"  # 21:00 at BRAVO (UTC-5)
    clock.reserve(ls.reserve_until(p1, cfg))
    c1 = ls.build(cfg, world, clock, "copycat", seed=3)  # C1 flies 19:00 to 20:30
    assert ls.iso_ms(c1.start_ms) == "2026-09-03T00:00:00.000Z"  # the next evening, 19:00
    assert c1.start_ms > p1.end_ms


def test_new_operator_flies_twice_at_two_bases_after_close(cfg, world, clock) -> None:
    sc = ls.build(cfg, world, clock, "new-operator-twice", seed=5, base="BRAVO")
    f1, f2 = sc.flights
    assert (f1.flight, f2.flight) == (1, 2)
    assert f1.plan.installation_id == "BRAVO" and f2.plan.installation_id == "CHARLIE"
    last1 = max(d.plan.launch_ms + round(float(d.hits.t_s[-1]) * 1000) for d in f1.drones)
    assert f2.plan.launch_ms >= last1 + cfg.scoring.live.idle_close_s * 1000
    assert sc.actor_id == "N1" and f2.plan.rf_family == "FAM-24"
    used = {p.rf_family for p in cfg.actors.probers} | {c.rf_family for c in cfg.actors.copycats}
    used |= {s.rf_family for s in cfg.actors.swarms} | set(cfg.actors.hobbyists.rf_families)
    assert "FAM-24" not in used
    op = ls.NEW_OPERATOR
    for p in cfg.actors.probers:  # an operator no configured actor resembles
        same_shape = (
            p.pattern.type == op.pattern["type"]
            and p.target == op.target
            and getattr(p.pattern, "direction", None) == op.pattern["direction"]
        )
        assert not same_shape, p.id
        assert (p.launch.bearing_deg, p.launch.distance_m) != (45.0, 1400.0)
    for c in cfg.actors.copycats:
        assert (c.launch.bearing_deg, c.launch.distance_m) != (45.0, 1400.0)


def test_swarm_repeat_flies_the_team(cfg, world, clock) -> None:
    sc = ls.build(cfg, world, clock, "swarm-repeat", seed=8)
    (f,) = sc.flights
    assert sc.actor_id == "S1" and len(f.drones) == 5
    assert {d.plan.installation_id for d in f.drones} == {"GOLF"}
    assert len({ls.sensor_track_id(sc.seed, d.plan.key, d.plan.launch_ms) for d in f.drones}) == 5


def test_sensor_track_ids_are_unique_per_launch() -> None:
    a = ls.sensor_track_id(1, "LIVE/x/P1/BRAVO/1/1", 1000)
    assert a == ls.sensor_track_id(1, "LIVE/x/P1/BRAVO/1/1", 1000)
    assert a != ls.sensor_track_id(1, "LIVE/x/P1/BRAVO/1/1", 2000)
    assert a != ls.sensor_track_id(1, "LIVE/x/P2/BRAVO/1/1", 1000)
