"""Assessments (SPEC §8.8): one label per history incident, with the planted error.

Recorded 2-36 h after the incident end (whole minutes) by ``<BASE> BDOC``. Rules, in order:
swarm incidents are ``swarm``; a registered Remote ID serial received (mode ``on``) means
``hobbyist``; anything else is ``unknown``, except that 20% of prober incidents are mislabeled
``hobbyist``. Nobody labels ``probing`` in history: no one has linked the flights yet. Live
incidents get no assessment (D-041). ``assessment_truth`` holds the correct label of every
incident: hobbyists ``hobbyist``, probers and copycats ``probing`` (D-042), swarms ``swarm``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from kairos_defense.sim.calendar import local_to_utc_ms
from kairos_defense.sim.facts import IncidentFacts

DELAY_S = (2 * 3600, 36 * 3600)
MISLABEL_P = 0.2
CORRECT = {"hobbyist": "hobbyist", "prober": "probing", "copycat": "probing", "swarm": "swarm"}
LABELS = ("hobbyist", "unknown", "probing", "swarm")
RECREATIONAL = "Single small drone; consistent with a recreational flight. No further action."


@dataclass(frozen=True)
class Assessment:
    assessment_id: str
    incident_id: str
    label: str
    rationale: str
    assessed_ms: int
    author: str


def correct_label(actor_type: str) -> str:
    return CORRECT[actor_type]


def _label(f: IncidentFacts, u: float) -> tuple[str, str]:
    if f.actor_type == "swarm":
        return "swarm", f"{f.n_drones} drones in a coordinated formation; referred for analysis."
    if f.rid_mode == "on" and f.rid_serial:
        return "hobbyist", f"Remote ID serial {f.rid_serial} registered; operator located."
    if f.actor_type == "prober" and u < MISLABEL_P:
        return "hobbyist", RECREATIONAL
    if f.rid_serial:
        return "unknown", (f"Remote ID serial {f.rid_serial} not registered; operator not "
                           "located. Purpose undetermined.")  # fmt: skip
    return "unknown", "No Remote ID; operator not located. Purpose undetermined."


def assess(f: IncidentFacts, rng: np.random.Generator) -> Assessment | None:
    """The generated assessment of one incident; None for a live incident."""
    u_label, u_delay = rng.random(), rng.random()
    if f.status == "live":
        return None
    label, why = _label(f, u_label)
    delay_s = 60 * round((DELAY_S[0] + (DELAY_S[1] - DELAY_S[0]) * u_delay) / 60.0)
    return Assessment(f"A-{f.incident_id}", f.incident_id, label, why,
                      f.end_ms + 1000 * delay_s, f"{f.installation_id} BDOC")  # fmt: skip


def planted_assessment(f: IncidentFacts, planted) -> Assessment:
    """The planted assessment from ``scenario_demo.yaml`` (DELTA's wrong ``hobbyist``)."""
    if planted.label not in LABELS:
        raise ValueError(f"planted assessment: unknown label {planted.label!r}")
    why = RECREATIONAL if planted.label == "hobbyist" else "Assessed by the base."
    return Assessment(f"A-{f.incident_id}", f.incident_id, planted.label, why,
                      local_to_utc_ms(planted.assessed_local, f.utc_offset_hours),
                      planted.author)  # fmt: skip
