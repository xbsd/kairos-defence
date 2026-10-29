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

## Data in and out

- Reads (through `TrackStore.sql`): `incidents`, `track_points`, `rf_detections`, `remote_id`,
  `installations`, `regions`, `assets`, `roads`, `parks`, `sensors`, and what the matcher, forecast
  and recall read.
- Writes: `live_points`, `live_rf`, `live_rid` in `data/live.duckdb` (through `LiveSink`);
  `incident_recorded`, `model_registered`, `match_proposed` into the ledger (through `CaseMemory`);
  `data/cache/live/<incident>/manifest.json`, `features.json`, `t0045.json` … (through
  `ResultCache`).

## How it works

A session's `step` (every 100 ms in the API) reads the engine's clock and returns, in order: a
`clock` (10 Hz while playing), the detections that became visible, one `ingest` per live table
written (the measured insert of those rows), `features` for each whole second passed, the result
messages when a rerun second is crossed, then `ledger` messages for rows appended anywhere. A seek
returns `clock` with `seeked: true` and a 120 s catch-up. Results come from `LiveLoop.result_at`,
which snaps to the latest rerun and serves memory, then the cache, then computes (about 120–300
ms on the laptop). Proposals target the case holding the best-ranked top-3 incident (D-106); the
§15.6 dedup makes reruns and seeks append nothing new. The swarm incident streams detections only: swarm matching lives in `match.swarm`, the Swarm view and `kairos-defense swarm` (phase 9), and the swarm replay proposes nothing.

## Configuration

`scoring.live.min_track_s` (45), `scoring.live.rerun_every_s` (5), `app.replay.default_speed`,
`app.paths.live`, `app.paths.cache` (results under `live/`), and everything the matcher, forecast
and recall read.

## Tests

`tests/unit/test_live_replay.py`, `test_live_phase.py`, `test_live_loop.py`, `test_live_cache.py`,
`test_live_session.py`, `test_live_recorder.py`, `test_live_cli.py`; slow
`tests/slow/test_full_live.py` (the full precompute equals a recompute at every rerun second).
Fixtures `live_kit`, `live_loop` and `make_loop` in `tests/conftest.py` (module scope: their
read-only connection must close before other modules write the P1 file).

## Gotchas

- A cache whose manifest has another fingerprint is cleared on first use (stale results are never
  served); `replay --precompute` refills it.
- Detection message dicts are shared between sessions: never mutate them.
- `features_at` recomputes the whole partial track (about 2 ms a second); precompute caches all
  515 seconds of BRAVO.
- The engine's clock is per session: two browser tabs replay independently but record into the
  same `live_*` tables.

## Changelog

- Phase 7: package created.
- Phase 8: the lens, ghosts, forecast and recall messages the Director and the Case board read
  (D-128 to D-147).
- Phase 9: the swarm replay stays detections only (matching in `match.swarm`); docstrings and the
  `replay` CLI say so (D-105, D-152).
- Phase 10: this README brought current.
- Demo video (D-168): `replay.scaled_clock(scale, now)`: a monotonic source running `scale` times
  as fast as wall time (`[0.05, 1]`); sessions use it when the API runs with `--time-scale`.
