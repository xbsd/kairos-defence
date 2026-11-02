"""``live reset`` (D-172, D-181): every live row goes; the history and the ledger chain stay."""

from __future__ import annotations

from kairos_defense.sim import live_scenarios as ls
from kairos_defense.sim.live_clock import LiveClock
from tests.unit.live_kit import feed

MAIN_TABLES = ("incidents", "track_points", "rf_detections", "remote_id", "track_features",
               "track_signatures", "reports", "swarm_features")  # fmt: skip


def _main_counts(svc) -> dict:
    with svc.lock:
        out = {t: int(svc.store.sql(f"SELECT count(*) AS n FROM {t}")["n"].iloc[0])
               for t in MAIN_TABLES}  # fmt: skip
    out["flight_windows"] = svc.lance.count("flight_windows")
    return out


def test_reset_removes_every_live_row_and_keeps_history_and_ledger(live_services, world,
                                                                   tmp_path) -> None:  # fmt: skip
    svc, live = live_services, live_services.live
    main_before = _main_counts(svc)
    clock = LiveClock(tmp_path / "clock.json", svc.cfg.world.calendar.end_local)
    sc = ls.build(svc.cfg, world, clock, "returning-prober", seed=7, base="BRAVO")
    feed(live.hub, sc, frame_s=50.0)
    counts = live.feed.counts()
    for t in ("live_points", "live_rf", "live_incidents", "live_tracks", "track_features",
              "track_signatures", "live_results"):  # fmt: skip
        assert counts[t] > 0, t
    assert live.vectors.count("flight_windows") > 0
    ledger_rows = svc.memory.count()
    out = live.reset()
    assert out["reset"]["live_points"] == counts["live_points"] and out["vectors"] > 0
    assert all(v == 0 for v in live.feed.counts().values())
    assert not live.vectors.has("flight_windows")
    assert live.hub.tracker.incidents == {}
    assert not any(t.startswith("LIVE-") for t in live.matcher.builder.cached_ids())
    assert _main_counts(svc) == main_before  # the 18-month history is never written
    assert svc.memory.count() == ledger_rows  # append-only: reset never touches the ledger
    assert svc.memory.verify_chain() is None
    assert live.status()["incidents"] == []
