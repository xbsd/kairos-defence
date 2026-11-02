"""Live incident formation (D-174): the app groups incoming radar tracks into incidents itself.

Pure logic on feed time (the newest timestamp received at an installation, heartbeats included):

- A point with an unseen sensor track id opens a track. The track joins an open incident at that
  installation when, at its first point, a track of that incident had a point within
  ``live.join_window_s`` seconds and ``swarm.max_spacing_m`` meters; otherwise it opens a new
  incident whose T+0 is that first point.
- An incident with ``swarm.min_drones`` or more tracks is a swarm incident.
- An incident closes when feed time passes its last detection by ``live.idle_close_s``: its
  tracks' radar points, or RF and Remote ID heard at the installation (they are not tied to a
  track at ingest), so a radar dropout while the RF sensor still hears the drone does not split
  the flight (incidents span every sensor's detections, as the generator's do, D-028). A sensor
  track seen again after its incident closed starts a new track.

Ids: ``LIVE-<BASE>-<YYMMDD>-<HHMMSS>`` of the first point in local time (``-2``, ``-3`` … on a
clash), tracks ``<incident>-T<n>``; they never carry the actor. Times are UTC epoch ms.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from kairos_defense.config import ScoringConfig

PREFIX = "LIVE"


@dataclass
class LiveTrack:
    track_id: str
    sensor_track_id: str
    incident_id: str
    installation_id: str
    first_ms: int
    last_ms: int
    last_xy: tuple[float, float]
    n_points: int = 1


@dataclass
class LiveIncidentState:
    """One live incident as the app knows it (no actor, ever)."""

    incident_id: str
    installation_id: str
    region_id: str
    start_ms: int  # T+0: the first radar point
    last_ms: int  # the last radar point of any of its tracks
    tracks: list[str] = field(default_factory=list)
    state: str = "open"  # open | closing (idle, results pending) | closed (learned)
    is_swarm: bool = False
    next_rerun_s: float = 0.0  # seconds after start of the next rerun to schedule
    reruns: int = 0  # reruns completed

    def t_s(self, ms: int) -> float:
        return round((ms - self.start_ms) / 1000.0, 3)


def incident_id(installation_id: str, first_ms: int, utc_offset_hours: int,
                used: set[str]) -> str:  # fmt: skip
    local = datetime(1970, 1, 1) + timedelta(milliseconds=first_ms, hours=utc_offset_hours)
    base = f"{PREFIX}-{installation_id}-{local:%y%m%d-%H%M%S}"
    out, k = base, 1
    while out in used:
        k += 1
        out = f"{base}-{k}"
    used.add(out)
    return out


class IncidentTracker:
    """Tracks and incidents of every installation. ``sites``: installation -> (region id, UTC
    offset in hours); ``used``: incident ids already taken (from the feed store)."""

    def __init__(self, scoring: ScoringConfig, sites: dict[str, tuple[str, int]],
                 used: Iterable[str] = ()) -> None:  # fmt: skip
        live, sw = scoring.live, scoring.swarm
        self.idle_ms = round(float(live.idle_close_s) * 1000)
        self.join_ms = round(float(live.join_window_s) * 1000)
        self.spacing_m = float(sw.max_spacing_m)
        self.min_drones = int(sw.min_drones)
        self.min_track_s, self.every_s = float(live.min_track_s), float(live.rerun_every_s)
        self.sites = dict(sites)
        self.used = set(used)
        self.incidents: dict[str, LiveIncidentState] = {}
        self.tracks: dict[str, LiveTrack] = {}  # by app track id
        self._by_sensor: dict[tuple[str, str], str] = {}  # (installation, sensor track) -> track

    def open_incidents(self, installation_id: str | None = None) -> list[LiveIncidentState]:
        return [i for i in self.incidents.values() if i.state == "open"
                and (installation_id is None or i.installation_id == installation_id)]  # fmt: skip

    def current(self, installation_id: str) -> LiveIncidentState | None:
        """The newest incident at an installation that is not closed (else the newest)."""
        incs = [i for i in self.incidents.values() if i.installation_id == installation_id]
        live = [i for i in incs if i.state != "closed"]
        pool = live or incs
        return max(pool, key=lambda i: (i.start_ms, i.incident_id)) if pool else None

    def point(self, installation_id: str, sensor_track_id: str, ms: int, x: float,
              y: float) -> tuple[LiveTrack, list[tuple[str, LiveIncidentState]]]:  # fmt: skip
        """One radar point. Returns its track and the events it caused: ``("opened", inc)``,
        ``("joined", inc)`` (a new track in an existing incident)."""
        key = (installation_id, sensor_track_id)
        tid = self._by_sensor.get(key)
        if tid is not None:
            trk = self.tracks[tid]
            inc = self.incidents[trk.incident_id]
            if inc.state == "open":
                trk.last_ms, trk.last_xy = max(trk.last_ms, ms), (x, y)
                trk.n_points += 1
                inc.last_ms = max(inc.last_ms, ms)
                return trk, []
        events: list[tuple[str, LiveIncidentState]] = []
        inc = self._joinable(installation_id, ms, x, y)
        if inc is None:
            region, offset = self.sites[installation_id]
            iid = incident_id(installation_id, ms, offset, self.used)
            inc = LiveIncidentState(iid, installation_id, region, ms, ms,
                                    next_rerun_s=self.min_track_s)  # fmt: skip
            self.incidents[iid] = inc
            events.append(("opened", inc))
        else:
            events.append(("joined", inc))
        tid = f"{inc.incident_id}-T{len(inc.tracks) + 1}"
        trk = LiveTrack(tid, sensor_track_id, inc.incident_id, installation_id, ms, ms, (x, y))
        self.tracks[tid] = trk
        self._by_sensor[key] = tid
        inc.tracks.append(tid)
        inc.last_ms = max(inc.last_ms, ms)
        inc.is_swarm = len(inc.tracks) >= self.min_drones
        return trk, events

    def _joinable(self, installation_id: str, ms: int, x: float, y: float):
        for inc in sorted(self.open_incidents(installation_id), key=lambda i: i.start_ms):
            for tid in inc.tracks:
                t = self.tracks[tid]
                near = math.hypot(t.last_xy[0] - x, t.last_xy[1] - y) <= self.spacing_m
                if ms - t.last_ms <= self.join_ms and near:
                    return inc
        return None

    def idle(self, installation_id: str, feed_ms: int,
             heard_ms: int | None = None) -> list[LiveIncidentState]:  # fmt: skip
        """Open incidents at an installation with no detection for more than ``idle_close_s``
        of feed time (their last radar point, or ``heard_ms``: the last RF or Remote ID heard
        at the installation); they become ``closing``."""
        out = []
        for inc in self.open_incidents(installation_id):
            if feed_ms - max(inc.last_ms, heard_ms or 0) > self.idle_ms:
                inc.state = "closing"
                out.append(inc)
        return out

    def due_reruns(self, inc: LiveIncidentState, feed_ms: int) -> list[float]:
        """Rerun seconds (after the incident's start) that feed time has passed, in order; each
        is returned once."""
        out = []
        while inc.state == "open" and feed_ms >= inc.start_ms + round(inc.next_rerun_s * 1000):
            out.append(inc.next_rerun_s)
            inc.next_rerun_s += self.every_s
        return out

    def forget(self) -> None:
        """Drop every track and incident (``live reset``); ids already used stay used."""
        self.incidents.clear()
        self.tracks.clear()
        self._by_sensor.clear()
