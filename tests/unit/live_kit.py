"""Helpers for the live-mode tests: a live-mode ``Services`` on the P1 nights and a feeder that
plays a simulated scenario into the hub in frames of feed time (no real-time waiting)."""

from __future__ import annotations

from pydantic import TypeAdapter

from kairos_defense.api.schemas_ingest import IngestMessage
from kairos_defense.sim import live_scenarios as ls

_ADAPTER = TypeAdapter(IngestMessage)


def fast_scoring(cfg, every_s: float = 20.0):
    """``cfg`` with reruns every ``every_s`` seconds (fewer reruns: the tests stay fast)."""
    live = cfg.scoring.live.model_copy(update={"rerun_every_s": every_s})
    return cfg.model_copy(update={"scoring": cfg.scoring.model_copy(update={"live": live})})


def rows(msgs):
    return [_ADAPTER.validate_python(m).row() for m in msgs]


def feed(hub, sc, frame_s: float = 1.0, idle_close_s: float = 30.0) -> list[dict]:
    """Play ``sc``'s detections into ``hub`` in frames of ``frame_s`` feed seconds, with a
    heartbeat per base each frame, until the last detection plus ``idle_close_s`` + 2 s.
    Returns the acks."""
    det = sc.detections()
    end = (det[-1][0] if det else sc.start_ms) + round((idle_close_s + 2) * 1000)
    acks, i, t = [], 0, sc.start_ms
    step = round(frame_s * 1000)
    while True:
        t = min(t + step, end)
        j = i
        while j < len(det) and det[j][0] <= t:
            j += 1
        beats = [{"v": 1, "type": "heartbeat", "installation_id": b, "ts": ls.iso_ms(t),
                  "rate": 1.0} for b in sc.bases]  # fmt: skip
        acks.append(hub.ingest(rows([m for _, m in det[i:j]] + beats)))
        i = j
        if t >= end:
            return acks
