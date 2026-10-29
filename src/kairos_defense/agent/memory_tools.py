"""The case-memory tools (SPEC §18.1, §15): as-of view, diff, shift delta and the two proposals.

The views return the API's response shapes; while the API holds the ledger (D-010) they ask its
REST routes instead (``ToolContext.remote``). ``propose_link`` appends exactly one
``match_proposed`` (actor ``agent:<name>``); ``propose_evidence_export`` appends nothing, because
an agent may append only ``match_proposed`` (D-094) and every export needs a human (rule 8).
"""

from __future__ import annotations

from kairos_defense.agent.common import (
    DEFAULT_WINDOW_S,
    INSTALLATION,
    MAX_RATIONALE,
    case_id_arg,
    head_time,
    id_arg,
    incident_row,
    ledger_rows,
    need_case,
    parse_ts,
    to_json,
    tool_query,
    tracks_of,
)
from kairos_defense.agent.context import LedgerBusy, ToolContext, ToolError


def as_of_view(ctx: ToolContext, case_id: str, as_of_ts: str) -> dict:
    """The case as known at ``as_of_ts`` (transaction time, §15.4)."""
    from kairos_defense.memory.asof import snapshot

    cid, t = case_id_arg(case_id), parse_ts(as_of_ts, "as_of_ts")
    try:
        rows = ledger_rows(ctx)
    except LedgerBusy:
        return ctx.remote(f"/api/cases/{cid}", {"as_of": as_of_ts})
    need_case(rows, cid)
    return to_json(snapshot(rows, cid, t).to_dict())


def diff_case(ctx: ToolContext, case_id: str, t1: str, t2: str | None = None) -> dict:
    """What changed in the case between ``t1`` and ``t2`` (default: the ledger head)."""
    from kairos_defense.memory.diff import case_diff, group

    cid, a = case_id_arg(case_id), parse_ts(t1, "t1")
    b = parse_ts(t2, "t2") if t2 is not None else None
    try:
        rows = ledger_rows(ctx)
    except LedgerBusy:
        return ctx.remote(f"/api/cases/{cid}/diff", {"t1": t1, "t2": t2})
    need_case(rows, cid)
    b = b or head_time(rows)
    items = case_diff(rows, cid, a, b)
    return to_json({"case_id": cid, "t1": a, "t2": b, "items": items, "groups": group(items)})


def shift_delta(ctx: ToolContext, since_ts: str, installation_id: str | None = None,
                until_ts: str | None = None) -> dict:  # fmt: skip
    """What the memory learned since ``since_ts`` (§15.8), grouped."""
    from kairos_defense.memory.delta import delta

    t0 = parse_ts(since_ts, "since_ts")
    t1 = parse_ts(until_ts, "until_ts") if until_ts is not None else None
    if installation_id is not None and (not isinstance(installation_id, str)
                                        or not INSTALLATION.match(installation_id)):  # fmt: skip
        raise ToolError(f"bad installation_id {installation_id!r}, e.g. DELTA")
    try:
        rows = ledger_rows(ctx)
    except LedgerBusy:
        return ctx.remote("/api/delta", {"since": since_ts, "until": until_ts,
                                         "installation": installation_id})  # fmt: skip
    return to_json(delta(rows, t0, t1 or head_time(rows), installation_id).to_dict())


def link_evidence(ctx: ToolContext, members: list[str], incident_id: str) -> dict:
    """The matcher's evidence for adding ``incident_id`` to a case with ``members``: the
    incident's own matches among the members (they flew earlier), else the founder's matches
    that include it (it flew earlier), at T+120 s. Empty when neither ranks the other."""
    if not members:
        return {}
    for query_inc, wanted in ((incident_id, set(members)), (members[0], {incident_id})):
        if len(tracks_of(ctx, query_inc)) != 1:
            continue
        try:
            q = tool_query(ctx, query_inc, DEFAULT_WINDOW_S)
        except ToolError:
            continue
        res = ctx.matcher.match(q)
        for rank, m in enumerate(res.matches, 1):
            if m.incident_id in wanted:
                d = m.to_dict()
                return to_json({"query_incident": query_inc, "query_track": q.track_id,
                                "matched_incident": m.incident_id, "match_track": m.track_id,
                                "rank": rank, "score": d["score"], "shape_sim": d["shape_sim"],
                                "warp_ratio": d["warp_ratio"], "reasons": list(m.reasons),
                                "model_version": m.model_version,
                                "t_s": DEFAULT_WINDOW_S})  # fmt: skip
    return {}


