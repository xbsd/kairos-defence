"""Data-card figures (SPEC §8.11): sample flights per pattern, and one figure per swarm team.

Colors are the dataviz reference palette on its light surface (blue and orange pass the palette
validator). Drones are never told apart by color: a swarm figure shows every drone in one color
and the choreography as small multiples, one formation snapshot per step.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from kairos_defense.sim import formations as fm
from kairos_defense.sim.generate import FlightResult, Generated
from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.swarm import choreography_clock

PATTERNS = ("orbit", "lawnmower", "figure8", "perimeter", "hover", "transit_dips", "random_walk")
SURFACE, INK, INK_2, MUTED, FILL = "#fcfcfb", "#0b0b0b", "#52514e", "#a3a29c", "#e6e5e1"
SERIES_PATH, SERIES_RADAR = "#2a78d6", "#eb6834"


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


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


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    _plt().close(fig)
    return path


def plot_pattern(g: Generated, kind: str, path: Path) -> Path | None:
    plt = _plt()
    samples = pick_samples(g, kind)
    if not samples:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), dpi=90, facecolor=SURFACE)
    for ax, r in zip(axes, [*samples, None, None][:3], strict=True):
        ax.set_facecolor(SURFACE)
        if r is None:
            ax.axis("off")
            continue
        who = "hobbyist" if r.plan.actor_type == "hobbyist" else r.plan.actor_id
        sub = (f"{who} · {r.plan.installation_id} · "
               f"w {r.plan.time_warp:.2f} · {len(r.hits)} radar points")  # fmt: skip
        _draw_paths(ax, g, [r], g.incident_of[r.plan.key], sub)
    fig.legend(handles=_legend_handles(), loc="lower center", ncol=4, frameon=False,
               labelcolor=INK_2, fontsize=9)  # fmt: skip
    fig.suptitle(f"Pattern: {kind}", color=INK, fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.11, 1, 0.95))
    return _save(fig, path)


def _legend_handles() -> list:
    from matplotlib.lines import Line2D

    return [
        Line2D([], [], color=SERIES_PATH, lw=1.5, label="true path"),
        Line2D([], [], color=SERIES_RADAR, marker="o", ms=5, lw=0, label="radar detection"),
        Line2D([], [], color=INK, marker="^", ms=7, lw=0, label="launch"),
        Line2D([], [], mfc=SURFACE, mec=INK, marker="s", ms=6, lw=0, label="recovery"),
    ]


def _style(ax) -> None:
    ax.tick_params(colors=INK_2, labelsize=8)
    for s in ax.spines.values():
        s.set_color(MUTED)


def _draw_paths(ax, g: Generated, rs: list[FlightResult], title: str, sub: str) -> None:
    """Base layout, true paths, radar points, launch and recovery, in km from the origin."""
    p = rs[0].plan
    site = g.world.sites[p.installation_id]
    o = site.origin

    def km(xy):
        xy = np.asarray(xy, dtype=np.float64)
        return (xy[..., 0] - o[0]) / 1000.0, (xy[..., 1] - o[1]) / 1000.0

    target = site.target(p.target_kind)
    for a in site.assets.values():
        x, y = km(np.asarray(a.polygon.exterior.coords))
        edge = INK if a.kind == target.kind and p.actor_type != "hobbyist" else MUTED
        ax.fill(x, y, color=FILL, ec=edge, lw=1.0, zorder=1)
    fx, fy = km(np.asarray(site.fence.exterior.coords))
    ax.plot(fx, fy, color=INK_2, lw=1.0, zorder=2)
    allx, ally = [fx], [fy]
    lw = 1.2 if len(rs) == 1 else 0.8
    for r in rs:
        px, py = km(r.path.xyz[:, :2])
        hx, hy = km(r.hits.xyz[:, :2])
        ax.scatter(hx, hy, s=3, color=SERIES_RADAR, lw=0, alpha=0.55, zorder=3)
        ax.plot(px, py, color=SERIES_PATH, lw=lw, zorder=4)
        lx, ly = km(r.path.xyz[0, :2])
        ax.scatter([lx], [ly], marker="^", s=40, color=INK, zorder=5)
        rx, ry = km(r.path.xyz[-1, :2])
        ax.scatter([rx], [ry], marker="s", s=28, facecolor=SURFACE, ec=INK, zorder=5)
        allx.append(px)
        ally.append(py)
    allx, ally = np.concatenate(allx), np.concatenate(ally)
    pad = 0.3
    ax.set_xlim(allx.min() - pad, allx.max() + pad)
    ax.set_ylim(ally.min() - pad, ally.max() + pad)
    ax.set_aspect("equal")
    _style(ax)
    ax.set_title(title, color=INK, fontsize=10, loc="left", pad=16)
    ax.text(0.0, 1.02, sub, transform=ax.transAxes, color=INK_2, fontsize=8, va="bottom")
    ax.set_xlabel("east (km)", color=INK_2, fontsize=8)
    ax.set_ylabel("north (km)", color=INK_2, fontsize=8)


def swarm_sample(g: Generated, team_id: str):
    """The team's planted history event if present, else its first event; ``Incident`` or None."""
    incs = [i for i in g.incidents if i.is_swarm and i.plan.actor_id == team_id]
    incs.sort(key=lambda i: (i.status == "live", i.plan.incident_id is None, i.key))
    return incs[0] if incs else None


