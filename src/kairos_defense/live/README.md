# kairos_defense.live

The live replay (SPEC §16.1, §16.2): a live incident on a replay clock, the live loop that reruns
the matcher, forecast, report recall and lens on that clock, and one client's session.

## Responsibilities

- Load a live incident's radar points, RF detections and Remote ID messages, each with `t_s`
  (seconds since `incidents.start_ts`, T+0) (`replay.py`).
- Keep the replay clock: play, pause, seek, reset, speed 1, 2 or 5 (`replay.ReplayEngine`, D-118).
- Rerun the matcher, the §13 forecast, §12 report recall and the top match's lens every
  `rerun_every_s` from `min_track_s`, on points up to the replay second only (rule 3), and cache
  results by replay second (`loop.py`, D-105).
- Precompute every rerun and feature second into the result cache (`precompute.py`, D-013).
- Classify the flight phase for the `features` message (`phase.py`, D-115).
- Run one WebSocket client's protocol without a web framework: the §16.3 messages, recording into
  the `live_*` tables, proposals into the case memory, ledger fan-out (`session.py`,
  `broadcast.py`, D-106, D-107).
- Build the 3D theater's scene for an installation (`scene.py`, D-109).
- Live mode (phase 11, D-169, D-172 to D-176): form live incidents from an incoming sensor feed
  (`incidents.py`), apply ingest messages, queue reruns and closes and fan the live stream out per
  installation (`feed.py`), run reruns fresh first and backfill, propose, and learn closed
  incidents (`runner.py`, `learn.py`).

## Public API

- `replay.load_incident(store, incident_id) -> LiveIncident` (`KeyError` unless `status = 'live'`);
  `replay.live_incident_ids(store)` (single-track first).
- `LiveIncident`: ids, `start_ts`/`end_ts` (naive UTC), `duration_s`, `tracks`, frames `points`,
  `rf`, `rid` (source columns plus `t_s`), `detections(t0, t1)` (messages with `t0 < t_s <= t1`,
  ordered by `t_s`, point, rf, rid, sensor), `rows(t0, t1)` (source rows per live table),
  `ts_at(t_s)`.
- `replay.ReplayEngine(incident, speed=1.0, now=time.monotonic)`: `elapsed_s` (pauses itself at the
  end), `play()`, `pause()`, `seek(t) -> t` (clamped), `reset()`, `set_speed(v)` (1, 2, 5 or
  `ValueError`), `visible_points()`.
- `loop.LiveLoop(incident, store, scoring, *, matcher=None, recall=None, cache=None, lock=None,
  fingerprint=None)`: `schedule` (rerun seconds), `rerun_at(t)`, `waiting_for_s(t)`,
  `result_at(t)` (memory, cache, or computed and stored; None before `min_track_s` or without
  single-track matching), `compute(r)`, `features_at(s)`, `features_range(s0, s1)`,
  `save_features()`, `lens(t, match_track_id, channel)`, `cache_state()`, `offsets`.
  `loop.rerun_seconds(duration, min_track_s, every_s)`.
- `precompute.fingerprint(store, scoring, app, incident_id) -> str` (SHA-256 hex);
  `precompute.precompute(loop, force=False) -> PrecomputeSummary`.
- `phase.flight_phase(features, target_kind) -> "approach" | "loiter" | "egress"`,
  `phase.first_loiter_s(...)`.
- `session.Session(incident, loop, *, sink, memory, feed, model, speed, now)`: `hello()`,
  `handle(client_msg) -> list[dict]`, `step() -> list[dict]`, `reset()`, `Session.error(...)`.
  Helpers `target_case(rows, top, at)` (D-106), `decorate(matches, rows, case_id, query_incident,
  at, offsets)` (adds `proposal_seq`, `decision`, `memory_status`), `ledger_message(row)`.
- `broadcast.Broadcaster` (`subscribe() -> Feed`, `publish(rows)`), `broadcast.PublishingMemory`
  (a `CaseMemory` wrapper that publishes appended rows; `replace(inner)` for a reseed).
