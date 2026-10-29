"""Response models for the phase 8 pages (SPEC §16.4, §17.9, D-135, D-136): the Match explainer,
the Case board's list and decisions, and the Evidence page's package list and verify.

Kept apart from ``schemas.py`` (the stream contract) so each module stays small. Times are ISO
8601 UTC with ``Z``; paths are target-relative meters (``x_rel_m`` east, ``y_rel_m`` north of the
flight's target asset centroid) with ``t_s`` seconds since the track's first radar point.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from kairos_defense.api.schemas import EvidenceCheck, LedgerBlock, MatchItem


# --- Match explainer --------------------------------------------------------------------------
class ContributionRow(BaseModel):
    feature: str
    value: float  # x_i
    coefficient: float
    contribution: float  # coef_i × x_i (§10.7)


class ExplainFlight(BaseModel):
    track_id: str
    incident_id: str
    installation_id: str
    target_asset_id: str
    local_start: str | None  # YYYY-MM-DDTHH:MM at its installation
    columns: list[str]  # ["t_s", "x_rel_m", "y_rel_m", "dist_target_m"]
    points: list[list[float | None]]


class ExplainSegment(BaseModel):
    start_s: int
    end_s: int


class ExplainAlignment(ExplainSegment):
    value: float  # subsequence DTW value of tonight's dist_target_m window (§10.4 step 6)


class ExplainResponse(BaseModel):
    incident_id: str
    at: float
    t_s: int  # the rerun second the result belongs to (≤ at)
    model_version: str
    window_s: int
    match: MatchItem
    contributions: list[ContributionRow]  # by |contribution|, largest first
    intercept: float
    logit: float  # intercept + Σ contributions
    score: float  # sigmoid(logit): the match's fused score
    tonight: ExplainFlight  # up to the rerun second only (rule 3)
    past: ExplainFlight  # the whole past flight
    segment: ExplainSegment  # the matcher's window on the past flight
    alignment: ExplainAlignment | None


# --- Case board ------------------------------------------------------------------------------
class CaseSummary(BaseModel):
    case_id: str
    founder: str
    base: str | None
    status: Literal["open", "closed", "unknown"]
    opened_at: str
    members: list[str]
    pending: int
    contradictions: int
    claims: list[str]
    last_decision: str | None
    exports: int


Decision = Literal["close", "reopen", "escalate", "notify_law_enforcement"]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    analyst: str = "demo"
    rationale: str = ""
    clock: str | None = None  # ISO time with Z or offset; default the ledger head


class DecisionResponse(BaseModel):
    case_id: str
    decision: Decision
    block: LedgerBlock


# --- Evidence ---------------------------------------------------------------------------------
class EvidencePackage(BaseModel):
    dir: str  # folder name under the exports root
    case_id: str | None
    created_at: str | None  # the case.json export clock
    manifest_sha256: str | None
    signed: bool
    files: list[str]


class EvidenceVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dir: str  # a folder name from GET /api/evidence (inside the exports root)


class EvidenceVerifyResponse(BaseModel):
    dir: str
    checks: list[EvidenceCheck]
    passed: bool
