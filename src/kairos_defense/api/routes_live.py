"""Live mode's routes (D-169, D-170, D-173, D-182 to D-184).

- ``WS /ws/ingest`` and ``POST /api/ingest``: the sensor adapter contract (``schemas_ingest``):
  each message is schema-checked here, then the hub checks and applies what passed; every frame
  or batch is answered with an ``IngestAck`` (accepted counts and ``{index, reason}`` rejections).
- ``WS /ws/live/{installation_id}``: the live stream (``LiveStreamMessage``): a catch-up
  (``hello`` and the current incident's last 120 s), then every 100 ms what the hub published,
  the ledger appends and a ``clock`` on feed time.
- ``GET /api/live/status``, ``GET /api/live/scenarios``, ``POST /api/live/reset``,
  ``POST /api/sim/launch`` (the simulator as a separate process, one at a time),
  ``POST /api/sim/stop`` (stops it and keeps every live row; its open incidents close, D-192),
  ``GET /api/live/incidents/{id}/reveal`` (the one route that touches ground truth, and only
  through ``kairos_defense.eval``, once the incident has closed, D-170), and
  ``GET /api/schema/live-stream``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from kairos_defense.api.deps import services
from kairos_defense.api.schemas import MatcherTraceMsg
from kairos_defense.api.schemas_ingest import IngestAck, IngestBatch, IngestMessage
from kairos_defense.api.schemas_live import (
    LiveResetResponse,
    LiveStatus,
    LiveStreamMessage,
    LiveStreamSchema,
    RevealResponse,
    ScenarioInfo,
    SimLaunchRequest,
    SimLaunchResponse,
    SimStopResponse,
)
from kairos_defense.api.services import Services
from kairos_defense.live.session import ledger_message
from kairos_defense.memory.actions import json_safe

log = logging.getLogger(__name__)
router = APIRouter()
Svc = Depends(services)
TICK_S = 0.1
_INGEST = TypeAdapter(IngestMessage)
_LIVE = TypeAdapter(LiveStreamMessage)


def _live(svc: Services):
    if svc.live is None:
        raise HTTPException(503, "live mode is unavailable: " + "; ".join(svc.problems))
    return svc.live


def encode(msg: dict, validate: bool = False) -> str:
    clean = json_safe(msg)
    if validate:
        _LIVE.validate_python(clean)
    return json.dumps(clean, separators=(",", ":"), allow_nan=False)


def _reason(exc: ValidationError) -> str:
    e = exc.errors()[0]
    where = ".".join(str(x) for x in e.get("loc", ()) if x not in ("point", "rf", "rid",
                                                                    "heartbeat"))  # fmt: skip
    return f"{where}: {e.get('msg')}" if where else str(e.get("msg"))


def ingest_batch(live, raw: list) -> dict:
    """Schema-check every message, apply the valid ones in order; the ``IngestAck`` body."""
    valid, index, rejected = [], [], []
    for i, m in enumerate(raw):
        try:
            valid.append(_INGEST.validate_python(m).row())
            index.append(i)
        except ValidationError as exc:
            rejected.append({"index": i, "reason": _reason(exc)})
    res = live.hub.ingest(valid) if valid else {"accepted": 0, "detections": 0, "rejected": []}
    rejected += [{"index": index[r["index"]], "reason": r["reason"]} for r in res["rejected"]]
    return {"type": "ack", "accepted": res["accepted"], "detections": res["detections"],
            "rejected": sorted(rejected, key=lambda r: r["index"])}  # fmt: skip


# --- ingest -----------------------------------------------------------------------------------
@router.websocket("/ws/ingest")
async def ingest_ws(ws: WebSocket) -> None:
    live = ws.app.state.services.live
    await ws.accept()
    if live is None:
        await ws.send_text(json.dumps({"type": "error", "message": "live mode is unavailable",
                                       "recoverable": False}))  # fmt: skip
        await ws.close(code=4503)
        return
    try:
        while True:
            text = await ws.receive_text()
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "ack", "accepted": 0, "detections": 0,
                                               "rejected": [{"index": 0,
                                                             "reason": "not JSON"}]}))  # fmt: skip
                continue
            raw = doc if isinstance(doc, list) else [doc]
            ack = await run_in_threadpool(ingest_batch, live, raw)
            await ws.send_text(json.dumps(ack, separators=(",", ":")))
    except WebSocketDisconnect:
        pass


@router.post("/api/ingest", response_model=IngestAck)
def ingest_rest(batch: IngestBatch, svc: Services = Svc) -> dict:
    """A batch of ingest messages for simple adapters (same contract as ``/ws/ingest``)."""
    return ingest_batch(_live(svc), batch.messages)


# --- the live stream --------------------------------------------------------------------------
@router.websocket("/ws/live/{installation_id}")
async def live_stream(ws: WebSocket, installation_id: str) -> None:
    svc = ws.app.state.services
    validate = os.environ.get("KD_VALIDATE_STREAM") == "1"
    await ws.accept()
    live = svc.live
    if live is None or installation_id not in live.hub.sites:
        what = "live mode is unavailable" if live is None else f"no installation {installation_id}"
        await ws.send_text(encode({"type": "error", "message": what, "recoverable": False}))
        await ws.close(code=4404)
        return
    feed = live.hub.subscribe(installation_id)
    ledger = svc.bus.subscribe()
    last_clock = None

    async def receive() -> None:
        while True:
            await ws.receive_text()  # the live stream takes no client messages; keep reading

    reader = asyncio.create_task(receive())
    try:
        for m in await run_in_threadpool(live.hub.catch_up, installation_id):
            await ws.send_text(encode(m, validate))
        while not reader.done():
            out = feed.drain() + [ledger_message(r) for r in ledger.drain()]
            clock = live.hub.clock(installation_id)
            if clock is not None and (clock["playing"] or clock != last_clock):
                out.append(clock)
                last_clock = clock
            for m in out:
                await ws.send_text(encode(m, validate))
            await asyncio.sleep(TICK_S)
        reader.result()
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("live stream %s failed", installation_id)
        with contextlib.suppress(Exception):
            await ws.send_text(encode({"type": "error", "message": "internal error; reconnect",
                                       "recoverable": True}))  # fmt: skip
    finally:
        reader.cancel()
        feed.close()
        ledger.close()


# --- REST -------------------------------------------------------------------------------------
@router.get("/api/live/status", response_model=LiveStatus)
def live_status(svc: Services = Svc) -> dict:
    """Feeds, every live incident since the last reset, the worker queue and the simulator."""
    return _live(svc).status()


@router.get("/api/live/scenarios", response_model=list[ScenarioInfo])
def live_scenarios(svc: Services = Svc) -> list[dict]:
    """The five scenarios with their actor or team choices and bases (for the launcher)."""
    from kairos_defense.sim.live_scenarios import catalog

    return catalog(svc.cfg)


@router.post("/api/live/reset", response_model=LiveResetResponse)
def live_reset(svc: Services = Svc) -> dict:
    """Remove every live-mode row (detections, incidents, learned history, results, vectors).
    The 18-month history and the ledger are untouched (rule 7)."""
    return _live(svc).reset()


@router.post("/api/sim/launch", response_model=SimLaunchResponse)
def sim_launch(req: SimLaunchRequest, request: Request, svc: Services = Svc) -> dict:
    """Start the simulator for one scenario as a separate process (D-182). The actor or team is
    passed to it and not kept here."""
    from kairos_defense.api.launcher import SimulatorBusy
    from kairos_defense.sim.live_clock import CLOCK_FILE, LiveClock
    from kairos_defense.sim.live_scenarios import ScenarioError, resolve

    live = _live(svc)
    cfg = svc.cfg
    clock = LiveClock(live.folder / CLOCK_FILE, cfg.world.calendar.end_local)
    seed = req.seed or clock.default_seed(cfg.world.seed)
    try:
        if req.actor == "random":  # the seed picks the actor in the child, never here
            if req.scenario != "returning-prober" or req.second_base:
                raise ScenarioError("only returning-prober takes a random actor, at one base")
            flies = {b for p in cfg.actors.probers for b in p.bases}
            if req.base is not None and req.base not in flies:
                raise ScenarioError(f"no prober flies at {req.base}")
            base, second = req.base, None
        else:
            _, base, second = resolve(cfg, req.scenario, req.actor, req.base, req.second_base,
                                      seed)  # fmt: skip
    except ScenarioError as exc:
        raise HTTPException(422, str(exc)) from exc
    host = request.url.hostname or "127.0.0.1"
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    url = f"{'wss' if request.url.scheme == 'https' else 'ws'}://{host}:{port}/ws/ingest"
    args = {"scenario": req.scenario, "actor": req.actor, "base": base, "second_base": second,
            "speed": req.speed, "seed": seed, "url": url}  # fmt: skip
    try:
        out = live.launcher.launch(args)
    except SimulatorBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"launched": True, "scenario": req.scenario, "base": base or "", "second_base": second,
            "speed": float(req.speed), "seed": int(seed), "pid": int(out["pid"])}  # fmt: skip


@router.post("/api/sim/stop", response_model=SimStopResponse)
def sim_stop(svc: Services = Svc) -> dict:
    """Stop the running simulator (SIGTERM, then SIGKILL) and keep everything live mode has
    recorded (D-192). Its exit hook closes the incidents it was feeding, so they can be revealed;
    the simulator wrote its ground truth before its first detection."""
    live = _live(svc)
    stopped = live.launcher.stop()
    return {"stopped": stopped, "simulator": live.launcher.state()}


@router.get("/api/live/incidents/{incident_id}/reveal", response_model=RevealResponse)
def live_reveal(incident_id: str, svc: Services = Svc) -> dict:
    """Who really flew a closed live incident and how the matcher did (D-170): computed by
    ``kairos_defense.eval`` on request, never stored. 404 unknown, 409 while open."""
    from kairos_defense.eval.reveal import NotClosed, reveal

    live = _live(svc)
    try:
        return reveal(svc.cfg, live.feed, incident_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    except NotClosed as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/api/live/trace", response_model=MatcherTraceMsg)
def live_trace(installation: str = "BRAVO", svc: Services = Svc) -> dict:
    """The latest live rerun's matcher trace at an installation (D-188); 404 before any."""
    live = _live(svc)
    if installation not in live.hub.sites:
        raise HTTPException(404, f"no installation {installation}")
    doc = live.hub.trace(installation)
    if doc is None:
        raise HTTPException(404, f"no live rerun at {installation} yet")
    return doc


@router.get("/api/schema/live-stream", response_model=LiveStreamSchema)
def schema_live_stream() -> dict:
    """One ``LiveStreamMessage`` and one ingest message: exists so OpenAPI (and the generated
    types) include every live type."""
    return {"message": {"type": "incident_opened", "incident_id": "LIVE-BRAVO-260901-210000",
                        "installation_id": "BRAVO", "start_ts": "2026-09-02T02:00:00.000Z"},
            "ingest": {"v": 1, "type": "heartbeat", "installation_id": "BRAVO",
                       "ts": "2026-09-02T02:00:00Z", "rate": 1.0}}  # fmt: skip
