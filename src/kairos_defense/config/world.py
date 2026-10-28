"""Models for ``config/world.yaml`` (SPEC §6.2). Region-frame meters, true bearings (D-007)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from kairos_defense.config._types import (
    Bearing,
    NonNeg,
    Pos,
    Prob,
    StrictModel,
    TimeWindow,
    Vec2,
    unique_ids,
)


class CalendarConfig(StrictModel):
    start_local: date
    end_local: date
    night_window_local: TimeWindow

    @model_validator(mode="after")
    def _order(self) -> CalendarConfig:
        if self.start_local >= self.end_local:
            raise ValueError("calendar start_local must be before end_local")
        return self


class TerrainMask(StrictModel):
    bearing_deg: tuple[Bearing, Bearing]  # clockwise sector from first to second (may wrap 0)
    beyond_fence_m: NonNeg
    below_alt_m: Pos


class Installation(StrictModel):
    id: str
    origin_m: Vec2
    rotation_deg: float
    terrain_mask: TerrainMask | None = None


class Park(StrictModel):
    id: str
    center_m: Vec2
    radius_m: Pos


class Road(StrictModel):
    name: str
    # alias: "construct" would shadow BaseModel.construct
    build: Literal["through_launch_points"] | None = Field(default=None, alias="construct")
    actor: str | None = None
    extend_m: NonNeg | None = None
    points_m: list[Vec2] | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> Road:
        if (self.build is None) == (self.points_m is None):
            raise ValueError(f"road {self.name!r}: give exactly one of construct or points_m")
        if self.build and not self.actor:
            raise ValueError(f"road {self.name!r}: construct needs an actor")
        if self.points_m is not None and len(self.points_m) < 2:
            raise ValueError(f"road {self.name!r}: needs at least two points")
        return self


class Region(StrictModel):
    id: str
    utc_offset_hours: Annotated[int, Field(ge=-12, le=14)]
    installations: list[Installation]
    parks: list[Park]
    roads: list[Road]


class Asset(StrictModel):
    center: Vec2
    size: tuple[Pos, Pos]


class InstallationTemplate(StrictModel):
    fence: Annotated[list[Vec2], Field(min_length=3)]
    assets: dict[str, Asset]
    jitter_m: NonNeg


class RadarSensor(StrictModel):
    kind: Literal["radar"]
    at: Vec2
    range_m: Pos
    rate_hz: Pos
    pos_sigma_m: NonNeg
    alt_sigma_m: NonNeg
    p_detect_near: Prob
    p_detect_far: Prob
    min_alt_m: NonNeg


class RfSensor(StrictModel):
    kind: Literal["rf"]
    at: Vec2
    range_m: Pos
    rate_hz: Pos
    bearing_sigma_deg: NonNeg


class RidSensor(StrictModel):
    kind: Literal["rid"]
    at: Vec2
    range_m: Pos
    rate_hz: Pos


Sensor = Annotated[RadarSensor | RfSensor | RidSensor, Field(discriminator="kind")]


class WorldConfig(StrictModel):
    seed: int
    calendar: CalendarConfig
    regions: Annotated[list[Region], Field(min_length=1)]
    installation_template: InstallationTemplate
    sensors_template: list[Sensor]

    @model_validator(mode="after")
    def _unique_ids(self) -> WorldConfig:
        unique_ids([r.id for r in self.regions], "region ids")
        unique_ids([i.id for r in self.regions for i in r.installations], "installation ids")
        unique_ids([p.id for r in self.regions for p in r.parks], "park ids")
        return self

    def installation_ids(self) -> list[str]:
        return [i.id for r in self.regions for i in r.installations]

    def region_of(self, installation_id: str) -> Region:
        for r in self.regions:
            if any(i.id == installation_id for i in r.installations):
                return r
        raise KeyError(installation_id)

    def installation(self, installation_id: str) -> Installation:
        region = self.region_of(installation_id)
        return next(i for i in region.installations if i.id == installation_id)
