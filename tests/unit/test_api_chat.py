"""The optional chat panel's routes (SPEC §18.3): off by default (409, the panel stays hidden);
with an LLM injected, the read-only tools run on the API's own handles and nothing is appended."""

from __future__ import annotations

from kairos_defense.agent.tools import READ_ONLY

LIVE = "DEMO-BRAVO-0828"


class ScriptedLLM:
    provider, model, enabled = "scripted", "test", True

    def __init__(self, replies: list[dict]) -> None:
        self.replies = list(replies)

    def chat(self, messages, tools=None):
        return self.replies.pop(0)


def test_chat_is_off_by_default(api) -> None:
    st = api.get("/api/chat/status").json()
    assert st == {"enabled": False, "provider": "none", "model": "", "tools": list(READ_ONLY),
                  "problem": None}  # fmt: skip
    r = api.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert r.status_code == 409 and "llm.provider" in r.json()["detail"]


def test_chat_runs_read_only_tools_and_appends_nothing(api) -> None:
    before = api.get("/api/ledger/tail", params={"n": 1}).json()[0]["seq"]
    api.app.state.chat_llm = ScriptedLLM([
        {"text": "", "stop_reason": "tool_use", "native": None,
         "tool_calls": [{"id": "1", "name": "find_similar_flights",
                         "arguments": {"incident_id": LIVE, "window_s": 90}},
                        {"id": "2", "name": "propose_link",
                         "arguments": {"case_id": "CASE-P1-DELTA-260419", "incident_id": LIVE,
                                       "rationale": "x"}}]},
        {"text": "P1-DELTA-260419 ranks first.", "stop_reason": "end_turn", "native": None,
         "tool_calls": []},
    ])  # fmt: skip
    try:
        assert api.get("/api/chat/status").json()["enabled"] is True
        r = api.post("/api/chat", json={"messages": [
            {"role": "user", "content": "Which past flights look like tonight's?"}]})  # fmt: skip
    finally:
        del api.app.state.chat_llm
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "P1-DELTA-260419 ranks first." and body["provider"] == "scripted"
    first, second = body["tool_calls"]
    assert first["name"] == "find_similar_flights" and first["result"]["matches"]
    assert second["name"] == "propose_link" and "not available" in second["result"]["error"]
    assert api.get("/api/ledger/tail", params={"n": 1}).json()[0]["seq"] == before


def test_chat_validates_its_input(api) -> None:
    api.app.state.chat_llm = ScriptedLLM([])
    try:
        r = api.post("/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]})
        assert r.status_code == 422
        assert api.post("/api/chat", json={"messages": []}).status_code == 422
        bad = api.post("/api/chat", json={"messages": [{"role": "system", "content": "x"}]})
        assert bad.status_code == 422
    finally:
        del api.app.state.chat_llm
