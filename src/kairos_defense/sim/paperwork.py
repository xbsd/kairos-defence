"""Paperwork for every incident (SPEC §8.8, §8.10): reports, assessments and their truth tables.

Planted incidents take their reports and assessment from ``scenario_demo.yaml``; an incident
with planted reports gets no generated ones (D-011). Streams are named by the incident key (the
flight or swarm event key), never by the incident id, so a reassigned id changes no text draws:
``rng_for(seed, "paperwork", key, "reports")`` and ``(…, "assessment")``.

``reports_llm_paraphrase: true`` is refused with a clear error (D-043, D-155): phase 9 built the
LLM adapter for the optional chat only; paraphrased report text would move the clue spans, change
the planted DELTA report and make generation depend on a remote model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.rng import rng_for
from kairos_defense.sim.assessments import (
    Assessment,
    assess,
    correct_label,
    planted_assessment,
)
from kairos_defense.sim.calendar import ms_to_ts
from kairos_defense.sim.facts import IncidentFacts, incident_facts
from kairos_defense.sim.incidents import Incident
from kairos_defense.sim.reports import Report, make_reports, planted_report
from kairos_defense.sim.world import World
from kairos_defense.store.ddl import RAW_COLUMNS, TRUTH_COLUMNS


@dataclass
class Paperwork:
    facts: list[IncidentFacts]
    reports: list[Report]
    assessments: list[Assessment]
    tables: dict[str, pd.DataFrame]  # reports, assessments, clue_truth, assessment_truth


def paperwork(cfg: Config, world: World, incidents: list[Incident], seed: int) -> Paperwork:
    if cfg.app.reports_llm_paraphrase:
        raise RuntimeError(
            "reports_llm_paraphrase is not supported: the LLM adapter built in phase 9 serves the "
            "optional chat only, and paraphrased reports would break the clue spans and seeded "
            "determinism; set it to false (D-043, D-155)"
        )
    planted = {f.incident_id: f for f in cfg.scenario.p1_flights}
    facts, reports, assessments = [], [], []
    for inc in incidents:
        f = incident_facts(cfg, world, inc, seed)
        facts.append(f)
        plant = planted.get(inc.incident_id)
        if plant is not None and plant.reports:
            reports += [planted_report(f, r) for r in plant.reports]
        else:
            reports += make_reports(f, rng_for(seed, "paperwork", inc.key, "reports"))
        if plant is not None and plant.assessment is not None:
            a = planted_assessment(f, plant.assessment)
        else:
            a = assess(f, rng_for(seed, "paperwork", inc.key, "assessment"))
        if a is not None:
            assessments.append(a)
    return Paperwork(facts, reports, assessments, frames(facts, reports, assessments))


def frames(facts, reports, assessments) -> dict[str, pd.DataFrame]:
    rep = pd.DataFrame(
        [(r.report_id, r.incident_id, r.installation_id, r.source, r.grade, r.event_ms,
          r.report_ms, r.text, r.xy[0], r.xy[1]) for r in reports],
        columns=RAW_COLUMNS["reports"],
    )  # fmt: skip
    rep["event_ts"] = ms_to_ts(rep.event_ts.to_numpy(np.int64))
    rep["report_ts"] = ms_to_ts(rep.report_ts.to_numpy(np.int64))
    clues = pd.DataFrame(
        [(r.report_id, c.type, c.value, c.is_true) for r in reports for c in r.clues],
        columns=TRUTH_COLUMNS["clue_truth"],
    )
    clues["is_true"] = clues.is_true.astype(bool)
    ass = pd.DataFrame(
        [(a.assessment_id, a.incident_id, a.label, a.rationale, a.assessed_ms, a.author)
         for a in assessments],
        columns=RAW_COLUMNS["assessments"],
    )  # fmt: skip
    ass["assessed_ts"] = ms_to_ts(ass.assessed_ts.to_numpy(np.int64))
    truth = pd.DataFrame(
        [(f.incident_id, correct_label(f.actor_type)) for f in facts],
        columns=TRUTH_COLUMNS["assessment_truth"],
    )
    return {"reports": rep, "assessments": ass, "clue_truth": clues, "assessment_truth": truth}
