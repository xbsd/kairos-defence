"""``kairos-defense index``: features, signatures and PAA windows for every history track.

Reads raw tables through the DuckDB adapter, runs the pure §9 functions per track, then writes
``track_features`` and ``track_signatures`` (DuckDB, §7.2) and ``flight_windows`` (LanceDB, §7.5).
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
from kairos_defense.features.windows import iter_windows
from kairos_defense.store.ddl import DERIVED_COLUMNS
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

log = logging.getLogger(__name__)

WINDOWS_TABLE = "flight_windows"


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