- `scene.installation_scene(store, world, installation_id, radius_m=6000) -> dict` (the API's
  `Scene`).
- Live mode (phase 11):
  - `incidents.IncidentTracker(scoring, sites, used=())`: `point(inst, sensor_track_id, ms, x, y)
    -> (LiveTrack, [("opened"|"joined", LiveIncidentState)])`, `idle(inst, feed_ms, heard_ms)`
    (open incidents with no detection for `idle_close_s`, now `closing`), `due_reruns(inc,
    feed_ms)` (rerun seconds after T+0, each once), `current(inst)`, `open_incidents(inst)`,
    `forget()`; `incidents.incident_id(inst, first_ms, offset, used)` (`LIVE-<BASE>-<YYMMDD>-
    <HHMMSS>`, `-2` on a clash). Times are UTC epoch ms.
  - `feed.LiveHub(scoring, sites, sensors, feed, history_end, *, submit, used_ids, matching,
    now)`: `check(msg) -> reason | None`, `ingest(rows) -> {accepted, detections, rejected}`
    (rows from `api.schemas_ingest`, `ts` naive UTC), `flush(installations)`, `result(incident,
    msgs)` and `closed(incident, summary)` (from the worker), `subscribe(inst) -> Feed`,
    `hello(inst)`, `clock(inst)`, `catch_up(inst)`, `reset()`, `feed_state()`, `states()`.
    `feed.RerunTask(meta, t_s, points)`, `feed.CloseTask(meta, points)`.
  - `runner.LiveCompute(hub, *, store, matcher, recall, swarm_matcher, feed, context,
    live_vectors, memory, model, scoring, sites, offsets, lock)`: `handle(task, fresh)`,
    `rerun(task, fresh) -> messages`, `close(task) -> {learned_tracks, windows}`.
    `runner.LiveWorker(handle, threaded=True)`: `start()`, `submit(task)`, `pending()`,
    `clear()`, `wait_idle(timeout)`, `stop()`; `runner.compact(matches)`.
  - `learn.learn_incident(incident_id, points, site, context, feed, vectors, scoring) -> Learned`.
  - Shared with the replay: `loop.compute_result(r, make_query, *, store, matcher, recall,
    scoring, offsets, incident_id)`, `loop.lens_for`, `loop.local_start`; `session.propose(memory,
    model, meta, res, r, at)` and `session.result_messages(res, r, at, meta, *, memory, model,
    offsets, hashes)`.

## Data in and out

- Reads (through `TrackStore.sql`): `incidents`, `track_points`, `rf_detections`, `remote_id`,
  `installations`, `regions`, `assets`, `roads`, `parks`, `sensors`, and what the matcher, forecast
  and recall read.
- Writes: `live_points`, `live_rf`, `live_rid` in `data/live.duckdb` (through `LiveSink`);
  `incident_recorded`, `model_registered`, `match_proposed` into the ledger (through `CaseMemory`);
  `data/cache/live/<incident>/manifest.json`, `features.json`, `t0045.json` … (through
  `ResultCache`).
- Live mode: writes `live_points`, `live_rf`, `live_rid`, `live_incidents`, `live_tracks`,
  learned `track_features` / `track_signatures` and `live_results` in `<live_mode>/feed.duckdb`
  (through `LiveFeed`), learned `flight_windows` in `<live_mode>/vectors` (through
  `VectorStore.upsert`), and `incident_recorded`, `model_registered`, `match_proposed` into the
  ledger for fresh single-track reruns. Reads history plus learned live history through
  `store.composite`.

## How it works

