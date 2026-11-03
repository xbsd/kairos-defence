"""Pydantic models of the replay stream and the REST API (SPEC §16.3–§16.5, D-107, D-108).

``StreamMessage`` is the discriminated union (on ``type``) of the thirteen §16.3 server messages
plus ``matcher_trace`` (phase 12, D-188);
``ClientMessage`` the five client messages. Models forbid unknown fields, so the contract test
catches any drift between what the server sends and what the web app's generated types say.
``kairos-defense api --dump-openapi web/openapi.json`` exports them; ``npm run gen:types`` turns
them into ``web/src/api/types.gen.ts``. Times are ISO 8601 UTC with ``Z``; coordinates are
region-frame meters; ``t_s`` is replay seconds since T+0.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from kairos_defense.api.schemas_trace import MatcherTraceMsg

Num = float | None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- server → client -------------------------------------------------------------------------
class HelloMsg(Strict):
    type: Literal["hello"]
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    duration_s: float
    speed: float
    playing: bool
    tracks: list[str]
    is_swarm: bool
    matching: bool  # false: no single-track matching (swarms: GET /api/swarm/{id}, phase 9)
    min_track_s: float
    rerun_every_s: float
    utc_offset_hours: int


class ClockMsg(Strict):
    type: Literal["clock"]
    t_s: float
    ts: str
    speed: float
    playing: bool
    seeked: bool  # true after a seek or reset: drop buffers, a catch-up follows


class PointMsg(Strict):
    type: Literal["point"]
    incident_id: str
    track_id: str
    sensor_id: str
    t_s: float
    x_m: Num
    y_m: Num
    alt_m: Num
    quality: Num


class RfMsg(Strict):
    type: Literal["rf"]
    sensor_id: str
    t_s: float
    band: str | None
    bearing_deg: Num
    protocol_family: str | None
    snr_db: Num


class RidMsg(Strict):
    type: Literal["rid"]
    serial: str
    t_s: float
    drone_x_m: Num
    drone_y_m: Num
    op_x_m: Num
    op_y_m: Num


class FeaturesMsg(Strict):
    type: Literal["features"]
    t_s: float
    track_id: str
    target_asset_id: str
    speed_ms: Num
    alt_m: Num
    turn_rate_dps: Num
    dist_target_m: Num
    vspeed_ms: Num
    heading_deg: Num
    phase: Literal["approach", "loiter", "egress"]


class IngestMsg(Strict):
    type: Literal["ingest"]
    table: Literal["live_points", "live_rf", "live_rid"]
    rows: int
    total_rows: int
    write_ms: float
    statement: str


class MatchItem(Strict):
    """§10.8 fields, plus the rank, the local start and what the memory says (D-107, D-116)."""

    query_incident_id: str
    track_id: str
    incident_id: str
    installation_id: str
    start_ts: str
    score: float
    shape_sim: float
    features: dict[str, Num]
    reasons: list[str]
    warp_ratio: Num
    window_offset_s: int
    model_version: str
    rank: int
    local_start: str  # YYYY-MM-DDTHH:MM, the match's installation's local time
    proposal_seq: int | None
    decision: Literal["approved", "rejected"] | None
    memory_status: str


class MatchMsg(Strict):
    type: Literal["match"]
    t_s: float
    model_version: str
    elapsed_ms: float  # measured when the result was computed
    cached: bool  # served from the precomputed cache (elapsed_ms is the original)
    case_id: str | None  # the case live proposals go to (D-106)
    query_track: str
    target_asset_id: str
    matches: list[MatchItem]


class LensBody(Strict):
    match_track_id: str
    channel: str
    query: list[float]
    candidate: list[float]
    path: list[tuple[int, int]]
    cost: str  # float32 little-endian, row-major, base64
    shape: tuple[int, int]
    band: int
    dtw_distance: float
    euclid_distance: float
    overlap: int
    warp_ratio: Num
    warp_text: str | None


class DtwMsg(LensBody):
    type: Literal["dtw"]
    t_s: float


class Analog(Strict):
    incident_id: str
    track_id: str
    score: float
    target_kind: str
    recovery_rel_m: list[float]
    rotation_deg: float
    anchor_asset_id: str
    aligned_t_s: int
    recovery_x_m: float
    recovery_y_m: float
    remainder_points: int


class ForecastMsg(Strict):
    type: Literal["forecast"]
    t_s: float
    at_s: int
    target_asset_id: str
    anchor: str
    center_x_m: float
    center_y_m: float
    radius_m: float
    path: list[tuple[float, float]]
    roads: list[str]
    analogs: list[Analog]


class Clue(Strict):
    type: Literal["vehicle", "road"]
    value: str
    start: int  # text[start:end] is the phrase as written
    end: int
    links: list[str]
    linked: bool


class RecalledReport(Strict):
    rank: int
    report_id: str
    incident_id: str
    source: str
    source_grade: str
    event_ts_ms: int
    report_ts_ms: int
    event_ts: str
    x_m: float
    y_m: float
    text: str
    score: float
    clues: list[Clue]


class RecallMatch(Strict):
    incident_id: str
    track_id: str
    installation_id: str
    match_rank: int
    match_score: float
    where: str
    reports: list[RecalledReport]


class RecallMsg(Strict):
    type: Literal["recall"]
    t_s: float
    query_text: str
    zone_roads: list[str]
    matches: list[RecallMatch]


class LedgerMsg(Strict):
    type: Literal["ledger"]
    seq: int
    event_type: str
    actor: str
    recorded_at: str
    hash: str
    prev_hash: str
    case_id: str | None
    subject_id: str | None


class ErrorMsg(Strict):
    type: Literal["error"]
    message: str
    recoverable: bool


MESSAGE_MODELS = (HelloMsg, ClockMsg, PointMsg, RfMsg, RidMsg, FeaturesMsg, IngestMsg, MatchMsg,
                  DtwMsg, ForecastMsg, RecallMsg, LedgerMsg, ErrorMsg,
                  MatcherTraceMsg)  # fmt: skip
StreamMessage = Annotated[
    HelloMsg
    | ClockMsg
    | PointMsg
    | RfMsg
    | RidMsg
    | FeaturesMsg
    | IngestMsg
    | MatchMsg
    | DtwMsg
    | ForecastMsg
    | RecallMsg
    | LedgerMsg
    | ErrorMsg
    | MatcherTraceMsg,
    Field(discriminator="type"),
]


# --- client → server -------------------------------------------------------------------------
class PlayCmd(Strict):
    type: Literal["play"]


class PauseCmd(Strict):
    type: Literal["pause"]


class SeekCmd(Strict):
    type: Literal["seek"]
    t_s: float


class SpeedCmd(Strict):
    type: Literal["speed"]
    value: Literal[1, 2, 5]


class DtwCmd(Strict):
    type: Literal["dtw"]
    match_track_id: str
    channel: str = "dist_target_m"


ClientMessage = Annotated[PlayCmd | PauseCmd | SeekCmd | SpeedCmd | DtwCmd,
                          Field(discriminator="type")]  # fmt: skip


class StreamSchema(BaseModel):
    """``GET /api/schema/stream``: one message, so OpenAPI includes every stream type."""

    message: StreamMessage
    client: ClientMessage | None = None


# --- REST ------------------------------------------------------------------------------------
class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    live_incidents: list[str]
    matching: bool
    problems: list[str]
    ledger_rows: int
    ledger_head_seq: int | None


class Installation(BaseModel):
    installation_id: str
    name: str
    region_id: str
    utc_offset_hours: int
    origin_x_m: float
    origin_y_m: float
    rotation_deg: float


class Asset(BaseModel):
    asset_id: str
    kind: str
    polygon: list[tuple[float, float]]
    centroid_x_m: float
    centroid_y_m: float


class Road(BaseModel):
    name: str
    lines: list[list[tuple[float, float]]]  # clipped to the scene radius


class Park(BaseModel):
    park_id: str
    name: str
    center_x_m: float
    center_y_m: float
    radius_m: float


class Sensor(BaseModel):
    sensor_id: str
    kind: str
    x_m: float
    y_m: float
    range_m: float
    rate_hz: float | None


class Shadow(BaseModel):
    label: str
    bearing_deg: tuple[float, float]
    beyond_fence_m: float
    below_alt_m: float
    polygons: list[list[tuple[float, float]]]


class Scene(BaseModel):
    """Everything the 3D theater draws for one installation, region-frame meters (D-109)."""

    installation_id: str
    name: str
    region_id: str
    utc_offset_hours: int
    origin_x_m: float
    origin_y_m: float
    rotation_deg: float
    radius_m: float
    fence: list[tuple[float, float]]
    assets: list[Asset]
    roads: list[Road]
    parks: list[Park]
    sensors: list[Sensor]
    radar_shadow: Shadow | None


class IncidentSummary(BaseModel):
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    end_ts: str
    duration_s: float
    n_tracks: int
    is_swarm: bool
    status: str


class MatchResponse(BaseModel):
    incident_id: str
    at: float
    t_s: float | None  # the rerun second used (latest at or before ``at``)
    waiting_for_s: float  # > 0 before min_track_s
    model_version: str | None
    elapsed_ms: float | None
    cached: bool | None
    case_id: str | None
    matches: list[MatchItem]


class LedgerBlock(BaseModel):
    seq: int
    event_type: str
    actor: str
    recorded_at: str
    hash: str
    prev_hash: str
    case_id: str | None
    subject_id: str | None


class LedgerRecord(LedgerBlock):
    predicate: str | None
    object_json: dict[str, Any] | None
    valid_from: str | None
    valid_to: str | None
    source_type: str | None
    source_id: str | None
    source_grade: str | None
    confidence: float | None
    supersedes_seq: int | None


class LedgerVerify(BaseModel):
    intact: bool
    first_broken_seq: int | None
    rows: int
    head_seq: int | None
    head_hash: str | None


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_seq: int
    decision: Literal["approve", "reject"]
    analyst: str = "demo"
    clock: str | None = None  # ISO time with Z or offset (the UI sends its replay time)
    rationale: str = ""


class LinkResponse(BaseModel):
    case_id: str
    proposal_seq: int
    decision: Literal["approve", "reject"]
    block: LedgerBlock


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool = False
    analyst: str = "demo"
    clock: str | None = None


class EvidenceFileLine(BaseModel):
    type: Literal["file"]
    name: str
    bytes: int
    sha256: str
    i: int
    n: int


class EvidenceCheck(BaseModel):
    name: str
    status: Literal["PASS", "FAIL", "SKIP"]
    detail: str


class EvidenceDoneLine(BaseModel):
    type: Literal["done"]
    dir: str
    manifest_sha256: str
    seq: int
    head_seq: int
    signed: bool
    checks: list[EvidenceCheck]
    passed: bool


class EvidenceErrorLine(BaseModel):
    type: Literal["error"]
    message: str


EvidenceLine = Annotated[EvidenceFileLine | EvidenceDoneLine | EvidenceErrorLine,
                         Field(discriminator="type")]  # fmt: skip


class ResetResponse(BaseModel):
    reset: dict[str, int]


class ReseedResponse(BaseModel):
    rows: int
    head_seq: int | None
    head_hash: str | None
    counts: dict[str, int]
