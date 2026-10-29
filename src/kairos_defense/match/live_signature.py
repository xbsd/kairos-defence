"""Partial signature of a query track as seen T seconds in (§10.5: "live signatures are partial").

The §9.4 ``signature`` runs on the query's own features (already rebuilt from points up to T), its
first radar point and its last point at or before T, and a sensor context bounded to T: RF and
Remote ID detections, the track's own points and the other tracks used by the concurrency test all
count only up to the replay time (D-071, CLAUDE.md rule 3). What is not known yet (no loiter, no
approach, launch unseen) stays None and fuses as 0.5.
"""

from __future__ import annotations

from kairos_defense.features.signatures import SensorContext, signature
from kairos_defense.match.query import Query
from kairos_defense.ports import TrackStore


def query_signature(store: TrackStore, q: Query) -> dict:
    """§9.4 fields of ``q`` from what was known at ``q.until`` (``SIGNATURE_COLUMNS`` keys)."""
    if q.points is None or q.site is None or len(q.points) == 0:
        raise ValueError(f"query {q.track_id} carries no points or site (build it with query_at)")
    ctx = SensorContext(**store.sensor_context_until(q.track_id, q.until))
    pts = q.points
    return signature(q.features, q.target, pts.iloc[0], pts.iloc[-1], q.site, ctx,
                     {"track_id": q.track_id, "incident_id": q.incident_id})  # fmt: skip
