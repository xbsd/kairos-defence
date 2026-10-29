"""REST routes for the case memory, the ledger and the admin resets (SPEC §16.4, D-010, D-108).

Writes go through ``memory.actions`` and ``memory.evidence`` (append only, rule 7); links and
exports need an explicit analyst action (rule 8). Every append is broadcast to the replay
sessions as a ``ledger`` message (``PublishingMemory``).
"""

from __future__ import annotations

import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from kairos_defense.api.deps import block, parse_time, record, services
from kairos_defense.api.schemas import (
    EvidenceLine,
    EvidenceRequest,
    LedgerBlock,
    LedgerRecord,
    LedgerVerify,
    LinkRequest,
    LinkResponse,
    ReseedResponse,
    ResetResponse,
)
from kairos_defense.api.services import Services
from kairos_defense.memory.actions import (
    ActionError,
    ProposalAlreadyDecided,
    ProposalNotFound,
    WrongCase,
    decide_link,
)
from kairos_defense.memory.diff import case_diff, group
from kairos_defense.memory.graph import case_graph
from kairos_defense.memory.ledger import InvalidEvent, analyst
from kairos_defense.ports import _jsonable

router = APIRouter(prefix="/api")
Svc = Depends(services)


def _head_time(svc: Services):
    head = svc.memory.head()
    if head is None:
        raise HTTPException(409, "the ledger is empty: run `kairos-defense memory seed`")
    return head.recorded_at


def _case_rows(svc: Services, case_id: str) -> list[dict]:
    rows = svc.memory.events()
    if not any(r["event_type"] == "case_opened" and r["case_id"] == case_id for r in rows):
        raise HTTPException(404, f"no case {case_id}")
    return rows


@router.get("/cases/{case_id}")
def case(case_id: str, as_of: str | None = None, svc: Services = Svc) -> dict:
    """The case as known at ``as_of`` (transaction time, §15.4; default the ledger head)."""
    from kairos_defense.memory.asof import snapshot

    rows = _case_rows(svc, case_id)
    return snapshot(rows, case_id, parse_time(as_of, "as_of", _head_time(svc))).to_dict()


@router.get("/cases/{case_id}/diff")
def diff(case_id: str, t1: str, t2: str | None = None, svc: Services = Svc) -> dict:
    rows = _case_rows(svc, case_id)
    a, b = parse_time(t1, "t1"), parse_time(t2, "t2", _head_time(svc))
    items = case_diff(rows, case_id, a, b)
    return _jsonable({"case_id": case_id, "t1": a, "t2": b, "items": items,
                      "groups": group(items)})  # fmt: skip


@router.get("/cases/{case_id}/graph")
def graph(case_id: str, as_of: str | None = None, svc: Services = Svc) -> dict:
    rows = _case_rows(svc, case_id)
    return case_graph(rows, case_id, parse_time(as_of, "as_of", _head_time(svc)))


@router.post("/cases/{case_id}/links", response_model=LinkResponse)
def links(case_id: str, body: LinkRequest, svc: Services = Svc) -> dict:
    """An analyst approves or rejects one proposal (rule 8): ``link_approved`` or
    ``link_rejected``. 404 unknown proposal, 409 wrong case or already decided."""
    clock = parse_time(body.clock, "clock", _head_time(svc))
    try:
        why = body.rationale or f"{body.decision}d in the Command Center"
        seq = decide_link(
            svc.memory, case_id, body.proposal_seq, body.decision, body.analyst, clock, why
        )
    except ProposalNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (WrongCase, ProposalAlreadyDecided) as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ActionError, InvalidEvent) as exc:
        raise HTTPException(422, str(exc)) from exc
    row = svc.memory.rows_for_seqs([seq])[0]
    return {"case_id": case_id, "proposal_seq": body.proposal_seq, "decision": body.decision,
            "block": block(row)}  # fmt: skip


@router.post("/cases/{case_id}/evidence", responses={200: {
    "model": EvidenceLine, "description": "NDJSON: one EvidenceLine per line",
    "content": {"application/x-ndjson": {}}}})  # fmt: skip
