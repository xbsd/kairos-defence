"""``FlightPlan``: everything drawn for one flight before it is flown."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class FlightPlan:
    """One planned flight. Region-frame meters, true bearings, nominal (unwarped) parameters.

    ``key`` is a stable name for the flight (``P2/007``, ``H/ALPHA/2025-03-01/0``, or a planted
    incident id); every random stream for the flight is derived from it, so adding an actor never
    changes another actor's flights (§8.9).
    """

    key: str
    actor_id: str
    actor_type: str  # hobbyist | prober | copycat
    installation_id: str
    region_id: str
    night: date
    launch_local: datetime  # naive local, whole seconds
    launch_ms: int  # UTC epoch milliseconds
    time_warp: float
    pattern: dict  # resolved for this flight: {"type": ..., per-flight parameters}
    target_kind: str  # an asset kind or "fence"
    launch_xy: tuple[float, float]
    recovery_xy: tuple[float, float]
    approach_bearing_deg: float | None  # None for hobbyists
    altitude_m: float
    cruise_ms: float
    rf_family: str
    rid: str  # on | off | spoofed (phase 2)
    incident_id: str | None = None  # planted incidents carry their id
    status: str = "history"  # history | live
    outage_s: tuple[float, float] | None = None  # seconds after launch with no radar (§8.10)
    pauses: bool = True  # False for `jitter: none` flights (D-025)
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)
