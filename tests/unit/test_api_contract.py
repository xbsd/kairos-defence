"""SPEC §16.5: the stream contract. One example of every message type validates; the union is
exactly the §16.3 table; the committed OpenAPI file is current."""

from __future__ import annotations

import json
import math
import typing

import pytest
from pydantic import TypeAdapter, ValidationError

from kairos_defense.api.app import create_app
from kairos_defense.api.schemas import MESSAGE_MODELS, ClientMessage, StreamMessage
from kairos_defense.api.stream import encode

TYPES_16_3 = {"hello", "clock", "point", "rf", "rid", "features", "ingest", "match", "dtw",
              "forecast", "recall", "ledger", "error"}  # fmt: skip
TA = TypeAdapter(StreamMessage)
LENS = {"match_track_id": "P1-DELTA-260419-T1", "channel": "dist_target_m", "query": [1.0, 2.0],
        "candidate": [1.0, 2.0, 3.0], "path": [[0, 0], [1, 2]], "cost": "AAAA", "shape": [2, 3],
        "band": 2, "dtw_distance": 1.0, "euclid_distance": 2.0, "overlap": 2, "warp_ratio": 1.2,
        "warp_text": "flown 17% slower"}  # fmt: skip
MATCH = {"query_incident_id": "DEMO-BRAVO-0828", "track_id": "P1-DELTA-260419-T1",
         "incident_id": "P1-DELTA-260419", "installation_id": "DELTA",
         "start_ts": "2026-04-20T02:35:00.000Z", "score": 0.94, "shape_sim": 0.8,
         "features": {"shape_sim": 0.8, "rf_match": None}, "reasons": ["same RF family"],
         "warp_ratio": None, "window_offset_s": 12, "model_version": "fusion-v1", "rank": 1,
         "local_start": "2026-04-19T21:35", "proposal_seq": 4682, "decision": None,
         "memory_status": "Closed as hobbyist on Apr 20"}  # fmt: skip
