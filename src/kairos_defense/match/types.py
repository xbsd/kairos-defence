"""Match results (SPEC §10.8)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Match:
    """One past track ranked against a query track.

    ``score`` is 0..1, higher is more alike. A method fills only what it computes: the Euclidean
    baseline has no warp ratio (NaN) and no reasons (D-054).
    """

    query_incident_id: str
    track_id: str
    incident_id: str
    installation_id: str
    start_ts: datetime
    score: float  # fused, 0..1
    shape_sim: float
    features: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    warp_ratio: float = float("nan")
    window_offset_s: int = 0
    model_version: str = ""

    def to_dict(self) -> dict:
        """JSON-safe dict: NaN becomes None (``json.dumps`` would write invalid ``NaN``), the start
        time becomes ISO 8601."""

        def clean(v):
            return None if isinstance(v, float) and not math.isfinite(v) else v

        d = asdict(self)
        d["start_ts"] = self.start_ts.isoformat()
        d["features"] = {k: clean(v) for k, v in self.features.items()}
        return {k: clean(v) for k, v in d.items()}
