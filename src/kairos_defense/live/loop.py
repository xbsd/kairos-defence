"""The live loop (SPEC §16.1, D-105): matcher, forecast, report recall and the lens, on the replay
clock, cached by replay second.

Reruns happen at ``min_track_s, min_track_s + rerun_every_s, …`` seconds of replay time; between
them the latest rerun at or before a second is current. A result is a JSON-ready dict:
``t_s``, ``model_version``, the top 10 matches (§10.8 fields plus ``rank`` and ``local_start``),
``forecast`` (§13 or None), ``recall`` (top 3 distinct incidents), ``dtw`` (the lens for the top
match on ``dist_target_m``), ``target_asset_id`` and ``elapsed_ms``, the measured computation
time. A cached result keeps its original ``elapsed_ms`` and is marked ``cached`` (rule 10).

Queries use the track's points up to the replay second only (rule 3); the matcher keeps its
started-before filter. Swarm incidents get no single-track result: they are matched by choreography
(``match.swarm``, the Swarm view and ``kairos-defense swarm``, phase 9).
Every store access holds ``lock``: one DuckDB connection is never used by two threads at once
(D-110).
"""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable
from datetime import timedelta

import numpy as np

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import channel_matrix, load_site
from kairos_defense.forecast.analog import forecast
from kairos_defense.live.phase import flight_phase
from kairos_defense.live.replay import LiveIncident, iso_z
from kairos_defense.match.lens import lens_payload
from kairos_defense.match.query import Query, query_at
from kairos_defense.memory.actions import json_safe
from kairos_defense.ports import ResultCache, TrackStore

CACHE_FORMAT = 1
TOP_N = 10
RECALL_N = 3
DEFAULT_CHANNEL = "dist_target_m"
FEATURE_KEYS = ("speed_ms", "alt_m", "turn_rate_dps", "dist_target_m", "vspeed_ms", "heading_deg")


def rerun_seconds(duration_s: float, min_track_s: float, every_s: float) -> list[int]:
    """``min_track_s, min_track_s + every_s, …`` up to ``duration_s`` (whole seconds)."""
    out, t = [], float(min_track_s)
    while t <= duration_s + 1e-9:
        out.append(round(t))
        t += every_s
    return out


def result_name(t_s: int) -> str:
    return f"t{int(t_s):04d}"


def _num(v) -> float | None:
    return None if v is None or not np.isfinite(v) else round(float(v), 3)


