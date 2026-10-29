"""Request and response models of the optional chat panel (SPEC §18.3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatStatus(BaseModel):
    enabled: bool  # false: llm.provider is none, the panel stays hidden
    provider: str
    model: str
    tools: list[str]  # the read-only tools the chat may call
    problem: str | None = None  # why a configured provider cannot be used


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ChatToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ChatToolCall]
    stop_reason: str
    provider: str
    model: str
