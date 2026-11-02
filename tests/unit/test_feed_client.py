"""The simulator's feed client (D-173): scaled clock, heartbeats to the close, reconnects."""

from __future__ import annotations

import json

import pytest

from kairos_defense.sim.live_feed import FeedClient, FeedError
from kairos_defense.sim.live_scenarios import iso_ms

T0 = 1_788_400_000_000


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


class FakeWs:
    def __init__(self, log: list, fail_after: int | None = None) -> None:
        self.log, self.fail_after, self.sent = log, fail_after, 0
        self.closed = False

    def send(self, text: str) -> None:
        if self.fail_after is not None and self.sent >= self.fail_after:
            raise ConnectionError("dropped")
        self.sent += 1
        self.log.append(json.loads(text))

    def recv(self, timeout=None) -> str:
        frame = self.log[-1]
        det = sum(1 for m in frame if m["type"] != "heartbeat")
        return json.dumps({"type": "ack", "accepted": len(frame), "detections": det,
                           "rejected": []})  # fmt: skip

    def close(self) -> None:
        self.closed = True


def _messages(n: int, step_ms: int = 1000) -> list[tuple[int, dict]]:
    return [(T0 + i * step_ms, {"v": 1, "type": "point", "installation_id": "BRAVO",
                                "ts": iso_ms(T0 + i * step_ms)}) for i in range(n)]  # fmt: skip


def _client(msgs, speed, clock, connect) -> FeedClient:
    return FeedClient("ws://x/ws/ingest", msgs, start_ms=T0, installations=["BRAVO"],
                      idle_close_s=30.0, speed=speed, connect=connect, now=clock.now,
                      sleep=clock.sleep)  # fmt: skip


@pytest.mark.parametrize("speed", [1.0, 50.0])
def test_batches_leave_on_the_scaled_clock(speed) -> None:
    clock, log = FakeClock(), []
    s = _client(_messages(60), speed, clock, lambda url: FakeWs(log)).run()
    assert s.sent == s.accepted == 60 and s.rejected == 0
    sent_at = {}
    for i, frame in enumerate(log):
        for m in frame:
            if m["type"] == "point":
                sent_at[m["ts"]] = i
    # every detection leaves in the first frame whose feed time reached it
    for ms, m in _messages(60):
        frame_feed = T0 + round(sent_at[m["ts"]] * 0.1 * speed * 1000)
        assert frame_feed >= ms
    # feed time per wall second is the speed: 60 s of detections + 32 s to the close
    assert s.wall_s == pytest.approx((59 + 32) / speed, abs=0.11)


def test_heartbeats_continue_until_after_the_idle_close() -> None:
    clock, log = FakeClock(), []
    _client(_messages(10), 50.0, clock, lambda url: FakeWs(log)).run()
    beats = [m for frame in log for m in frame if m["type"] == "heartbeat"]
    assert all(b["rate"] == 50.0 and b["installation_id"] == "BRAVO" for b in beats)
    assert beats[-1]["ts"] == iso_ms(T0 + 9_000 + 32_000)  # last detection + idle 30 s + 2 s
    assert all(frame[-1]["type"] == "heartbeat" for frame in log)


def test_reconnect_resends_the_unacknowledged_frame() -> None:
    clock, log, conns = FakeClock(), [], []

    def connect(url):
        ws = FakeWs(log, fail_after=3 if not conns else None)
        conns.append(ws)
        return ws

    s = _client(_messages(20), 50.0, clock, connect).run()
    assert s.reconnects == 1 and len(conns) == 2 and conns[0].closed
    points = [m["ts"] for frame in log for m in frame if m["type"] == "point"]
    assert len(points) == len(set(points)) == 20  # nothing lost, nothing sent twice


def test_unreachable_app_gives_up_after_bounded_retries() -> None:
    clock, tries = FakeClock(), []

    def connect(url):
        tries.append(url)
        raise ConnectionRefusedError("no")

    with pytest.raises(FeedError, match="cannot reach"):
        _client(_messages(5), 1.0, clock, connect).run()
    assert len(tries) == 6


def test_stop_ends_cleanly() -> None:
    clock, log = FakeClock(), []
    c = _client(_messages(600), 1.0, clock, lambda url: FakeWs(log))
    orig = clock.sleep

    def sleep(s):
        orig(s)
        if clock.t > 2.0:
            c.stop()

    c._sleep = sleep
    s = c.run()
    assert s.stopped and s.sent < 600


def test_speed_is_bounded() -> None:
    with pytest.raises(ValueError, match="speed"):
        FeedClient("ws://x", [], start_ms=T0, installations=["BRAVO"], idle_close_s=30, speed=60)