def _step_label(s: dict) -> str:
    k = s["kind"]
    if k in fm.FORMATIONS:
        return f"{k.replace('_', ' ')}, {s['spacing_m']:.0f} m"
    if k == "rotate":
        return f"rotate {s['degrees']:.0f}° {s['direction']}"
    if k == "expand":
        return f"expand ×{s['factor']:g}"
    if k == "split":
        return f"split {'+'.join(map(str, s['groups']))}, {s['separation_m']:.0f} m"
    return f"orbit target, {s['radius_m']:.0f} m"


def plot_swarm(g: Generated, team_id: str, path: Path) -> Path | None:
    """Overview of one swarm event plus one formation snapshot per choreography step (positions
    about the swarm centroid, north up; the arrow is the swarm heading; drone 0 is ringed)."""
    inc = swarm_sample(g, team_id)
    if inc is None:
        return None
    plt = _plt()
    plan, rs = inc.plan, list(inc.flights)
    xyz = np.stack([r.path.xyz for r in rs])
    mean = FlightPath(plan.key, rs[0].path.t_s, xyz.mean(axis=0), rs[0].path.phase)
    tau = choreography_clock(plan, mean)
    tl = fm.timeline(plan.pattern["steps"], len(rs))
    k = len(tl.steps)
    cols = 3
    rows = (k + 1 + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(12, 4.2 * rows), dpi=90, facecolor=SURFACE)
    axes = axes.ravel()
    sub = f"{team_id} · {plan.installation_id} · w {plan.time_warp:.2f} · {len(rs)} drones"
    _draw_paths(axes[0], g, rs, inc.incident_id, sub)
    snaps = []
    for i, s in enumerate(tl.steps):
        t = sum(tl.hold(i)) / 2.0 if s["kind"] in fm.FORMATIONS else tl.end_s[i] - 1.0
        j = int(np.argmin(np.abs(tau - t)))
        snaps.append(xyz[:, j, :2] - xyz[:, j, :2].mean(axis=0))
    lim = max(60.0, float(np.max(np.abs(np.concatenate(snaps)))) * 1.15)
    head = np.radians(plan.pattern["heading_deg"])
    for i, (s, rel) in enumerate(zip(tl.steps, snaps, strict=True)):
        ax = axes[i + 1]
        ax.set_facecolor(SURFACE)
        ax.axhline(0, color=FILL, lw=0.8, zorder=0)
        ax.axvline(0, color=FILL, lw=0.8, zorder=0)
        a = 0.45 * lim
        ax.annotate(
            "",
            xy=(a * np.sin(head), a * np.cos(head)),
            xytext=(0, 0),
            arrowprops={"arrowstyle": "->", "color": MUTED, "lw": 1.0},
            zorder=1,
        )
        ax.scatter(rel[:, 0], rel[:, 1], s=64, color=SERIES_PATH, ec=SURFACE, lw=2, zorder=3)
        ax.scatter(rel[:1, 0], rel[:1, 1], s=150, facecolor="none", ec=INK, lw=1.2, zorder=4)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        _style(ax)
        ax.set_title(f"{i + 1}. {_step_label(s)}", color=INK, fontsize=10, loc="left")
        ax.set_xlabel("east of centroid (m)", color=INK_2, fontsize=8)
        ax.set_ylabel("north of centroid (m)", color=INK_2, fontsize=8)
    for ax in axes[k + 1 :]:
        ax.axis("off")
    fig.legend(handles=_legend_handles(), loc="lower center", ncol=4, frameon=False,
               labelcolor=INK_2, fontsize=9)  # fmt: skip
    fig.suptitle(f"Swarm team {team_id}: path and choreography", color=INK, fontsize=12,
                 x=0.01, ha="left")  # fmt: skip
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    return _save(fig, path)
