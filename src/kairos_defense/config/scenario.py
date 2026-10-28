"""Models for ``config/scenario_demo.yaml`` (SPEC §6.4). Times are naive local."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from kairos_defense.config._types import Pos, Range, StrictModel, TimeWindow, ordered, unique_ids


class ReportClue(StrictModel):
    type: str
    value: str
    road: str | None = None
    seen_local: TimeWindow
    is_true: bool = Field(alias="true")  # ground truth of the clue; only eval may use it


class PlantedReport(StrictModel):
    source: str
    report_local: datetime
    grade: Annotated[str, Field(pattern=r"^[A-F][1-6]$")]  # source reliability + credibility
    clues: list[ReportClue]


class PlantedAssessment(StrictModel):
    label: str
    assessed_local: datetime
    author: str


class P1Flight(StrictModel):
    incident_id: str
    base: str
    start_local: datetime  # launch time; truth only (D-003)
    time_warp: Pos
    sensor_outage_s: Range | None = None
    reports: list[PlantedReport] = Field(default_factory=list)
    assessment: PlantedAssessment | None = None
    jitter: Literal["none"] | None = None
    status: Literal["live"] | None = None
    target_override: str | None = None


class SwarmEvent(StrictModel):
    incident_id: str
    team: str
    base: str
    start_local: datetime
    status: Literal["live"] | None = None


class Expectations(StrictModel):
    live_first_contact_local: Annotated[tuple[datetime, datetime], AfterValidator(ordered)]
    live_orbit_established_s: Range
    live_top3_at_s: Pos
    live_top3_incidents: Annotated[list[str], Field(min_length=3, max_length=3)]
    live_rank1_report_for: str
    forecast_at_s: Pos
    forecast_error_max_m: Pos
    swarm_top1: str


class ScenarioConfig(StrictModel):
    live_incident: str
    p1_flights: list[P1Flight]
    swarm_events: list[SwarmEvent]
    expectations: Expectations

    @model_validator(mode="after")
    def _refs(self) -> ScenarioConfig:
        p1 = {f.incident_id: f for f in self.p1_flights}
        unique_ids([*p1] + [s.incident_id for s in self.swarm_events], "incident ids")
        live = p1.get(self.live_incident)
        if live is None or live.status != "live":
            raise ValueError(f"live_incident {self.live_incident!r} must be a live P1 flight")
        ex = self.expectations
        for inc in [*ex.live_top3_incidents, ex.live_rank1_report_for]:
            if inc not in p1:
                raise ValueError(f"expectations name unknown P1 incident {inc!r}")
        if ex.swarm_top1 not in {s.incident_id for s in self.swarm_events}:
            raise ValueError(f"expectations name unknown swarm incident {ex.swarm_top1!r}")
        return self
