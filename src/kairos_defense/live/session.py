"""One replay client's state machine (SPEC §16.1–§16.3, D-105 to D-107, D-118). No web framework
here: the WebSocket endpoint feeds client messages to ``handle`` and calls ``step`` every 100 ms.

``step`` returns, in order: a ``clock`` (10 Hz while playing), the detections that became
visible (``point``, ``rf``, ``rid``), one ``ingest`` per live table written (the real write of
those rows, §16.2), ``features`` for each whole second passed, the result messages when a rerun
second is crossed (``match``, ``forecast``, and ``dtw`` / ``recall`` only when they changed),
then a ``ledger`` message per row appended anywhere (proposals, approvals, exports).

Recording keeps a high-water mark: each detection is written once per session, when the clock
first passes it (a seek forward writes the skipped ones in one batch; a seek back writes
nothing). After a seek or reset the client gets ``clock`` with ``seeked: true`` and a catch-up:
the detections and features of the last 120 s and the current result. Proposals (§15.6) target
the case of the best-ranked top-3 incident that belongs to one (D-106); the swarm encore does
not write to the ledger (D-010).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from kairos_defense.live.loop import LiveLoop
from kairos_defense.live.replay import LiveIncident, ReplayEngine, iso_z
from kairos_defense.memory.actions import (
    json_safe,
    propose_matches,
    record_incident,
    register_model,
)
from kairos_defense.memory.asof import members_at
from kairos_defense.memory.ledger import known_at
from kairos_defense.memory.views import UNATTRIBUTED, incident_statuses, obj
from kairos_defense.ports import LiveSink

CLOCK_HZ = 10.0
CATCH_UP_S = 120.0
CLIENT_TYPES = ("play", "pause", "seek", "speed", "dtw")


def ledger_message(r: Mapping) -> dict:
    return {"type": "ledger", "seq": int(r["seq"]), "event_type": r["event_type"],
            "actor": r["actor"], "recorded_at": iso_z(r["recorded_at"]), "hash": r["hash"],
            "prev_hash": r["prev_hash"], "case_id": r["case_id"],
            "subject_id": r["subject_id"]}  # fmt: skip


def target_case(rows: Sequence[Mapping], top: Sequence[str], at: datetime) -> str | None:
    """The case (as known at ``at``) holding the best-ranked of ``top`` (D-106); ties between
    cases go to the earliest opened. None when no top incident belongs to a case."""
    known = known_at(rows, at)
    cases = [r["case_id"] for r in known if r["event_type"] == "case_opened"]
    members = {c: set(members_at(known, c, at)) for c in cases}
    for inc in top:
        for c in cases:
            if inc in members[c]:
                return c
    return None


def decorate(matches: Sequence[Mapping], rows: Sequence[Mapping], case_id: str | None,
             query_incident: str, at: datetime,
             offsets: Mapping[str, int]) -> list[dict]:  # fmt: skip
    """Add ``proposal_seq``, ``decision`` and ``memory_status`` (§17.8, D-116) to result matches
    from the ledger as known at ``at``."""
    statuses = incident_statuses(list(rows), at, offsets)
    approved = {obj(r).get("proposal_seq") for r in rows if r["event_type"] == "link_approved"}
    rejected = {r["supersedes_seq"] for r in rows if r["event_type"] == "link_rejected"}
    latest: dict[str, int] = {}
    for r in rows:
        if (case_id is not None and r["event_type"] == "match_proposed"
                and r["case_id"] == case_id
                and obj(r).get("query_incident") == query_incident):  # fmt: skip
            latest[r["subject_id"]] = int(r["seq"])
    out = []
    for m in matches:
        seq = latest.get(m["incident_id"])
        decision = ("approved" if seq in approved else "rejected" if seq in rejected
                    else None)  # fmt: skip
        out.append({**m, "proposal_seq": seq, "decision": decision,
                    "memory_status": statuses.get(m["incident_id"], UNATTRIBUTED)})  # fmt: skip
    return out


def _digest(doc: object) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


class Session:
    """One client's replay. ``memory``: a ``CaseMemory`` (``PublishingMemory`` in the API) or
    None; ``feed``: the ledger rows appended anywhere (``Feed.drain``) or None; ``model``:
    ``{"version", "sha256", "file", "validation"}`` for ``model_registered``."""

    def __init__(self, incident: LiveIncident, loop: LiveLoop, *, sink: LiveSink | None = None,
                 memory=None, feed=None, model: Mapping | None = None, speed: float = 1.0,
                 now: Callable[[], float] = time.monotonic) -> None:  # fmt: skip
        self.incident, self.loop, self.sink = incident, loop, sink
        self.memory, self.feed, self.model = memory, feed, model
        self.engine = ReplayEngine(incident, speed, now)
        self._now = now
        self._sent_t = -1.0  # detections sent to the client up to here
        self._mark = -1.0  # detections recorded up to here (never decreases)
        self._feat_s = 0  # features sent up to this whole second
        self._result_t: int | None = None
        self._last_clock: float | None = None
        self._hashes: dict[str, str] = {}

    # --- messages -------------------------------------------------------------------------
    def hello(self) -> dict:
        inc, live = self.incident, self.loop.scoring.live
        return {"type": "hello", "incident_id": inc.incident_id,
                "installation_id": inc.installation_id, "region_id": inc.region_id,
                "start_ts": iso_z(inc.start_ts), "duration_s": inc.duration_s,
                "speed": self.engine.speed, "playing": False, "tracks": list(inc.tracks),
                "is_swarm": inc.is_swarm, "matching": self.loop.matching,
                "min_track_s": float(live.min_track_s),
                "rerun_every_s": float(live.rerun_every_s),
                "utc_offset_hours": inc.utc_offset_hours}  # fmt: skip

    def _clock(self, t: float, seeked: bool = False) -> dict:
        self._last_clock = self._now()
        return {"type": "clock", "t_s": round(t, 3), "ts": iso_z(self.incident.ts_at(t)),
                "speed": self.engine.speed, "playing": self.engine.playing,
                "seeked": seeked}  # fmt: skip

    @staticmethod
    def error(message: str, recoverable: bool = True) -> dict:
        return {"type": "error", "message": message, "recoverable": recoverable}

    # --- client messages ------------------------------------------------------------------
    def handle(self, msg: object) -> list[dict]:
        """Apply one client message; returns the messages to send now."""
        if not isinstance(msg, Mapping) or msg.get("type") not in CLIENT_TYPES:
            kind = msg.get("type") if isinstance(msg, Mapping) else type(msg).__name__
            return [self.error(f"unknown client message {kind!r}: use one of "
                               f"{', '.join(CLIENT_TYPES)}")]  # fmt: skip
        kind, e = msg["type"], self.engine
        try:
            if kind == "play":
                e.play()
                return [self._clock(e.elapsed_s)]
            if kind == "pause":
                e.pause()
                return [self._clock(e.elapsed_s)]
            if kind == "speed":
                e.set_speed(float(msg.get("value")))
                return [self._clock(e.elapsed_s)]
            if kind == "seek":
                t = float(msg.get("t_s"))
                if not math.isfinite(t):
                    raise ValueError("t_s must be a number")
                return self._seek(t)
            return [self._dtw(str(msg.get("match_track_id")),
                              str(msg.get("channel") or "dist_target_m"))]  # fmt: skip
        except (TypeError, ValueError, KeyError) as exc:
            return [self.error(f"{kind}: {exc}")]

    def reset(self) -> list[dict]:
        self.engine.reset()
        return self._seek(0.0)

    def _dtw(self, track_id: str, channel: str) -> dict:
        t = self.engine.elapsed_s
        try:
            doc = self.loop.lens(t, track_id, channel)
        except KeyError as exc:
            return self.error(str(exc).strip("'\""))
        return {"type": "dtw", "t_s": float(self.loop.rerun_at(t) or 0), **doc}

    def _seek(self, t_s: float) -> list[dict]:
        t = self.engine.seek(t_s)
        out = [self._clock(t, seeked=True)]
        out += self.incident.detections(max(-1.0, t - CATCH_UP_S), t)
        self._sent_t = t
        out += self._record(t)
        s1 = math.floor(t)
        s0 = max(1, s1 - int(CATCH_UP_S) + 1)
        out += [{"type": "features", **f} for f in self.loop.features_range(s0, s1)]
        self._feat_s = s1
        self._hashes.clear()
        r = self.loop.rerun_at(t) if self.loop.matching else None
        self._result_t = r
        if r is not None:
            out += self._results(r)
        out += self._ledger()
        return out

    # --- the tick ---------------------------------------------------------------------------
    def step(self) -> list[dict]:
        """Everything that happened since the last step (see the module docstring)."""
        out: list[dict] = []
        e = self.engine
        was_playing = e.playing
        t = e.elapsed_s
        due = self._last_clock is None or self._now() - self._last_clock >= 1 / CLOCK_HZ - 1e-6
        if (was_playing and due) or was_playing != e.playing:  # 10 Hz, and once when it stops
            out.append(self._clock(t))
        if t > self._sent_t:
            out += self.incident.detections(self._sent_t, t)
            self._sent_t = t
        out += self._record(t)
        s1 = math.floor(t)
        if s1 > self._feat_s:
            feats = self.loop.features_range(self._feat_s + 1, s1)
            out += [{"type": "features", **f} for f in feats]
            self._feat_s = s1
        r = self.loop.rerun_at(t) if self.loop.matching else None
        if r is not None and r != self._result_t:
            self._result_t = r
            out += self._results(r)
        out += self._ledger()
        return out

    def _record(self, t: float) -> list[dict]:
        if self.sink is None or t <= self._mark:
            return []
        batches = self.incident.rows(self._mark, t)
        self._mark = t
        return [{"type": "ingest", **self.sink.append(table, rows).to_dict()}
                for table, rows in batches.items()]  # fmt: skip

    def _ledger(self) -> list[dict]:
        return [ledger_message(r) for r in self.feed.drain()] if self.feed is not None else []

    # --- results and proposals --------------------------------------------------------------
    def _results(self, r: int) -> list[dict]:
        res = self.loop.result_at(r)
        if res is None:
            return []
        inc = self.incident
        meta = {"incident_id": inc.incident_id, "installation_id": inc.installation_id,
                "region_id": inc.region_id, "start_ts": inc.start_ts, "n_tracks": inc.n_tracks,
                "is_swarm": inc.is_swarm}  # fmt: skip
        return result_messages(res, r, inc.ts_at(r), meta, memory=self.memory, model=self.model,
                               offsets=self.loop.offsets, hashes=self._hashes)  # fmt: skip


def propose(memory, model: Mapping | None, meta: Mapping, res: Mapping, r: int,
            at: datetime) -> tuple[str | None, list[dict]]:  # fmt: skip
    """Record the incident (once) and propose the result's top 3 to the case holding the
    best-ranked top-3 incident (D-106, §15.6 dedup); returns that case (or None) and the ledger
    rows. Swarm incidents propose nothing (D-010). Shared by replays and live mode (D-181)."""
    if memory is None:
        return None, []
    rows = memory.events()
    top = [m["incident_id"] for m in res["matches"][:3]]
    case_id = target_case(rows, top, at)
    if case_id is None or meta["is_swarm"]:
        return case_id, rows
    iid = meta["incident_id"]
    recorded = any(row["event_type"] == "incident_recorded"
                   and row["subject_id"] == iid for row in rows)  # fmt: skip
    if not recorded:  # checked on the rows, so it holds after a reseed
        record_incident(memory, dict(meta), meta["start_ts"])
        if model is not None:
            register_model(memory, model["version"], model["sha256"], at, model.get("file", ""),
                           model.get("validation"))  # fmt: skip
    seqs = propose_matches(memory, case_id, iid, res["matches"][:3], at,
                           query_track=res["query_track"], t_s=r,
                           model_version=res["model_version"])  # fmt: skip
    if seqs:
        rows = memory.events()
    return case_id, rows


def result_messages(res: Mapping, r: int, at: datetime, meta: Mapping, *, memory,
                    model: Mapping | None, offsets: Mapping[str, int],
                    hashes: dict[str, str]) -> list[dict]:  # fmt: skip
    """The stream messages of one rerun result: ``match`` (decorated with the memory, §17.8),
    ``forecast``, and ``dtw`` / ``recall`` only when they changed since ``hashes``."""
    case_id, rows = propose(memory, model, meta, res, r, at)
    matches = decorate(res["matches"], rows, case_id, meta["incident_id"], at, offsets)
    out = [json_safe({"type": "match", "t_s": float(r), "model_version": res["model_version"],
                      "elapsed_ms": res["elapsed_ms"], "cached": bool(res.get("cached")),
                      "case_id": case_id, "query_track": res["query_track"],
                      "target_asset_id": res["target_asset_id"],
                      "matches": matches})]  # fmt: skip
    if res.get("forecast"):
        out.append({"type": "forecast", "t_s": float(r), **res["forecast"]})
    if res.get("trace"):  # the DTW workbench's record of this rerun (D-188)
        out.append({"type": "matcher_trace", "t_s": float(r),
                    "incident_id": meta["incident_id"], "trace": res["trace"]})  # fmt: skip
    for kind in ("dtw", "recall"):
        doc = res.get(kind)
        if doc is None:
            continue
        h = _digest(doc)
        if hashes.get(kind) != h:
            hashes[kind] = h
            out.append({"type": kind, "t_s": float(r), **doc})
    return out
