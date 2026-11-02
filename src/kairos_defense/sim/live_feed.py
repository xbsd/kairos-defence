"""The simulator's sensor feed (D-169, D-173): detections to the app's ingest WebSocket.

``FeedClient`` replays a scenario's time-ordered ingest messages on the live clock: feed time
advances ``speed`` times as fast as wall time from the first launch, and every tick (0.1 s of wall
time) sends one JSON array frame holding the messages that became due plus a ``heartbeat`` for
each installation in the scenario (feed time and rate), then reads the app's ``ack``. Heartbeats
continue until feed time passes the last detection by ``idle_close_s`` plus a margin, so the app
closes the last incident on its own clock. A dropped connection reconnects with backoff and
resends the unacknowledged frame; ``stop()`` (or SIGINT and SIGTERM in the CLI) ends cleanly. The
transport is injectable (``connect``), so tests need no server.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from kairos_defense.sim.live_scenarios import iso_ms

try:  # the real transport's "connection closed" errors; tests inject their own transport
    from websockets.exceptions import ConnectionClosed, InvalidHandshake
except ImportError:  # pragma: no cover - websockets ships with uvicorn[standard]
    ConnectionClosed = InvalidHandshake = ConnectionError  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)
DROPPED = (OSError, EOFError, TimeoutError, ConnectionError, ConnectionClosed)

TICK_S = 0.1
CLOSE_MARGIN_S = 2.0
BACKOFF_S = (0.5, 1.0, 2.0, 4.0, 8.0)
SPEED_RANGE = (1.0, 50.0)


class FeedError(RuntimeError):
    """The app could not be reached (after every retry) or refused the feed."""


@dataclass
class FeedSummary:
    sent: int = 0  # detections sent
    accepted: int = 0  # detections the app accepted (heartbeats not counted)
    rejected: int = 0
    frames: int = 0
    reconnects: int = 0
    reasons: list[str] = field(default_factory=list)  # the first few rejection reasons
    wall_s: float = 0.0
    feed_s: float = 0.0
    stopped: bool = False


def websocket_connect(url: str):
    """The real transport: a synchronous ``websockets`` client (``send``, ``recv``, ``close``)."""
    from websockets.sync.client import connect

    return connect(url, open_timeout=10, close_timeout=2, max_size=2**22)


class FeedClient:
    """Send ``messages`` (``(utc ms, message)``, time-ordered) to ``url`` at ``speed``."""

    def __init__(self, url: str, messages: Sequence[tuple[int, dict]], *, start_ms: int,
                 installations: Sequence[str], idle_close_s: float, speed: float = 1.0,
                 connect: Callable[[str], object] = websocket_connect,
                 now: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 tick_s: float = TICK_S) -> None:  # fmt: skip
        if not SPEED_RANGE[0] <= float(speed) <= SPEED_RANGE[1]:
            raise ValueError(f"speed must be in [1, 50], not {speed!r}")
        self.url, self.messages, self.speed = url, list(messages), float(speed)
        self.start_ms, self.installations = int(start_ms), list(installations)
        last = self.messages[-1][0] if self.messages else self.start_ms
        self.end_ms = last + round((idle_close_s + CLOSE_MARGIN_S) * 1000)
        self._connect, self._now, self._sleep, self.tick_s = connect, now, sleep, tick_s
        self._ws = None
        self._connected = False  # once connected, a later connect is a reconnect
        self._stop = False
        self.summary = FeedSummary()

    def stop(self) -> None:
        self._stop = True

    # --- transport --------------------------------------------------------------------------
    def _open(self) -> None:
        for wait in (0.0, *BACKOFF_S):
            if self._stop:
                return
            if wait:
                self._sleep(wait)
            try:
                self._ws = self._connect(self.url)
                if self._connected:
                    self.summary.reconnects += 1
                self._connected = True
                return
            except (*DROPPED, InvalidHandshake) as exc:  # refused, reset, timed out
                log.warning("feed: cannot reach %s (%s)", self.url, exc)
        raise FeedError(f"cannot reach the app at {self.url} after {len(BACKOFF_S) + 1} tries")

    def _send(self, frame: list[dict]) -> dict:
        """Send one frame and wait for its ack; reconnect and resend on a dropped connection."""
        text = json.dumps(frame, separators=(",", ":"), allow_nan=False)
        for _ in range(len(BACKOFF_S) + 1):
            if self._ws is None:
                self._open()
                if self._ws is None:  # stopped while reconnecting
                    return {}
            try:
                self._ws.send(text)
                return json.loads(self._ws.recv(timeout=30))
            except DROPPED as exc:
                log.warning("feed: connection lost (%s); reconnecting", exc)
                self._drop()
        raise FeedError(f"the app at {self.url} keeps dropping the connection")

    def _drop(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:  # already gone
                log.debug("feed: close failed", exc_info=True)

    # --- the run ------------------------------------------------------------------------------
    def heartbeats(self, feed_ms: int) -> list[dict]:
        return [{"v": 1, "type": "heartbeat", "installation_id": inst, "ts": iso_ms(feed_ms),
                 "rate": self.speed} for inst in self.installations]  # fmt: skip

    def run(self) -> FeedSummary:
        """Send everything on the scaled clock; returns what happened."""
        s = self.summary
        wall0 = self._now()
        i = 0
        try:
            self._open()
            while not self._stop:
                feed_ms = self.start_ms + round((self._now() - wall0) * self.speed * 1000)
                feed_ms = min(feed_ms, self.end_ms)
                j = i
                while j < len(self.messages) and self.messages[j][0] <= feed_ms:
                    j += 1
                frame = [m for _, m in self.messages[i:j]] + self.heartbeats(feed_ms)
                ack = self._send(frame)
                if self._stop and not ack:
                    break
                s.frames += 1
                s.sent += j - i
                s.accepted += int(ack.get("detections", 0))
                rej = ack.get("rejected") or []
                s.rejected += len(rej)
                s.reasons += [str(r.get("reason")) for r in rej][: max(0, 5 - len(s.reasons))]
                i = j
                if feed_ms >= self.end_ms:
                    break
                self._sleep(self.tick_s)
        finally:
            s.stopped = self._stop
            s.wall_s = self._now() - wall0
            s.feed_s = s.wall_s * self.speed
            self._drop()
        return s
