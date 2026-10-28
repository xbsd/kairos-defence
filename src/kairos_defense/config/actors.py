"""Models for ``config/actors.yaml`` (SPEC §6.3)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from kairos_defense.config._types import (
    Bearing,
    IntRange,
    NonNeg,
    Pos,
    Prob,
    Range,
    StrictModel,
    TimeWindow,
    ordered,
    unique_ids,
)


class Hobbyists(StrictModel):
    rate_per_night_per_base: NonNeg
    duration_s: Range
    altitude_m: Range
    speed_ms: Range
    rid_on_prob: Prob
    rf_families: list[str]
    launch_from: list[Literal["parks", "public_events"]]
    cross_fence_prob: Prob
    pattern: Literal["random_walk"]


class OrbitPattern(StrictModel):
    type: Literal["orbit"]
    radius_m: Pos
    direction: Literal["cw", "ccw"]
    laps: IntRange
    angular_speed_dps: Pos


class LawnmowerPattern(StrictModel):
    type: Literal["lawnmower"]
    leg_m: Pos
    spacing_m: Pos
    legs: IntRange


class Figure8Pattern(StrictModel):
    type: Literal["figure8"]
    lobe_radius_m: Pos
    loops: IntRange


class PerimeterPattern(StrictModel):
    type: Literal["perimeter"]
    offset_m: float
    fraction: Annotated[tuple[Prob, Prob], AfterValidator(ordered)]


class HoverPattern(StrictModel):
    type: Literal["hover"]
    dwell_s: Range
    jitter_m: NonNeg


class TransitDipsPattern(StrictModel):
    type: Literal["transit_dips"]
    transit_alt_m: Pos
    dip_alt_m: Pos
    dips: Annotated[int, Field(ge=1)]


Pattern = Annotated[
    OrbitPattern
    | LawnmowerPattern
    | Figure8Pattern
    | PerimeterPattern
    | HoverPattern
    | TransitDipsPattern,
    Field(discriminator="type"),
]


class Launch(StrictModel):
    bearing_deg: Bearing
    distance_m: Pos
    jitter_m: NonNeg
    snap_to_road: str | None = None
    from_: Literal["parks"] | None = Field(default=None, alias="from")  # label only (D-005)


class Clues(StrictModel):
    vehicle: str | None = None
    road: str | None = None


class Prober(StrictModel):
    id: str
    nickname: str
    bases: list[str]
    flights: Annotated[int, Field(ge=0)] | Literal["planted_only"]
    target: str
    pattern: Pattern
    approach_bearing_deg: Bearing
    launch: Launch
    altitude_m: Range
    cruise_speed_ms: Pos
    rf_family: str
    rid: Literal["off", "on", "spoofed"]
    clues: Clues
    time_local: TimeWindow


class Copycat(StrictModel):
    id: str
    mimics: str
    bases: list[str]
    flights: Annotated[int, Field(ge=0)]
    pattern_overrides: dict[str, Range] = Field(default_factory=dict)
    launch: Launch
    rf_family: str
    rid_on_prob: Prob
    time_local: TimeWindow


class FormationStep(StrictModel):
    formation: Literal["line_abreast", "v", "triangle", "trail"]
    spacing_m: Pos
    duration_s: Pos


_ACTION_PARAMS = {
    "rotate": {"degrees", "direction"},
    "split": {"groups", "separation_m"},
    "orbit_target": {"radius_m"},
    "expand": {"factor"},
}


class ActionStep(StrictModel):
    action: Literal["rotate", "split", "orbit_target", "expand"]
    duration_s: Pos
    degrees: float | None = None
    direction: Literal["cw", "ccw"] | None = None
    groups: list[Annotated[int, Field(ge=1)]] | None = None
    separation_m: Pos | None = None
    radius_m: Pos | None = None
    factor: Pos | None = None

    @model_validator(mode="after")
    def _params(self) -> ActionStep:
        all_params = set().union(*_ACTION_PARAMS.values())
        given = {k for k in all_params if getattr(self, k) is not None}
        need = _ACTION_PARAMS[self.action]
        if given != need:
            raise ValueError(f"action {self.action!r} takes exactly {sorted(need)}")
        return self


ChoreoStep = Annotated[FormationStep | ActionStep, Field(union_mode="left_to_right")]


class Swarm(StrictModel):
    id: str
    drones: Annotated[int, Field(ge=2)]
    bases: list[str]
    random_events: Annotated[int, Field(ge=0)]
    rf_family: str
    altitude_m: Range
    target: str
    choreography: Annotated[list[ChoreoStep], Field(min_length=1)]

    @model_validator(mode="after")
    def _split_sizes(self) -> Swarm:
        for step in self.choreography:
            if isinstance(step, ActionStep) and step.groups and sum(step.groups) != self.drones:
                raise ValueError(f"swarm {self.id}: split groups must add up to {self.drones}")
        return self


class ActorsConfig(StrictModel):
    hobbyists: Hobbyists
    probers: list[Prober]
    copycats: list[Copycat]
    swarms: list[Swarm]

    @model_validator(mode="after")
    def _refs(self) -> ActorsConfig:
        unique_ids([a.id for a in [*self.probers, *self.copycats, *self.swarms]], "actor ids")
        prober_ids = {p.id for p in self.probers}
        for c in self.copycats:
            if c.mimics not in prober_ids:
                raise ValueError(f"copycat {c.id} mimics unknown prober {c.mimics!r}")
        return self