A session's `step` (every 100 ms in the API) reads the engine's clock and returns, in order: a
`clock` (10 Hz while playing), the detections that became visible, one `ingest` per live table
written (the measured insert of those rows), `features` for each whole second passed, the result
messages when a rerun second is crossed, then `ledger` messages for rows appended anywhere. A seek
returns `clock` with `seeked: true` and a 120 s catch-up. Results come from `LiveLoop.result_at`,
which snaps to the latest rerun and serves memory, then the cache, then computes (about 120–300
ms on the laptop). Proposals target the case holding the best-ranked top-3 incident (D-106); the
§15.6 dedup makes reruns and seeks append nothing new. The swarm incident streams detections only: swarm matching lives in `match.swarm`, the Swarm view and `kairos-defense swarm` (phase 9), and the swarm replay proposes nothing.
**Live mode (phase 11).** The API's `/ws/ingest` and `POST /api/ingest` hand schema-checked
messages to `LiveHub.ingest`, which checks installation, sensor, history end and lateness,
groups radar points into incidents (`IncidentTracker`: join within 10 s and 300 m, swarm at three
tracks, close after 30 s of feed time without a detection), writes each table's rows in one timed
batch (the `ingest` message), streams the §16.3 messages plus `incident_opened`/`incident_closed`
to the installation's subscribers, and queues a `RerunTask` for every `min_track_s + k ×
rerun_every_s` that feed time passed (points up to that second only, rule 3) and a `CloseTask` for
idle incidents. `LiveWorker` runs the newest rerun first (streamed and proposed through the
replay's `result_messages`), backfills the skipped ones (recorded in `live_results` only) and
learns a closed incident last (`learn_incident`: the index build's `track_rows` on the received
points, written through the ports). D-172 to D-176.

## Configuration

`scoring.live.min_track_s` (45), `scoring.live.rerun_every_s` (5), `app.replay.default_speed`,
`app.paths.live`, `app.paths.cache` (results under `live/`), and everything the matcher, forecast
and recall read.
Live mode: `scoring.live.idle_close_s` (30), `join_window_s` (10), `max_lateness_s` (10),
`scoring.swarm.min_drones` and `max_spacing_m`; `app.paths.live_mode`.

## Tests

`tests/unit/test_live_replay.py`, `test_live_phase.py`, `test_live_loop.py`, `test_live_cache.py`,
`test_live_session.py`, `test_live_recorder.py`, `test_live_cli.py`; slow
`tests/slow/test_full_live.py` (the full precompute equals a recompute at every rerun second).
Fixtures `live_kit`, `live_loop` and `make_loop` in `tests/conftest.py` (module scope: their
read-only connection must close before other modules write the P1 file).
Live mode: `test_live_incidents.py`, `test_live_hub.py` (a simulated P1 flight end to end; the
worker's fresh-first order), `test_live_learning.py` (no look-ahead, learned rows equal the index
build's), `test_live_reset.py`; fixture `live_services` and `tests/unit/live_kit.py` (reruns every
20 s, frames of feed time, the worker on submit: nothing waits in real time).

## Gotchas

- A cache whose manifest has another fingerprint is cleared on first use (stale results are never
  served); `replay --precompute` refills it.
- Detection message dicts are shared between sessions: never mutate them.
- `features_at` recomputes the whole partial track (about 2 ms a second); precompute caches all
  515 seconds of BRAVO.
- The engine's clock is per session: two browser tabs replay independently but record into the
  same `live_*` tables.
- Live mode: RF and Remote ID are not tied to a track at ingest, so any RF heard at an
  installation keeps every open incident there alive (D-174). A hello's `duration_s` is 0 for a
  live incident (open-ended); `clockNow` in the web app treats 0 as unbounded.
- `LiveWorker` with `threaded=False` runs each task on submit (tests): the order is then FIFO
  and every rerun is fresh.

## Changelog

- Phase 7: package created.
- Phase 8: the lens, ghosts, forecast and recall messages the Director and the Case board read
  (D-128 to D-147).
- Phase 9: the swarm replay stays detections only (matching in `match.swarm`); docstrings and the
  `replay` CLI say so (D-105, D-152).
- Phase 10: this README brought current.
- Demo video (D-168): `replay.scaled_clock(scale, now)`: a monotonic source running `scale` times
  as fast as wall time (`[0.05, 1]`); sessions use it when the API runs with `--time-scale`.
- Phase 11: live mode (`incidents.py`, `feed.py`, `runner.py`, `learn.py`); `LiveLoop.compute`
  became the shared `loop.compute_result` and `Session._results` the shared
  `session.result_messages` (replay results unchanged), D-172 to D-176.