class LiveLoop:
    """Results for one live incident. ``matcher`` (a ``DtwMatcher``) and ``recall`` (a
    ``ReportRecall``) may be None (no models or reports index): then results carry no matches."""

    def __init__(self, incident: LiveIncident, store: TrackStore, scoring: ScoringConfig, *,
                 matcher=None, recall=None, cache: ResultCache | None = None,
                 lock: threading.RLock | None = None, fingerprint: str | None = None,
                 clock: Callable[[], float] = time.perf_counter) -> None:  # fmt: skip
        self.incident, self.store, self.scoring = incident, store, scoring
        self.matcher, self.recall, self.cache = matcher, recall, cache
        self.lock = lock or threading.RLock()
        self.fingerprint, self._clock = fingerprint, clock
        self.single = not incident.is_swarm and len(incident.tracks) == 1
        self.matching = self.single and matcher is not None
        live = scoring.live
        self.min_track_s, self.every_s = float(live.min_track_s), float(live.rerun_every_s)
        self.schedule = rerun_seconds(incident.duration_s, self.min_track_s, self.every_s)
        self._results: dict[int, dict] = {}
        self._features: dict[int, dict] = {}
        with self.lock:
            self.site = load_site(store, incident.installation_id)
            self.offsets = dict(store.sql("SELECT installation_id, utc_offset_hours FROM "
                                          "installations JOIN regions USING (region_id)")
                                .itertuples(index=False))  # fmt: skip
        self.track_id = incident.tracks[0] if self.single else None
        if self.single:
            pts = incident.points
            self._points = pts[pts["track_id"] == self.track_id].reset_index(drop=True)
            first = self._points["t_s"].min()
            self._track_offset = float(first)  # the track's first point, in replay seconds
        self._check_cache()

    # --- cache ------------------------------------------------------------------------------
    def _check_cache(self) -> None:
        """Keep the cache only if its manifest has this loop's fingerprint; otherwise clear it
        and start a fresh manifest (stale results are never served)."""
        if self.cache is None or self.fingerprint is None:
            return
        inc = self.incident.incident_id
        with self.lock:
            man = self.cache.get(inc, "manifest")
            if man is None or man.get("fingerprint") != self.fingerprint:
                self.cache.clear(inc)
                self.cache.put(inc, "manifest", {"incident_id": inc, "format": CACHE_FORMAT,
                                                 "fingerprint": self.fingerprint})  # fmt: skip
            feats = self.cache.get(inc, "features")
        if feats is not None:
            self._features = {int(r["t_s"]): r for r in feats.get("rows", [])}

    def cache_state(self) -> dict:
        """How much of the schedule is cached (for ``replay`` and the CLI)."""
        if self.cache is None:
            return {"results": 0, "features": 0, "fresh": False}
        inc = self.incident.incident_id
        man = self.cache.get(inc, "manifest") or {}
        n = sum(self.cache.get(inc, result_name(r)) is not None for r in self.schedule)
        return {"results": n, "features": len(self._features),
                "fresh": man.get("fingerprint") == self.fingerprint}  # fmt: skip

    # --- schedule ---------------------------------------------------------------------------
    def rerun_at(self, t_s: float) -> int | None:
        """The latest rerun second at or before ``t_s`` (None before ``min_track_s``)."""
        best = None
        for r in self.schedule:
            if r <= t_s + 1e-9:
                best = r
        return best

    def waiting_for_s(self, t_s: float) -> float:
        return max(0.0, self.min_track_s - float(t_s))

    # --- queries ----------------------------------------------------------------------------
    def query(self, t_s: int) -> Query:
        """Tonight's track as seen at replay second ``t_s`` (points up to it only, rule 3)."""
        at = round(t_s - self._track_offset)
        ids = {"track_id": self.track_id, "incident_id": self.incident.incident_id}
        return query_at(self._points, self.site, at, self.scoring, ids)

    def features_at(self, s: int) -> dict | None:
        """The ``features`` message body at whole second ``s`` (None before the track starts)."""
        if not self.single or s < 1 or s > self.incident.duration_s:
            return None
        s = int(s)
        if s in self._features:
            return self._features[s]
        with self.lock:
            q = self.query(s)
        last = q.features.iloc[-1]
        row = {"t_s": float(s), "track_id": self.track_id, "target_asset_id": q.target.asset_id,
               **{k: _num(last[k]) for k in FEATURE_KEYS},
               "phase": flight_phase(q.features, q.target.kind)}  # fmt: skip
        self._features[s] = row
        return row

    def features_range(self, s0: int, s1: int) -> list[dict]:
        out = [self.features_at(s) for s in range(max(1, int(s0)), int(s1) + 1)]
        return [f for f in out if f is not None]

    def save_features(self) -> int:
        """Compute every second's features and store them in the cache; returns the count."""
        rows = self.features_range(1, int(self.incident.duration_s))
        if self.cache is not None:
            with self.lock:
                self.cache.put(self.incident.incident_id, "features",
                               {"track_id": self.track_id, "rows": rows})  # fmt: skip
        return len(rows)

    # --- results ----------------------------------------------------------------------------
    def result_at(self, t_s: float) -> dict | None:
        """The current result at replay second ``t_s`` (snapped to the latest rerun), from
        memory, the cache, or computed now and stored. None before ``min_track_s`` or when
        this incident has no single-track matching."""
        r = self.rerun_at(t_s)
        if r is None or not self.matching:
            return None
        if r in self._results:
            return self._results[r]
        inc = self.incident.incident_id
        doc = None
        if self.cache is not None:
            with self.lock:
                doc = self.cache.get(inc, result_name(r))
            if doc is not None:
                doc = {**doc, "cached": True}
        if doc is None:
            doc = self.compute(r)
            if self.cache is not None:
                with self.lock:
                    self.cache.put(inc, result_name(r), doc)
        self._results[r] = doc
        return doc

    def compute(self, r: int) -> dict:
        """Run the matcher, forecast, recall and the top match's lens at rerun second ``r``."""
        if not self.matching:
            raise ValueError(f"{self.incident.incident_id} has no single-track matching")
        with self.lock:
            return compute_result(r, lambda: self.query(r), store=self.store,
                                  matcher=self.matcher, recall=self.recall, scoring=self.scoring,
                                  offsets=self.offsets, incident_id=self.incident.incident_id,
                                  clock=self._clock)  # fmt: skip

    def _lens(self, q: Query, match: dict, channel: str) -> dict:
        return lens_for(q, match, channel, self.matcher, self.scoring)

    def lens(self, t_s: float, match_track_id: str, channel: str = DEFAULT_CHANNEL) -> dict:
        """The lens for one of the current result's matches; ``KeyError`` if it is not one."""
        res = self.result_at(t_s)
        if res is None:
            raise KeyError(f"no result at T+{t_s:g} s")
        top = res.get("dtw")
        if top and top["match_track_id"] == match_track_id and top["channel"] == channel:
            return copy.deepcopy(top)
        m = next((m for m in res["matches"] if m["track_id"] == match_track_id), None)
        if m is None:
            raise KeyError(f"{match_track_id} is not among the matches at T+{res['t_s']} s")
        if channel not in self.scoring.features.channels:
            raise ValueError(f"unknown channel {channel!r}")
        with self.lock:
            return self._lens(self.query(res["t_s"]), m, channel)


