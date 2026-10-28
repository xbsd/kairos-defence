"""Remote ID modes (SPEC §8.6): on, off and spoofed; range, mask and stable serials."""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pytest

from kairos_defense import geo
from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.sensors import RID_SPOOF_M, rid_track, stable_serial

SERIAL = re.compile(r"^SN-[0-9A-F]{16}$")
N_S = 600


def _static(xy, alt: float = 80.0, n: int = N_S) -> FlightPath:
    xyz = np.tile([xy[0], xy[1], alt], (n, 1))
    return FlightPath("static", np.arange(n, dtype=np.float64), xyz, np.zeros(n, np.int8))


def _near(site, dist: float = 1500.0, bearing: float = 120.0):
    return geo.destination(site.sensors["rid"].xy, bearing, dist)


def test_rid_stable_serial_per_drone() -> None:
    a = stable_serial(42, "H-ALPHA-250301-0")
    assert SERIAL.match(a)
    assert a == stable_serial(42, "H-ALPHA-250301-0")  # same drone, every flight
    assert a != stable_serial(42, "H-ALPHA-250301-1")
    assert stable_serial(42, "S1", 0) != stable_serial(42, "S1", 1)
    assert a != stable_serial(43, "H-ALPHA-250301-0")


def test_rid_on_broadcasts_serial_and_operator(world) -> None:
    site = world.sites["GOLF"]
    launch = _near(site, 2000.0)
    xy = _near(site)
    hits = rid_track(_static(xy), site, "on", "SN-0123456789ABCDEF", launch,
                     np.random.default_rng(0))  # fmt: skip
    assert len(hits) == N_S
    np.testing.assert_allclose(np.diff(hits.t_s), 1.0)  # 1 Hz
    assert hits.serial == "SN-0123456789ABCDEF"
    assert np.hypot(*(hits.op_xy - launch)) <= 10.0 + 0.1
    err = np.hypot(*(hits.drone_xy - xy).T)
    assert err.max() < 12.0 and err.mean() < 4.0


def test_rid_spoofed_serial_changes_every_flight(world) -> None:
    site = world.sites["CHARLIE"]
    launch = _near(site, 1600.0, 200.0)
    serials, dists = set(), []
    for k in range(20):
        h = rid_track(_static(_near(site)), site, "spoofed", "SN-0123456789ABCDEF", launch,
                      np.random.default_rng(k))  # fmt: skip
        assert len(h) == N_S
        serials.add(h.serial)
        dists.append(float(np.hypot(*(h.op_xy - launch))))
    assert len(serials) == 20 and "SN-0123456789ABCDEF" not in serials
    assert all(SERIAL.match(s) for s in serials)
    assert RID_SPOOF_M[0] - 0.1 <= min(dists) and max(dists) <= RID_SPOOF_M[1] + 0.1


def test_rid_off_broadcasts_nothing(world) -> None:
    site = world.sites["DELTA"]
    h = rid_track(_static(_near(site)), site, "off", "SN-0123456789ABCDEF", _near(site, 2000),
                  np.random.default_rng(0))  # fmt: skip
    assert len(h) == 0 and h.serial is None


def test_rid_range_ground_and_mask(world) -> None:
    site = world.sites["GOLF"]
    args = ("on", "SN-0123456789ABCDEF", _near(site, 2000.0), np.random.default_rng(0))
    assert len(rid_track(_static(_near(site, 3050.0), alt=10.0), site, *args)) == 0
    assert len(rid_track(_static(_near(site), alt=0.0), site, *args)) == 0
    bravo = world.sites["BRAVO"]
    xy = geo.destination(bravo.origin, 330.0, 2000.0)  # in the radar shadow
    masked = rid_track(_static(xy, 120.0), bravo, "on", "SN-0123456789ABCDEF", xy,
                       np.random.default_rng(0))  # fmt: skip
    assert len(masked) == 0


def test_rid_unknown_mode_is_an_error(world) -> None:
    site = world.sites["GOLF"]
    with pytest.raises(ValueError):
        rid_track(_static(_near(site)), site, "maybe", "x", _near(site), np.random.default_rng(0))


def test_rid_modes_per_actor(cfg, world, cal) -> None:
    from kairos_defense.sim.actors import schedule

    modes = defaultdict(list)
    for p in schedule(cfg, world, cal, 42):
        modes[p.actor_type if p.actor_type == "hobbyist" else p.actor_id].append(p.rid)
    for p in cfg.actors.probers:
        if p.id != "P1":
            assert set(modes[p.id]) == {p.rid}, p.id
    assert set(modes["P2"]) == {"spoofed"}
    for c in cfg.actors.copycats:
        assert set(modes[c.id]) <= {"on", "off"}
    on = np.mean([m == "on" for m in modes["hobbyist"]])
    assert on == pytest.approx(cfg.actors.hobbyists.rid_on_prob, abs=0.03)
