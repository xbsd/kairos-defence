"""Response models for the Swarm view (SPEC §14, §17.9, D-153).

Times are ISO 8601 UTC with ``Z``. Positions are target-relative meters (``x_rel_m`` east,
``y_rel_m`` north of the flight's target asset centroid) and altitude in meters; ``t_s`` counts
seconds since the incident's first radar point. ``curves`` hold the §14 descriptors for the seconds
with at least ``swarm.min_drones`` drones; ``aligned[i]`` is the matched flight's ``curves`` row
for the query's ``curves`` row ``i`` (from the DTW path).
"""

from __future__ import annotations

from pydantic import BaseModel


class SwarmTarget(BaseModel):
    asset_id: str
    kind: str
    x_m: float  # region meters (the frame's origin)
    y_m: float


class SwarmCurves(BaseModel):
    t_s: list[int]
    n_drones: list[int]
    spread_m: list[float | None]
    pd_q25_m: list[float | None]
    pd_q50_m: list[float | None]
    pd_q75_m: list[float | None]
    rot_rate_dps: list[float | None]
    centroid_speed_ms: list[float | None]
    axis_angle_deg: list[float | None]
    centroid_x_rel_m: list[float | None]
    centroid_y_rel_m: list[float | None]


class SwarmFlightOut(BaseModel):
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    n_drones: int
    track_ids: list[str]
    is_swarm: bool  # §14 detection on the observed seconds
    together_s: int
    target: SwarmTarget
    curves: SwarmCurves
    t_s: list[int]  # every observed second (the positions grid)
    positions: list[list[list[float | None]]]  # [drone][second][x_rel_m, y_rel_m, alt_m]


class SwarmMatchOut(BaseModel):
    rank: int
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    n_drones: int
    duration_s: float
    distance: float
    similarity: float
    warp_ratio: float  # matched seconds per query second
    matched_s: int


class SwarmResponse(BaseModel):
    incident_id: str
    at_s: float | None  # the query second asked for; None: the whole observed flight
    observed_s: int  # seconds of the query actually used
    model_version: str
    query: SwarmFlightOut
    matches: list[SwarmMatchOut]
    match: SwarmFlightOut | None  # the selected match's whole flight
    match_rank: int | None
    aligned: list[int]
    path: list[list[int]]
    elapsed_ms: float


class SwarmIncident(BaseModel):
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    n_tracks: int
    status: str
