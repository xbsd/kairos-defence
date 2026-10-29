"""The MCP server (SPEC §18.2): the §18.1 tools for any MCP client, over stdio.

A thin adapter over the installed ``mcp`` 2.x, where §18.2's ``FastMCP`` is called ``MCPServer``
(``mcp.server.mcpserver``; the 1.x import path is gone). Each tool is a small wrapper with an
explicit signature (the server derives the input schema from it) that calls ``tools.call_tool``,
so errors come back as ``{"error": …}`` JSON instead of failing the call.

Read-only by default: the six read-only tools always; ``propose_link`` and
``propose_evidence_export`` only with ``allow_proposals`` (``kairos-defense mcp
--allow-proposals``). The ``ToolContext`` is built on the first tool call, so listing the tools
needs no data, models or ledger. Run it with ``make mcp`` or
``claude mcp add kairos-defense -- uv run kairos-defense mcp``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from kairos_defense.agent.tools import PROPOSALS, READ_ONLY, TOOL_SPECS, call_tool

INSTRUCTIONS = (
    "Kairos Defense: one memory of drone flights across installations (all data synthetic). "
    "Search past flights that started before an incident, the reports behind them, the "
    "predicted recovery zone and the case memory as known at any time. Proposals need "
    "--allow-proposals, and a human approves every link and export."
)


class _Lazy:
    """Builds the ``ToolContext`` once, on the first tool call."""

    def __init__(self, factory: Callable) -> None:
        self.factory, self._ctx, self._lock = factory, None, threading.Lock()

    def call(self, name: str, **args) -> dict:
        with self._lock:
            if self._ctx is None:
                self._ctx = self.factory()
        return call_tool(self._ctx, name, args)


def build_server(ctx_factory: Callable, allow_proposals: bool = False,
                 name: str = "kairos-defense"):  # fmt: skip
    """An ``MCPServer`` with the read-only tools, plus the proposal tools when allowed.
    ``ctx_factory()`` returns the ``ToolContext`` (called once, lazily)."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    lazy = _Lazy(ctx_factory)
    server = MCPServer(name, instructions=INSTRUCTIONS, log_level="WARNING")

    def find_similar_flights(incident_id: str, window_s: int = 120, k: int = 5,
                             track_id: str | None = None) -> dict:  # fmt: skip
        return lazy.call("find_similar_flights", incident_id=incident_id, window_s=window_s,
                         k=k, track_id=track_id)  # fmt: skip

    def recall_reports(incident_id: str, match_incident_id: str, query: str | None = None,
                       k: int = 5, at_s: int = 120) -> dict:  # fmt: skip
        return lazy.call("recall_reports", incident_id=incident_id, query=query, k=k, at_s=at_s,
                         match_incident_id=match_incident_id)  # fmt: skip

    def forecast_recovery(incident_id: str, at_s: int = 105) -> dict:
        return lazy.call("forecast_recovery", incident_id=incident_id, at_s=at_s)

    def as_of_view(case_id: str, as_of_ts: str) -> dict:
        return lazy.call("as_of_view", case_id=case_id, as_of_ts=as_of_ts)

    def diff_case(case_id: str, t1: str, t2: str | None = None) -> dict:
        return lazy.call("diff_case", case_id=case_id, t1=t1, t2=t2)

    def shift_delta(since_ts: str, installation_id: str | None = None,
                    until_ts: str | None = None) -> dict:  # fmt: skip
        return lazy.call("shift_delta", since_ts=since_ts, installation_id=installation_id,
                         until_ts=until_ts)  # fmt: skip

    def propose_link(case_id: str, incident_id: str, rationale: str) -> dict:
        return lazy.call("propose_link", case_id=case_id, incident_id=incident_id,
                         rationale=rationale)  # fmt: skip

    def propose_evidence_export(case_id: str) -> dict:
        return lazy.call("propose_evidence_export", case_id=case_id)

    wrappers = {f.__name__: f for f in (find_similar_flights, recall_reports, forecast_recovery,
                                        as_of_view, diff_case, shift_delta, propose_link,
                                        propose_evidence_export)}  # fmt: skip
    read = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    write = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                            idempotent_hint=False, open_world_hint=False)  # fmt: skip
    for tool in READ_ONLY + (PROPOSALS if allow_proposals else ()):
        server.add_tool(wrappers[tool], name=tool, description=TOOL_SPECS[tool]["description"],
                        annotations=read if tool in READ_ONLY else write)  # fmt: skip
    return server


def serve(ctx_factory: Callable, allow_proposals: bool = False) -> None:
    """Run the server over stdio until the client disconnects."""
    build_server(ctx_factory, allow_proposals).run("stdio")
