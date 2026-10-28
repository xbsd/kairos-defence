"""In-memory raw (§7.1) and truth (§7.3) tables from incidents, sensor logs and paperwork.

``rf_detections`` and ``remote_id`` log every flown drone, incident or not: sensors record what
they hear (D-038). Truth rows exist for radar tracks only. Rows are ordered by key and time; the
writer hashes them in a canonical order anyway.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense.sim.calendar import Calendar, ms_to_ts
from kairos_defense.sim.incidents import FlightResult, Incident
from kairos_defense.sim.world import World
from kairos_defense.store.ddl import RAW_COLUMNS, TRUTH_COLUMNS

PAPER_TABLES = ("reports", "assessments")
PAPER_TRUTH = ("clue_truth", "assessment_truth")


def empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object) for c in columns})


def _ms(r: FlightResult, t_s: np.ndarray) -> np.ndarray:
    return r.plan.launch_ms + np.round(np.asarray(t_s) * 1000.0).astype(np.int64)


def _repeat(values: list, counts: list[int]) -> np.ndarray:
    return np.repeat(np.asarray(values, dtype=object), counts)


def incidents_table(incidents: list[Incident]) -> pd.DataFrame:
    rows = [(i.incident_id, i.plan.installation_id, i.plan.region_id, i.start_ms, i.end_ms,
             len(i.tracks), i.is_swarm, i.status) for i in incidents]  # fmt: skip
    df = pd.DataFrame(rows, columns=RAW_COLUMNS["incidents"])
    df["start_ts"] = ms_to_ts(df.start_ts.to_numpy(np.int64))
    df["end_ts"] = ms_to_ts(df.end_ts.to_numpy(np.int64))
    df["n_tracks"] = df.n_tracks.astype("int32")
    df["is_swarm"] = df.is_swarm.astype(bool)
    return df


def track_points_table(incidents: list[Incident]) -> pd.DataFrame:
    parts = []
    for inc in incidents:
        for i, r in enumerate(inc.tracks):
            n = len(r.hits)
            p = r.plan
            parts.append(
                pd.DataFrame(
                    {
                        "incident_id": np.full(n, inc.incident_id, dtype=object),
                        "track_id": np.full(n, inc.track_id(i), dtype=object),
                        "installation_id": np.full(n, p.installation_id, dtype=object),
                        "region_id": np.full(n, p.region_id, dtype=object),
                        "sensor_id": np.full(n, r.hits.sensor_id, dtype=object),
                        "ts": ms_to_ts(_ms(r, r.hits.t_s)),
                        "x_m": r.hits.xyz[:, 0],
                        "y_m": r.hits.xyz[:, 1],
                        "alt_m": r.hits.xyz[:, 2],
                        "quality": r.hits.quality,
                    }
                )
            )
    return pd.concat(parts, ignore_index=True) if parts else empty(RAW_COLUMNS["track_points"])


def rf_table(results: list[FlightResult]) -> pd.DataFrame:
    rs = [r for r in results if len(r.rf)]
    if not rs:
        return empty(RAW_COLUMNS["rf_detections"])
    n = [len(r.rf) for r in rs]
    df = pd.DataFrame(
        {
            "installation_id": _repeat([r.plan.installation_id for r in rs], n),
            "sensor_id": _repeat([r.rf.sensor_id for r in rs], n),
            "ts": ms_to_ts(np.concatenate([_ms(r, r.rf.t_s) for r in rs])),
            "band": _repeat([r.rf.band for r in rs], n),
            "protocol_family": _repeat([r.rf.family for r in rs], n),
            "bearing_deg": np.concatenate([r.rf.bearing_deg for r in rs]),
            "snr_db": np.concatenate([r.rf.snr_db for r in rs]),
        }
    )
    return df.sort_values(
        ["installation_id", "ts", "bearing_deg"], kind="stable", ignore_index=True
    )


def rid_table(results: list[FlightResult]) -> pd.DataFrame:
    rs = [r for r in results if len(r.rid)]
    if not rs:
        return empty(RAW_COLUMNS["remote_id"])
    n = [len(r.rid) for r in rs]
    op = np.repeat(np.asarray([r.rid.op_xy for r in rs]), n, axis=0)
    drone = np.concatenate([r.rid.drone_xy for r in rs])
    df = pd.DataFrame(
        {
            "installation_id": _repeat([r.plan.installation_id for r in rs], n),
            "ts": ms_to_ts(np.concatenate([_ms(r, r.rid.t_s) for r in rs])),
            "serial": _repeat([r.rid.serial for r in rs], n),
            "drone_x_m": drone[:, 0],
            "drone_y_m": drone[:, 1],
            "op_x_m": op[:, 0],
            "op_y_m": op[:, 1],
        }
    )
    return df.sort_values(["installation_id", "ts", "serial"], kind="stable", ignore_index=True)


def truth_tables(incidents: list[Incident]) -> dict[str, pd.DataFrame]:
    """``track_truth`` and ``true_paths`` for every radar track."""
    rows, parts = [], []
    for inc in incidents:
        for i, r in enumerate(inc.tracks):
            p, track = r.plan, inc.track_id(i)
            land = r.path.xyz[-1]
            rows.append(
                (track, inc.incident_id, p.actor_id, p.actor_type, p.launch_ms, p.time_warp,
                 float(r.path.xyz[0, 0]), float(r.path.xyz[0, 1]), float(land[0]), float(land[1]))
            )  # fmt: skip
            m = len(r.path.t_s)
            parts.append(
                pd.DataFrame(
                    {
                        "track_id": np.full(m, track, dtype=object),
                        "t_s": r.path.t_s,
                        "x_m": r.path.xyz[:, 0],
                        "y_m": r.path.xyz[:, 1],
                        "alt_m": r.path.xyz[:, 2],
                    }
                )
            )
    tt = pd.DataFrame(rows, columns=TRUTH_COLUMNS["track_truth"])
    tt["launch_ts"] = ms_to_ts(tt.launch_ts.to_numpy(np.int64))
    paths = pd.concat(parts, ignore_index=True) if parts else empty(TRUTH_COLUMNS["true_paths"])
    return {"track_truth": tt, "true_paths": paths}


def build_tables(
    incidents: list[Incident],
    results: list[FlightResult],
    world: World,
    cal: Calendar,
    paper: dict[str, pd.DataFrame] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Raw tables (§7.1) and truth tables (§7.3). ``paper`` holds the reports, assessments and
    their truth tables (built by ``reports`` and ``assessments``)."""
    paper = paper or {}
    raw = world.tables() | {
        "incidents": incidents_table(incidents),
        "track_points": track_points_table(incidents),
        "rf_detections": rf_table(results),
        "remote_id": rid_table(results),
        "weather": cal.weather,
        "base_events": cal.base_events,
        "public_events": cal.public_events,
    }
    for t in PAPER_TABLES:
        raw[t] = paper.get(t, empty(RAW_COLUMNS[t]))
    truth = truth_tables(incidents)
    for t in PAPER_TRUTH:
        truth[t] = paper.get(t, empty(TRUTH_COLUMNS[t]))
    return {t: raw[t] for t in RAW_COLUMNS}, {t: truth[t] for t in TRUTH_COLUMNS}
