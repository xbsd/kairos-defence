"""The optional chat panel's routes (SPEC §18.3).

- ``GET /api/chat/status``: whether the panel is shown (``llm.provider`` in ``config/app.yaml``;
  ``none`` by default, so the web app hides it and nothing calls out, rule 5).
- ``POST /api/chat``: answer the last user turn with the read-only §18.1 tools (``agent.chat``);
  409 while no provider is configured, 503 when the configured one cannot be used.

The tools run on the API's own handles (store, indexes, matcher, recall, ledger) under its lock,
through a ``ToolContext`` built here; the chat never appends to the ledger.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from kairos_defense.agent.tools import READ_ONLY
from kairos_defense.api.deps import services
from kairos_defense.api.schemas_chat import ChatRequest, ChatResponse, ChatStatus
from kairos_defense.api.services import Services

router = APIRouter(prefix="/api")
Svc = Depends(services)


def _llm(request: Request, svc: Services):
    """The adapter: one injected on ``app.state.chat_llm`` (tests), else from the config."""
    from kairos_defense.agent.llm import make_llm

    llm = getattr(request.app.state, "chat_llm", None)
    return llm if llm is not None else make_llm(svc.cfg.app.llm)


def _context(svc: Services):
    from kairos_defense.agent.context import ToolContext

    ctx = getattr(svc, "chat_context", None)
    if ctx is None:
        ctx = ToolContext(svc.cfg, store=svc.store, vstore=svc.lance, matcher=svc.matcher,
                          recall=svc.recall, memory=svc.memory, lock=svc.lock,
                          agent="chat")  # fmt: skip
        svc.chat_context = ctx
    return ctx


@router.get("/chat/status", response_model=ChatStatus)
def chat_status(request: Request, svc: Services = Svc) -> dict:
    from kairos_defense.agent.llm import LLMUnavailable

    cfg = svc.cfg.app.llm
    try:
        llm = _llm(request, svc)
    except LLMUnavailable as exc:
        return {"enabled": False, "provider": cfg.provider, "model": cfg.model,
                "tools": list(READ_ONLY), "problem": str(exc)}  # fmt: skip
    return {"enabled": bool(llm.enabled), "provider": llm.provider, "model": llm.model,
            "tools": list(READ_ONLY), "problem": None}  # fmt: skip


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, svc: Services = Svc) -> dict:
    from kairos_defense.agent.chat import run_chat
    from kairos_defense.agent.llm import LLMUnavailable

    try:
        llm = _llm(request, svc)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if not llm.enabled:
        raise HTTPException(409, "the chat is off: set llm.provider in config/app.yaml")
    if body.messages[-1].role != "user":
        raise HTTPException(422, "the last message must be the user's question")
    try:
        return run_chat(llm, _context(svc), [m.model_dump() for m in body.messages])
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
