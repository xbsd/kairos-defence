"""Demo assertions (SPEC §19.3, ``scenario_demo.yaml`` expectations) as far as phase 5 can check.

First contact is checked on the radar data; the orbit on the noiseless truth path with the phase 1
definition (``orbit_established_s``). The live top 3 at T+90 is an assertion for the DTW matcher
(phase 4): it passes when every expected incident is in the top 3 with a score and at least one
reason. Under ``--method euclidean`` it stays information only, since the baseline has no reasons
(D-076). Phase 5 adds two rows (D-088): at T+120 the expected incident is among the top 3 matched
incidents and its recall rank 1 is its own report (§1.2); at ``forecast_at_s`` the forecast
center is within ``forecast_error_max_m`` of the true recovery point. Both are information only
under the Euclidean baseline, like the top 3. The swarm check is pending until phase 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
import shapely

from kairos_defense.config import Config
from kairos_defense.eval.truth import true_path
from kairos_defense.features.channels import load_site
from kairos_defense.match.query import load_query
from kairos_defense.ports import TrackStore
from kairos_defense.sim.scenario import orbit_established_s

FENCE_WITHIN_M = 100.0  # §1.2: first point within 100 m of the fence
RECALL_AT_S = 120  # §1.2: the linked report beat
BASELINE_INFO = "info (Euclidean baseline)"


@dataclass(frozen=True)
class DemoRow:
    key: str
    expected: str
    observed: str
    status: str  # pass | fail | info (...) | pending (phase N)


def top3_row(cfg: Config, matches: list, assert_top3: bool) -> DemoRow:
    """``live_top3_incidents``: ranks of the expected incidents, each one's score and first
    reason; ``pass`` only when all are in the top 3 with a score and a reason."""
    ex = cfg.scenario.expectations
    ranked = [m.incident_id for m in matches]
    found = {inc: ranked.index(inc) + 1 if inc in ranked else None
             for inc in ex.live_top3_incidents}  # fmt: skip
    hits = sum(r is not None and r <= 3 for r in found.values())
    parts = []
    for inc, r in found.items():
        if r is None:
            parts.append(f"{inc} -")
            continue
        m = matches[r - 1]
        why = f", {m.reasons[0]!r}" if m.reasons else ""
        parts.append(f"{inc} #{r} ({m.score:.2f}{why})")
    observed = f"{hits}/3 in top 3; " + "; ".join(parts)
    expected = f"{', '.join(ex.live_top3_incidents)} at T+{ex.live_top3_at_s:g} s, with reasons"
    if not assert_top3:
        return DemoRow("live_top3_incidents", expected, observed, "info (Euclidean baseline)")
    ok = all(r is not None and r <= 3 and matches[r - 1].reasons and
             np.isfinite(matches[r - 1].score) for r in found.values())  # fmt: skip
    return DemoRow("live_top3_incidents", expected, observed, "pass" if ok else "fail")


def rank1_report_row(cfg: Config, rec, asserting: bool) -> DemoRow:
    """``live_rank1_report_for`` from a ``RecallResult`` at T+120 (None: no report index)."""
    want = cfg.scenario.expectations.live_rank1_report_for
    expected = f"{want} among the top 3 matched incidents, its own report rank 1 (T+{RECALL_AT_S})"
    if rec is None:
        return DemoRow("live_rank1_report_for", expected, "-", "pending (no report index)")
    mr = next((m for m in rec.matches if m.incident_id == want), None)
    if mr is None:
        got = ", ".join(m.incident_id for m in rec.matches) or "none"
        observed, ok = f"{want} not in the top 3 matched incidents ({got})", False
    elif not mr.reports:
        observed, ok = f"{want} match #{mr.match_rank}: no report in its filter window", False
    else:
        top = mr.reports[0]
        clues = "; ".join(f"{c.value}" + (f" ({' '.join(c.links)})" if c.linked else "")
                          for c in top.clues) or "no clue"  # fmt: skip
        observed = (f"{top.report_id} rank 1 of {len(mr.reports)} for {want} (match "
                    f"#{mr.match_rank}, score {top.score:.4f}); clues: {clues}")  # fmt: skip
        ok = top.incident_id == want
    status = ("pass" if ok else "fail") if asserting else BASELINE_INFO
    return DemoRow("live_rank1_report_for", expected, observed, status)


def forecast_row(cfg: Config, fc, error_m: float, asserting: bool) -> DemoRow:
    """``forecast_error_max_m``: the live forecast at ``forecast_at_s`` against truth."""
    ex = cfg.scenario.expectations
    expected = f"<= {ex.forecast_error_max_m:g} m at T+{ex.forecast_at_s:g} s"
    if fc is None:
        observed = "no forecast (no match with a known recovery point)"
    else:
        analogs = ", ".join(a.incident_id for a in fc.analogs)
        observed = (f"{error_m:.0f} m (radius {fc.radius_m:.0f} m; analogs {analogs}; roads "
                    f"{', '.join(fc.roads) or 'none'})")  # fmt: skip
    ok = error_m <= ex.forecast_error_max_m
    status = ("pass" if ok else "fail") if asserting else BASELINE_INFO
    return DemoRow("forecast_error_max_m", expected, observed, status)


def demo_rows(
    cfg: Config,
    store: TrackStore,
    truth: pd.DataFrame,
    ranker,
    assert_top3: bool = True,
    downstream=None,
) -> list[DemoRow]:
    """Every ``scenario_demo.yaml`` row this phase can check; ``downstream`` (an
    ``eval.downstream.Downstream``) enables the forecast and recall rows."""
    ex = cfg.scenario.expectations
    live = cfg.scenario.live_incident
    track = f"{live}-T1"
    pts = store.track_points(track)
    first = pts.iloc[0]
    site = load_site(store, str(first.installation_id))
    local = pd.Timestamp(first.ts) + timedelta(hours=site.utc_offset_hours)
    fence_m = float(shapely.distance(shapely.points([first.x_m, first.y_m]), site.fence))
    lo, hi = ex.live_first_contact_local
    ok = lo <= local.to_pydatetime() <= hi and fence_m <= FENCE_WITHIN_M
    rows = [DemoRow("live_first_contact_local", f"{lo:%H:%M:%S}-{hi:%H:%M:%S}, <= 100 m from fence",
                    f"{local:%H:%M:%S}, {fence_m:.0f} m", "pass" if ok else "fail")]  # fmt: skip

    p1 = next(p for p in cfg.actors.probers if p.id == "P1")
    tp = true_path(cfg.app, track)
    launch = pd.Timestamp(truth.set_index("track_id").loc[track, "launch_ts"])
    after = (pd.Timestamp(first.ts) - launch).total_seconds()
    center = site.target(f"{site.installation_id}-{p1.target}").centroid
    est = orbit_established_s(tp.t_s.to_numpy(), tp[["x_m", "y_m"]].to_numpy(), center,
                              p1.pattern.radius_m, after_s=after)  # fmt: skip
    t_orbit = None if est is None else est - after
    olo, ohi = ex.live_orbit_established_s
    ok = t_orbit is not None and olo <= t_orbit <= ohi
    rows.append(DemoRow("live_orbit_established_s", f"T+{olo:g}-{ohi:g} s",
                        "never" if t_orbit is None else f"T+{t_orbit:.0f} s",
                        "pass" if ok else "fail"))  # fmt: skip

    q = load_query(store, track, int(ex.live_top3_at_s), cfg.scoring)
    rows.append(top3_row(cfg, ranker(q).matches, assert_top3))
    if downstream is None:
        rows.append(DemoRow("live_rank1_report_for", ex.live_rank1_report_for, "-",
                            "pending (no report index)"))  # fmt: skip
        rows.append(DemoRow("forecast_error_max_m", f"<= {ex.forecast_error_max_m:g} m", "-",
                            "pending (no forecast)"))  # fmt: skip
    else:
        rec = None
        if downstream.recall is not None:
            q = load_query(store, track, RECALL_AT_S, cfg.scoring)
            res = ranker(q)
            fc, _, _ = downstream.forecast(q, res)
            rec = downstream.recall.for_matches(q, res, fc.roads if fc else (), n=3)
        rows.append(rank1_report_row(cfg, rec, assert_top3))
        q = load_query(store, track, int(ex.forecast_at_s), cfg.scoring)
        fc, err, _ = downstream.forecast(q, ranker(q))
        rows.append(forecast_row(cfg, fc, err, assert_top3))
    rows.append(DemoRow("swarm_top1", ex.swarm_top1, "-", "pending (phase 9)"))
    return rows
