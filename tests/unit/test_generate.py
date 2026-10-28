"""Generation pipeline invariants (SPEC §7.1, §7.3, §8.11, D-003)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from kairos_defense.sim.datacard import card_markdown, write_data_card
from kairos_defense.sim.incidents import FlightResult, group_incidents, heard_only
from kairos_defense.sim.sensors import RadarHits
from kairos_defense.sim.tables import build_tables
from kairos_defense.store.ddl import RAW_COLUMNS, TRUTH_COLUMNS

ID = re.compile(r"^[A-Z]+-\d{6}-\d{4}(-\d+)?$")


def test_tables_match_the_ddl(g42) -> None:
    assert list(g42.tables) == list(RAW_COLUMNS)
    for name, df in g42.tables.items():
        assert list(df.columns) == RAW_COLUMNS[name], name
    for name, df in g42.truth.items():
        assert list(df.columns) == TRUTH_COLUMNS[name], name


def test_incident_spans_its_detections_by_any_sensor(g42) -> None:
    """D-028: start and end are the first and last detection by radar, RF or Remote ID."""
    inc = g42.tables["incidents"].set_index("incident_id")
    for i in g42.incidents:
        ms = np.concatenate([r.detection_ms() for r in i.flights])
        row = inc.loc[i.incident_id]
        assert row.start_ts == pd.Timestamp(int(ms.min()), unit="ms"), i.incident_id
        assert row.end_ts == pd.Timestamp(int(ms.max()), unit="ms"), i.incident_id
    tp = g42.tables["track_points"]
    span = tp.groupby("incident_id").ts.agg(["min", "max"])
    assert (inc.start_ts.loc[span.index] <= span["min"]).all()
    assert (inc.end_ts.loc[span.index] >= span["max"]).all()
    rf_first = sum(
        int(np.min(r.plan.launch_ms + r.rf.t_s * 1000)) < int(i.radar_ms().min())
        for i in g42.incidents for r in i.flights[:1] if len(r.rf)
    )  # fmt: skip
    assert rf_first > 0  # RF hears takeoff before the radar sees 15 m
    assert tp.groupby("track_id").ts.is_monotonic_increasing.all()


def test_tracks_per_incident(g42) -> None:
    inc = g42.tables["incidents"].set_index("incident_id")
    tp = g42.tables["track_points"]
    single = inc[~inc.is_swarm]
    assert (single.n_tracks == 1).all()
    t1 = tp[tp.incident_id.isin(single.index)]
    assert (t1.track_id == t1.incident_id + "-T1").all()
    n = tp.groupby("incident_id").track_id.nunique()
    assert (n.loc[inc.index] == inc.n_tracks).all()
    swarms = inc[inc.is_swarm]
    assert len(swarms) >= 1  # S1's random event at HOTEL falls in the window
    for iid, row in swarms.iterrows():
        tracks = sorted(tp[tp.incident_id == iid].track_id.unique())
        assert tracks == [f"{iid}-T{k}" for k in range(1, row.n_tracks + 1)]
        assert row.n_tracks >= 3


def test_incident_ids_never_name_the_actor(g42) -> None:
    planted = {r.plan.key for r in g42.results if r.plan.incident_id}
    for r in g42.results:
        if not r.detected:
            continue
        inc = g42.incident_of[r.plan.key]
        if r.plan.key in planted:
            assert inc == r.plan.incident_id
            continue
        assert ID.match(inc), inc
        assert inc.startswith(r.plan.installation_id + "-")
        i = next(i for i in g42.incidents if i.incident_id == inc)
        off = g42.world.sites[r.plan.installation_id].utc_offset_hours
        first = pd.Timestamp(i.start_ms, unit="ms") + pd.Timedelta(hours=off)
        assert inc[: len(r.plan.installation_id) + 12].endswith(first.strftime("%y%m%d-%H%M"))


def test_truth_links_every_track(g42) -> None:
    tt = g42.truth["track_truth"].set_index("track_id")
    tracks = set(g42.tables["track_points"].track_id)
    assert set(tt.index) == tracks
    inc = g42.tables["incidents"].set_index("incident_id")
    assert (tt.launch_ts.to_numpy() <= inc.loc[tt.incident_id].start_ts.to_numpy()).all()
    assert set(tt.actor_type) == {"hobbyist", "prober", "copycat", "swarm"}
    paths = g42.truth["true_paths"]
    steps = paths.groupby("track_id").t_s.diff().dropna()
    assert (steps == 1.0).all()  # 1 Hz noiseless paths
    assert (paths.groupby("track_id").t_s.min() == 0.0).all()


def test_undetected_flights_make_no_incident(g42) -> None:
    """D-038: no radar track, no incident, even when RF heard it; its RF is still logged."""
    r = next(r for r in g42.results if r.detected and len(r.rf))
    none = RadarHits(r.hits.sensor_id, np.zeros(0), np.zeros((0, 3)), np.zeros(0))
    ghost = FlightResult(r.plan, r.path, none, r.rf, r.rid)
    assert group_incidents([ghost], g42.world) == []
    assert heard_only([ghost]) == 1
    raw, truth = build_tables([], [ghost], g42.world, g42.calendar)
    assert len(raw["incidents"]) == 0 and len(truth["track_truth"]) == 0
    assert len(raw["rf_detections"]) == len(r.rf)


def test_data_card(cfg, g42, tmp_path) -> None:
    md = card_markdown(g42, [])
    for heading in ("## Volumes against SPEC §8.11", "## Swarm incidents", "## Sensors",
                    "## Reports", "## Clue rates", "## Assessments", "## Planted items",
                    "## Live incident timing", "## Row counts"):  # fmt: skip
        assert heading in md, heading
    assert "DEMO-BRAVO-0828" in md
    assert "| 0–10 min |" in md  # report-delay histogram
    paths = cfg.app.paths.model_copy(update={"reports": tmp_path})
    small = cfg.model_copy(update={"app": cfg.app.model_copy(update={"paths": paths})})
    card = write_data_card(small, g42)
    text = card.read_text(encoding="utf-8")
    assert text.startswith("# Data card")
    kinds = {
        r.plan.pattern["type"] for r in g42.results if r.detected and r.plan.actor_type != "swarm"
    }
    assert {"orbit", "random_walk"} <= kinds
    for k in kinds:
        assert (tmp_path / "figures" / f"pattern_{k}.png").stat().st_size > 10_000, k
        assert f"(figures/pattern_{k}.png)" in text
    teams = {i.plan.actor_id for i in g42.incidents if i.is_swarm}
    assert teams
    for t in teams:
        assert (tmp_path / "figures" / f"swarm_{t}.png").stat().st_size > 10_000, t
        assert f"(figures/swarm_{t}.png)" in text


@pytest.mark.parametrize("t", ["weather", "base_events", "public_events"])
def test_window_trims_calendar_tables(g42, t) -> None:
    df = g42.tables[t]
    col = "ts" if t == "weather" else "start_ts"
    if len(df):
        assert df[col].min() >= pd.Timestamp("2026-08-11")
        assert df[col].max() <= pd.Timestamp("2026-09-02")
