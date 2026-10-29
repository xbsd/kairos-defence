"""Ledger fan-out (SPEC §16.2, D-107): every ledger append reaches every open replay session.

``PublishingMemory`` wraps a ``CaseMemory`` adapter: after each successful append it publishes the
new rows to a ``Broadcaster``, whose per-session ``Feed`` queues are drained by the sessions into
``ledger`` messages. The wrapped adapter can be swapped (``replace``) for a reseed, under the same
lock that every append holds, so no write lands in a file being replaced.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from collections.abc import Sequence
from datetime import datetime

from kairos_defense.ports import CaseSnapshot


class Feed:
    """One subscriber's queue of appended ledger rows."""

    def __init__(self, owner: Broadcaster, key: int) -> None:
        self._owner, self._key = owner, key
        self._q: deque[dict] = deque()
        self._lock = threading.Lock()

    def push(self, rows: Sequence[dict]) -> None:
        with self._lock:
            self._q.extend(rows)

    def drain(self) -> list[dict]:
        with self._lock:
            out = list(self._q)
            self._q.clear()
        return out

    def close(self) -> None:
        self._owner.unsubscribe(self._key)


class Broadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[int, Feed] = {}
        self._ids = itertools.count(1)

    def subscribe(self) -> Feed:
        with self._lock:
            key = next(self._ids)
            feed = self._subs[key] = Feed(self, key)
        return feed

    def unsubscribe(self, key: int) -> None:
        with self._lock:
            self._subs.pop(key, None)

    def publish(self, rows: Sequence[dict]) -> None:
        with self._lock:
            subs = list(self._subs.values())
        for f in subs:
            f.push(rows)

    @property
    def subscribers(self) -> int:
        with self._lock:
            return len(self._subs)


class PublishingMemory:
    """A ``CaseMemory`` (the port's methods, plus ``head``, ``count``, ``rows_for_seqs``) that
    publishes appended rows; reads and writes go to ``inner`` under ``lock``."""

    def __init__(self, inner, broadcaster: Broadcaster, lock: threading.RLock | None = None):
        self.inner, self.broadcaster = inner, broadcaster
        self.lock = lock or threading.RLock()

    def replace(self, inner) -> None:
        with self.lock:
            self.inner = inner

    def append(self, event: dict) -> int:
        return self.append_many([event])[0]

    def append_many(self, events: Sequence[dict]) -> list[int]:
        with self.lock:
            seqs = self.inner.append_many(events)
            rows = self.inner.rows_for_seqs(seqs) if seqs else []
        if rows:
            self.broadcaster.publish(rows)
        return seqs

    def events(self, after: datetime | None = None, until: datetime | None = None) -> list[dict]:
        with self.lock:
            return self.inner.events(after, until)

    def as_of(self, case_id: str, t: datetime) -> CaseSnapshot:
        with self.lock:
            return self.inner.as_of(case_id, t)

    def diff(self, case_id: str, t1: datetime, t2: datetime) -> list[dict]:
        with self.lock:
            return self.inner.diff(case_id, t1, t2)

    def verify_chain(self) -> int | None:
        with self.lock:
            return self.inner.verify_chain()

    def head(self):
        with self.lock:
            return self.inner.head()

    def count(self) -> int:
        with self.lock:
            return self.inner.count()

    def rows_for_seqs(self, seqs: Sequence[int]) -> list[dict]:
        with self.lock:
            return self.inner.rows_for_seqs(seqs)
