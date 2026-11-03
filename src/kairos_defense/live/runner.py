"""The live worker (D-175, D-176, D-181): reruns and closes, one at a time, never skipped.

``LiveWorker`` is one thread draining a FIFO of the hub's tasks (or, with ``threaded=False``,
running each task as it is submitted: the tests). ``LiveCompute.handle`` does the work:

- ``RerunTask`` on a single-track incident: the query from the points received up to the rerun
  second (``match.query.query_at``, rule 3), then the replay's own ``compute_result`` (the
  ``DtwMatcher`` over history plus learned live history, the §13 forecast, §12 recall and the
  lens), the matches recorded in ``live_results``, proposals into the case memory as for the
  demo (``session.result_messages``, rule 8), and the stream messages handed to the hub.
- ``RerunTask`` on a swarm incident: the §14 swarm matcher on the received drones
  (``SwarmMatcher.match_flight``) and a ``swarm_match`` message; swarms propose nothing.
- ``CloseTask``: learn the incident (``learn.learn_incident``), then tell the hub it is closed.

Every rerun is computed whatever the feed speed, so the recorded results are identical at speed 1
and 50. At high speed the worker computes the newest rerun first (streamed and proposed: the
screen stays current) and backfills the skipped ones afterwards (recorded only); ``pending`` says
how many tasks wait.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import timedelta

from kairos_defense.features.swarm_features import build_flight
from kairos_defense.live.feed import CloseTask, RerunTask
from kairos_defense.live.learn import learn_incident
from kairos_defense.live.loop import compute_result
from kairos_defense.live.session import result_messages
from kairos_defense.match.query import query_at

log = logging.getLogger(__name__)
SWARM_K = 5


def compact(matches: list[dict]) -> list[dict]:
    """What ``live_results`` keeps of each shown match."""
    keep = ("rank", "track_id", "incident_id", "installation_id", "start_ts", "score",
            "shape_sim", "similarity", "distance")  # fmt: skip
    return [{k: m[k] for k in keep if k in m} for m in matches]


class LiveCompute:
    """What a task needs. ``store``/``vectors``: the composite ports (history plus learned live
    history, read on the worker's own cursor); ``feed``: the live-mode store (``LiveFeed``);
    ``live_vectors``: the live-mode LanceDB; ``lock``: the main store lock (as replays hold it)."""

    def __init__(self, hub, *, store, matcher, recall, swarm_matcher, feed, context, live_vectors,
                 memory, model, scoring, sites, offsets, lock) -> None:  # fmt: skip
        self.hub, self.store, self.matcher, self.recall = hub, store, matcher, recall
        self.swarm_matcher, self.feed, self.context = swarm_matcher, feed, context
        self.live_vectors, self.memory, self.model = live_vectors, memory, model
        self.scoring, self.sites, self.offsets, self.lock = scoring, sites, offsets, lock
        self._hashes: dict[str, dict[str, str]] = {}

    def handle(self, task, fresh: bool = True) -> None:
        """Run one task; a backfilled rerun (``fresh=False``) is recorded, not streamed or
        proposed (its moment has passed on screen)."""
        try:
            if isinstance(task, RerunTask):
                msgs = self.rerun(task, fresh)
                self.hub.result(task.meta["incident_id"], msgs)
            elif isinstance(task, CloseTask):
                self.hub.closed(task.meta["incident_id"], self.close(task))
        except Exception:
            log.exception("live task failed: %s", type(task).__name__)
            if isinstance(task, CloseTask):  # an incident must not stay open forever
                self.hub.closed(task.meta["incident_id"], {"learned_tracks": 0})

    # --- reruns -------------------------------------------------------------------------------
    def rerun(self, task: RerunTask, fresh: bool = True) -> list[dict]:
        meta, r = task.meta, round(task.t_s)
        if meta["is_swarm"]:
            msgs = self._swarm(task)
            return msgs if fresh else []
        if self.matcher is None:
            return []
        first = meta["tracks"][0]
        pts = task.points[task.points["track_id"] == first].reset_index(drop=True)
        if len(pts) < 2:
            return []
        site = self.sites[meta["installation_id"]]
        ids = {"track_id": first, "incident_id": meta["incident_id"]}
        try:
            with self.lock:
                res = compute_result(
                    r, lambda: query_at(pts, site, r, self.scoring, ids), store=self.store,
                    matcher=self.matcher, recall=self.recall, scoring=self.scoring,
                    offsets=self.offsets, incident_id=meta["incident_id"])  # fmt: skip
        except ValueError as exc:  # too few seconds to describe yet
            log.info("rerun %s T+%s skipped: %s", meta["incident_id"], r, exc)
            return []
        at = meta["start_ts"] + timedelta(seconds=r)
        self.feed.add_result({"incident_id": meta["incident_id"], "track_id": first, "t_s": r,
                              "kind": "track", "computed_ts": at,
                              "model_version": res["model_version"],
                              "elapsed_ms": float(res["elapsed_ms"]),
                              "matches": compact(res["matches"])})  # fmt: skip
        if not fresh:
            return []
        record = {k: meta[k] for k in ("incident_id", "installation_id", "region_id", "start_ts",
                                       "n_tracks", "is_swarm")}  # fmt: skip
        hashes = self._hashes.setdefault(meta["incident_id"], {})
        return result_messages(res, r, at, record, memory=self.memory, model=self.model,
                               offsets=self.offsets, hashes=hashes)  # fmt: skip

    def _swarm(self, task: RerunTask) -> list[dict]:
        meta, r = task.meta, round(task.t_s)
        if self.swarm_matcher is None:
            return []
        cols = ["track_id", "ts", "x_m", "y_m", "alt_m", "quality"]
        pts = task.points[cols].sort_values(["track_id", "ts"], kind="stable")
        site = self.sites[meta["installation_id"]]
        t0 = time.perf_counter()
        try:
            flight = build_flight(meta, pts.reset_index(drop=True), site, self.scoring)
            with self.lock:
                res = self.swarm_matcher.match_flight(flight, SWARM_K, t0)
        except ValueError as exc:
            log.info("swarm rerun %s T+%s skipped: %s", meta["incident_id"], r, exc)
            return []
        matches = [m.to_dict() for m in res.matches]
        at = meta["start_ts"] + timedelta(seconds=r)
        elapsed = float(res.timings.get("total_ms", (time.perf_counter() - t0) * 1e3))
        self.feed.add_result({"incident_id": meta["incident_id"], "track_id": None, "t_s": r,
                              "kind": "swarm", "computed_ts": at,
                              "model_version": self.swarm_matcher.model_version,
                              "elapsed_ms": elapsed, "matches": compact(matches)})  # fmt: skip
        return [{"type": "swarm_match", "t_s": float(r), "incident_id": meta["incident_id"],
                 "model_version": self.swarm_matcher.model_version, "elapsed_ms": elapsed,
                 "n_drones": int(flight.n_drones), "detected": bool(flight.is_swarm),
                 "matches": matches}]  # fmt: skip

    # --- close --------------------------------------------------------------------------------
    def close(self, task: CloseTask) -> dict:
        meta = task.meta
        site = self.sites[meta["installation_id"]]
        learned = learn_incident(meta["incident_id"], task.points, site, self.context, self.feed,
                                 self.live_vectors, self.scoring)  # fmt: skip
        self._hashes.pop(meta["incident_id"], None)
        return {"learned_tracks": len(learned.tracks), "windows": learned.windows}


class LiveWorker:
    """The live work queue on one thread (``threaded=False``: run on submit, for tests).

    Closes first, then fresh, then backfill (D-175): a closing incident's remaining reruns and
    then its learning run before anything else, so every incident that starts after it closed is
    matched with it learned (as at speed 1). Otherwise the next task is the newest rerun of the
    newest incident when it is newer than anything computed for that incident (``fresh``: its
    result is streamed and proposed), else the oldest skipped rerun (backfill: recorded only). So
    the screen shows the latest second's result and every rerun is still computed and recorded
    whatever the feed speed."""

    def __init__(self, handle: Callable[[object, bool], None], *, threaded: bool = True) -> None:
        self.handle, self.threaded = handle, threaded
        self._pending: list = []
        self._fresh: dict[str, float] = {}  # incident -> newest rerun second computed fresh
        self._busy = 0
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.threaded and self._thread is None:
            self._thread = threading.Thread(target=self._run, name="live-worker", daemon=True)
            self._thread.start()

    def submit(self, task) -> None:
        if not self.threaded:
            self.handle(task, True)
            return
        with self._cond:
            self._pending.append(task)
            self._cond.notify()

    def _next(self):
        reruns = [t for t in self._pending if isinstance(t, RerunTask)]
        closes = [t for t in self._pending if isinstance(t, CloseTask)]
        if closes:  # a closing incident finishes (its reruns, then learning) before any other
            iid = closes[0].meta["incident_id"]
            own = [t for t in reruns if t.meta["incident_id"] == iid]
            if not own:
                self._pending.remove(closes[0])
                return closes[0], False
            reruns = own
        if reruns:
            newest = max(reruns, key=lambda t: (t.meta["start_ts"], t.t_s))
            iid = newest.meta["incident_id"]
            if newest.t_s > self._fresh.get(iid, -1.0):
                self._fresh[iid] = newest.t_s
                self._pending.remove(newest)
                return newest, True
            self._pending.remove(reruns[0])
            return reruns[0], False
        return (self._pending.pop(0), False) if self._pending else None

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._cond:
                nxt = self._next()
                if nxt is None:
                    self._cond.wait(0.2)
                    continue
                self._busy += 1
            try:
                self.handle(*nxt)
            finally:
                with self._cond:
                    self._busy -= 1

    def pending(self) -> int:
        with self._cond:
            return len(self._pending) + self._busy

    def clear(self) -> int:
        """Drop the queued tasks (``live reset``); returns how many."""
        with self._cond:
            n = len(self._pending)
            self._pending.clear()
            self._fresh.clear()
            return n

    def wait_idle(self, timeout: float = 60.0) -> bool:
        end = time.monotonic() + timeout
        while self.pending() and time.monotonic() < end:
            time.sleep(0.05)
        return self.pending() == 0

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
