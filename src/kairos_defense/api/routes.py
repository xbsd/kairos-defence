"""REST routes for the replay and the scene (SPEC §16.4, D-108, D-109). Sync handlers: FastAPI
runs them in its thread pool; each store read holds ``Services.lock``."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from kairos_defense.api.deps import services
from kairos_defense.api.schemas import (
    DtwMsg,
    ErrorMsg,
    Health,
    IncidentSummary,
    Installation,
    MatchResponse,
    Scene,
    StreamSchema,
)
from kairos_defense.api.services import Services
from kairos_defense.live.loop import DEFAULT_CHANNEL
from kairos_defense.live.replay import iso_z
from kairos_defense.live.scene import installation_scene
from kairos_defense.live.session import decorate, target_case
from kairos_defense.memory.canonical import utc_naive
from kairos_defense.store.composite import is_live_id

router = APIRouter(prefix="/api")
Svc = Depends(services)


@router.get("/health", response_model=Health)
def health(svc: Services = Svc) -> dict:
    return svc.health()


@router.get("/installations", response_model=list[Installation])
def installations(svc: Services = Svc) -> list[dict]:
    with svc.lock:
        df = svc.store.sql("SELECT i.installation_id, i.name, i.region_id, g.utc_offset_hours, "
                           "i.origin_x_m, i.origin_y_m, i.rotation_deg FROM installations i "
                           "JOIN regions g USING (region_id) ORDER BY installation_id")  # fmt: skip
    return df.to_dict("records")


@router.get("/installations/{installation_id}/scene", response_model=Scene)
def scene(installation_id: str, svc: Services = Svc) -> dict:
    try:
        with svc.lock:
            return installation_scene(svc.store, svc.cfg.world, installation_id)
    except KeyError as exc:
        raise HTTPException(404, f"no installation {installation_id}") from exc


@router.get("/incidents", response_model=list[IncidentSummary])
def incidents(status: str = Query("live", pattern="^(live|history)$"),
              limit: int = Query(500, ge=1, le=5000),
              svc: Services = Svc) -> list[dict]:  # fmt: skip
    with svc.lock:
        df = svc.store.sql("SELECT * FROM incidents WHERE status = $s ORDER BY start_ts DESC, "
                           "incident_id LIMIT $n", {"s": status, "n": limit})  # fmt: skip
    out = []
    for r in df.to_dict("records"):
        start, end = utc_naive(r["start_ts"]), utc_naive(r["end_ts"])
        out.append({**r, "start_ts": iso_z(start), "end_ts": iso_z(end),
                    "duration_s": (end - start).total_seconds()})  # fmt: skip
    return out


def _loop(svc: Services, incident_id: str):
    try:
        return svc.loop(incident_id)
    except KeyError as exc:
        raise HTTPException(404, f"no live incident {incident_id}") from exc


@router.get("/match/{incident_id}", response_model=MatchResponse)
def match(incident_id: str, at: float = Query(..., ge=0), svc: Services = Svc) -> dict:
    """Matches at a replay second: the latest rerun at or before ``at`` (D-105)."""
    loop = _loop(svc, incident_id)
    res = loop.result_at(at)
    base = {"incident_id": incident_id, "at": at, "waiting_for_s": loop.waiting_for_s(at)}
    if res is None:
        return {**base, "t_s": None, "model_version": None, "elapsed_ms": None, "cached": None,
                "case_id": None, "matches": []}  # fmt: skip
    clock = loop.incident.ts_at(res["t_s"])
    rows = svc.memory.events()
    case_id = target_case(rows, [m["incident_id"] for m in res["matches"][:3]], clock)
    return {**base, "t_s": float(res["t_s"]), "model_version": res["model_version"],
            "elapsed_ms": res["elapsed_ms"], "cached": bool(res.get("cached")),
            "case_id": case_id, "matches": decorate(res["matches"], rows, case_id, incident_id,
                                                    clock, loop.offsets)}  # fmt: skip


@router.get("/dtw/{incident_id}/{match_track_id}", response_model=DtwMsg)
def dtw(incident_id: str, match_track_id: str, at: float = Query(..., ge=0),
        channel: str = DEFAULT_CHANNEL, svc: Services = Svc) -> dict:  # fmt: skip
    """The lens payload: the same shape as the stream's ``dtw`` message (``DtwMsg``)."""
    loop = _loop(svc, incident_id)
    try:
        doc = loop.lens(at, match_track_id, channel)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"type": "dtw", "t_s": float(loop.rerun_at(at)), **doc}


@router.get("/history/{track_id}")
def history(track_id: str, frame: str = Query("target", pattern="^(target|region)$"),
            svc: Services = Svc) -> dict:  # fmt: skip
    """A past track's 1 Hz path (ghost trails, phase 8): target-relative or region meters. Live
    tracks are refused (rule 3: tonight is not history) until their incident closes and live
    mode learns them (D-176): then they are served from the live-mode store."""
    store = svc.store
    if is_live_id(track_id) and svc.live is not None:
        store = svc.live.feed  # learned live history: closed incidents only
    with svc.lock:
        sig = store.sql("SELECT * FROM track_signatures WHERE track_id = $t", {"t": track_id})
        if sig.empty:
            raise HTTPException(404, f"no history track {track_id} (live tracks are not history)")
        f = store.features(track_id)
    x, y = ("x_rel_m", "y_rel_m") if frame == "target" else ("x_m", "y_m")
    s = sig.iloc[0]
    pts = [[int(r.t_s), _r(getattr(r, x)), _r(getattr(r, y)), _r(r.alt_m)]
           for r in f.itertuples()]  # fmt: skip
    return {"track_id": track_id, "incident_id": s["incident_id"],
            "installation_id": s["installation_id"], "target_asset_id": s["target_asset_id"],
            "start_ts": iso_z(utc_naive(s["start_ts"])), "frame": frame,
            "columns": ["t_s", "x_m", "y_m", "alt_m"], "points": pts}  # fmt: skip


def _r(v) -> float | None:
    v = float(v)
    return None if v != v else round(v, 2)


@router.get("/eval/latest")
def eval_latest(svc: Services = Svc) -> dict:
    """The newest ``reports/eval_<date>.json`` written by the evaluation harness."""
    files = sorted(Path(svc.app.paths.reports).glob("eval_*.json"))
    if not files:
        raise HTTPException(404, "no evaluation yet: run `make eval`")
    return {"file": files[-1].name, **json.loads(files[-1].read_text())}


@router.get("/schema/stream", response_model=StreamSchema)
def schema_stream() -> dict:
    """One ``StreamMessage``: exists so OpenAPI (and the generated types) include every type."""
    return {"message": ErrorMsg(type="error", message="example", recoverable=True).model_dump()}