def evidence(case_id: str, body: EvidenceRequest, svc: Services = Svc) -> StreamingResponse:
    """Export an evidence package (``approve: true`` required, rule 8) and stream the real
    hashing progress as NDJSON: one ``EvidenceFileLine`` per file, then ``EvidenceDoneLine``
    with the verification checks (or one ``{"type": "error"}`` line)."""
    from kairos_defense.memory.evidence import (
        EvidenceError,
        export_evidence,
        passed,
        signer_for,
        verify_evidence,
    )

    if not body.approve:
        raise HTTPException(400, "approval required (rule 8): an export needs an explicit human "
                                 "approval; send approve: true. Nothing was written.")  # fmt: skip
    try:
        who = analyst(body.analyst)
    except InvalidEvent as exc:
        raise HTTPException(422, str(exc)) from exc
    _case_rows(svc, case_id)
    clock = parse_time(body.clock, "clock", _head_time(svc))
    lines: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            with svc.lock:
                res = export_evidence(
                    svc.memory,
                    case_id,
                    approve=True,
                    approved_by=who,
                    clock=clock,
                    out_root=svc.app.paths.exports,
                    signer=signer_for(svc.app),
                    store=svc.store,
                    progress=lambda d: lines.put({"type": "file", **d}),
                )
            checks = verify_evidence(res.path, svc.memory)
            lines.put({"type": "done", "dir": res.path.as_posix(),
                       "manifest_sha256": res.manifest_sha256, "seq": res.seq,
                       "head_seq": res.head_seq, "signed": res.signed,
                       "checks": [c.__dict__ for c in checks],
                       "passed": passed(checks)})  # fmt: skip
        except (EvidenceError, ActionError, InvalidEvent, OSError) as exc:
            lines.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            lines.put(None)

    threading.Thread(target=work, name=f"evidence-{case_id}", daemon=True).start()

    def gen():
        while (item := lines.get()) is not None:
            yield json.dumps(item) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.get("/ledger/verify", response_model=LedgerVerify)
def ledger_verify(svc: Services = Svc) -> dict:
    head = svc.memory.head()
    return {"intact": (b := svc.memory.verify_chain()) is None, "first_broken_seq": b,
            "rows": svc.memory.count(), "head_seq": head.seq if head else None,
            "head_hash": head.hash if head else None}  # fmt: skip


@router.get("/ledger/tail", response_model=list[LedgerBlock])
def ledger_tail(n: int = Query(12, ge=1, le=200), svc: Services = Svc) -> list[dict]:
    head = svc.memory.head()
    if head is None:
        return []
    seqs = list(range(max(1, head.seq - n + 1), head.seq + 1))
    return [block(r) for r in svc.memory.rows_for_seqs(seqs)]


@router.get("/ledger/{seq}", response_model=LedgerRecord)
def ledger_record(seq: int, svc: Services = Svc) -> dict:
    rows = svc.memory.rows_for_seqs([seq])
    if not rows:
        raise HTTPException(404, f"no ledger row {seq}")
    return _jsonable(record(rows[0]))


@router.get("/delta")
def delta(since: str, until: str | None = None, installation: str | None = None,
          svc: Services = Svc) -> dict:  # fmt: skip
    """The shift delta (§15.8): what the memory learned in ``(since, until]``."""
    from kairos_defense.memory.delta import delta as shift_delta

    t0 = parse_time(since, "since")
    t1 = parse_time(until, "until", _head_time(svc))
    return shift_delta(svc.memory.events(), t0, t1, installation).to_dict()


@router.post("/admin/reset", response_model=ResetResponse)
def admin_reset(svc: Services = Svc) -> dict:
    """Empty the ``live_*`` scratch tables (never the ledger), D-010."""
    return {"reset": svc.reset_live()}


@router.post("/admin/reseed", response_model=ReseedResponse)
def admin_reseed(svc: Services = Svc) -> dict:
    """Rebuild the ledger from seed (D-010); clients refetch ``/api/ledger/tail`` after it."""
    from kairos_defense.memory.ledger import LedgerError
    from kairos_defense.memory.seed import SeedError

    try:
        s = svc.reseed()
    except (LedgerError, SeedError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"rows": s.rows, "head_seq": s.head_seq, "head_hash": s.head_hash,
            "counts": s.counts}  # fmt: skip
