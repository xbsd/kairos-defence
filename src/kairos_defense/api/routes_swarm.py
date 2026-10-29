"""Swarm view routes (SPEC §14, §17.9, D-153).

- ``GET /api/swarms``: every swarm incident (live and history), newest first.
- ``GET /api/swarm/{incident_id}?at=&match=``: the §14 result for one swarm incident seen up to
  ``at`` seconds after its first radar point (default: its whole observed flight): the query's
  descriptors and target-relative drone positions, the ranked earlier swarms, and for the selected
  match (``match`` = an incident id among the matches, default rank 1) its whole flight and the
  DTW alignment. 404 for an unknown incident, 422 for an incident that is not a swarm or a match
  not among the results, 503 when the swarm index is missing (run ``make index``).

Results are cached in memory per (incident, at, match): the same request gives the same answer,
and the encore never waits on DTW twice. Nothing here writes to the ledger (§15.6).
"""

from __future__ import annotations

import time

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from kairos_defense.api.deps import services
from kairos_defense.api.schemas_swarm import SwarmIncident, SwarmResponse
from kairos_defense.api.services import Services
from kairos_defense.features.swarm_features import DESCRIPTOR_COLUMNS, SwarmFlight, load_swarm
from kairos_defense.live.replay import iso_z
from kairos_defense.match.swarm import MODEL_VERSION, SwarmIndexMissing, SwarmMatcher
from kairos_defense.memory.canonical import utc_naive

router = APIRouter(prefix="/api")
Svc = Depends(services)
CACHE_MAX = 64


def _r(v, nd: int = 2) -> float | None:
    v = float(v)
    return round(v, nd) if np.isfinite(v) else None


def flight_out(fl: SwarmFlight) -> dict:
    """A ``SwarmFlightOut`` dict: descriptors as columns, positions target-relative."""
    d = fl.descriptors
    curves = {"t_s": [int(x) for x in d.t_s], "n_drones": [int(x) for x in d.n_drones]}
    for c in DESCRIPTOR_COLUMNS[2:]:
        curves[c] = [_r(x, 3) for x in d[c]]
    rel = fl.relative_positions()
    positions = [[[_r(p[0], 1), _r(p[1], 1), _r(p[2], 1)] for p in drone] for drone in rel]
    t = fl.target
    return {
        "incident_id": fl.incident_id, "installation_id": fl.installation_id,
        "region_id": fl.region_id, "start_ts": iso_z(utc_naive(fl.start_ts.to_pydatetime())),
        "n_drones": fl.n_drones, "track_ids": list(fl.track_ids), "is_swarm": fl.is_swarm,
        "together_s": fl.together_s,
        "target": {"asset_id": t.asset_id, "kind": t.kind, "x_m": float(t.centroid[0]),
                   "y_m": float(t.centroid[1])},
        "curves": curves, "t_s": [int(x) for x in fl.t_s], "positions": positions,
    }  # fmt: skip


def _matcher(svc: Services) -> SwarmMatcher:
    m = getattr(svc, "swarm_matcher", None)
    if m is None:
        m = svc.swarm_matcher = SwarmMatcher(svc.store, svc.lance, svc.cfg.scoring)
        svc.swarm_cache = {}
    return m


@router.get("/swarms", response_model=list[SwarmIncident])
def swarms(svc: Services = Svc) -> list[dict]:
    with svc.lock:
        df = svc.store.sql("SELECT incident_id, installation_id, region_id, start_ts, n_tracks, "
                           "status FROM incidents WHERE is_swarm "
                           "ORDER BY start_ts DESC, incident_id")  # fmt: skip
    return [{**r, "start_ts": iso_z(utc_naive(r["start_ts"])), "n_tracks": int(r["n_tracks"])}
            for r in df.to_dict("records")]  # fmt: skip


@router.get("/swarm/{incident_id}", response_model=SwarmResponse)
def swarm(
    incident_id: str,
    at: float | None = Query(None, ge=0),
    match: str | None = Query(None, max_length=200),
    svc: Services = Svc,
) -> dict:
    key = (incident_id, at, match)
    with svc.lock:
        m = _matcher(svc)
        if key in svc.swarm_cache:
            return svc.swarm_cache[key]
        inc = svc.store.sql("SELECT is_swarm FROM incidents WHERE incident_id = $i",
                            {"i": incident_id})  # fmt: skip
        if len(inc) != 1:
            raise HTTPException(404, f"no incident {incident_id}")
        if not bool(inc.iloc[0]["is_swarm"]):
            raise HTTPException(422, f"{incident_id} is not a swarm incident")
        t0 = time.perf_counter()
        try:
            res = m.match(incident_id, at_s=at)
        except SwarmIndexMissing as exc:
            raise HTTPException(503, str(exc)) from exc
        ranked = [x.incident_id for x in res.matches]
        if match is not None and match not in ranked:
            raise HTTPException(422, f"{match} is not among the swarm matches of {incident_id}")
        chosen = match or (ranked[0] if ranked else None)
        sel = None
        if chosen is not None:
            sel = flight_out(load_swarm(svc.store, chosen, svc.cfg.scoring))
        doc = {
            "incident_id": incident_id, "at_s": at,
            "observed_s": int(res.query.t_s[-1]) if len(res.query.t_s) else 0,
            "model_version": MODEL_VERSION, "query": flight_out(res.query),
            "matches": [x.to_dict() for x in res.matches], "match": sel,
            "match_rank": ranked.index(chosen) + 1 if chosen else None,
            "aligned": res.aligned(chosen) if chosen else [],
            "path": [list(p) for p in res.paths.get(chosen, [])] if chosen else [],
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 1),
        }  # fmt: skip
        if len(svc.swarm_cache) >= CACHE_MAX:
            svc.swarm_cache.pop(next(iter(svc.swarm_cache)))
        svc.swarm_cache[key] = doc
        return doc
