"""The ingest contract v1: what a sensor adapter sends the app (D-169, D-173).

The seam a real radar, RF or Remote ID adapter would implement; the live simulator is the first
adapter. Messages are JSON objects discriminated by ``type`` (``point``, ``rf``, ``rid``,
``heartbeat``), each with ``v: 1``. Send them on ``WS /ws/ingest`` (one object or an array per
frame; each frame gets an ``IngestAck``) or ``POST /api/ingest`` (``IngestBatch``, answered with
the same ``IngestAck``). Times are ISO 8601 with ``Z`` or an offset; coordinates are the region's
local ENU meters (``x_m`` east, ``y_m`` north), altitudes meters, bearings degrees clockwise from
north. No message names a person, an operator or an incident: the app forms incidents itself.
Beyond the schema the app refuses unknown installations, a sensor that is not that
installation's sensor of that kind, timestamps at or before the end of the history (rule 3) and
messages more than ``live.max_lateness_s`` behind the installation's feed time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION = 1
Id = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Meters = Annotated[float, Field(allow_inf_nan=False, ge=-1e6, le=1e6)]


class _Msg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: Literal[1] = Field(1, description="Contract version (only 1 exists).")
    installation_id: Id = Field(description="The installation whose sensor saw this.")
    ts: datetime = Field(description="When it was seen: ISO 8601 with Z or an offset.")

    @field_validator("ts")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("ts needs a time zone (Z or an offset)")
        return v

    def row(self) -> dict:
        """The message as the hub takes it: ``ts`` naive UTC."""
        d = self.model_dump()
        d["ts"] = self.ts.astimezone(UTC).replace(tzinfo=None)
        return d


class IngestPoint(_Msg):
    """One radar detection of one sensor track (``track_points`` columns)."""

    type: Literal["point"]
    sensor_id: Id = Field(description="The installation's radar sensor id.")
    sensor_track_id: Id = Field(description="The radar's own track id (opaque, stable per track).")
    x_m: Meters
    y_m: Meters
    alt_m: Annotated[float, Field(allow_inf_nan=False, ge=0, le=20000)]
    quality: Annotated[float, Field(allow_inf_nan=False, ge=0, le=1)]


class IngestRf(_Msg):
    """One RF detection of a control link (``rf_detections`` columns)."""

    type: Literal["rf"]
    sensor_id: Id = Field(description="The installation's RF sensor id.")
    band: Annotated[str, Field(min_length=1, max_length=16)]
    protocol_family: Annotated[str, Field(min_length=1, max_length=32)]
    bearing_deg: Annotated[float, Field(allow_inf_nan=False, ge=0, lt=360)]
    snr_db: Annotated[float, Field(allow_inf_nan=False, ge=-50, le=150)]


class IngestRid(_Msg):
    """One Remote ID broadcast received (``remote_id`` columns)."""

    type: Literal["rid"]
    serial: Annotated[str, Field(min_length=1, max_length=64)]
    drone_x_m: Meters
    drone_y_m: Meters
    op_x_m: Meters
    op_y_m: Meters


class IngestHeartbeat(_Msg):
    """The adapter is alive and its clock reads ``ts``; advances the installation's feed time
    (incidents close on it). ``rate``: feed seconds per wall second (1 for a real sensor)."""

    type: Literal["heartbeat"]
    rate: Annotated[float, Field(allow_inf_nan=False, gt=0, le=100)] = 1.0


IngestMessage = Annotated[IngestPoint | IngestRf | IngestRid | IngestHeartbeat,
                          Field(discriminator="type")]  # fmt: skip


class IngestBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[dict] = Field(max_length=10000, description="Ingest messages, in time order.")


class Rejected(BaseModel):
    index: int
    reason: str


class IngestAck(BaseModel):
    type: Literal["ack"] = "ack"
    accepted: int = Field(description="Messages accepted, heartbeats included.")
    detections: int = Field(description="Detections accepted (point, rf, rid).")
    rejected: list[Rejected]
