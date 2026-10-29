"""LLM adapters behind the ``LLM`` port (SPEC §18.3): none, anthropic, openai and ollama.

Off by default (``llm.provider: none`` in ``config/app.yaml``): nothing calls out unless a person
configures a provider (rule 5). Keys come only from the environment (``ANTHROPIC_API_KEY``,
``OPENAI_API_KEY``); ``ollama`` needs none. Requests go over ``httpx`` (no provider SDK), so a test
can pass an ``httpx.MockTransport``.

``chat(messages, tools)`` takes provider-neutral messages and returns a neutral reply:

- messages: ``{"role": "system"|"user", "content": str}``; ``{"role": "assistant", "content": str,
  "tool_calls": [{"id", "name", "arguments": dict}], "native": …}`` (``native`` is the provider's
  own assistant content, replayed unchanged); ``{"role": "tool", "tool_call_id", "name",
  "content": str}``.
- tools: ``{"name", "description", "parameters": JSON Schema}``.
- reply: ``{"text": str, "tool_calls": [...], "stop_reason": str, "native": …}``.

Anthropic: ``POST {base}/v1/messages`` with ``anthropic-version: 2026-10-21``, default model
``claude-opus-5-5``, tool results as ``tool_result`` blocks in one user message, no sampling
parameters (rejected by that API version), and the server-side refusal fallback
(``fallbacks: "default"``, beta ``server-side-fallback-2026-07-01``). OpenAI and Ollama: the
OpenAI-compatible ``POST {base}/chat/completions``; a model must be configured.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2026-10-21"
ANTHROPIC_MODEL = "claude-opus-5-5"
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
OPENAI_BASE = "https://api.openai.com/v1"
OLLAMA_BASE = "http://127.0.0.1:11434/v1"
MAX_TOKENS = 16000
TIMEOUT_S = 120.0


class LLMUnavailable(RuntimeError):
    """The configured provider cannot be used (no key, no model, an HTTP error)."""


class NoLLM:
    """``provider: none``: the chat panel is hidden and nothing is called."""

    provider, model, enabled = "none", "", False

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        raise LLMUnavailable("no LLM is configured (llm.provider: none in config/app.yaml)")


class _HttpLLM:
    enabled = True

    def __init__(self, provider: str, model: str, base_url: str, key: str | None,
                 transport=None) -> None:  # fmt: skip
        self.provider, self.model, self.base_url, self._key = provider, model, base_url, key
        self._transport = transport

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        import httpx

        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT_S) as client:
                r = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"{self.provider}: {exc}") from exc
        if r.status_code >= 400:
            raise LLMUnavailable(f"{self.provider} answered {r.status_code}: {r.text[:300]}")
        return r.json()


class AnthropicLLM(_HttpLLM):
    """The Claude Messages API over HTTP (a manual tool loop runs in ``agent.chat``)."""

    def request(self, messages: list[dict], tools: list[dict] | None) -> tuple[str, dict, dict]:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        out: list[dict] = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                content = m.get("native")
                if content is None:
                    content = [{"type": "text", "text": m.get("content") or ""}] + [
                        {"type": "tool_use", "id": c["id"], "name": c["name"],
                         "input": c["arguments"]} for c in m.get("tool_calls", [])]  # fmt: skip
                out.append({"role": "assistant", "content": content})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"],
                         "content": m["content"]}  # fmt: skip
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)  # every result of one turn in one message
                else:
                    out.append({"role": "user", "content": [block]})
        body: dict = {"model": self.model, "max_tokens": MAX_TOKENS, "messages": out,
                      "fallbacks": "default"}  # fmt: skip
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"],
                              "input_schema": t["parameters"]} for t in tools]  # fmt: skip
        headers = {"x-api-key": self._key or "", "anthropic-version": ANTHROPIC_VERSION,
                   "anthropic-beta": ANTHROPIC_FALLBACK_BETA,
                   "content-type": "application/json"}  # fmt: skip
        return f"{self.base_url.rstrip('/')}/v1/messages", headers, body

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        url, headers, body = self.request(messages, tools)
        data = self._post(url, headers, body)
        content = data.get("content") or []
        stop = str(data.get("stop_reason") or "")
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        calls = [] if stop == "refusal" else [
            {"id": b["id"], "name": b["name"], "arguments": b.get("input") or {}}
            for b in content if b.get("type") == "tool_use"]  # fmt: skip
        return {"text": text, "tool_calls": calls, "stop_reason": stop, "native": content}


class OpenAICompatibleLLM(_HttpLLM):
    """OpenAI chat completions, also Ollama's OpenAI-compatible endpoint."""

    def request(self, messages: list[dict], tools: list[dict] | None) -> tuple[str, dict, dict]:
        out: list[dict] = []
        for m in messages:
            if m["role"] in ("system", "user"):
                out.append({"role": m["role"], "content": m["content"]})
            elif m["role"] == "assistant":
                msg: dict = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"],
                                                       "arguments": json.dumps(c["arguments"])}}
                                         for c in m["tool_calls"]]  # fmt: skip
                out.append(msg)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"],
                            "content": m["content"]})  # fmt: skip
        body: dict = {"model": self.model, "messages": out}
        if tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t["name"],
                                                  "description": t["description"],
                                                  "parameters": t["parameters"]}}
                for t in tools
            ]  # fmt: skip
        headers = {"content-type": "application/json"}
        if self._key:
            headers["authorization"] = f"Bearer {self._key}"
        return f"{self.base_url.rstrip('/')}/chat/completions", headers, body

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        url, headers, body = self.request(messages, tools)
        data = self._post(url, headers, body)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {"_unparsed": fn.get("arguments")}
            calls.append({"id": c.get("id", ""), "name": fn.get("name", ""), "arguments": args})
        return {"text": msg.get("content") or "", "tool_calls": calls,
                "stop_reason": str(choice.get("finish_reason") or ""), "native": None}  # fmt: skip


def make_llm(llm_cfg, *, transport=None, env: Mapping[str, str] | None = None):
    """The adapter for ``config/app.yaml``'s ``llm`` block (``provider``, ``model``,
    ``base_url``). Raises ``LLMUnavailable`` when a provider is chosen but cannot be used."""
    env = os.environ if env is None else env
    provider = llm_cfg.provider
    if provider == "none":
        return NoLLM()
    if provider == "anthropic":
        key = env.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMUnavailable("llm.provider is anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicLLM("anthropic", llm_cfg.model or ANTHROPIC_MODEL,
                            llm_cfg.base_url or ANTHROPIC_BASE, key, transport)  # fmt: skip
    if not llm_cfg.model:
        raise LLMUnavailable(f"llm.provider is {provider}: set llm.model in config/app.yaml")
    if provider == "openai":
        key = env.get("OPENAI_API_KEY")
        if not key:
            raise LLMUnavailable("llm.provider is openai but OPENAI_API_KEY is not set")
        return OpenAICompatibleLLM("openai", llm_cfg.model, llm_cfg.base_url or OPENAI_BASE, key,
                                   transport)  # fmt: skip
    return OpenAICompatibleLLM("ollama", llm_cfg.model, llm_cfg.base_url or OLLAMA_BASE,
                               env.get("OPENAI_API_KEY"), transport)  # fmt: skip