def local_start(m, offsets: dict) -> str:
    """A match's start in its installation's local time, ``YYYY-MM-DDTHH:MM``."""
    off = timedelta(hours=offsets.get(m.installation_id, 0))
    return f"{m.start_ts + off:%Y-%m-%dT%H:%M}"


def lens_for(q: Query, match: dict, channel: str, matcher, scoring: ScoringConfig) -> dict:
    """The time-warp lens payload of one match on one channel (§17.4, D-117)."""
    c = scoring.features.channels.index(channel)
    live = channel_matrix(q.features.iloc[-q.rows_used :], scoring)[:, c]
    seg = matcher.builder.segment(match["track_id"], int(match["window_offset_s"]),
                                  int(match["features"]["window_s"]))  # fmt: skip
    return lens_payload(live, seg[:, c], channel=channel, band_fraction=scoring.dtw.band_fraction,
                        warp_ratio=match.get("warp_ratio"),
                        match_track_id=match["track_id"])  # fmt: skip


def compute_result(r: int, make_query: Callable[[], Query], *, store: TrackStore, matcher,
                   recall, scoring: ScoringConfig, offsets: dict, incident_id: str,
                   clock: Callable[[], float] = time.perf_counter) -> dict:  # fmt: skip
    """One rerun at second ``r``: build the query (``make_query``, points up to ``r`` only), run
    the matcher, the §13 forecast, §12 recall and the top match's lens, and return the JSON-ready
    result (see the module docstring). Shared by replays and live mode (D-175); the caller holds
    the store lock."""
    t0 = clock()
    q = make_query()
    res = matcher.match(q)
    t1 = clock()
    fc = forecast(store, q, res, scoring)
    t2 = clock()
    rc = None
    if recall is not None:
        rc = recall.for_matches(q, res, fc.roads if fc else (), n=RECALL_N)
    t3 = clock()
    top = res.matches[0].to_dict() if res.matches else None
    lens = lens_for(q, top, DEFAULT_CHANNEL, matcher, scoring) if top else None
    t4 = clock()
    matches = []
    for rank, m in enumerate(res.matches[:TOP_N], 1):
        d = m.to_dict()
        d.update(rank=rank, start_ts=iso_z(m.start_ts), local_start=local_start(m, offsets))
        matches.append(d)
    recall_doc = rc.to_dict() if rc is not None else None
    if recall_doc is not None:
        for mr in recall_doc["matches"]:
            for rep in mr["reports"]:
                rep["event_ts"] = iso_z(_ms_to_dt(rep["event_ts_ms"]))
    timings = {**{k: float(v) for k, v in res.timings.items()},
               "forecast_ms": (t2 - t1) * 1e3, "recall_ms": (t3 - t2) * 1e3,
               "lens_ms": (t4 - t3) * 1e3}  # fmt: skip
    return json_safe({
        "t_s": int(r), "incident_id": incident_id, "query_track": q.track_id,
        "model_version": matcher.model_version, "window_s": int(q.window_s),
        "rows_used": int(q.rows_used), "target_asset_id": q.target.asset_id,
        "matches": matches, "forecast": fc.to_dict() if fc else None, "recall": recall_doc,
        "dtw": lens, "elapsed_ms": (t4 - t0) * 1e3, "timings": timings, "cached": False,
    })  # fmt: skip


def _ms_to_dt(ms: int):
    from kairos_defense.match.baseline import _ts

    return _ts(int(ms))
