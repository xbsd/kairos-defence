"""The ingest contract v1 (D-173): schema checks here, the app's own checks in the hub."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from kairos_defense.api.routes_live import ingest_batch
from kairos_defense.api.schemas_ingest import IngestMessage

ADAPTER = TypeAdapter(IngestMessage)
TS = "2026-09-02T02:00:00.000Z"


def point(**kw) -> dict:
    return {"v": 1, "type": "point", "installation_id": "BRAVO", "sensor_id": "BRAVO-RADAR-1",
            "sensor_track_id": "TRK-1", "ts": TS, "x_m": 10.0, "y_m": -20.0, "alt_m": 100.0,
            "quality": 0.9, **kw}  # fmt: skip


def rf(**kw) -> dict:
    return {"v": 1, "type": "rf", "installation_id": "BRAVO", "sensor_id": "BRAVO-RF-1",
            "ts": TS, "band": "2.4GHz", "protocol_family": "FAM-07", "bearing_deg": 312.5,
            "snr_db": 21.0, **kw}  # fmt: skip


def rid(**kw) -> dict:
    return {"v": 1, "type": "rid", "installation_id": "BRAVO", "ts": TS, "serial": "SN-1",
            "drone_x_m": 1.0, "drone_y_m": 2.0, "op_x_m": 3.0, "op_y_m": 4.0, **kw}  # fmt: skip


def beat(**kw) -> dict:
    return {"v": 1, "type": "heartbeat", "installation_id": "BRAVO", "ts": TS, "rate": 5, **kw}


@pytest.mark.parametrize(
    "msg", [point(), rf(), rid(), beat(), {**beat(), "ts": "2026-09-01T21:00:00-05:00"}]
)
def test_valid_messages_are_accepted(msg) -> None:
    row = ADAPTER.validate_python(msg).row()
    assert row["ts"] == datetime(2026, 9, 2, 2, 0) and row["ts"].tzinfo is None


@pytest.mark.parametrize(("msg", "match"), [
    ({**point(), "type": "sonar"}, "tag"),
    ({k: v for k, v in point().items() if k != "sensor_track_id"}, "sensor_track_id"),
    (point(ts="2026-09-02T02:00:00"), "time zone"),
    (point(v=2), "v"),
    (point(x_m=float("nan")), "finite"),
    (point(quality=1.5), "quality"),
    (rf(bearing_deg=360.0), "bearing_deg"),
    (point(actor="P1"), "actor"),  # no message may carry who flew (extra fields refused)
    (point(sensor_track_id="bad id!"), "sensor_track_id"),
])  # fmt: skip
def test_schema_rejects_with_a_reason(msg, match) -> None:
    with pytest.raises(ValidationError, match=match):
        ADAPTER.validate_python(msg)


class FakeHub:
    """Records what reaches the hub and refuses one message (the app's own checks)."""

    def __init__(self) -> None:
        self.got = []

    def ingest(self, rows):
        self.got = rows
        bad = [{"index": i, "reason": "late"} for i, r in enumerate(rows) if r.get("serial")]
        n = len(rows) - len(bad)
        det = sum(1 for r in rows if r["type"] != "heartbeat") - len(bad)
        return {"accepted": n, "detections": det, "rejected": bad}


def test_batch_keeps_the_original_indexes() -> None:
    live = type("Live", (), {"hub": FakeHub()})()
    ack = ingest_batch(live, [point(), {"type": "sonar"}, rid(), beat(), point(quality=-1)])
    assert ack["accepted"] == 2 and ack["detections"] == 1
    assert [r["index"] for r in ack["rejected"]] == [1, 2, 4]
    assert ack["rejected"][1]["reason"] == "late"
    assert [r["type"] for r in live.hub.got] == ["point", "rid", "heartbeat"]
