"""Demo assertions (SPEC §19.3, ``scenario_demo.yaml`` expectations) as far as phase 3 can check.

First contact is checked on the radar data; the orbit on the noiseless truth path with the phase 1
definition (``orbit_established_s``). The live top 3 at T+90 is reported for information: it
becomes a target with DTW and fusion in phase 4. Report recall, forecast and swarm checks are
pending until phases 5 and 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
import shapely

from kairos_defense.config import Config
from kairos_defense.eval.truth import true_path
from kairos_defense.features.channels import load_site
from kairos_defense.match.query import load_query
from kairos_defense.ports import TrackStore, VectorStore
from kairos_defense.sim.scenario import orbit_established_s

FENCE_WITHIN_M = 100.0  # §1.2: first point within 100 m of the fence


@dataclass(frozen=True)
class DemoRow:
    key: str
    expected: str
    observed: str
    status: str  # pass | fail | info (...) | pending (phase N)


def demo_rows(
    cfg: Config, store: TrackStore, vstore: VectorStore, truth: pd.DataFrame, ranker
) -> list[DemoRow]:
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
    matches, _ = ranker(q, vstore, cfg.scoring)
    ranked = [m.incident_id for m in matches]
    found = {
        inc: (ranked.index(inc) + 1 if inc in ranked else None) for inc in ex.live_top3_incidents
    }
    hits = sum(r is not None and r <= 3 for r in found.values())
    observed = f"{hits}/3 in top 3; ranks " + ", ".join(
        f"{inc} {'-' if r is None else r}" for inc, r in found.items())  # fmt: skip
    expected = f"{', '.join(ex.live_top3_incidents)} at T+{ex.live_top3_at_s:g} s"
    rows.append(DemoRow("live_top3_incidents", expected, observed, "info (target from phase 4)"))
    rows.append(
        DemoRow("live_rank1_report_for", ex.live_rank1_report_for, "-", "pending (phase 5)")
    )
    rows.append(DemoRow("forecast_error_max_m", f"<= {ex.forecast_error_max_m:g} m at "
                        f"T+{ex.forecast_at_s:g} s", "-", "pending (phase 5)"))  # fmt: skip
    rows.append(DemoRow("swarm_top1", ex.swarm_top1, "-", "pending (phase 9)"))
    return rows
