"""The matcher trace's models (D-187, D-188): the ``matcher_trace`` stream message and
``GET /api/trace/{incident}`` / ``GET /api/live/trace``, the DTW workbench's data.

Columnar: ``prefilter``'s columns hold one entry per candidate in prefilter order, which is also
the order the DTW computes them and the fusion scores them, so ``dtw`` and ``fusion`` line up with
``prefilter.track_id`` index by index (ids are sent once). ``dtw.detail`` holds the first
``trace_paths`` candidates plus any final top-10 track beyond them, with their warping paths
(the full-matrix alignment with relaxed ends, indices into the full ``n`` × ``m`` matrix),
curves and cost thumbnails.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Num = float | None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TraceQuery(Strict):
    track_id: str
    incident_id: str
    at_s: int
    window_s: int
    rows_used: int
    n: int  # query samples (the DTW's rows)
    curve: list[Num]  # the trace channel, PAA to at most 48 points, raw units


class TracePrefilter(Strict):
    """Every candidate track in prefilter order (columns line up index by index)."""

    ms: Num
    k_windows: int
    candidates: int
    track_id: list[str]
    incident_id: list[str]
    start_ts_ms: list[int]
    distance: list[Num]  # vector search distance, squared L2
    window_s: list[int]
    offset_s: list[int]


class TraceDetail(Strict):
    """One of the first ``trace_paths`` candidates: its warping path (down-sampled, indices into
    the full ``n`` × ``m`` matrix), the candidate's curve and a cost-matrix thumbnail."""

    order: int
    track_id: str
    path: list[list[int]]
    path_len: int
    curve: list[Num]
    cost: list[list[Num]]  # 12 x 12 block minimum of the accumulated cost; None: unreachable


class TraceDtw(Strict):
    ms: Num
    band_fraction: float
    normalize: str
    n: int | None
    distance: list[Num]  # DTW distance per candidate, in the order computed (= prefilter order)
    d_norm: list[Num]
    band: list[int]
    m: list[int]
    ms_each: list[Num]
    shape_sim: list[Num] = []
    detail: list[TraceDetail]


class TraceFusion(Strict):
    ms: Num
    features: list[str]
    tau: Num
    coefficients: list[Num]
    intercept: Num
    values: list[list[Num]]  # per candidate, in ``features`` order
    score: list[Num]


class TraceRank(Strict):
    rank: int
    track_id: str
    incident_id: str
    installation_id: str
    score: Num
    shape_sim: Num
    reasons: list[str]


class MatcherTrace(Strict):
    """The record of one matcher call (D-187): what the DTW workbench replays."""

    t_s: int
    version: int
    trace_paths: int
    channel: str
    query: TraceQuery
    prefilter: TracePrefilter
    dtw: TraceDtw
    fusion: TraceFusion
    ranking: list[TraceRank]
    explain_ms: Num
    total_ms: Num  # the matcher's own time (the recording excluded)
    trace_ms: Num  # what recording paths and thumbnails cost


class MatcherTraceMsg(Strict):
    type: Literal["matcher_trace"]
    t_s: float
    incident_id: str
    trace: MatcherTrace
