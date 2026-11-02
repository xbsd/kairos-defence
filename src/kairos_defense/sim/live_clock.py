"""The live calendar (D-177): live flights fly after the last history night, forward only.

``clock.json`` in the live-mode folder holds the next free UTC instant (epoch ms) and how many
scenarios were launched (the counter behind default seeds, rule 4). Its default is
the night after ``calendar.end_local`` at 21:00 local at the base, so every history flight started
before every live flight (rule 3). A scenario launches at the earliest time at or after the clock
whose local time of day falls inside its actor's usual window, then reserves the clock up to the
end of its last flight plus a margin; resets never rewind it.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

from kairos_defense.rng import rng_for
from kairos_defense.sim.calendar import local_to_utc_ms, utc_ms_to_local

CLOCK_FILE = "clock.json"
DEFAULT_START = time(21, 0)
NOON = time(12, 0)


def _hhmm(s: str) -> time:
    return time.fromisoformat(s)


def window_on(night: date, window: tuple[str, str]) -> tuple[datetime, datetime]:
    """The local ``[start, end]`` of ``window`` (``("21:00", "22:30")``) on ``night``: times
    before noon belong to the morning after (``("23:00", "01:00")`` ends the next day)."""
    a, b = _hhmm(window[0]), _hhmm(window[1])
    start = datetime.combine(night + timedelta(days=a < NOON), a)
    end = datetime.combine(night + timedelta(days=b < NOON), b)
    if end < start:
        end += timedelta(days=1)
    return start, end


def launch_at(after_local: datetime, window: tuple[str, str]) -> datetime:
    """The earliest local time at or after ``after_local`` (whole seconds, rounded up) inside
    ``window`` on some night."""
    t = after_local
    if t.microsecond:
        t = t.replace(microsecond=0) + timedelta(seconds=1)
    first = (t - timedelta(days=1)).date()
    for k in range(4):
        start, end = window_on(first + timedelta(days=k), window)
        if t <= start:
            return start
        if t <= end:
            return t
    raise AssertionError("a window always recurs within four nights")  # pragma: no cover


class LiveClock:
    """The persisted live clock. ``calendar_end``: ``calendar.end_local`` (the last history
    night); ``path``: ``<live_mode>/clock.json``."""

    def __init__(self, path: Path | str, calendar_end: date) -> None:
        self.path = Path(path)
        self.calendar_end = calendar_end

    def default_ms(self, utc_offset_hours: int) -> int:
        night = self.calendar_end + timedelta(days=1)
        return local_to_utc_ms(datetime.combine(night, DEFAULT_START), utc_offset_hours)

    def _doc(self) -> dict:
        try:
            doc = json.loads(self.path.read_text())
            return doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            return {}

    def stored_ms(self) -> int | None:
        try:
            return int(self._doc()["next_utc_ms"])
        except (KeyError, TypeError, ValueError):
            return None

    def launches(self) -> int:
        try:
            return int(self._doc().get("launches", 0))
        except (TypeError, ValueError):
            return 0

    def default_seed(self, world_seed: int) -> int:
        """The seed of the next launch when none is given: a pure function of the world seed and
        the launch counter (rule 4), so successive launches differ and a run is reproducible."""
        rng = rng_for(int(world_seed), "live", "seed", str(self.launches()))
        return int(rng.integers(1, 2**31 - 1))

    def next_ms(self, utc_offset_hours: int) -> int:
        """The next free instant: the stored clock, never before the default start."""
        d = self.default_ms(utc_offset_hours)
        s = self.stored_ms()
        return d if s is None else max(s, d)

    def launch_local(self, utc_offset_hours: int, window: tuple[str, str]) -> datetime:
        """A scenario's first launch, local at the base (naive)."""
        return launch_at(utc_ms_to_local(self.next_ms(utc_offset_hours), utc_offset_hours),
                         window)  # fmt: skip

    def reserve(self, until_ms: int) -> int:
        """Move the clock forward to ``until_ms`` (never back) and count one launch; returns the
        stored instant."""
        s = self.stored_ms()
        value = int(until_ms) if s is None else max(int(until_ms), s)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"next_utc_ms": value, "launches": self.launches() + 1}) + "\n")
        os.replace(tmp, self.path)
        return value
