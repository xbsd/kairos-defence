"""Kinematics (SPEC §8.3, §8.5) on noise-free (true) paths."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from kairos_defense.rng import rng_for
from kairos_defense.sim import kinematics as K
from kairos_defense.sim.kinematics import Phase

MAX_WIND_MS = 25.0  # well above any Weibull draw in the calendar


def _band(cfg, plan) -> tuple[float, float]:
    if plan.actor_type == "hobbyist":
        return cfg.actors.hobbyists.altitude_m
    probers = {p.id: p for p in cfg.actors.probers}
    copy = {c.id: c.mimics for c in cfg.actors.copycats}
    return probers[copy.get(plan.actor_id, plan.actor_id)].altitude_m


def test_sample_covers_every_pattern(sample) -> None:
    kinds = {p.pattern["type"] for p in sample.plans}
    assert kinds == {"orbit", "lawnmower", "figure8", "perimeter", "hover", "transit_dips",
                     "random_walk"}  # fmt: skip


def test_speed_climb_and_turn_rate_limits(sample) -> None:
    for plan, fp in zip(sample.plans, sample.paths, strict=True):
        v = np.gradient(fp.xyz[:, :2], axis=0)  # m/s at 1 Hz
        speed = np.hypot(*v.T)
        assert speed.max() <= K.vmax_for(plan) + K.WIND_DRIFT * MAX_WIND_MS, plan.key
        assert np.abs(np.diff(fp.xyz[:, 2])).max() <= K.CLIMB_CAP_MS + 1e-9, plan.key
        heading = np.degrees(np.arctan2(v[:, 0], v[:, 1]))
        turn = np.abs((np.diff(heading) + 180.0) % 360.0 - 180.0)
        fast = (speed[1:] >= 5.0) & (speed[:-1] >= 5.0)
        if fast.any():
            assert turn[fast].max() <= K.TURN_CAP_DPS, plan.key


def test_altitude_within_band(cfg, sample) -> None:
    for plan, fp in zip(sample.plans, sample.paths, strict=True):
        lo, hi = _band(cfg, plan)
        cruise = np.isin(fp.phase, K.CRUISE_PHASES)
        z = fp.xyz[cruise, 2]
        assert z.min() >= lo - 15.0 and z.max() <= hi + 15.0, plan.key


def test_orbit_radius_within_10_percent(cfg, world, sample) -> None:
    p1 = next(p for p in cfg.actors.probers if p.id == "P1").pattern.radius_m
    orbits = [(p, f) for p, f in zip(sample.plans, sample.paths, strict=True)
              if p.pattern["type"] == "orbit"]  # fmt: skip
    assert len(orbits) >= 6
    for plan, fp in orbits:
        c = world.sites[plan.installation_id].target(plan.target_kind).centroid
        idx = np.flatnonzero(fp.phase == Phase.PATTERN)[20:]  # after joining the circle
        d = np.hypot(*(fp.xyz[idx, :2] - c).T)
        r = plan.pattern["radius_m"]
        assert np.abs(d - r).max() <= 0.10 * r, plan.key
        assert np.median(d) == pytest.approx(p1, rel=0.10), plan.key


def test_ground_starts_and_ends_on_the_ground(sample) -> None:
    for plan, fp in zip(sample.plans, sample.paths, strict=True):
        np.testing.assert_allclose(fp.xyz[0], [*plan.launch_xy, 0.0], atol=1e-9)
        assert fp.xyz[-1, 2] < 1.0, plan.key
        assert np.hypot(*(fp.xyz[-1, :2] - plan.recovery_xy)) < 15.0, plan.key


def _warped(sample, world, w: float):
    base = next(p for p in sample.plans if p.actor_id == "P2")
    plan = dataclasses.replace(base, time_warp=w, pauses=False, key="WARP")
    site = world.sites[plan.installation_id]
    ref = K.build_reference(plan, site, rng_for(1, "warp"))
    s = K.sample_reference(ref, w, rng_for(1, "warp-alt"))
    calm = np.zeros((len(s.t), 2))
    return plan, ref, K.fly([plan], [s], [calm])[0]


def _resample_by_length(xy: np.ndarray, n: int = 400) -> np.ndarray:
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    q = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(q, s, xy[:, i]) for i in range(2)])


def test_time_warp_scales_durations_not_shapes(sample, world) -> None:
    _, ref1, fp1 = _warped(sample, world, 1.0)
    _, ref2, fp2 = _warped(sample, world, 1.3)
    np.testing.assert_array_equal(ref1.xyz, ref2.xyz)  # same knots: same geometry
    np.testing.assert_array_equal(ref1.t, ref2.t)  # nominal time; warp applied when sampling
    assert fp2.t_s[-1] / fp1.t_s[-1] == pytest.approx(1.3, rel=0.02)
    a = _resample_by_length(fp1.xyz[:, :2])
    b = _resample_by_length(fp2.xyz[:, :2])
    assert np.hypot(*(a - b).T).mean() < 10.0
    v1 = np.hypot(*np.diff(fp1.xyz[:, :2], axis=0).T)
    v2 = np.hypot(*np.diff(fp2.xyz[:, :2], axis=0).T)
    assert np.median(v2[v2 > 1]) == pytest.approx(np.median(v1[v1 > 1]) / 1.3, rel=0.05)


def test_pauses_never_inside_the_pattern(cfg, world, sample) -> None:
    n_pauses, transit_min = 0, 0.0
    for plan in sample.plans:
        for rep in range(8):
            ref = K.build_reference(
                plan, world.sites[plan.installation_id], rng_for(5, plan.key, str(rep))
            )
            ph = ref.phase
            pattern = np.flatnonzero(ph == Phase.PATTERN)
            pauses = np.flatnonzero(ph == Phase.PAUSE)
            if len(pattern) and len(pauses):
                inside = (pauses > pattern[0]) & (pauses < pattern[-1])
                assert not inside.any(), plan.key
            n_pauses += int(np.sum(np.diff(np.r_[0, (ph == Phase.PAUSE).astype(int)]) == 1))
            d = np.diff(ref.t)
            transit_min += d[np.isin(ph, (Phase.TRANSIT, Phase.EGRESS))].sum() / 60.0
    assert n_pauses / transit_min == pytest.approx(K.PAUSE_PER_MIN, rel=0.3)


def test_jitter_none_has_no_pauses(sample, world) -> None:
    for plan in sample.plans:
        p = dataclasses.replace(plan, pauses=False)
        for rep in range(5):
            ref = K.build_reference(p, world.sites[p.installation_id], rng_for(9, p.key, str(rep)))
            assert not (ref.phase == Phase.PAUSE).any()


def test_rows_are_independent_of_their_batch(sample, world, cal) -> None:
    plans = sample.plans[:12]
    alone = K.fly_plans(plans[3:4], world, cal, 42)[0]
    together = K.fly_plans(plans, world, cal, 42)[3]
    np.testing.assert_allclose(alone.xyz, together.xyz, rtol=0, atol=1e-9)


def test_wind_drift_pushes_a_hover_downwind(sample, world) -> None:
    plan = next(p for p in sample.plans if p.pattern["type"] == "hover")
    plan = dataclasses.replace(plan, pauses=False)
    site = world.sites[plan.installation_id]
    s = K.sample_reference(K.build_reference(plan, site, rng_for(2, "h")), plan.time_warp,
                           rng_for(2, "a"))  # fmt: skip
    calm = K.fly([plan], [s], [np.zeros((len(s.t), 2))])[0]
    east = K.fly([plan], [s], [np.tile([10.0, 0.0], (len(s.t), 1))])[0]
    hov = calm.phase == Phase.PATTERN
    shift = east.xyz[hov, 0] - calm.xyz[hov, 0]
    assert 2.0 < np.median(shift) < 0.3 * 10.0 / K.KP_H + 1.0  # downwind, bounded by the pull
