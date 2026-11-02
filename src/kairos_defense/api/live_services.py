"""Live mode's composition root (D-172, D-175, D-182): the only place that builds its adapters.

``LiveServices`` opens the live-mode store (``<live_mode>/feed.duckdb``) and vectors, composes the
history plus learned live history behind the ports (``CompositeTrackStore``,
``CompositeVectorStore``), builds a second ``DtwMatcher`` and ``ReportRecall`` over them (the
replay's stay on the history alone), the swarm matcher, the hub, the worker and the simulator
launcher. The worker reads on its own cursor of the live-mode database and holds the main store
lock while it matches, as replays do.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from kairos_defense.features.build import WINDOWS_TABLE
from kairos_defense.features.channels import load_site
from kairos_defense.live.feed import LiveHub
from kairos_defense.live.replay import iso_z
from kairos_defense.live.runner import LiveCompute, LiveWorker
from kairos_defense.store.composite import CompositeTrackStore, CompositeVectorStore, is_live_id

log = logging.getLogger(__name__)


class LiveServices:
    def __init__(self, svc, folder: Path | str | None = None, *, threaded: bool = True,
                 sim_command=None, config_dir: Path | str | None = None) -> None:  # fmt: skip
        from kairos_defense.api.launcher import SimLauncher
        from kairos_defense.store.lance import LanceVectorStore
        from kairos_defense.store.live_feed import VECTORS_DIR, DuckFeedStore

        cfg = svc.cfg
        self.cfg, self.svc = cfg, svc
        self.folder = Path(folder or cfg.app.paths.live_mode)
        with svc.lock:
            sensors = svc.store.sql("SELECT * FROM sensors ORDER BY sensor_id")
            insts = svc.store.sql("SELECT installation_id FROM installations ORDER BY 1")
            sites = {i: load_site(svc.store, i) for i in insts["installation_id"]}
            end = svc.store.sql("SELECT max(end_ts) AS t FROM incidents")["t"].iloc[0]
        self.feed = DuckFeedStore(self.folder, cfg.app, sensors=sensors)
        self.vectors = LanceVectorStore(self.folder / VECTORS_DIR)
        self.reader = self.feed.reader()
        self.store = CompositeTrackStore(svc.store, self.reader)  # the worker's
        self.rest_store = CompositeTrackStore(svc.store, self.feed)  # REST handlers'
        self.cvectors = CompositeVectorStore(svc.lance, self.vectors)
        self.matcher, self.recall, self.swarm_matcher = self._matchers(svc)
        self._finalize_abandoned()
        sensor_map = {r.sensor_id: (r.installation_id, r.kind) for r in sensors.itertuples()}
        self.worker = LiveWorker(lambda task, fresh: self.compute.handle(task, fresh),
                                 threaded=threaded)  # fmt: skip
        self.hub = LiveHub(cfg.scoring, sites, sensor_map, self.feed,
                           pd.Timestamp(end).to_pydatetime(), submit=self.worker.submit,
                           used_ids=self.feed.incidents()["incident_id"].tolist(),
                           matching=self.matcher is not None)  # fmt: skip
        offsets = {i: s.utc_offset_hours for i, s in sites.items()}
        self.compute = LiveCompute(
            self.hub, store=self.store, matcher=self.matcher, recall=self.recall,
            swarm_matcher=self.swarm_matcher, feed=self.feed, context=self.reader,
            live_vectors=self.vectors, memory=svc.memory, model=svc.model, scoring=cfg.scoring,
            sites=sites, offsets=offsets, lock=svc.lock)  # fmt: skip
        config_dir = Path(config_dir) if config_dir else Path(cfg.root) / "config"
        self.launcher = SimLauncher(self.folder, config_dir.resolve(), on_exit=self.hub.flush,
                                    command=sim_command)  # fmt: skip
        self.windows_table = WINDOWS_TABLE
        self.worker.start()

    def _matchers(self, svc):
        from kairos_defense.match.matcher import DtwMatcher
        from kairos_defense.match.swarm import SwarmMatcher
        from kairos_defense.recall.embed import make_embedder
        from kairos_defense.recall.search import ReportRecall
        from kairos_defense.store.lance import LanceReportIndex

        matcher = recall = swarm = None
        if svc.matcher is not None:
            matcher = DtwMatcher(self.store, self.cvectors, self.cfg.scoring,
                                 self.cfg.app.paths.models, verify_index=False)  # fmt: skip
        if svc.recall is not None:
            recall = ReportRecall(self.store, LanceReportIndex(self.cfg.app.paths.lancedb),
                                  svc.lance, make_embedder(self.cfg.app),
                                  self.cfg.scoring)  # fmt: skip
        if svc.lance.has("swarm_windows"):
            swarm = SwarmMatcher(svc.store, svc.lance, self.cfg.scoring)
        return matcher, recall, swarm

    def _finalize_abandoned(self) -> None:
        """Incidents left open by a stopped API are closed unlearned (their feed is gone)."""
        inc = self.feed.incidents()
        for row in inc[inc["state"] != "closed"].to_dict("records"):
            log.warning("closing abandoned live incident %s (not learned)", row["incident_id"])
            self.feed.put_incident({**row, "state": "closed"})

    # --- status and reset ---------------------------------------------------------------------
    def status(self) -> dict:
        states = self.hub.states()
        rows = []
        for r in self.feed.incidents().to_dict("records"):
            state, reruns = states.get(r["incident_id"], (r["state"], None))
            if reruns is None:
                reruns = len(self.feed.results(r["incident_id"]))
            rows.append({"incident_id": r["incident_id"], "installation_id": r["installation_id"],
                         "start_ts": iso_z(pd.Timestamp(r["start_ts"]).to_pydatetime()),
                         "end_ts": iso_z(pd.Timestamp(r["end_ts"]).to_pydatetime()),
                         "n_tracks": int(r["n_tracks"]), "is_swarm": bool(r["is_swarm"]),
                         "state": state, "reruns": int(reruns)})  # fmt: skip
        feeds = [{"installation_id": i, **f} for i, f in sorted(self.hub.feed_state().items())]
        problems = [] if self.matcher is not None else ["no matching: models or index missing"]
        return {"enabled": True, "matching": self.matcher is not None, "problems": problems,
                "feeds": feeds, "incidents": rows, "pending": self.worker.pending(),
                "learned_tracks": self.feed.count("track_signatures"),
                "simulator": self.launcher.state()}  # fmt: skip

    def reset(self) -> dict:
        """Stop the simulator, forget the hub's state, drop queued work, then empty every
        live-mode table and the live vectors. The history and the ledger are untouched."""
        stopped = self.launcher.stop()
        self.hub.reset()
        self.worker.clear()
        self.worker.wait_idle(30.0)
        counts = self.feed.reset()
        n = self.vectors.drop(self.windows_table)
        if self.matcher is not None:
            self.matcher.builder.forget([t for t in self.matcher.builder.cached_ids()
                                         if is_live_id(t)])  # fmt: skip
        self.hub.reset()  # anything a finishing task published meanwhile
        return {"reset": counts, "vectors": n, "stopped_simulator": stopped}

    def close(self) -> None:
        for closer in (self.launcher.stop, self.worker.stop, self.reader.close, self.feed.close):
            try:
                closer()
            except Exception:
                log.exception("live close failed")