def propose_link(ctx: ToolContext, case_id: str, incident_id: str, rationale: str) -> dict:
    """Propose ``incident_id`` for ``case_id``: one ``match_proposed`` row; a human decides."""
    from kairos_defense.memory.asof import members_at

    cid, inc = case_id_arg(case_id), id_arg(incident_id, "incident_id")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > MAX_RATIONALE:
        raise ToolError(f"rationale must be non-empty text of at most {MAX_RATIONALE} characters")
    incident_row(ctx, inc)
    rows = ledger_rows(ctx)
    need_case(rows, cid)
    members = members_at(rows, cid, head_time(rows))
    if inc in members:
        raise ToolError(f"{inc} is already a member of {cid}")
    ev = link_evidence(ctx, members, inc)
    actor = f"agent:{ctx.agent}"
    linked = (ev.get("matched_incident") if ev.get("query_incident") == inc
              else ev.get("query_incident")) or members[0]  # fmt: skip
    obj = {"query_incident": linked, "query_track": ev.get("query_track"),
           "match_track": ev.get("match_track"), "rank": ev.get("rank"),
           "score": ev.get("score"), "reasons": ev.get("reasons", []),
           "warp_ratio": ev.get("warp_ratio"), "model_version": ev.get("model_version") or actor,
           "t_s": ev.get("t_s"), "top3": [inc], "rationale": rationale.strip(),
           "proposed_by": actor, "evidence": ev or None}  # fmt: skip
    try:
        with ctx.ledger(write=True) as mem:
            seq = mem.append({"event_type": "match_proposed", "actor": actor,
                              "recorded_at": ctx.clock(), "case_id": cid, "subject_id": inc,
                              "predicate": "member_of", "valid_from": ctx.clock(),
                              "source_type": "agent", "source_id": ctx.agent,
                              "confidence": ev.get("score"), "object_json": obj})  # fmt: skip
    except LedgerBusy as exc:
        raise ToolError(f"{exc}: stop the API to propose from here, or approve links in the "
                        "Case board") from exc  # fmt: skip
    return to_json(
        {
            "case_id": cid,
            "incident_id": inc,
            "proposal_seq": seq,
            "event_type": "match_proposed",
            "actor": actor,
            "appended": 1,
            "evidence": ev or None,
            "next": f"an analyst approves or rejects proposal {seq} on the Case board "
            f"(or POST /api/cases/{cid}/links); nothing is linked until then",
        }
    )


def propose_evidence_export(ctx: ToolContext, case_id: str) -> dict:
    """A proposal to export the case's evidence package; appends nothing (D-094)."""
    from kairos_defense.memory.asof import snapshot

    cid = case_id_arg(case_id)
    try:
        rows = ledger_rows(ctx)
        need_case(rows, cid)
        snap = snapshot(rows, cid, head_time(rows)).to_dict()
    except LedgerBusy:
        snap = ctx.remote(f"/api/cases/{cid}")
    head = snap.get("head_seq")
    return to_json(
        {
            "proposal_id": f"EXPORT-PROPOSAL-{cid}-{head}",
            "case_id": cid,
            "head_seq": head,
            "head_hash": snap.get("head_hash"),
            "status": snap.get("status"),
            "members": snap.get("members", []),
            "appended": 0,
            "requires": "an explicit human approval (rule 8)",
            "how": [
                f"kairos-defense export --case {cid} --approve --analyst <handle>",
                "the Evidence page: Export evidence package, then confirm",
            ],
        }
    )
