"""Models of live mode's stream and routes (D-170, D-182 to D-184).

``LiveStreamMessage`` is what ``WS /ws/live/{installation_id}`` sends: the thirteen §16.3 types
the Live watch components already understand (``hello`` per incident, ``clock`` on feed time …)
plus ``incident_opened``, ``incident_closed`` and ``swarm_match``. The replay's ``StreamMessage``
is unchanged. ``GET /api/schema/live-stream`` exists so OpenAPI (and the web app's generated
types) include every live type and the ingest messages.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from kairos_defense.api.schemas import (
    MESSAGE_MODELS,
    ClockMsg,
    DtwMsg,
    ErrorMsg,
    FeaturesMsg,
    ForecastMsg,
    HelloMsg,
    IngestMsg,
    LedgerMsg,
    MatcherTraceMsg,
    MatchMsg,
    Num,
    PointMsg,
    RecallMsg,
    RfMsg,
    RidMsg,
    Strict,
)
from kairos_defense.api.schemas_ingest import IngestMessage


class IncidentOpenedMsg(Strict):
    type: Literal["incident_opened"]
    incident_id: str
    installation_id: str
    start_ts: str


class IncidentClosedMsg(Strict):
    type: Literal["incident_closed"]
    incident_id: str
    installation_id: str
    end_ts: str
    duration_s: float
    n_tracks: int
    is_swarm: bool
    reruns: int
    learned_tracks: int  # tracks added to the live history (D-176)


class SwarmMatchItem(Strict):
    rank: int
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: str
    n_drones: int
    duration_s: float
    distance: float
    similarity: float
    warp_ratio: float
    matched_s: int


class SwarmMatchMsg(Strict):
    """A live swarm's rerun: the §14 swarm matcher on the drones received so far."""

    type: Literal["swarm_match"]
    t_s: float
    incident_id: str
    model_version: str
    elapsed_ms: float
    n_drones: int
    detected: bool  # passes the §14 swarm detection
    matches: list[SwarmMatchItem]


LIVE_MESSAGE_MODELS = (*MESSAGE_MODELS, IncidentOpenedMsg, IncidentClosedMsg, SwarmMatchMsg)
LiveStreamMessage = Annotated[
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
    | MatcherTraceMsg
    | IncidentOpenedMsg
    | IncidentClosedMsg
    | SwarmMatchMsg,
    Field(discriminator="type"),
]


class LiveStreamSchema(Strict):
    message: LiveStreamMessage
    ingest: IngestMessage


# --- REST -------------------------------------------------------------------------------------
class ScenarioActor(Strict):
    id: str
    nickname: str
    bases: list[str]


class ScenarioInfo(Strict):
    name: str
    title: str
    actor_label: str | None
    actors: list[ScenarioActor]
    default_actor: str | None
    allow_random: bool
    bases: list[str]
    second_base: bool
    expectation: str


class LiveIncidentRow(Strict):
    incident_id: str
    installation_id: str
    start_ts: str
    end_ts: str
    n_tracks: int
    is_swarm: bool
    state: Literal["open", "closing", "closed"]
    reruns: int


class SimulatorState(Strict):
    running: bool
    scenario: str | None
    base: str | None
    second_base: str | None
    speed: float | None
    seed: int | None
    started_at: str | None
    exit_code: int | None


class FeedState(Strict):
    installation_id: str
    feed_ts: str | None
    rate: float
    active: bool


class LiveStatus(Strict):
    enabled: bool
    matching: bool
    problems: list[str]
    feeds: list[FeedState]
    incidents: list[LiveIncidentRow]
    pending: int  # worker tasks waiting or running (D-175)
    learned_tracks: int
    simulator: SimulatorState


class SimLaunchRequest(Strict):
    scenario: str
    actor: str | None = None
    base: str | None = None
    second_base: str | None = None
    speed: Annotated[float, Field(ge=1, le=50)] = 1.0
    seed: Annotated[int, Field(ge=1, lt=2**31)] | None = None


class SimLaunchResponse(Strict):
    launched: bool
    scenario: str
    base: str
    second_base: str | None
    speed: float
    seed: int
    pid: int


class LiveResetResponse(Strict):
    reset: dict[str, int]
    vectors: int
    stopped_simulator: bool


class RevealRerun(Strict):
    t_s: int
    kind: str
    first_same_rank: int | None
    mimic_rank: int | None
    top_incident: str | None
    top_track: str | None
    top_actor: str | None
    top_score: Num


class RevealExpectation(Strict):
    text: str
    met: bool | None
    observed: str


class RevealResponse(Strict):
    """Who flew a closed live incident (D-170): served through ``kairos_defense.eval``, never
    stored."""

    incident_id: str
    installation_id: str
    start_ts: str
    n_tracks: int
    is_swarm: bool
    known: bool
    actor_id: str | None
    actor_type: str | None
    nickname: str | None
    scenario: str | None
    seed: int | None
    flight: int | None
    base: str | None
    mimics: str | None = None
    reruns: list[RevealRerun]
    same_actor_history: int
    expectation: RevealExpectation
    words: str
