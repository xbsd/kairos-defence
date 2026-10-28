"""Data card and sample figures (SPEC §8.11).

``write_data_card`` writes ``reports/data_card.md`` (row counts, volumes against §8.11, incidents
per base and actor type, planted flights, live timing) and ``reports/figures/pattern_<type>.png``
(three sample flights per pattern type: true path and radar detections, installation frame).
The card holds no wall-clock times, so the same seed gives the same card.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

import numpy as np

from kairos_defense.config import Config
from kairos_defense.sim.generate import FlightResult, Generated

PATTERNS = ("orbit", "lawnmower", "figure8", "perimeter", "hover", "transit_dips", "random_walk")
EXPECTED = {  # §8.11, ± 15%
    "incidents": 1900,
    "tracks": 1950,
    "track_points": 1_000_000,
    "rf_detections": 500_000,
    "reports": 1000,
    "assessments": 1900,
}
PHASE2 = {"rf_detections", "reports", "assessments"}
# Light-surface roles from the dataviz reference palette (validated: blue/orange pass all checks)
SURFACE, INK, INK_2, MUTED, FILL = "#fcfcfb", "#0b0b0b", "#52514e", "#a3a29c", "#e6e5e1"
SERIES_PATH, SERIES_RADAR = "#2a78d6", "#eb6834"


def _n(x: int) -> str:
    return f"{x:,}"


def _status(name: str, value: int) -> str:
    if name in PHASE2:
        return "phase 2"
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
    det = [r for r in g.results if r.detected]
    lines = [
        "# Data card",
        "",
        f"`kairos-defense gen --seed {g.seed}` · phase 1 (world, flights and radar). "
        "All data is synthetic. RF, Remote ID, reports, assessments and swarms arrive in phase 2.",
        "",
        "## Volumes against SPEC §8.11",
        "",
        "| Metric | Value | Expected | Status |",
        "|---|---:|---:|---|",
    ]
    for k, v in vol.items():
        lines.append(f"| {k} | {_n(v)} | ≈{_n(EXPECTED[k])} | {_status(k, v)} |")
    lines += [
        "",
        "Track points come in below ≈1 M: hobbyist flights last 180–720 s (mean ≈450 s), the "
        "radar detects about 80% of scans at a launch park's range (2.2 km) and dropouts remove "
        "≈15% (D-030).",
        "",
        "## Flights",
        "",
        "| Actor type | Flown | Detected | Not detected (no incident) |",
        "|---|---:|---:|---:|",
    ]
    flown = Counter(r.plan.actor_type for r in g.results)
    seen = Counter(r.plan.actor_type for r in det)
    for a in ("hobbyist", "prober", "copycat"):
        lines.append(f"| {a} | {_n(flown[a])} | {_n(seen[a])} | {_n(flown[a] - seen[a])} |")
    missed = len(g.results) - len(det)
    lines.append(f"| **all** | {_n(sum(flown.values()))} | {_n(len(det))} | {_n(missed)} |")
    lines += _per_base(g, det) + _per_actor(det) + _quality(det) + _planted(g) + _live(g)
    lines += ["", "## Row counts", "", "| Database | Table | Rows |", "|---|---|---:|"]
    for t, df in g.tables.items():
        lines.append(f"| app | {t} | {_n(len(df))} |")
    for t, df in g.truth.items():
        lines.append(f"| truth | {t} | {_n(len(df))} |")
    lines += ["", "## Report delays and clue rates", "", "Phase 2: no reports yet.", ""]
    lines += ["## Sample flights", ""]
    lines += [
        "Three flights per pattern type, in each installation's frame (km from its origin): true "
        "path (blue line) and radar detections (orange dots).",
        "",
    ]
    lines += [f"![{Path(f).stem}](figures/{Path(f).name})" for f in figures]
    return "\n".join(lines) + "\n"


def _per_base(g: Generated, det: list[FlightResult]) -> list[str]:
    out = ["", "## Incidents per installation and actor type", ""]
    out += ["| Installation | hobbyist | prober | copycat | total |", "|---|---:|---:|---:|---:|"]
    c = Counter((r.plan.installation_id, r.plan.actor_type) for r in det)
    for sid in g.world.sites:
        row = [c[(sid, a)] for a in ("hobbyist", "prober", "copycat")]
        out.append(f"| {sid} | " + " | ".join(_n(x) for x in row) + f" | {_n(sum(row))} |")
    return out


def _per_actor(det: list[FlightResult]) -> list[str]:
    out = ["", "## Probers and copycats", ""]
    out += ["| Actor | Pattern | Incidents | Bases | Time warp range |", "|---|---|---:|---|---|"]
    by: dict[str, list[FlightResult]] = {}
    for r in det:
        if r.plan.actor_type != "hobbyist":
            by.setdefault(r.plan.actor_id, []).append(r)
    for a in sorted(by):
        rs = by[a]
        w = [r.plan.time_warp for r in rs]
        bases = ", ".join(sorted({r.plan.installation_id for r in rs}))
        out.append(
            f"| {a} | {rs[0].plan.pattern['type']} | {len(rs)} | {bases} | "
            f"{min(w):.2f}–{max(w):.2f} |"
        )
    return out


def _quality(det: list[FlightResult]) -> list[str]:
    pts = np.array([len(r.hits) for r in det])
    dur = np.array([r.path.t_s[-1] for r in det])
    ratio = pts.sum() / max(dur.sum(), 1.0)
    q = np.percentile(pts, [5, 50, 95]).astype(int) if len(pts) else [0, 0, 0]
    return [
        "",
        "## Radar tracks",
        "",
        f"- Points per track: median {q[1]}, p5 {q[0]}, p95 {q[2]}.",
        f"- Flight seconds: {_n(int(dur.sum()))}; radar points per flight second: {ratio:.2f}.",
    ]


def _planted(g: Generated) -> list[str]:
    out = ["", "## Planted P1 flights (scenario_demo.yaml)", ""]
    out += [
        "| Incident | Base | Launch (local) | First contact (local) | Warp | Points | Status |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for r in g.results:
        if r.plan.actor_id != "P1":
            continue
        p = r.plan
        first = "not detected"
        if r.detected:
            first = f"{(p.launch_local + _td(r.hits.t_s[0])):%Y-%m-%d %H:%M:%S}"
        out.append(
            f"| {p.incident_id} | {p.installation_id} | {p.launch_local:%Y-%m-%d %H:%M:%S} | "
            f"{first} | {p.time_warp:.2f} | {len(r.hits)} | {p.status} |"
        )
    return out


def _td(s: float) -> timedelta:
    return timedelta(seconds=float(s))


def _live(g: Generated) -> list[str]:
    out = ["", "## Live incident timing (§1.2, D-003)", ""]
    lt = g.live
    if lt is None:
        return [*out, "Live incident not in this run."]
    est = "never" if lt.orbit_established_s is None else f"T+{lt.orbit_established_s:.0f} s"
    return [
        *out,
        f"- Launch {lt.launch_local:%H:%M:%S}; first radar contact (T+0) "
        f"{lt.first_contact_local:%H:%M:%S}, {lt.first_contact_after_launch_s:.0f} s after launch, "
        f"{lt.first_contact_fence_m:.0f} m outside the fence.",
        f"- Orbit established (within 15 m of the radius for 10 s): {est}.",
    ]


# ------------------------------------------------------------------------------------- figures


def pick_samples(g: Generated, kind: str, n: int = 3) -> list[FlightResult]:
    """Up to ``n`` detected flights of a pattern, planted first, then by key, distinct bases."""
    cands = sorted(
        (r for r in g.results if r.detected and r.plan.pattern["type"] == kind),
        key=lambda r: (r.plan.incident_id is None, r.plan.key),
    )
    out, bases = [], set()
    for r in cands:
        if r.plan.installation_id not in bases:
            out.append(r)
            bases.add(r.plan.installation_id)
        if len(out) == n:
            return out
    out += [r for r in cands if r not in out][: n - len(out)]
    return out


def plot_pattern(g: Generated, kind: str, path: Path) -> Path | None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    samples = pick_samples(g, kind)
    if not samples:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), dpi=90, facecolor=SURFACE)
    for ax, r in zip(axes, [*samples, None, None][:3], strict=True):
        ax.set_facecolor(SURFACE)
        if r is None:
            ax.axis("off")
            continue
        _draw_flight(ax, g, r)
    fig.legend(handles=_legend_handles(), loc="lower center", ncol=4, frameon=False,
               labelcolor=INK_2, fontsize=9)  # fmt: skip
    fig.suptitle(f"Pattern: {kind}", color=INK, fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return path


def _legend_handles() -> list:
    from matplotlib.lines import Line2D

    return [
        Line2D([], [], color=SERIES_PATH, lw=1.5, label="true path"),
        Line2D([], [], color=SERIES_RADAR, marker="o", ms=5, lw=0, label="radar detection"),
        Line2D([], [], color=INK, marker="^", ms=7, lw=0, label="launch"),
        Line2D([], [], mfc=SURFACE, mec=INK, marker="s", ms=6, lw=0, label="recovery"),
    ]


def _draw_flight(ax, g: Generated, r: FlightResult) -> None:
    site = g.world.sites[r.plan.installation_id]
    o = site.origin

    def km(xy):
        xy = np.asarray(xy, dtype=np.float64)
        return (xy[..., 0] - o[0]) / 1000.0, (xy[..., 1] - o[1]) / 1000.0

    target = site.target(r.plan.target_kind)
    for a in site.assets.values():
        x, y = km(np.asarray(a.polygon.exterior.coords))
        edge = INK if a.kind == target.kind and r.plan.actor_type != "hobbyist" else MUTED
        ax.fill(x, y, color=FILL, ec=edge, lw=1.0, zorder=1)
    x, y = km(np.asarray(site.fence.exterior.coords))
    ax.plot(x, y, color=INK_2, lw=1.0, zorder=2)
    px, py = km(r.path.xyz[:, :2])
    hx, hy = km(r.hits.xyz[:, :2])
    ax.scatter(hx, hy, s=3, color=SERIES_RADAR, lw=0, alpha=0.55, zorder=3, label="radar detection")
    ax.plot(px, py, color=SERIES_PATH, lw=1.2, zorder=4, label="true path")
    lx, ly = km(r.plan.launch_xy)
    ax.scatter([lx], [ly], marker="^", s=40, color=INK, zorder=5, label="launch")
    rx, ry = km(r.path.xyz[-1, :2])
    ax.scatter([rx], [ry], marker="s", s=28, facecolor=SURFACE, ec=INK, zorder=5, label="recovery")
    allx, ally = np.r_[px, x], np.r_[py, y]
    pad = 0.3
    ax.set_xlim(allx.min() - pad, allx.max() + pad)
    ax.set_ylim(ally.min() - pad, ally.max() + pad)
    ax.set_aspect("equal")
    ax.tick_params(colors=INK_2, labelsize=8)
    for s in ax.spines.values():
        s.set_color(MUTED)
    inc = g.incident_of[r.plan.key]
    ax.set_title(inc, color=INK, fontsize=10, loc="left", pad=16)
    who = "hobbyist" if r.plan.actor_type == "hobbyist" else r.plan.actor_id
    sub = (f"{who} · {r.plan.installation_id} · "
           f"w {r.plan.time_warp:.2f} · {len(r.hits)} radar points")  # fmt: skip
    ax.text(0.0, 1.02, sub, transform=ax.transAxes, color=INK_2, fontsize=8, va="bottom")
    ax.set_xlabel("east (km)", color=INK_2, fontsize=8)
    ax.set_ylabel("north (km)", color=INK_2, fontsize=8)


def write_data_card(cfg: Config, g: Generated, figures: bool = True) -> Path:
    reports = Path(cfg.app.paths.reports)
    fig_dir = reports / "figures"
    made = []
    if figures:
        for kind in PATTERNS:
            p = plot_pattern(g, kind, fig_dir / f"pattern_{kind}.png")
            if p is not None:
                made.append(str(p))
    reports.mkdir(parents=True, exist_ok=True)
    out = reports / "data_card.md"
    out.write_text(card_markdown(g, made), encoding="utf-8")
    return out
