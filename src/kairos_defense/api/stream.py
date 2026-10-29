"""The replay WebSocket ``/ws/replay/{incident_id}`` (SPEC §16.3, D-107, D-110).

Accepts, sends ``hello``, then every 100 ms applies the client messages that arrived and runs one
``Session.step`` (in a worker thread: steps read and write DuckDB), and sends what it returns,
one JSON object per message. An unknown incident gets one unrecoverable ``error`` and a close.
With ``KD_VALIDATE_STREAM=1`` (the tests) every outgoing message is validated against
``StreamMessage`` first.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter
from starlette.concurrency import run_in_threadpool

from kairos_defense.api.schemas import StreamMessage
from kairos_defense.live.session import Session
from kairos_defense.memory.actions import json_safe

log = logging.getLogger(__name__)
router = APIRouter()
TICK_S = 0.1
_ADAPTER = TypeAdapter(StreamMessage)


def encode(msg: dict, validate: bool = False) -> str:
    clean = json_safe(msg)
    if validate:
        _ADAPTER.validate_python(clean)
    return json.dumps(clean, separators=(",", ":"), allow_nan=False)


@router.websocket("/ws/replay/{incident_id}")
async def replay(ws: WebSocket, incident_id: str) -> None:
    svc = ws.app.state.services
    validate = os.environ.get("KD_VALIDATE_STREAM") == "1"
    await ws.accept()
    try:
        session: Session = await run_in_threadpool(svc.session, incident_id)
    except KeyError:
        await ws.send_text(encode(Session.error(f"no live incident {incident_id}", False)))
        await ws.close(code=4404)
        return
    inbox: asyncio.Queue = asyncio.Queue()

    async def receive() -> None:
        while True:
            text = await ws.receive_text()
            try:
                await inbox.put(json.loads(text))
            except json.JSONDecodeError:
                await inbox.put({"type": "<not JSON>"})

    reader = asyncio.create_task(receive())
    try:
        await ws.send_text(encode(session.hello(), validate))
        while not reader.done():
            out: list[dict] = []
            while not inbox.empty():
                out += await run_in_threadpool(session.handle, inbox.get_nowait())
            out += await run_in_threadpool(session.step)
            for m in out:
                await ws.send_text(encode(m, validate))
            await asyncio.sleep(TICK_S)
        reader.result()  # re-raise a disconnect
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("replay stream %s failed", incident_id)
        with contextlib.suppress(Exception):  # the socket may be gone
            await ws.send_text(encode(Session.error("internal error; reconnect", True)))
    finally:
        reader.cancel()
        if session.feed is not None:
            session.feed.close()
