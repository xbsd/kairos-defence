"""Data-card sections on paperwork (SPEC §8.8): reports, delays, styles, clues, assessments."""

from __future__ import annotations

from collections import Counter

import numpy as np

from kairos_defense.sim.datacard_util import ACTOR_TYPES, n, pct, table
from kairos_defense.sim.generate import Generated
from kairos_defense.sim.reports import SOURCES, style

DELAY_BINS_S = [0, 600, 1800, 5400, 6 * 3600, 24 * 3600, 48 * 3600, 5 * 86400 + 1]
DELAY_LABELS = ["0–10 min", "10–30 min", "30–90 min", "1.5–6 h", "6–24 h", "1–2 d", "2–5 d"]


def reports_section(g: Generated) -> list[str]:
    rep = g.tables["reports"]
    inc = g.tables["incidents"].set_index("incident_id")
    facts = {f.incident_id: f for f in g.paper.facts}
    src = Counter(rep.source)
    rows = [
        [
            s,
            n(src[s]),
            ", ".join(
                f"{k} {v}" for k, v in sorted(Counter(rep[rep.source == s].source_grade).items())
            ),
        ]
        for s in SOURCES
    ]
    per = Counter(facts[i].actor_type for i in rep.incident_id)
    n_inc = Counter(f.actor_type for f in facts.values() if f.status == "history")
    rows2 = [[a, n(n_inc[a]), n(per[a]), f"{per[a] / max(n_inc[a], 1):.2f}"] for a in ACTOR_TYPES]
    delay = (rep.report_ts - inc.loc[rep.incident_id].end_ts.to_numpy()).dt.total_seconds()
    hist = []
    for s in SOURCES:
        h, _ = np.histogram(delay[rep.source == s], bins=DELAY_BINS_S)
        hist.append([s, *(n(int(x)) for x in h)])
    styles = Counter(style(b) for b in g.world.sites)
    by_style = {st: ", ".join(b for b in g.world.sites if style(b) == st) for st in styles}
    return [
        "",
        "## Reports (§8.8, Appendix A)",
        "",
        *table(["Source", "Reports", "Grades"], rows, 1),
        "",
        *table(["Actor type", "History incidents", "Reports", "Per incident"], rows2),
        "",
        "Report delay after the incident end (histogram, reports per bin):",
        "",
        *table(["Source", *DELAY_LABELS], hist),
        "",
        "Security-forces styles: " + "; ".join(f"{k} ({v})" for k, v in by_style.items()) + ".",
    ]


def clues_section(g: Generated) -> list[str]:
    ct = g.truth["clue_truth"]
    rows = [
        [
            t,
            n(int((ct.clue_type == t).sum())),
            pct(ct[ct.clue_type == t].is_true.mean()) if (ct.clue_type == t).any() else "–",
        ]
        for t in ("vehicle", "road", "lights", "sound", "launch_site", "departure")
    ]
    slots = [
        r
        for r in g.paper.reports
        if r.source in ("security_forces", "local_pd") and not r.text.startswith("Operator located")
    ]
    veh = sum(any(c.type == "vehicle" for c in r.clues) for r in slots)
    road = sum(any(c.type == "road" for c in r.clues) for r in slots)
    total = max(len(slots), 1)
    return [
        "",
        "## Clue rates (§8.8)",
        "",
        *table(["Clue type", "Mentions", "True"], rows),
        "",
        f"In the {n(len(slots))} security-forces and local-PD reports that can carry a vehicle, "
        f"a vehicle is mentioned in {pct(veh / total)} (model 35%) and a road in "
        f"{pct(road / total)} "
        "(model 30%). Vehicles are true only for probers with a vehicle in their profile; every "
        "other actor's observed vehicles are wrong by construction. Hobbyist reports name the "
        "park where the operator was found, so most launch-site clues are true.",
    ]


def assessments_section(g: Generated) -> list[str]:
    a = g.tables["assessments"].set_index("incident_id").label
    truth = g.truth["assessment_truth"].set_index("incident_id").correct_label
    labels = ("hobbyist", "unknown", "probing", "swarm")
    rows = []
    for c in ("hobbyist", "probing", "swarm"):
        ids = truth[truth == c].index.intersection(a.index)
        cnt = Counter(a.loc[ids])
        rows.append([c, *(n(cnt[x]) for x in labels), n(len(ids))])
    probers = [
        f.incident_id
        for f in g.paper.facts
        if f.actor_type == "prober" and f.incident_id in a.index
    ]
    mis = np.mean([a.loc[i] == "hobbyist" for i in probers]) if probers else 0.0
    return [
        "",
        "## Assessments (§8.8)",
        "",
        "Rows: correct label (truth). Columns: label given. Live incidents get none (D-041).",
        "",
        *table(["Correct \\ given", *labels, "total"], rows),
        "",
        f"Prober incidents labeled hobbyist: {pct(mis)} (model 20%; the count includes the "
        "planted DELTA label). Nobody labels probing: no one has linked the flights yet.",
    ]
