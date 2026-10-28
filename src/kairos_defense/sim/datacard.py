"""Data card (SPEC §8.11): ``reports/data_card.md`` and its figures.

Sections: volumes against §8.11, flights and incidents, probers and swarms, sensors (radar, RF,
Remote ID), reports (sources, counts, delay histogram, styles), clue rates, assessments, planted
items and the live timing, then row counts and figures (``figures.py``). The card holds no
wall-clock times, so the same seed gives the same card.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from kairos_defense.config import Config
from kairos_defense.sim.datacard_paper import assessments_section, clues_section, reports_section
from kairos_defense.sim.datacard_util import ACTOR_TYPES, local, n, table
from kairos_defense.sim.figures import PATTERNS, plot_pattern, plot_swarm
from kairos_defense.sim.generate import Generated
from kairos_defense.sim.incidents import heard_only

EXPECTED = {  # §8.11, ± 15%
    "incidents": 1900,
    "tracks": 1950,
    "track_points": 1_000_000,
    "rf_detections": 500_000,
    "reports": 1000,
    "assessments": 1900,
}


def _status(name: str, value: int) -> str:
    lo, hi = 0.85 * EXPECTED[name], 1.15 * EXPECTED[name]
    return "within ±15%" if lo <= value <= hi else f"outside ±15% ({value / EXPECTED[name]:.0%})"


def volumes(g: Generated) -> dict[str, int]:
    t = g.tables
    return {
        "incidents": len(t["incidents"]),
        "tracks": int(t["track_points"].track_id.nunique()),
        "track_points": len(t["track_points"]),
        "rf_detections": len(t["rf_detections"]),
        "reports": len(t["reports"]),
        "assessments": len(t["assessments"]),
    }


def card_markdown(g: Generated, figures: list[str]) -> str:
    vol = volumes(g)
    lines = [
        "# Data card",
        "",
        f"`kairos-defense gen --seed {g.seed}` · phase 2 (complete dataset: flights, swarms, "
        "radar, RF, Remote ID, reports and assessments). All data is synthetic.",
        "",
        "## Volumes against SPEC §8.11",
        "",
        *table(
            ["Metric", "Value", "Expected", "Status"],
            [[k, n(v), f"≈{n(EXPECTED[k])}", _status(k, v)] for k, v in vol.items()],
            right=1,
        ),
        "",
        "Track points and RF detections come in below §8.11 for the same reason: hobbyist flights "
        "last 180–720 s (mean ≈450 s) and are ≈95% of all flights (D-030, D-044). Incident, "
        "track, report and assessment counts are on target.",
    ]
    lines += _flights(g) + _incidents(g) + _probers(g) + _swarms(g) + _sensors(g)
    lines += reports_section(g) + clues_section(g) + assessments_section(g) + _planted(g) + _live(g)
    lines += [
        "",
        "## Row counts",
        "",
        *table(
            ["Database", "Table", "Rows"],
            [["app", t, n(len(df))] for t, df in g.tables.items()]
            + [["truth", t, n(len(df))] for t, df in g.truth.items()],
            right=2,
        ),
    ]
    lines += ["", "## Sample flights and swarms", ""]
    lines += [
        "Pattern figures: three flights per pattern type, in each installation's frame (km from "
        "its origin): true path (blue line) and radar detections (orange dots). Swarm figures: "
        "one event per team, then one snapshot per choreography step at that step's hold (or "
        "end): drones about their centroid, north up, the arrow is the swarm heading and drone 0 "
        "is ringed.",
        "",
    ]
    lines += [f"![{Path(f).stem}](figures/{Path(f).name})" for f in figures]
    return "\n".join(lines) + "\n"


def _flights(g: Generated) -> list[str]:
    flown = Counter(r.plan.actor_type for r in g.results)
    seen = Counter(r.plan.actor_type for r in g.results if r.detected)
    rows = [
        [f"{a} drones" if a == "swarm" else a, n(flown[a]), n(seen[a]), n(flown[a] - seen[a])]
        for a in ACTOR_TYPES
    ]
    rows.append(
        [
            "**all**",
            n(sum(flown.values())),
            n(sum(seen.values())),
            n(sum(flown.values()) - sum(seen.values())),
        ]
    )
    return [
        "",
        "## Flights",
        "",
        *table(["Actor type", "Flown", "Radar track", "No track"], rows),
        "",
        f"Flights heard by RF or Remote ID but never tracked by radar (no incident, "
        f"D-038): {n(heard_only(g.results))}.",
    ]


def _incidents(g: Generated) -> list[str]:
    c = Counter((i.plan.installation_id, i.plan.actor_type) for i in g.incidents)
    rows = []
    for sid in g.world.sites:
        row = [c[(sid, a)] for a in ACTOR_TYPES]
        rows.append([sid, *(n(x) for x in row), n(sum(row))])
    return [
        "",
        "## Incidents per installation and actor type",
        "",
        *table(["Installation", *ACTOR_TYPES, "total"], rows),
    ]


def _probers(g: Generated) -> list[str]:
    by: dict[str, list] = {}
    for i in g.incidents:
        if i.plan.actor_type in ("prober", "copycat"):
            by.setdefault(i.plan.actor_id, []).append(i.plan)
    rows = []
    for a in sorted(by):
        ps = by[a]
        w = [p.time_warp for p in ps]
        rows.append(
            [
                a,
                ps[0].pattern["type"],
                len(ps),
                ", ".join(sorted({p.installation_id for p in ps})),
                f"{min(w):.2f}–{max(w):.2f}",
            ]
        )
    return [
        "",
        "## Probers and copycats",
        "",
        *table(["Actor", "Pattern", "Incidents", "Bases", "Time warp range"], rows, 2),
    ]


def _swarms(g: Generated) -> list[str]:
    reps = Counter(g.tables["reports"].incident_id)
    rows = []
    for i in sorted((i for i in g.incidents if i.is_swarm), key=lambda i: i.start_ms):
        p = i.plan
        rows.append(
            [
                i.incident_id,
                p.actor_id,
                p.installation_id,
                f"{local(g, p.installation_id, i.start_ms):%Y-%m-%d %H:%M}",
                f"{len(i.tracks)}/{p.extra['drones']}",
                f"{p.time_warp:.2f}",
                p.status,
                reps[i.incident_id],
            ]
        )
    head = [
        "Incident",
        "Team",
        "Base",
        "Start (local)",
        "Tracks/drones",
        "Warp",
        "Status",
        "Reports",
    ]
    return ["", "## Swarm incidents (§8.7)", "", *table(head, rows, 4)]


def _sensors(g: Generated) -> list[str]:
    rf = g.tables["rf_detections"]
    rid = g.tables["remote_id"]
    tracked = [r for r in g.results if r.detected]
    pts = np.array([len(r.hits) for r in tracked])
    dur = np.array([r.path.t_s[-1] for r in tracked])
    q = np.percentile(pts, [5, 50, 95]).astype(int) if len(pts) else [0, 0, 0]
    first_rf = [i for i in g.incidents if i.start_ms < int(i.radar_ms().min())]
    bands = Counter(rf.band)
    modes = Counter(r.plan.rid for r in g.results)
    heard = Counter(r.plan.rid for r in g.results if len(r.rid))
    return [
        "",
        "## Sensors (§8.6)",
        "",
        f"- Radar: points per track median {q[1]}, p5 {q[0]}, p95 {q[2]}; "
        f"{pts.sum() / max(dur.sum(), 1.0):.2f} points per flight second.",
        f"- RF: {n(len(rf))} detections at 0.5 Hz; bands "
        + ", ".join(f"{b} {n(k)}" for b, k in sorted(bands.items()))
        + f". RF heard {n(len(first_rf))} of {n(len(g.incidents))} incidents before "
        "the radar's first point (takeoff is below the radar's 15 m floor), so incident start "
        "is the first RF detection there (D-028).",
        f"- Remote ID: {n(len(rid))} broadcasts, {n(rid.serial.nunique())} distinct serials. "
        "Drones by mode (heard / flown): "
        + ", ".join(f"{m} {n(heard[m])}/{n(modes[m])}" for m in ("on", "spoofed", "off"))
        + ".",
    ]


def _planted(g: Generated) -> list[str]:
    out = ["", "## Planted items (scenario_demo.yaml, §8.10)", ""]
    rows = []
    for i in sorted((i for i in g.incidents if i.plan.incident_id), key=lambda i: i.start_ms):
        p = i.plan
        first = int(i.radar_ms().min())
        rows.append(
            [
                i.incident_id,
                p.installation_id,
                f"{p.launch_local:%Y-%m-%d %H:%M:%S}",
                f"{local(g, p.installation_id, first):%Y-%m-%d %H:%M:%S}",
                f"{p.time_warp:.2f}",
                sum(len(r.hits) for r in i.tracks),
                p.status,
            ]
        )
    head = [
        "Incident",
        "Base",
        "Launch (local)",
        "First radar point (local)",
        "Warp",
        "Points",
        "Status",
    ]
    out += table(head, rows, 4)
    rep = g.tables["reports"]
    delta = rep[rep.incident_id == "P1-DELTA-260419"]
    asm = g.tables["assessments"].set_index("incident_id")
    if len(delta):
        r = delta.iloc[0]
        out += [
            "",
            f"Planted DELTA report ({r.source}, {r.source_grade}, its only report):",
            "",
            f"> {r.text}",
        ]
    if "P1-DELTA-260419" in asm.index:
        x = asm.loc["P1-DELTA-260419"]
        when = f"{local(g, 'DELTA', int(x.assessed_ts.value // 1_000_000)):%Y-%m-%d %H:%M}"
        out += [
            "",
            f"Planted assessment: **{x.label}** by {x.author} at {when} local (truth: probing).",
        ]
    return out


def _live(g: Generated) -> list[str]:
    out = ["", "## Live incident timing (§1.2, D-003, D-033)", ""]
    lt = g.live
    if lt is None:
        return [*out, "Live incident not in this run."]
    est = "never" if lt.orbit_established_s is None else f"T+{lt.orbit_established_s:.0f} s"
    return [
        *out,
        f"- Launch {lt.launch_local:%H:%M:%S}; first radar contact (T+0) "
        f"{lt.first_contact_local:%H:%M:%S}, {lt.first_contact_after_launch_s:.0f} s after launch, "
        f"{lt.first_contact_fence_m:.0f} m outside the fence.",
        f"- First detection by any sensor: {lt.radar_lag_s:.0f} s before first radar contact "
        "(the terrain mask hides it from RF too, D-039).",
        f"- Orbit established (within 15 m of the radius for 10 s): {est}.",
    ]


def write_data_card(cfg: Config, g: Generated, figures: bool = True) -> Path:
    reports = Path(cfg.app.paths.reports)
    fig_dir = reports / "figures"
    made = []
    if figures:
        for kind in PATTERNS:
            p = plot_pattern(g, kind, fig_dir / f"pattern_{kind}.png")
            if p is not None:
                made.append(str(p))
        for team in cfg.actors.swarms:
            p = plot_swarm(g, team.id, fig_dir / f"swarm_{team.id}.png")
            if p is not None:
                made.append(str(p))
    reports.mkdir(parents=True, exist_ok=True)
    out = reports / "data_card.md"
    out.write_text(card_markdown(g, made), encoding="utf-8")
    return out
