"""The live stream's contract (D-184): one example of every live message type validates, the
union is exactly §16.3 plus the three live types, and OpenAPI carries it."""

from __future__ import annotations

import typing

import pytest
from pydantic import TypeAdapter

from kairos_defense.api.schemas_ingest import IngestMessage
from kairos_defense.api.schemas_live import LIVE_MESSAGE_MODELS, LiveStreamMessage
from tests.unit.test_api_contract import EXAMPLES, TYPES

LIVE = TypeAdapter(LiveStreamMessage)
LIVE_TYPES = {"incident_opened", "incident_closed", "swarm_match"}
LIVE_EXAMPLES = {
    "incident_opened": {"type": "incident_opened", "incident_id": "LIVE-BRAVO-260901-210136",
                        "installation_id": "BRAVO", "start_ts": "2026-09-02T02:01:36.000Z"},
    "incident_closed": {"type": "incident_closed", "incident_id": "LIVE-BRAVO-260901-210136",
                        "installation_id": "BRAVO", "end_ts": "2026-09-02T02:12:59.000Z",
                        "duration_s": 683.0, "n_tracks": 1, "is_swarm": False, "reruns": 111,
                        "learned_tracks": 1},
    "swarm_match": {"type": "swarm_match", "t_s": 300.0, "incident_id": "LIVE-GOLF-260902-200005",
                    "model_version": "swarm-dtw-v1", "elapsed_ms": 210.0, "n_drones": 5,
                    "detected": True, "matches": [{
                        "rank": 1, "incident_id": "S1-GOLF-260503", "installation_id": "GOLF",
                        "region_id": "DESERT", "start_ts": "2026-05-04T03:10:00Z", "n_drones": 5,
                        "duration_s": 400.0, "distance": 0.4, "similarity": 0.71,
                        "warp_ratio": 1.05, "matched_s": 280}]},
}  # fmt: skip


def test_every_live_message_type_has_a_valid_example() -> None:
    replay = {k: {"type": k, **v} for k, v in EXAMPLES.items()}  # its examples omit the type
    for kind, doc in {**replay, **LIVE_EXAMPLES}.items():
        assert LIVE.validate_python(doc).type == kind


def test_the_live_union_is_16_3_plus_the_live_types() -> None:
    (union, _) = typing.get_args(LiveStreamMessage)
    kinds = {typing.get_args(m.model_fields["type"].annotation)[0]
             for m in typing.get_args(union)}  # fmt: skip
    assert kinds == TYPES | LIVE_TYPES and len(LIVE_MESSAGE_MODELS) == 17


@pytest.mark.parametrize(
    "bad",
    [
        {**LIVE_EXAMPLES["incident_closed"], "actor_id": "P1"},
        {"type": "incident_opened", "incident_id": "X"},
    ],
)
def test_live_messages_refuse_extra_or_missing_fields(bad) -> None:
    with pytest.raises(ValueError):
        LIVE.validate_python(bad)


def test_ingest_messages_validate() -> None:
    a = TypeAdapter(IngestMessage)
    for kind in ("point", "rf", "rid", "heartbeat"):
        from tests.unit import test_ingest_schema as t

        msg = {"point": t.point, "rf": t.rf, "rid": t.rid, "heartbeat": t.beat}[kind]()
        assert a.validate_python(msg).type == kind


def test_openapi_has_the_live_schema_route() -> None:
    from kairos_defense.api.app import create_app

    doc = create_app().openapi()
    assert "/api/schema/live-stream" in doc["paths"]
    names = set(doc["components"]["schemas"])
    assert {
        "IncidentOpenedMsg",
        "IncidentClosedMsg",
        "SwarmMatchMsg",
        "IngestPoint",
        "IngestHeartbeat",
        "RevealResponse",
        "LiveStatus",
    } <= names
