"""Flown swarms (SPEC §8.7, D-009, D-035): schedule, spacing, actions, orbit and independence."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from kairos_defense import geo
from kairos_defense.sim import formations as fm
from kairos_defense.sim.actors import TIME_WARP_RANGE
from kairos_defense.sim.swarm import STEP_JITTER, choreography_clock, swarm_plans


def _events(swarms):
    for plan, center, drones in zip(swarms.plans, swarms.centers, swarms.drones, strict=True):
        tl = fm.timeline(plan.pattern["steps"], plan.pattern["drones"])
        tau = choreography_clock(plan, center)
        yield plan, center, np.stack([d.xyz for d in drones]), tl, tau


def _nn(xy: np.ndarray) -> np.ndarray:
    """Nearest-neighbor distance ``(n, t)`` for positions ``(n, t, 2)``."""
    d = np.hypot(*(xy[:, None] - xy[None, :]).transpose(3, 0, 1, 2))
    d[np.arange(len(xy)), np.arange(len(xy))] = np.inf
    return d.min(axis=1)


def test_swarm_schedule(cfg, swarms) -> None:
    teams = {s.id: s for s in cfg.actors.swarms}
    keys = [p.key for p in swarms.plans]
    assert len(keys) == len(set(keys))
    planted = {e.incident_id: e for e in cfg.scenario.swarm_events}
    for p in swarms.plans:
        tm = teams[p.actor_id]
        assert p.actor_type == "swarm" and p.installation_id in tm.bases
        assert p.rf_family == tm.rf_family and p.rid == "off"
        assert TIME_WARP_RANGE[0] <= p.time_warp <= TIME_WARP_RANGE[1]
        if p.key in planted:
            ev = planted[p.key]
            assert (p.installation_id, p.launch_local, p.incident_id) == (
                ev.base, ev.start_local, ev.incident_id)  # fmt: skip
            assert p.status == (ev.status or "history")
        else:
            assert p.incident_id is None and p.status == "history"
    for tm in cfg.actors.swarms:
        rand = [p for p in swarms.plans if p.actor_id == tm.id and p.key not in planted]
        assert len(rand) == tm.random_events
    # D-009: S1's random events fall after the encore, so GOLF 05-03 is its only earlier event
    s1 = [p for p in swarms.plans if p.actor_id == "S1" and p.key not in planted]
    assert all(p.night > date(2026, 6, 14) for p in s1)
    assert sum(p.status == "live" for p in swarms.plans) == 1


def test_swarm_same_choreography_with_jitter(cfg, swarms) -> None:
    teams = {s.id: s for s in cfg.actors.swarms}
    for p in swarms.plans:
        cfg_steps = teams[p.actor_id].choreography
        steps = p.pattern["steps"]
        assert [s["kind"] for s in steps] == [
            getattr(s, "formation", None) or s.action for s in cfg_steps
        ]
        for s, c in zip(steps, cfg_steps, strict=True):
            assert abs(s["duration_s"] / c.duration_s - 1.0) <= STEP_JITTER + 1e-12
    warps = {round(p.time_warp, 6) for p in swarms.plans}
    assert len(warps) == len(swarms.plans)  # each event its own time warp


def test_swarm_spacing_within_20_percent(swarms) -> None:
    n_holds = 0
    for plan, _, xyz, tl, tau in _events(swarms):
        for i, s in enumerate(tl.steps):
            if s["kind"] not in fm.FORMATIONS:
                continue
            lo, hi = tl.hold(i)
            m = (tau >= lo) & (tau <= hi)
            assert m.sum() >= 5, (plan.key, s["kind"])
            nn = np.median(_nn(xyz[:, m, :2]), axis=1)
            assert np.all(np.abs(nn / s["spacing_m"] - 1.0) <= 0.20), (plan.key, s["kind"], nn)
            n_holds += 1
    assert n_holds == 2 * len(swarms.plans)


def test_swarm_rotation_direction(swarms) -> None:
    for plan, _, xyz, tl, tau in _events(swarms):
        for i, s in enumerate(tl.steps):
            if s["kind"] != "rotate":
                continue
            j0 = int(np.argmin(np.abs(tau - tl.start_s[i])))
            jm = int(np.argmin(np.abs(tau - (tl.start_s[i] + tl.end_s[i]) / 2.0)))
            rel = xyz[0, :, :2] - xyz.mean(axis=0)[:, :2]  # drone 0 about the swarm centroid
            turned = float(geo.wrap180(geo.bearing((0, 0), rel[jm]) - geo.bearing((0, 0), rel[j0])))
            sign = 1.0 if s["direction"] == "cw" else -1.0  # cw adds to the bearing
            assert turned * sign == pytest.approx(s["degrees"] / 2.0, abs=12.0), plan.key


def test_swarm_orbit_target(world, swarms) -> None:
    n = 0
    for plan, _, xyz, tl, tau in _events(swarms):
        target = world.sites[plan.installation_id].target(plan.target_kind).centroid
        for i, s in enumerate(tl.steps):
            if s["kind"] != "orbit_target":
                continue
            m = (tau >= tl.start_s[i] + 15.0) & (tau <= tl.end_s[i])
            c = xyz.mean(axis=0)[m, :2]
            r = np.hypot(*(c - target).T)
            assert np.all(np.abs(r / s["radius_m"] - 1.0) <= 0.15), plan.key
            b = geo.bearing(target, c)
            assert float(np.sum(geo.wrap180(np.diff(b)))) > 90.0  # clockwise, a good part of a lap
            n += 1
    assert n == sum(p.actor_id == "S1" for p in swarms.plans)


def test_swarm_drones_are_plausible(swarms) -> None:
    for plan, center, xyz, _, _ in _events(swarms):
        assert xyz.shape[0] == plan.pattern["drones"]
        v = np.hypot(*np.diff(xyz[:, :, :2], axis=1).transpose(2, 0, 1))
        assert v.max() < 25.0, plan.key
        assert (xyz[:, :, 2] >= 0.0).all()
        np.testing.assert_allclose(xyz[:, :, 2].max(axis=1), center.xyz[:, 2].max(), atol=12.0)
        alt = xyz[:, len(center.t_s) // 2, 2]
        lo, hi = 80 - 15, 100 + 15  # band ± 15 m (S1 80-100, S2 60-80)
        if plan.actor_id == "S2":
            lo, hi = 60 - 15, 80 + 15
        assert ((alt >= lo) & (alt <= hi)).all(), plan.key


def test_adding_a_swarm_team_changes_no_other_event(cfg, world, cal, swarms) -> None:
    s2 = next(s for s in cfg.actors.swarms if s.id == "S2")
    s3 = s2.model_copy(update={"id": "S3"})
    more = cfg.model_copy(
        update={"actors": cfg.actors.model_copy(update={"swarms": [*cfg.actors.swarms, s3]})}
    )
    after = {p.key: p for p in swarm_plans(more, world, cal, 42)}
    for p in swarms.plans:
        assert after[p.key].as_dict() == p.as_dict(), p.key
    assert {k for k in after if k.startswith("S3/")} and len(after) == len(swarms.plans) + 5
