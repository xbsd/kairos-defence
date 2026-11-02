"""The live calendar (D-177): after the history, forward only, deterministic default seeds."""

from __future__ import annotations

import json
from datetime import date, datetime

from kairos_defense.sim.calendar import utc_ms_to_local
from kairos_defense.sim.live_clock import LiveClock, launch_at, window_on


def test_default_start_is_the_night_after_the_calendar_at_21_local(cfg, tmp_path) -> None:
    c = LiveClock(tmp_path / "clock.json", cfg.world.calendar.end_local)
    assert cfg.world.calendar.end_local == date(2026, 8, 31)
    assert utc_ms_to_local(c.next_ms(-5), -5) == datetime(2026, 9, 1, 21, 0)
    assert utc_ms_to_local(c.next_ms(-7), -7) == datetime(2026, 9, 1, 21, 0)
    assert c.stored_ms() is None


def test_windows_wrap_past_midnight() -> None:
    n = date(2026, 9, 1)
    assert window_on(n, ("21:00", "22:30")) == (
        datetime(2026, 9, 1, 21),
        datetime(2026, 9, 1, 22, 30),
    )
    assert window_on(n, ("23:00", "01:00")) == (datetime(2026, 9, 1, 23), datetime(2026, 9, 2, 1))
    assert window_on(n, ("01:00", "03:00")) == (datetime(2026, 9, 2, 1), datetime(2026, 9, 2, 3))


def test_launch_falls_in_the_window() -> None:
    w = ("21:00", "22:30")
    assert launch_at(datetime(2026, 9, 1, 20, 0), w) == datetime(2026, 9, 1, 21, 0)
    assert launch_at(datetime(2026, 9, 1, 21, 40, 0, 5), w) == datetime(2026, 9, 1, 21, 40, 1)
    assert launch_at(datetime(2026, 9, 1, 23, 0), w) == datetime(2026, 9, 2, 21, 0)
    assert launch_at(datetime(2026, 9, 2, 0, 30), ("23:00", "01:00")) == datetime(2026, 9, 2, 0, 30)


def test_clock_persists_and_only_moves_forward(cfg, tmp_path) -> None:
    p = tmp_path / "live" / "clock.json"
    c = LiveClock(p, cfg.world.calendar.end_local)
    start = c.next_ms(-5)
    assert c.reserve(start + 600_000) == start + 600_000
    assert c.reserve(start + 1_000) == start + 600_000  # never back
    again = LiveClock(p, cfg.world.calendar.end_local)
    assert again.next_ms(-5) == start + 600_000
    assert json.loads(p.read_text()) == {"next_utc_ms": start + 600_000, "launches": 2}
    later = again.launch_local(-5, ("21:00", "22:30"))
    assert later == datetime(
        2026, 9, 1, 21, 10
    )  # the second scenario after the first's reservation


def test_default_seed_is_a_function_of_the_world_seed_and_the_launch_counter(cfg, tmp_path) -> None:
    a = LiveClock(tmp_path / "a.json", cfg.world.calendar.end_local)
    b = LiveClock(tmp_path / "b.json", cfg.world.calendar.end_local)
    s0 = a.default_seed(42)
    assert s0 == b.default_seed(42) and 1 <= s0 < 2**31
    assert a.default_seed(43) != s0
    a.reserve(a.next_ms(-5))
    assert a.default_seed(42) != s0  # the next launch gets another seed
    b.reserve(b.next_ms(-5))
    assert a.default_seed(42) == b.default_seed(42)
