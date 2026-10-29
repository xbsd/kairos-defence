"""Agent tools (SPEC §18.1): functions over a ``ToolContext``, JSON in and out, no truth access.

Each tool takes plain JSON values and returns a JSON-safe dict (strings, numbers, booleans, None,
lists and dicts; times as ISO 8601 UTC with ``Z``; region meters). Bad input raises ``ToolError``
with a message a person can act on; ``call_tool`` turns it into ``{"error": …}`` for the MCP
server and the chat. Times given to a tool need ``Z`` or an offset (D-100). The tools live in
``flight_tools`` and ``memory_tools`` (helpers in ``common``); this module is their registry, their
JSON Schemas for the chat and the dispatcher.

- ``find_similar_flights(incident_id, window_s=120, k=5)``: the DTW matcher on the incident's track
  as seen ``window_s`` seconds after its first radar point (the replay second, not the matcher's
  window W), against history that started before it (rule 3).
- ``recall_reports(incident_id, match_incident_id, query=None, k=5, at_s=120)``: the §12 reports of
  one matched incident with clue spans; only reports whose event is before the query's start and
  that were filed by its replay time (D-082).
- ``forecast_recovery(incident_id, at_s=105)``: the §13 recovery zone.
- ``as_of_view``, ``diff_case``, ``shift_delta``: the §15 views, in the API's response shapes.
- ``propose_link(case_id, incident_id, rationale)``: appends exactly one ``match_proposed`` (actor
  ``agent:<name>``), with the matcher's evidence when the incident and the case's flights rank
  each other; an analyst approves or rejects it (rule 8).
- ``propose_evidence_export(case_id)``: appends nothing (an agent may append only
  ``match_proposed``, D-094) and returns a proposal id and the human step that exports.
"""

from __future__ import annotations

from collections.abc import Mapping

from kairos_defense.agent.common import iso_ms, parse_ts, to_json  # noqa: F401  (re-exported)
from kairos_defense.agent.context import ToolContext, ToolError
from kairos_defense.agent.flight_tools import (
    find_similar_flights,
    forecast_recovery,
    recall_reports,
)
from kairos_defense.agent.memory_tools import (
    as_of_view,
    diff_case,
    link_evidence,  # noqa: F401  (re-exported)
    propose_evidence_export,
    propose_link,
    shift_delta,
)

READ_ONLY = ("find_similar_flights", "recall_reports", "forecast_recovery", "as_of_view",
             "diff_case", "shift_delta")  # fmt: skip
PROPOSALS = ("propose_link", "propose_evidence_export")

TOOLS = {f.__name__: f for f in (find_similar_flights, recall_reports, forecast_recovery,
                                 as_of_view, diff_case, shift_delta, propose_link,
                                 propose_evidence_export)}  # fmt: skip

_TIME = {"type": "string", "description": "ISO 8601 with Z or an offset, e.g. 2026-04-20T15:00Z"}
_INC = {"type": "string", "description": "incident id, e.g. DEMO-BRAVO-0828"}
_CASE = {"type": "string", "description": "case id, e.g. CASE-P1-DELTA-260419"}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}  # fmt: skip


# name -> description and JSON Schema of the arguments (the chat's tool list, §18.3)
TOOL_SPECS: dict[str, dict] = {
    "find_similar_flights": {
        "description": "Past flights most similar to an incident's track, seen window_s seconds "
                       "after its first radar contact. Only flights that started earlier are "
                       "searched. Returns matches with scores, reasons and warp ratio.",
        "parameters": _schema({"incident_id": _INC,
                               "window_s": {"type": "integer", "minimum": 45, "default": 120,
                                            "description": "seconds after first contact"},
                               "k": {"type": "integer", "minimum": 1, "maximum": 50,
                                     "default": 5},
                               "track_id": {"type": "string"}}, ["incident_id"]),
    },
    "recall_reports": {
        "description": "Written reports behind one matched incident (hybrid search), with clue "
                       "spans and links; only reports filed before the query's replay time.",
        "parameters": _schema({"incident_id": _INC, "match_incident_id": _INC,
                               "query": {"type": "string"},
                               "k": {"type": "integer", "minimum": 1, "maximum": 20,
                                     "default": 5},
                               "at_s": {"type": "integer", "minimum": 45, "default": 120}},
                              ["incident_id", "match_incident_id"]),
    },
    "forecast_recovery": {
        "description": "Predicted recovery zone of an incident's drone: center, radius, exit path "
                       "and the roads crossing the zone (region meters).",
        "parameters": _schema({"incident_id": _INC,
                               "at_s": {"type": "integer", "minimum": 45, "default": 105}},
                              ["incident_id"]),
    },
    "as_of_view": {
        "description": "A case exactly as the memory knew it at a time (transaction time).",
        "parameters": _schema({"case_id": _CASE, "as_of_ts": _TIME}, ["case_id", "as_of_ts"]),
    },
    "diff_case": {
        "description": "What changed in a case between t1 and t2 (default t2: now).",
        "parameters": _schema({"case_id": _CASE, "t1": _TIME, "t2": _TIME}, ["case_id", "t1"]),
    },
    "shift_delta": {
        "description": "Everything the memory learned since a time, grouped (optionally for one "
                       "installation).",
        "parameters": _schema({"since_ts": _TIME, "installation_id": {"type": "string"},
                               "until_ts": _TIME}, ["since_ts"]),
    },
    "propose_link": {
        "description": "Propose adding an incident to a case. Appends one match_proposed event; "
                       "an analyst must approve it. Never links by itself.",
        "parameters": _schema({"case_id": _CASE, "incident_id": _INC,
                               "rationale": {"type": "string"}},
                              ["case_id", "incident_id", "rationale"]),
    },
    "propose_evidence_export": {
        "description": "Propose an evidence package export for a case. Appends nothing; a human "
                       "exports with an explicit approval.",
        "parameters": _schema({"case_id": _CASE}, ["case_id"]),
    },
}  # fmt: skip


def call_tool(ctx: ToolContext, name: str, arguments: Mapping | None = None,
              allowed: tuple[str, ...] = READ_ONLY + PROPOSALS) -> dict:  # fmt: skip
    """Run one tool under ``ctx.lock``; a ``ToolError`` or a bad argument list becomes
    ``{"error": …, "tool": name}``."""
    import inspect

    if name not in TOOLS or name not in allowed:
        return {"error": f"tool {name!r} is not available here", "tool": name}
    args = dict(arguments or {})
    params = list(inspect.signature(TOOLS[name]).parameters.values())[1:]
    names = [p.name for p in params]
    extra = sorted(set(args) - set(names))
    empty = inspect.Parameter.empty
    missing = [p.name for p in params if p.default is empty and p.name not in args]
    if extra or missing:
        return {"error": f"{name} takes {names}; unknown {extra or '-'}, missing {missing or '-'}",
                "tool": name}  # fmt: skip
    try:
        with ctx.lock:
            return TOOLS[name](ctx, **args)
    except ToolError as exc:
        return {"error": str(exc), "tool": name}
