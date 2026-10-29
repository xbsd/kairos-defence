"""The chat panel's tool loop (SPEC §18.3): an LLM answers from the §18.1 tools.

Only the six read-only tools are offered: the chat can read and explain, never append (proposals
stay with the MCP server's ``--allow-proposals`` and, above all, with humans, rule 8). Tool calls
go through ``tools.call_tool``, the same functions the MCP server wraps. A tool error goes back to
the model as its result, so it can say "unknown" instead of guessing. The loop stops after
``max_steps`` rounds of tool calls.
"""

from __future__ import annotations

import json

from kairos_defense.agent.prompts import SYSTEM_PROMPT
from kairos_defense.agent.tools import READ_ONLY, TOOL_SPECS, call_tool

MAX_STEPS = 6
MAX_RESULT_CHARS = 30_000  # a tool result sent back to the model is cut here (the reply keeps all)


def read_only_specs() -> list[dict]:
    return [{"name": n, **TOOL_SPECS[n]} for n in READ_ONLY]


def clean_history(messages: list[dict]) -> list[dict]:
    """The client's turns: ``user`` and ``assistant`` text only (a client cannot inject system
    prompts or tool results)."""
    out = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content[:8000]})
    return out


def run_chat(llm, ctx, messages: list[dict], max_steps: int = MAX_STEPS) -> dict:
    """Answer the last user turn of ``messages``: ``{"reply", "tool_calls": [{"name",
    "arguments", "result"}], "stop_reason", "provider", "model"}``."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, *clean_history(messages)]
    calls: list[dict] = []
    specs = read_only_specs()
    base = {"provider": llm.provider, "model": llm.model}
    for _ in range(max_steps):
        out = llm.chat(msgs, specs)
        if out["stop_reason"] == "refusal":
            return {**base, "reply": "The model declined to answer this request.",
                    "tool_calls": calls, "stop_reason": "refusal"}  # fmt: skip
        if not out["tool_calls"]:
            return {**base, "reply": out["text"], "tool_calls": calls,
                    "stop_reason": out["stop_reason"]}  # fmt: skip
        msgs.append({"role": "assistant", "content": out["text"], "tool_calls": out["tool_calls"],
                     "native": out.get("native")})  # fmt: skip
        for tc in out["tool_calls"]:
            args = tc["arguments"] if isinstance(tc["arguments"], dict) else {}
            result = call_tool(ctx, tc["name"], args, allowed=READ_ONLY)
            calls.append({"name": tc["name"], "arguments": args, "result": result})
            text = json.dumps(result, default=str)
            if len(text) > MAX_RESULT_CHARS:
                text = text[:MAX_RESULT_CHARS] + " … (cut)"
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "name": tc["name"],
                         "content": text})  # fmt: skip
    return {**base, "reply": f"Stopped after {max_steps} rounds of tool calls without an answer.",
            "tool_calls": calls, "stop_reason": "max_steps"}  # fmt: skip
