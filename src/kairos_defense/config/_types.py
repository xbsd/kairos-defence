"""Shared pydantic base and field types for the config models."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def ordered(v: tuple[float, float]) -> tuple[float, float]:
    if v[0] > v[1]:
        raise ValueError(f"range {list(v)} is reversed (low > high)")
    return v


def _hhmm(v: str) -> str:
    m = re.fullmatch(r"(\d{2}):(\d{2})", v)
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ValueError(f"{v!r} is not a HH:MM local time")
    return v


def _bearing(v: float) -> float:
    if not 0.0 <= v < 360.0:
        raise ValueError(f"bearing {v} must be in [0, 360)")
    return v


Vec2 = tuple[float, float]
Pos = Annotated[float, Field(gt=0)]
NonNeg = Annotated[float, Field(ge=0)]
Prob = Annotated[float, Field(ge=0, le=1)]
Bearing = Annotated[float, AfterValidator(_bearing)]
Range = Annotated[tuple[float, float], AfterValidator(ordered)]
IntRange = Annotated[tuple[int, int], AfterValidator(ordered)]
HHMM = Annotated[str, AfterValidator(_hhmm)]
TimeWindow = tuple[HHMM, HHMM]  # may wrap past midnight, e.g. ["23:00", "01:00"]


def unique_ids(ids: list[str], what: str) -> None:
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate {what}: {dupes}")