EXAMPLES = {
    "hello": {"incident_id": "DEMO-BRAVO-0828", "installation_id": "BRAVO", "region_id": "COASTAL",
              "start_ts": "2026-08-29T02:40:06.000Z", "duration_s": 515.0, "speed": 1.0,
              "playing": False, "tracks": ["DEMO-BRAVO-0828-T1"], "is_swarm": False,
              "matching": True, "min_track_s": 45.0, "rerun_every_s": 5.0,
              "utc_offset_hours": -5},
    "clock": {"t_s": 62.0, "ts": "2026-08-29T02:41:08.000Z", "speed": 5.0, "playing": True,
              "seeked": False},
    "point": {"incident_id": "DEMO-BRAVO-0828", "track_id": "DEMO-BRAVO-0828-T1",
              "sensor_id": "BRAVO-RADAR-1", "t_s": 3.0, "x_m": 21680.2, "y_m": -4883.9,
              "alt_m": 85.5, "quality": 0.887},
    "rf": {"sensor_id": "BRAVO-RF-1", "t_s": 1.0, "band": "2.4GHz", "bearing_deg": 334.9,
           "protocol_family": "FAM-07", "snr_db": 18.2},
    "rid": {"serial": "RID-1", "t_s": 4.0, "drone_x_m": 1.0, "drone_y_m": 2.0, "op_x_m": None,
            "op_y_m": None},
    "features": {"t_s": 90.0, "track_id": "DEMO-BRAVO-0828-T1",
                 "target_asset_id": "BRAVO-fuel_farm", "speed_ms": 4.7, "alt_m": 93.0,
                 "turn_rate_dps": -26.6, "dist_target_m": 129.0, "vspeed_ms": 0.7,
                 "heading_deg": 206.9, "phase": "loiter"},
    "ingest": {"table": "live_points", "rows": 3, "total_rows": 90, "write_ms": 0.4,
               "statement": "INSERT INTO live_points … 3 rows"},
    "match": {"t_s": 90.0, "model_version": "fusion-v1", "elapsed_ms": 286.0, "cached": True,
              "case_id": "CASE-P1-DELTA-260419", "query_track": "DEMO-BRAVO-0828-T1",
              "target_asset_id": "BRAVO-fuel_farm", "matches": [MATCH]},
    "dtw": {"t_s": 90.0, **LENS},
    "forecast": {"t_s": 105.0, "at_s": 105, "target_asset_id": "BRAVO-fuel_farm",
                 "anchor": "match_kind", "center_x_m": 21000.0, "center_y_m": -4300.0,
                 "radius_m": 370.0, "path": [[1.0, 2.0], [3.0, 4.0]], "roads": ["County Rd 12"],
                 "analogs": [{"incident_id": "P1-DELTA-260419", "track_id": "P1-DELTA-260419-T1",
                              "score": 0.9, "target_kind": "fuel_farm",
                              "recovery_rel_m": [-1500.0, 1400.0], "rotation_deg": 5.0,
                              "anchor_asset_id": "BRAVO-fuel_farm", "aligned_t_s": 80,
                              "recovery_x_m": 21000.0, "recovery_y_m": -4300.0,
                              "remainder_points": 200}]},
    "recall": {"t_s": 120.0, "query_text": "white pickup", "zone_roads": ["County Rd 12"],
               "matches": [{"incident_id": "P1-DELTA-260419", "track_id": "P1-DELTA-260419-T1",
                            "installation_id": "DELTA", "match_rank": 1, "match_score": 0.9,
                            "where": "installation_id = 'DELTA'",
                            "reports": [{"rank": 1, "report_id": "R-P1-DELTA-260419-1",
                                         "incident_id": "P1-DELTA-260419",
                                         "source": "security_forces", "source_grade": "B2",
                                         "event_ts_ms": 1, "report_ts_ms": 2,
                                         "event_ts": "2026-04-20T02:20:00.000Z", "x_m": 1.0,
                                         "y_m": 2.0, "text": "white pickup on County Rd 12",
                                         "score": 0.03,
                                         "clues": [{"type": "road", "value": "County Rd 12",
                                                    "start": 16, "end": 28, "links": ["x"],
                                                    "linked": True}]}]}]},
    "ledger": {"seq": 4682, "event_type": "match_proposed", "actor": "matcher@fusion-v1",
               "recorded_at": "2026-08-29T02:41:36.000Z", "hash": "a" * 64, "prev_hash": "b" * 64,
               "case_id": "CASE-P1-DELTA-260419", "subject_id": "P1-DELTA-260419"},
    "error": {"message": "speed must be 1, 2 or 5", "recoverable": True},
}  # fmt: skip


def test_every_message_type_has_a_valid_example() -> None:
    assert set(EXAMPLES) == TYPES_16_3
    for kind, body in EXAMPLES.items():
        m = TA.validate_python({"type": kind, **body})
        assert m.type == kind
    with pytest.raises(ValidationError):  # unknown fields are refused (drift is caught)
        TA.validate_python({"type": "error", **EXAMPLES["error"], "extra": 1})
    with pytest.raises(ValidationError):
        TA.validate_python({"type": "telemetry"})


def test_union_covers_exactly_the_16_3_types() -> None:
    members = typing.get_args(typing.get_args(StreamMessage)[0])
    kinds = {typing.get_args(m.model_fields["type"].annotation)[0] for m in members}
    assert kinds == TYPES_16_3 and len(members) == len(MESSAGE_MODELS) == 13


def test_client_messages_validate() -> None:
    ta = TypeAdapter(ClientMessage)
    for m in ({"type": "play"}, {"type": "pause"}, {"type": "seek", "t_s": 60},
              {"type": "speed", "value": 2},
              {"type": "dtw", "match_track_id": "T", "channel": "dist_target_m"}):  # fmt: skip
        assert ta.validate_python(m).type == m["type"]
    with pytest.raises(ValidationError):
        ta.validate_python({"type": "speed", "value": 3})


def test_messages_serialize_without_nan() -> None:
    s = encode({"type": "features", **EXAMPLES["features"], "speed_ms": math.nan}, validate=True)
    assert "NaN" not in s and json.loads(s)["speed_ms"] is None


def test_openapi_json_is_current(root) -> None:
    committed = json.loads((root / "web" / "openapi.json").read_text())
    assert committed == json.loads(json.dumps(create_app().openapi())), (
        "web/openapi.json is stale: run `uv run kairos-defense api --dump-openapi web/openapi.json`"
        " and `npm --prefix web run gen:types`")  # fmt: skip
