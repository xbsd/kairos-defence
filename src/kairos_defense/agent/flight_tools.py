"""The flight tools (SPEC §18.1): similar flights, the reports behind a match, the recovery zone.

Each runs the phase 4 matcher on the incident's track as seen ``at_s`` seconds after its first
radar point (the replay second), against history that started before it (rule 3).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from kairos_defense.agent.common import (
    DEFAULT_WINDOW_S,
    id_arg,
    int_arg,
    iso_ms,
    match_dict,
    query_info,
    to_json,
    tool_query,
)
from kairos_defense.agent.context import ToolContext, ToolError


def find_similar_flights(ctx: ToolContext, incident_id: str, window_s: int = DEFAULT_WINDOW_S,
                         k: int = 5, track_id: str | None = None) -> dict:  # fmt: skip
    """Past flights most like the incident's track ``window_s`` seconds after first contact
    (``window_s`` is the replay second, not the matcher's window W)."""
    k = int_arg(k, "k", 1, 50)
    q = tool_query(ctx, incident_id, window_s, track_id)
    res = ctx.matcher.match(q)
    return {**query_info(q), "window_s": int(q.at_s), "model_version": ctx.matcher.model_version,
            "searched": "flights that started before query_start (no look-ahead)",
            "matches": [match_dict(m, i) for i, m in enumerate(res.matches[:k], 1)]}  # fmt: skip


def recall_reports(
    ctx: ToolContext,
    incident_id: str,
    match_incident_id: str,
    query: str | None = None,
    k: int = 5,
    at_s: int = DEFAULT_WINDOW_S,
) -> dict:
    """The reports behind one matched incident, with clue spans and links: only reports whose
    event is before the query's start and that were filed by its replay time (D-082)."""
    k = int_arg(k, "k", 1, 20)
    want = id_arg(match_incident_id, "match_incident_id")
    if query is not None and (not isinstance(query, str) or len(query) > 500):
        raise ToolError("query must be text of at most 500 characters")
    q = tool_query(ctx, incident_id, at_s)
    res = ctx.matcher.match(q)
    found = next(((i, m) for i, m in enumerate(res.matches, 1) if m.incident_id == want), None)
    if found is None:
        raise ToolError(f"{want} is not among the flights matched to {incident_id} at T+{q.at_s} s "
                        "(only flights that started earlier are searched)")  # fmt: skip
    rank, m = found
    one = SimpleNamespace(matches=[m], signature=res.signature, signatures=res.signatures)
    rec = ctx.recall.for_matches(q, one, (), n=1, k=k, query=query)
    mr = rec.matches[0].to_dict()
    reports = [{**r, "event_ts": iso_ms(r["event_ts_ms"]), "report_ts": iso_ms(r["report_ts_ms"])}
               for r in mr["reports"]]  # fmt: skip
    return to_json({**query_info(q), "query_text": rec.query_text,
                    "match": {"incident_id": want, "track_id": m.track_id, "rank": rank,
                              "score": m.to_dict()["score"],
                              "installation_id": m.installation_id},
                    "where": mr["where"], "reports": reports})  # fmt: skip


def forecast_recovery(ctx: ToolContext, incident_id: str, at_s: int = 105) -> dict:
    """The §13 recovery zone: center, radius, exit path and the roads crossing the zone."""
    from kairos_defense import geo
    from kairos_defense.forecast.analog import forecast

    q = tool_query(ctx, incident_id, at_s)
    res = ctx.matcher.match(q)
    fc = forecast(ctx.store, q, res, ctx.cfg.scoring)
    base = {**query_info(q), "installation_id": q.installation_id,
            "frame": "region meters: x_m east, y_m north"}  # fmt: skip
    if fc is None:
        return to_json({**base, "forecast": None,
                        "reason": "no matched flight with a known recovery point"})  # fmt: skip
    center = np.array([fc.center_x_m, fc.center_y_m])
    origin = np.asarray(q.target.centroid, dtype=np.float64)
    return to_json({**base, "forecast": fc.to_dict(), "target_asset_id": q.target.asset_id,
                    "distance_from_target_m": float(np.hypot(*(center - origin))),
                    "bearing_from_target_deg": float(geo.bearing(origin, center))})  # fmt: skip
