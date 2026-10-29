"""``GET /api/explain/{incident_id}/{track_id}`` (SPEC §17.9 Match explainer, §10.7, D-135).

One match of the live result at a replay second, taken apart: the decorated match, the fusion
contributions (``coef × x`` per feature, the intercept, the logit and the score), tonight's
target-relative path up to the rerun second only (rule 3), the past flight's whole
target-relative path, the matcher's anchored window on it, and where tonight's
``dist_target_m`` window falls inside the whole past flight (§10.4 step 6, ``explain_alignment``).
Errors as ``/api/dtw``: 404 for an unknown incident, a track not among the matches, or no result
yet (before ``min_track_s``).
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from kairos_defense.api.deps import services
from kairos_defense.api.schemas_pages import ExplainResponse
from kairos_defense.api.services import Services
from kairos_defense.live.session import decorate, target_case
from kairos_defense.match.dtw_rerank import explain_alignment
from kairos_defense.match.explain import contribution_table

router = APIRouter(prefix="/api")
Svc = Depends(services)
COLUMNS = ["t_s", "x_rel_m", "y_rel_m", "dist_target_m"]


def _r(v) -> float | None:
    v = float(v)
    return None if not np.isfinite(v) else round(v, 2)


def path_points(f) -> list[list[float | None]]:
    """``[[t_s, x_rel_m, y_rel_m, dist_target_m], …]`` from 1 Hz features."""
    return [[int(r.t_s), _r(r.x_rel_m), _r(r.y_rel_m), _r(r.dist_target_m)]
            for r in f.itertuples()]  # fmt: skip


@router.get("/explain/{incident_id}/{track_id}", response_model=ExplainResponse)
def explain(incident_id: str, track_id: str, at: float = Query(..., ge=0),
            svc: Services = Svc) -> dict:  # fmt: skip
    try:
        loop = svc.loop(incident_id)
    except KeyError as exc:
        raise HTTPException(404, f"no live incident {incident_id}") from exc
    res = loop.result_at(at)
    if res is None:
        raise HTTPException(404, f"no result at T+{at:g} s (the matcher starts at "
                                 f"T+{loop.min_track_s:g} s)")  # fmt: skip
    m = next((x for x in res["matches"] if x["track_id"] == track_id), None)
    if m is None:
        raise HTTPException(404, f"{track_id} is not among the matches at T+{res['t_s']} s")
    r = int(res["t_s"])
    clock = loop.incident.ts_at(r)
    rows = svc.memory.events()
    case_id = target_case(rows, [x["incident_id"] for x in res["matches"][:3]], clock)
    match = decorate([m], rows, case_id, incident_id, clock, loop.offsets)[0]
    with svc.lock:
        q = loop.query(r)
        past = svc.store.features(track_id)
        sig = svc.store.sql("SELECT incident_id, installation_id, target_asset_id FROM "
                            "track_signatures WHERE track_id = $t", {"t": track_id})  # fmt: skip
        model = loop.matcher.model
    table = contribution_table(m["features"], model)
    tonight = q.features
    window = tonight["dist_target_m"].to_numpy()[-int(q.rows_used) :]
    alignment = None
    if len(past) >= 2 and len(window) >= 2:
        s0, s1, value = explain_alignment(window, past["dist_target_m"].to_numpy())
        ts = past["t_s"].to_numpy()
        alignment = {"start_s": int(ts[s0]), "end_s": int(ts[min(s1, len(ts) - 1)]),
                     "value": float(value)}  # fmt: skip
    w = int(m["features"].get("window_s") or res["window_s"])
    s = sig.iloc[0] if len(sig) else None
    return {
        "incident_id": incident_id, "at": float(at), "t_s": r,
        "model_version": res["model_version"], "window_s": w, "match": match,
        "contributions": table["rows"], "intercept": table["intercept"],
        "logit": table["logit"], "score": table["score"],
        "tonight": {"track_id": q.track_id, "incident_id": incident_id,
                    "installation_id": loop.incident.installation_id,
                    "target_asset_id": q.target.asset_id, "local_start": None,
                    "columns": COLUMNS, "points": path_points(tonight)},
        "past": {"track_id": track_id, "incident_id": m["incident_id"],
                 "installation_id": m["installation_id"],
                 "target_asset_id": str(s["target_asset_id"]) if s is not None else "",
                 "local_start": m.get("local_start"), "columns": COLUMNS,
                 "points": path_points(past)},
        "segment": {"start_s": int(m["window_offset_s"]),
                    "end_s": int(m["window_offset_s"]) + w},
        "alignment": alignment,
    }  # fmt: skip
