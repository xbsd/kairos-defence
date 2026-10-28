"""Swarm formations and actions as pure geometry (SPEC §8.7, D-035)."""

from __future__ import annotations

import numpy as np
import pytest

from kairos_defense import geo
from kairos_defense.sim import formations as fm


def _nn(xy: np.ndarray) -> np.ndarray:
    d = np.hypot(*(xy[:, None] - xy[None, :]).transpose(2, 0, 1))
    np.fill_diagonal(d, np.inf)
    return d.min(axis=1)


def _steps(*specs) -> list[dict]:
    return [dict(s) for s in specs]


@pytest.mark.parametrize("kind", fm.FORMATIONS)
@pytest.mark.parametrize("n", [3, 5, 7])
def test_swarm_formation_spacing_and_center(kind: str, n: int) -> None:
    xy = fm.formation(kind, n, 40.0)
    assert xy.shape == (n, 2)
    np.testing.assert_allclose(xy.mean(axis=0), 0.0, atol=1e-9)
    np.testing.assert_allclose(_nn(xy), 40.0, rtol=1e-9)  # every drone's nearest neighbor


def test_swarm_formation_orientation() -> None:
    line = fm.formation("line_abreast", 5, 40.0)
    trail = fm.formation("trail", 5, 30.0)
    np.testing.assert_allclose(line[:, 1], 0.0)  # side by side across the heading
    np.testing.assert_allclose(trail[:, 0], 0.0)  # single file along it
    assert trail[0, 1] > trail[-1, 1]  # drone 0 leads
    v = fm.formation("v", 5, 35.0)
    assert v[0, 1] == v[:, 1].max()  # apex forward
    tri = fm.formation("triangle", 3, 50.0)
    assert tri[0, 1] == tri[:, 1].max()


def test_swarm_unknown_formation_is_an_error() -> None:
    with pytest.raises(ValueError):
        fm.formation("diamond", 4, 30.0)


def test_swarm_choreography_must_start_with_a_formation() -> None:
    with pytest.raises(ValueError):
        fm.timeline(_steps({"kind": "expand", "factor": 2.0, "duration_s": 10.0}), 3)


def test_swarm_rotate_is_clockwise_for_cw() -> None:
    tl = fm.timeline(_steps({"kind": "line_abreast", "spacing_m": 40.0, "duration_s": 20.0},
                            {"kind": "rotate", "degrees": 90.0, "direction": "cw",
                             "duration_s": 30.0}), 5)  # fmt: skip
    start, mid, end = tl.offsets([20.0, 35.0, 50.0])
    np.testing.assert_allclose(end, geo.rotate(start, 90.0), atol=1e-9)
    right = int(np.argmax(start[:, 0]))  # the drone on the right ends up behind
    assert end[right, 1] == pytest.approx(-80.0)
    b0, b1, b2 = (float(geo.bearing((0, 0), o[right])) for o in (start, mid, end))
    assert b0 == pytest.approx(90.0) and b1 == pytest.approx(135.0) and b2 == pytest.approx(180.0)


def test_swarm_rotate_ccw_and_expand() -> None:
    tl = fm.timeline(_steps({"kind": "triangle", "spacing_m": 50.0, "duration_s": 10.0},
                            {"kind": "expand", "factor": 2.0, "duration_s": 30.0},
                            {"kind": "rotate", "degrees": 180.0, "direction": "ccw",
                             "duration_s": 40.0}), 3)  # fmt: skip
    a, b, mid, c = tl.offsets([10.0, 40.0, 60.0, 80.0])
    np.testing.assert_allclose(b, 2.0 * a, atol=1e-9)
    np.testing.assert_allclose(_nn(b), 100.0)
    np.testing.assert_allclose(c, -b, atol=1e-9)
    # half way through a ccw half turn the apex has turned 90° to the left
    assert float(geo.bearing((0, 0), mid[0])) == pytest.approx(270.0)


def test_swarm_split_keeps_the_centroid() -> None:
    tl = fm.timeline(_steps({"kind": "line_abreast", "spacing_m": 40.0, "duration_s": 10.0},
                            {"kind": "split", "groups": [2, 3], "separation_m": 250.0,
                             "duration_s": 45.0}), 5)  # fmt: skip
    a, b = tl.offsets([10.0, 55.0])
    np.testing.assert_allclose(b.mean(axis=0), 0.0, atol=1e-9)
    gap = lambda o: o[2:, 0].mean() - o[:2, 0].mean()  # noqa: E731
    assert gap(b) - gap(a) == pytest.approx(250.0)


def test_swarm_formation_change_blends_then_holds() -> None:
    steps = _steps({"kind": "line_abreast", "spacing_m": 40.0, "duration_s": 30.0},
                   {"kind": "v", "spacing_m": 35.0, "duration_s": 40.0})  # fmt: skip
    tl = fm.timeline(steps, 5)
    lo, hi = tl.hold(1)
    assert 30.0 < lo <= 30.0 + fm.BLEND_MAX_FRAC * 40.0 and hi == 70.0
    held = tl.offsets(np.linspace(lo, hi - 1e-6, 5))
    for o in held:
        np.testing.assert_allclose(o, fm.formation("v", 5, 35.0), atol=1e-9)
    t = np.linspace(0.0, 70.0, 701)
    speed = np.hypot(*np.diff(tl.offsets(t), axis=0).transpose(2, 0, 1)) / 0.1
    assert speed.max() < 3.0 * fm.BLEND_SPEED_MS  # smooth, no jumps


def test_swarm_timeline_from_config_with_jitter(cfg) -> None:
    s1 = next(s for s in cfg.actors.swarms if s.id == "S1")
    factors = [0.9, 1.1, 1.0, 0.95, 1.05]
    steps = fm.resolve_steps(s1.choreography, factors)
    assert [s["kind"] for s in steps] == ["line_abreast", "rotate", "split", "v", "orbit_target"]
    for s, c, f in zip(steps, s1.choreography, factors, strict=True):
        assert s["duration_s"] == pytest.approx(c.duration_s * f)
    tl = fm.timeline(steps, s1.drones)
    assert tl.duration_s == pytest.approx(sum(s["duration_s"] for s in steps))
    assert fm.first_orbit_radius(steps) == 220.0
    np.testing.assert_allclose(tl.offsets([-5.0])[0], tl.keys[0])
    np.testing.assert_allclose(tl.offsets([tl.duration_s + 5.0])[0], tl.keys[-1])


def test_swarm_centroid_path_creeps_then_orbits_clockwise(cfg) -> None:
    s1 = next(s for s in cfg.actors.swarms if s.id == "S1")
    steps = fm.resolve_steps(s1.choreography, [1.0] * 5)
    pattern = {"steps": steps}
    target, approach = np.array([1000.0, 2000.0]), 330.0
    entry = geo.destination(target, approach, 220.0 + 300.0)
    path = fm.centroid_path(pattern, target, entry, approach, 10.0)
    np.testing.assert_allclose(path.xy[0], entry)
    assert np.isnan(path.speed).all()
    assert path.dur.sum() == pytest.approx(sum(s["duration_s"] for s in steps))
    r = np.hypot(*(path.xy - target).T)
    assert r[4] == pytest.approx(220.0)  # on the orbit circle when the orbit starts
    np.testing.assert_allclose(r[4:], 220.0)
    b = geo.bearing(target, path.xy[4:])
    assert (geo.wrap180(np.diff(b)) > 0).all()  # clockwise
    arc = np.radians(geo.wrap360(b[-1] - b[0])) * 220.0
    assert arc == pytest.approx(10.0 * 90.0, rel=0.02)  # cruise speed for the orbit's duration
