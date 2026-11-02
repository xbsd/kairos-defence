"""Learning a closed live incident (D-176): it becomes history the next live flight can match.

For each of the incident's tracks, the index build's own code (``features.build.track_rows``:
§9 features, the §9.4 signature with the sensor context of the whole flight, and the PAA
windows) runs on the received radar points; the rows go to the live-mode store through the
``LiveFeed`` port and the windows to the live-mode vectors through ``VectorStore.upsert``. Only
closed incidents are learned, so an open incident is never a candidate, and the matcher's
started-before filters still apply to learned tracks (rule 3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.build import WINDOWS_TABLE, track_rows
from kairos_defense.features.channels import SiteGeometry
from kairos_defense.features.signatures import SIGNATURE_COLUMNS, SensorContext
from kairos_defense.match.candidates import FAR_FUTURE
from kairos_defense.ports import LiveFeed, TrackStore, VectorStore
from kairos_defense.store.ddl import DERIVED_COLUMNS

log = logging.getLogger(__name__)


@dataclass
class Learned:
    tracks: list[str] = field(default_factory=list)
    windows: int = 0
    skipped: list[str] = field(default_factory=list)  # too short to describe


def learn_incident(incident_id: str, points: pd.DataFrame, site: SiteGeometry,
                   context: TrackStore, feed: LiveFeed, vectors: VectorStore,
                   scoring: ScoringConfig) -> Learned:  # fmt: skip
    """Learn every track of one closed incident. ``points``: its radar points (the
    ``track_points`` columns), ``context``: a store whose ``sensor_context_until`` sees the
    incident's RF and Remote ID (the live-mode store)."""
    out = Learned()
    feats, sigs, wins, vecs = [], [], [], []
    for tid, p in points.sort_values(["track_id", "ts"], kind="stable").groupby("track_id"):
        # the whole flight's RF and Remote ID, as the index build reads them (no bound)
        ctx = SensorContext(**context.sensor_context_until(str(tid), FAR_FUTURE))
        try:
            rows = track_rows(str(tid), incident_id, p.reset_index(drop=True), site, ctx, scoring)
        except ValueError as exc:
            log.info("not learning %s: %s", tid, exc)
            out.skipped.append(str(tid))
            continue
        feats.append(rows.features)
        sigs.append(rows.signature)
        wins += rows.windows
        vecs += rows.vectors
        out.tracks.append(str(tid))
    if not out.tracks:
        return out
    features = pd.concat(feats, ignore_index=True)[DERIVED_COLUMNS["track_features"]]
    signatures = pd.DataFrame(sigs, columns=SIGNATURE_COLUMNS)
    feed.learn(features, signatures)
    vectors.upsert(WINDOWS_TABLE, [{**w, "vector": v} for w, v in zip(wins, vecs, strict=True)])
    out.windows = len(wins)
    return out
