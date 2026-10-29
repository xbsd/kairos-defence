"""``kairos-defense index``: features, signatures and PAA windows for every history track.

Reads raw tables through the DuckDB adapter, runs the pure §9 functions per track, then writes
``track_features`` and ``track_signatures`` (DuckDB, §7.2) and ``flight_windows`` (LanceDB, §7.5).
Phase 9 adds the §14 swarm tables: ``swarm_features`` (DuckDB, one row per described second of
each history swarm incident) and ``swarm_windows`` (LanceDB, one 96-d PAA vector per incident).
Live tracks are skipped everywhere: no derived table holds a live track's future (D-049). The
build talks to the adapters directly; matching and evaluation use only the ports (D-053).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyarrow as pa

from kairos_defense.config import Config
from kairos_defense.features.channels import load_site, track_features
from kairos_defense.features.resample import epoch_ms
from kairos_defense.features.signatures import SIGNATURE_COLUMNS, SensorContext, signature
from kairos_defense.features.swarm_features import SERIES_COLUMNS as SWARM_SERIES
from kairos_defense.features.swarm_features import build_flight, swarm_series, swarm_vector
from kairos_defense.features.windows import iter_windows
from kairos_defense.store.ddl import DERIVED_COLUMNS
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

log = logging.getLogger(__name__)

WINDOWS_TABLE = "flight_windows"
SWARM_TABLE = "swarm_windows"  # §7.5, one row per history swarm incident (D-148)


@dataclass
class IndexSummary:
    tracks: int = 0
    history_tracks: int = 0
    live_tracks_skipped: int = 0
    feature_rows: int = 0
    gap_seconds: int = 0
    signatures: int = 0
    windows_by_size: dict[int, int] = field(default_factory=dict)
    target_kinds: dict[str, int] = field(default_factory=dict)
    loiter_dirs: dict[str, int] = field(default_factory=dict)
    rf_unknown: int = 0
    rid_present: int = 0
    failed: list[str] = field(default_factory=list)
    swarm_incidents: int = 0  # history swarm incidents indexed (§14)
    swarm_detected: int = 0  # of those, how many pass the §14 detection
    swarm_seconds: int = 0  # swarm_features rows
    elapsed_s: float = 0.0


def windows_table(rows: list[dict], vectors: list[np.ndarray], dim: int) -> pa.Table:
    """Arrow table for ``flight_windows`` (§7.5) from metadata rows and (dim,) float32 vectors."""
    meta = pd.DataFrame(rows)
    flat = np.concatenate(vectors).astype(np.float32) if vectors else np.zeros(0, np.float32)
    return pa.table(
        {
            "window_id": pa.array(meta.get("window_id", []), pa.string()),
            "track_id": pa.array(meta.get("track_id", []), pa.string()),
            "incident_id": pa.array(meta.get("incident_id", []), pa.string()),
            "installation_id": pa.array(meta.get("installation_id", []), pa.string()),
            "region_id": pa.array(meta.get("region_id", []), pa.string()),
            "window_s": pa.array(meta.get("window_s", []), pa.int32()),
            "offset_s": pa.array(meta.get("offset_s", []), pa.int32()),
            "start_ts_ms": pa.array(meta.get("start_ts_ms", []), pa.int64()),
            "win_ts_ms": pa.array(meta.get("win_ts_ms", []), pa.int64()),
            "rf_family": pa.array(meta.get("rf_family", []), pa.string()),
            "tod_minutes": pa.array(meta.get("tod_minutes", []), pa.int32()),
            "vector": pa.FixedSizeListArray.from_arrays(pa.array(flat, pa.float32()), dim),
        }
    )


def swarm_windows_table(rows: list[dict], vectors: list[np.ndarray], dim: int) -> pa.Table:
    """Arrow table for ``swarm_windows`` from metadata rows and (dim,) float32 vectors."""
    meta = pd.DataFrame(rows)
    flat = np.concatenate(vectors).astype(np.float32) if vectors else np.zeros(0, np.float32)
    return pa.table(
        {
            "incident_id": pa.array(meta.get("incident_id", []), pa.string()),
            "installation_id": pa.array(meta.get("installation_id", []), pa.string()),
            "region_id": pa.array(meta.get("region_id", []), pa.string()),
            "start_ts_ms": pa.array(meta.get("start_ts_ms", []), pa.int64()),
            "n_drones": pa.array(meta.get("n_drones", []), pa.int32()),
            "duration_s": pa.array(meta.get("duration_s", []), pa.float64()),
            "together_s": pa.array(meta.get("together_s", []), pa.int32()),
            "is_swarm": pa.array(meta.get("is_swarm", []), pa.bool_()),
            "vector": pa.FixedSizeListArray.from_arrays(pa.array(flat, pa.float32()), dim),
        }
    )


def build_swarm_index(cfg: Config, store: DuckTrackStore, out: IndexSummary) -> None:
    """``swarm_features`` (DuckDB) and ``swarm_windows`` (LanceDB) for every history swarm
    incident (§14); live swarms are never indexed (D-049)."""
    sc = cfg.scoring
    incs = store.sql(
        "SELECT incident_id, installation_id, region_id FROM incidents "
        "WHERE is_swarm AND status = 'history' ORDER BY start_ts, incident_id"
    )
    frames: list[pd.DataFrame] = []
    rows: list[dict] = []
    vectors: list[np.ndarray] = []
    sites = {}
    for meta in incs.to_dict("records"):
        inst = meta["installation_id"]
        sites.setdefault(inst, load_site(store, inst))
        pts = store.sql(
            "SELECT track_id, ts, x_m, y_m, alt_m, quality FROM track_points "
            "WHERE incident_id = $i ORDER BY track_id, ts",
            {"i": meta["incident_id"]},
        )
        try:
            fl = build_flight(meta, pts, sites[inst], sc)
        except ValueError as exc:
            log.warning("skipping swarm %s: %s", meta["incident_id"], exc)
            out.failed.append(str(meta["incident_id"]))
            continue
        d = fl.descriptors
        frames.append(d.assign(incident_id=fl.incident_id)[DERIVED_COLUMNS["swarm_features"]])
        rows.append({"incident_id": fl.incident_id, "installation_id": inst,
                     "region_id": fl.region_id, "start_ts_ms": epoch_ms(fl.start_ts),
                     "n_drones": fl.n_drones, "duration_s": float(len(fl.t_s)),
                     "together_s": fl.together_s, "is_swarm": fl.is_swarm})  # fmt: skip
        vectors.append(swarm_vector(swarm_series(d), sc.windows.paa_segments))
        out.swarm_incidents += 1
        out.swarm_detected += int(fl.is_swarm)
    cols = DERIVED_COLUMNS["swarm_features"]
    feats = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    out.swarm_seconds = store.write_table("swarm_features", feats)
    dim = len(SWARM_SERIES) * sc.windows.paa_segments
    table = swarm_windows_table(rows, vectors, dim)
    LanceVectorStore(cfg.app.paths.lancedb).replace(SWARM_TABLE, table)


def build_index(cfg: Config) -> IndexSummary:
    """Rebuild every derived table from the raw tables; deterministic (no random draws)."""
    t0 = time.perf_counter()
    sc = cfg.scoring
    out = IndexSummary()
    feat_frames: list[pd.DataFrame] = []
    sigs: list[dict] = []
    win_rows: list[dict] = []
    vectors: list[np.ndarray] = []
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app, read_only=False) as store:
        tracks = store.tracks()
        hist = tracks[tracks["status"] == "history"].set_index("track_id")
        out.tracks, out.history_tracks = len(tracks), len(hist)
        out.live_tracks_skipped = len(tracks) - len(hist)
        sites = {i: load_site(store, i) for i in sorted(hist["installation_id"].unique())}
        ctx = store.sensor_context()
        pts = store.sql(
            "SELECT p.track_id, p.ts, p.x_m, p.y_m, p.alt_m, p.quality FROM track_points p "
            "JOIN incidents i USING (incident_id) WHERE i.status = 'history' "
            "ORDER BY p.track_id, p.ts"
        )
        for tid, p in pts.groupby("track_id", sort=True):
            meta = hist.loc[tid]
            site = sites[meta["installation_id"]]
            try:
                f, target = track_features(p, site, sc)
            except ValueError as exc:
                log.warning("skipping %s: %s", tid, exc)
                out.failed.append(str(tid))
                continue
            sig = signature(f, target, p.iloc[0], p.iloc[-1], site, ctx.get(tid, SensorContext()),
                            {"track_id": tid, "incident_id": meta["incident_id"]})  # fmt: skip
            sigs.append(sig)
            f = f.assign(track_id=tid, incident_id=meta["incident_id"],
                         installation_id=meta["installation_id"])  # fmt: skip
            feat_frames.append(f[DERIVED_COLUMNS["track_features"]])
            start_ms = epoch_ms(sig["start_ts"])
            for w in iter_windows(f, sc):
                win_rows.append({
                    "window_id": f"{tid}:{w.window_s}:{w.offset_s}", "track_id": tid,
                    "incident_id": meta["incident_id"], "installation_id": site.installation_id,
                    "region_id": site.region_id, "window_s": w.window_s, "offset_s": w.offset_s,
                    "start_ts_ms": start_ms, "win_ts_ms": start_ms + 1000 * w.offset_s,
                    "rf_family": sig["rf_family"], "tod_minutes": sig["tod_minutes"],
                })  # fmt: skip
                vectors.append(w.vector)
        features = pd.concat(feat_frames, ignore_index=True)
        signatures = pd.DataFrame(sigs, columns=SIGNATURE_COLUMNS)
        out.feature_rows = store.write_table("track_features", features)
        out.signatures = store.write_table("track_signatures", signatures)
        build_swarm_index(cfg, store, out)
    out.gap_seconds = int(features["in_gap"].sum())
    out.target_kinds = signatures["target_kind"].value_counts().sort_index().to_dict()
    out.loiter_dirs = signatures["loiter_dir"].value_counts().sort_index().to_dict()
    out.rf_unknown = int((signatures["rf_family"] == "unknown").sum())
    out.rid_present = int(signatures["rid_present"].sum())
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    table = windows_table(win_rows, vectors, sc.vector_dim)
    lance.replace(WINDOWS_TABLE, table)
    sizes = pd.Series([r["window_s"] for r in win_rows], dtype="int64")
    out.windows_by_size = {int(k): int(v) for k, v in sizes.value_counts().sort_index().items()}
    out.elapsed_s = time.perf_counter() - t0
    return out
