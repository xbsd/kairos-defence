# Phase 11: Live mode MVP (simulated sensor feed, live matching, scenarios), plan

## Goal

Turn the replay demo into a live system (`docs/phases/PHASE_11.md`, D-169, D-170). A separate
simulator process flies new, never-seen flights on a live calendar after the 18-month history and
streams **only sensor detections** to the app through a versioned ingest contract. The app forms
incidents itself, reruns the existing matcher, forecast and report recall on what it has received
(swarms through the phase 9 swarm matcher), learns closed incidents into a separable live history
that the next live flight can match, records incidents and proposals in the case memory, and shows
it all on a new Live page. After an incident closes, "Reveal who flew" shows the true operator and
the matcher's verdict through `kairos_defense.eval`. `kairos-defense live check` flies the five
scenarios headless and scores them with the same `eval` function.

## Inputs read

- `CLAUDE.md` (rules 1 to 10, rule 2's D-170 exception), `docs/phases/PHASE_11.md` (as updated by
  `b295c73`, D-170), `docs/CLOUD_HANDOFF.md`, `docs/phases/TEMPLATES.md`, `.claude/skills/phase-auto/SKILL.md`.
- SPEC §1 (demo story), §4 (ports and adapters), §7 (tables), §8 (generator), §9 (features), §10
  (matcher), §11.3 (no look-ahead), §14 (swarms), §15.6 (proposal dedup), §16 (replay and stream
  protocol), §17.2 to §17.4 (layout, theater, memory rail).
- `docs/phases/phase-07/REPORT.md`, `phase-09/REPORT.md`, `phase-10/REPORT.md`; D-063 (soft gaps),
  D-010 (resets through the API), D-103 to D-110 (live tables, composition root, locks), D-150 (swarm
  matcher), D-168, D-169, D-170.
- Package READMEs: `live`, `sim`, `match`, `api`, `web`. Code read before deciding the layout:
  `live/session.py`, `loop.py`, `replay.py`, `broadcast.py`; `api/services.py`, `stream.py`,
  `schemas.py`; `store/duck.py`, `lance.py`, `live_duck.py`, `ddl.py`, `guard.py`; `match/query.py`,
  `candidates.py`, `matcher.py`, `prefilter.py`, `live_signature.py`, `swarm.py`;
  `features/build.py`, `swarm_features.py`; `forecast/analog.py`; `recall/search.py`;
  `sim/actors.py`, `kinematics.py`, `sensors.py`, `incidents.py`, `swarm.py`, `calendar.py`,
  `writers.py`; `eval/truth.py`; `tests/conftest.py`, `test_truth_isolation.py`,
  `test_api_contract.py`, `test_docs.py`; `web/src` stores, dispatch, `useReplay`, `LiveWatch`,
  `CommandBar`, `routes.ts`, `playwright.config.ts`; `scripts/cloud_gate.py`, `docs/phases/gates.json`.
- PROGRESS.md: phases 0 to 10 done; 803 fast Python tests and 169 Vitest at the start (this
  container, `make check` in `scripts/cloud_setup.sh`).

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md` during the build (numbers are provisional).

1. **D-171 How this session runs.** `claude -p` answered in this container, but the user asked for
   both phases to be built in this session with `scripts/cloud_gate.py` as the only judge, and the
   nested `claude -p` reported this session's own id; so step 3 of `docs/CLOUD_HANDOFF.md` is used.
2. **D-172 Live stores, separable by construction.** One new config key, `paths.live_mode`
   (default `data/live_mode/`), holds everything live mode writes, apart from the history:
   - `feed.duckdb`: the ingested detections in `live_points`, `live_rf`, `live_rid` (the columns of
     `track_points`, `rf_detections`, `remote_id`, the §16.2 names the Recorder already shows), views
     `track_points`, `rf_detections`, `remote_id` over them and a copy of `sensors`, so the existing
     `DuckTrackStore` SQL (RF and Remote ID association up to `until`, §11.2, D-071) runs unchanged
     on live data; `live_incidents` (the `incidents` columns plus `state` open, closing or closed,
     and `source = 'live'`), `live_tracks` (app track id, incident, installation and the sensor's
     track id), `track_features` and `track_signatures` of learned (closed) live tracks, and
     `live_results` (each rerun's shown matches: incident, query track, `t_s`, kind, model version,
     elapsed ms, matches JSON).
   - `vectors/` (LanceDB): `flight_windows` of learned live tracks.
   - `clock.json`: the persisted live clock. `sim/`: simulator logs written by launched processes.
   `store/live_feed.py` (`DuckFeedStore`, a `DuckTrackStore` subclass over `feed.duckdb` with the
   write methods and `reset()`), `store/composite.py` (`CompositeTrackStore(main, live)` and
   `CompositeVectorStore(main, live)`: unions for `features_many`, `tracks_before`, `signature`,
   `features`, `track_points`, `sensor_context_until` by owner, `search` merged by `_distance`).
   A new `ports.LiveFeed` Protocol names the write side (append detections, incidents, results,
   learned tracks, reset). The main database stays read-only; the 18-month history, evaluation and
   the replay are never written. `live reset` empties the feed tables, drops the live vectors and
   forgets the hub's in-memory state; the live clock only moves forward (it is not rewound).
3. **D-173 Ingest contract v1 (the sensor adapter seam).** `api/schemas_ingest.py`: `IngestPoint`
   (`installation_id`, `sensor_id`, `sensor_track_id`, `ts`, `x_m`, `y_m`, `alt_m`, `quality`),
   `IngestRf` (`installation_id`, `sensor_id`, `ts`, `band`, `protocol_family`, `bearing_deg`,
   `snr_db`), `IngestRid` (`installation_id`, `ts`, `serial`, `drone_x_m`, `drone_y_m`, `op_x_m`,
   `op_y_m`), `IngestHeartbeat` (`installation_id`, `ts`, optional `rate`, feed seconds per wall
   second), each with `v: 1` (default; other versions rejected) and a `type` discriminator. Times
   need `Z` or an offset. Accepted on `WS /ws/ingest` (a JSON object or array per frame; each frame
   gets an `ack` with `accepted` and `rejected: [{index, reason}]`) and `POST /api/ingest`
   (`{"messages": [...]}`, same answer). Rejected with a reason: schema errors, unknown
   installation, unknown sensor or a sensor of another installation or kind, a timestamp at or
   before the end of the history (rule 3 guard), non-finite numbers, out-of-range quality or
   bearing, and messages more than `live.max_lateness_s` (10 s) older than the installation's feed
   time. No message carries an actor, a name or an incident id: the app assigns incidents.
4. **D-174 Live incidents.** Per installation, feed time is the newest timestamp received there
   (any message, heartbeats included). A point with an unseen `sensor_track_id` opens a track; the
   track joins an open incident at that installation when, at its first point, a track of that
   incident had a point within `live.join_window_s` (10 s) and `swarm.max_spacing_m` (300 m);
   otherwise it opens a new incident (its T+0 is that first point). An incident with two or more
   tracks is a swarm incident (`is_swarm`), matched by the swarm matcher once it has
   `swarm.min_drones` tracks, otherwise its first track is matched as a single track. An incident
   closes when feed time passes its last radar point by `live.idle_close_s` (30 s, new in
   `config/scoring.yaml` with `max_lateness_s` and `join_window_s`). Ids:
   `LIVE-<BASE>-<YYMMDD>-<HHMMSS>` of the first point, local time (`-2` on a clash), tracks
   `<incident>-T<n>`; ids never carry the actor.
5. **D-175 Reruns are queued, never skipped.** A single worker thread runs a FIFO of tasks: a
   rerun for each `t = min_track_s + k × rerun_every_s` (seconds after the incident's first point)
   as soon as feed time passes `start + t`, with the points received up to `start + t` (rule 3);
   then the incident's close task (remaining reruns first, then learning). So every rerun is
   computed whatever `--speed` is, results are identical at speed 1 and 50, and at high speed they
   arrive later than the theater (the stream says how far behind: `match.elapsed_ms` is the real
   compute time, and the status reports the queue length). `features` messages are computed in the
   ingest path for the newest whole second, at most 5 per wall second.
6. **D-176 Learning and look-ahead.** The close task builds the closed incident's tracks'
   `track_features`, `track_signatures` and `flight_windows` with the existing code
   (`features.channels.track_features`, `features.signatures.signature`, `features.windows.iter_windows`,
   the same rows `features.build` writes), then writes them through `LiveFeed` and
   `VectorStore.upsert`. Only closed incidents are learned, so an open incident is never a
   candidate; a live query still keeps the prefilter's `start_ts_ms < query start` and
   `tracks_before(start)` (rule 3), so a learned flight that started later is never seen. Swarm
   drone tracks are learned like single tracks; swarm choreography (`swarm_features`,
   `swarm_windows`) is not learned in the MVP (no scenario needs a live swarm to match an earlier
   live swarm).
7. **D-177 The live clock.** The simulator stamps flights after the last history night:
   `clock.json` holds the next free UTC instant (default: the night after `calendar.end_local`,
   2026-09-01, 21:00 local at the base). A scenario launches at the earliest time at or after the
   clock whose local time falls inside its actor's usual window (`time_local` of the prober or
   copycat; 19:00 to 23:00 for hobbyists and the invented operator; the swarm start window), then
   reserves the clock up to the end of its last flight plus `idle_close_s` plus 60 s. The wind of a
   live flight is drawn from the scenario seed (not from the night), so the same seed flies the
   same flight relative to its launch on any date. The seed is printed and recorded (status, the
   simulator's log, the truth row); when omitted it comes from OS entropy, and every draw after
   that is `rng_for(seed, "live", …)` (rule 4).
8. **D-178 Scenarios.** `sim/live_scenarios.py` builds them from the generator's functions:
   `returning-prober` (`actors.make_flight` with `prober_spec`, actors P1 to P6, default P1,
   `--base` among the actor's bases, default its first base, or `random` to let the seed choose the
   actor); `copycat` (C1 via `copycat_spec`, bases BRAVO and DELTA); `hobbyist` (the generator's
   hobbyist plan from the base's park); `swarm-repeat` (`swarm.swarm_plan`, `drone_paths`,
   `drone_plans`, team S1 or S2, default S1, the team's bases); `new-operator-twice` (an invented
   operator `N1`: an orbit around `hq`, radius 260 m clockwise, 2 laps, altitude 70 to 90 m, cruise
   12 m/s, RF family `FAM-40` (used by no actor), Remote ID off, launch 1,400 m at bearing 45°; flown
   at `--base`, then at `--second-base`, default the next installation of the same region, after
   the first incident has closed). Kinematics and sensing are `kinematics.build_reference`,
   `sample_reference`, `fly`, `sensors.radar_track`, `rf_track`, `rid_track`; a returning drone
   broadcasts its known Remote ID serial (`stable_serial` of the world seed). Sensor track ids are
   opaque hashes of (seed, flight key, drone): unique, reproducible, and they carry no actor.
9. **D-179 Ground truth of live flights, and the reveal.** The simulator writes one row per sensor
   track it sends through `sim/writers.py` (the only truth writer) into a truth table `live_truth`
   (`sensor_track_id`, `actor_id`, `actor_type`, `nickname`, `scenario`, `seed`, `base`, `flight`,
   `launch_ts`), idempotent by `sensor_track_id`, with a short retry while another process holds
   the file. `eval/reveal.py` (`reveal(feed, app, incident_id)`) is the only reader: it joins the
   incident's tracks to that table and the history's `track_truth` (and to the same table for
   learned live tracks), and returns the actor or team, nickname, scenario, seed, one verdict row
   per rerun (rank of the first same-actor flight among the shown matches, the top match and its
   actor) and the scenario expectation with plain words. `GET /api/live/incidents/{id}/reveal`
   serves it (404 unknown, 409 unless closed); nothing revealed is stored. `live reset` does not
   touch the truth file (the API never writes truth); rows of reset incidents are simply never
   joined again.
10. **D-180 Expectations (scored by the same `eval` function).** Times are seconds after the
    incident's first radar point. `returning-prober`: met when some rerun at or before T+120 shows
    a same-actor flight in the top 3 ("first recognized at T+x (rank r)"; "top match from T+y" is
    the earliest rerun from which rank 1 stays same-actor). `copycat`: met when the rerun at or
    before T+120 (the latest) shows a C1 flight in the top 5 above every P1 flight. `hobbyist`: no
    expectation (always met); the top score is reported. `swarm-repeat`: met when the incident's
    final swarm rerun ranks a past event of the same team first. `new-operator-twice`: flight 1
    reports that no same-actor history existed (met when none did); flight 2 is met when its final
    rerun ranks flight 1's learned track first. A scenario whose flight produced no incident, or
    whose incident closed without a rerun, is a GAP with the reason.
11. **D-181 Case memory.** Live results go through the same code as the replay (`session.target_case`,
    `decorate`, `memory.actions.record_incident`, `register_model`, `propose_matches`): the
    incident is recorded and the top 3 are proposed to the case holding the best-ranked top-3
    incident, deduplicated (§15.6); single-track results only (swarm results propose nothing, as in
    the replay). Approve and Reject on the Live page are the existing link route (rule 8). The
    ledger is append-only (rule 7): `live reset` never touches it, and the chain stays intact
    (`memory verify`). The demo's reset (R, `POST /api/admin/reseed`) still rebuilds the ledger from
    seed as before.
12. **D-182 Launching the simulator.** `POST /api/sim/launch {scenario, actor?, base?,
    second_base?, speed, seed?}` validates against `GET /api/live/scenarios` and starts
    `python -m kairos_defense.cli simulate … --url ws://127.0.0.1:<port>/ws/ingest --live-mode-dir …`
    as a separate process (stdout to `live_mode/sim/<n>.log`, never read by the API). One simulator
    at a time (409 while one runs). The actor or team chosen in the launcher is passed to the child
    and not kept by the API (status shows scenario, base, speed and seed only). `POST /api/live/reset`
    stops a running simulator first. The API stops its children on shutdown.
13. **D-183 `live check`.** `kairos-defense live check [--scenarios all|a,b] [--speed 50]
    [--timeout 900]` (in `eval/live_check.py`, run by `cli_live_mode.py`): scratch stores under
    `data/cache/live_check/` (live-mode folder, a reseeded ledger copy, exports), the API started
    in-process with uvicorn in a thread on a free loopback port, each scenario launched through
    `POST /api/sim/launch` with a fixed seed, waits for the simulator to exit, every incident to
    close and the work queue to drain (`GET /api/live/status`), then scores each scenario from
    `GET /api/live/incidents/{id}/reveal`. Prints one line per scenario (`PASS <scenario>: …` or
    `GAP <scenario>: expected …; observed …`) and a timing line; exit 0 all pass, 1 only gaps, 2 on a
    crash or timeout; resets the scratch live data at the end; stops the server and every child.
14. **D-184 Live stream and Live page.** `WS /ws/live/{installation_id}` sends the §16.3 types the
    Live watch components understand (`hello` per incident, `clock` at up to 10 Hz on feed time with
    `speed` = the feed rate, `point`, `rf`, `rid`, `ingest`, `features`, `match`, `forecast`,
    `dtw`, `recall`, `ledger`, `error`) plus `incident_opened`, `incident_closed` and `swarm_match`.
    They form `LiveStreamMessage` in `api/schemas_live.py`; the replay's `StreamMessage` (exactly
    §16.3, contract test) is unchanged. On connect: `hello` for the open incident (or an empty one:
    `incident_id: ""` when nothing flies) and a catch-up of the last 120 s. The web Live page is
    route `/live` (Live watch stays `/live/:incidentId`), in the Pages menu and behind a Replay or
    Live switch in the command bar, whose live mode shows the feed's local time, the current
    incident's T+ and a feed status chip instead of the replay controls.

## Work breakdown

Each step ends with `make check` and a checkpoint commit (`phase 11: checkpoint (…)`).

1. **Config and stores.** `config/scoring.yaml` `live.idle_close_s: 30`, `max_lateness_s: 10`,
   `join_window_s: 10`; `config/app.yaml` `paths.live_mode: data/live_mode`;
   `config/scoring.py`, `config/__init__.py` (path distinct from the others). `ports.py`
   (`LiveFeed`). `store/live_feed.py` (`DuckFeedStore`), `store/composite.py`,
   `DuckTrackStore.over(con, path)` (a store on an existing connection, for the worker's cursor).
   `tests/conftest.py`: `tmp_config` and `with_paths` move `live_mode`.
2. **Simulator.** `sim/live_scenarios.py` (scenario catalog, plans, flights, detections),
   `sim/live_clock.py` (`LiveClock`), `sim/live_feed.py` (`FeedClient`: time-ordered batches on the
   live clock × speed, heartbeats every tick and until `idle_close_s + 2` after the last detection,
   reconnect with backoff, clean stop on SIGINT/SIGTERM), `sim/writers.py`
   (`record_live_flights(app, rows)`), CLI `simulate` in `cli_live_mode.py`
   (`--scenario --base --actor --second-base --speed --seed --url --live-mode-dir --dry-run`;
   prints the seed, the launch time and, in its own terminal, the actor).
3. **App live core.** `live/incidents.py` (`IncidentTracker`, pure), `live/feed.py` (`LiveHub`:
   ingest, tracker, feed time, stream fan-out and catch-up per installation, status, reset),
   `live/runner.py` (the worker: reruns with `DtwMatcher`/forecast/recall/lens or `SwarmMatcher`,
   proposals, `live_results`), `live/learn.py` (close-task learning). `loop.compute_result(...)`
   extracted from `LiveLoop.compute` and shared (replay results unchanged); `SwarmMatcher.match_flight`
   extracted from `SwarmMatcher.match` (unchanged results); `CandidateBuilder.forget(ids)` for reset.
4. **Eval.** `eval/reveal.py` (`reveal`, `expectation`, `verdict_words`), `eval/live_check.py`,
   CLI `live check`, `live reset`, `live status`.
5. **API.** `api/schemas_ingest.py`, `api/schemas_live.py`, `api/routes_live.py` (ingest WS and
   REST, live WS, status, scenarios, reset, launch, reveal), `api/launcher.py` (child process),
   `api/services.py` (`Services.live`: the hub, the composite matcher and recall, the worker;
   started and stopped in the lifespan), `api/app.py` and `cli_live.py` (`--live-mode-dir`,
   `KD_LIVE_MODE`). Regenerate `web/openapi.json` and `types.gen.ts`.
6. **Web.** `src/app/routes.ts` (`/live` → `livemode`, Pages menu "Live"), `CommandBar.tsx` (mode
   switch, live clock and status), `src/api/stream.ts` (`liveUrl`), `src/api/client.ts`
   (`liveStatus`, `liveScenarios`, `simLaunch`, `liveReset`, `reveal`), `src/api/messages.ts`,
   `src/state/liveStore.ts`, `src/state/useLive.ts`, `src/state/dispatch.ts` (live types),
   `src/live/Launcher.tsx`, `IncidentList.tsx`, `RevealCard.tsx`, `ResetLive.tsx`,
   `SwarmMatchList.tsx`, `src/pages/LiveMode.tsx` (theater, rails, launcher, incidents, reveal,
   reset; "Nothing is flying" when idle), `App.tsx` (lazy route). Vitest and Playwright as below.
   Review the Playwright screenshots against §17 and fix what is wrong.
7. **Make and docs.** `Makefile` `live` (build the web app, serve it, print the Live page URL) and
   `live-check`; `web/playwright.config.ts` (`--live-mode-dir data/cache/e2e/live_mode`). Docs and
   READMEs (below). Exit check, EXIT_CHECK.md, REPORT.md, PROGRESS.md entry, DECISIONS.md, commit,
   push, then the gate.

## Tests

Python (fast unless marked slow):

- `tests/unit/test_sim_live.py`
  - `test_scenario_catalog_lists_the_five_scenarios`: names, actors, bases, defaults.
  - `test_same_seed_same_detections` and `test_different_seeds_differ`: every scenario, detection
    lists equal (times relative to launch) for one seed at two clock positions; differ across seeds.
  - `test_detections_are_time_ordered_and_carry_no_actor`: sorted `ts`; no key or value names the
    actor, team, nickname or scenario; sensor track ids do not contain the actor id.
  - `test_new_operator_flies_twice_at_two_bases_after_close`: second launch ≥ first flight's last
    detection + `idle_close_s`; distinct bases; `FAM-40` used by no configured actor.
  - `test_swarm_repeat_flies_the_team`: S1 gives 5 tracked drones at one base.
  - `test_bad_actor_or_base_is_refused`.
- `tests/unit/test_live_clock.py`: default start is 2026-09-01 21:00 local at the base (after
  `calendar.end_local`); launch falls in the actor's window; the clock persists and only moves
  forward; a second scenario starts after the first one's reservation.
- `tests/unit/test_feed_client.py` (fake transport, fake clock): batches leave on the scaled clock
  (speed 1 and 50), heartbeats continue to `idle_close_s + 2` after the last detection, reconnect
  after a dropped connection resends the unacknowledged batch, `stop()` ends cleanly.
- `tests/unit/test_ingest_schema.py`: valid point, rf, rid and heartbeat accepted; rejected with
  reasons: unknown type, missing field, naive time, version 2, unknown installation, unknown
  sensor, sensor of another kind, timestamp before the end of history, NaN, quality out of range,
  late message; `POST /api/ingest` batch counts.
- `tests/unit/test_live_incidents.py`: one track opens one incident at its first point and closes
  after `idle_close_s` of feed time (heartbeats advance it); two concurrent nearby tracks form one
  swarm incident; a distant concurrent track opens a second incident; a track after close opens a
  new incident; ids and T+0.
- `tests/unit/test_live_stores.py`: `DuckFeedStore` appends, views and `sensor_context_until` on
  live rows; composite unions and ordering; composite vector search merges by distance; reset
  empties every live table and vector; the feed store refuses the truth path.
- `tests/unit/test_live_hub.py` (on `toy_models`, a scratch live-mode folder, a ledger copy):
  feeding a simulated P1 flight at BRAVO opens an incident, reruns start at T+45 every 5 s with the
  points up to each rerun only (`rows_used`, last point time ≤ start + t), results are identical
  at speed 1 and 50, proposals land in the ledger once (dedup), close learns the track.
- `tests/unit/test_live_learning.py`: **no look-ahead**: a live query never sees a history or live
  track that started after it, and an open incident is never a candidate; after close, the learned
  track is searchable by a later query (prefilter, signatures, features) and absent for an earlier
  one; learned rows equal what `features.build` would write for the same points.
- `tests/unit/test_live_reset.py`: after `live reset` every live row (detections, incidents,
  tracks, learned tables, results, vectors) is gone, the main database's table counts are
  unchanged and the ledger's row count and chain are unchanged (`verify_chain() is None`).
- `tests/unit/test_api_live.py`: ingest over the WebSocket and REST with acks; `/ws/live/BRAVO`
  sends `hello`, `incident_opened`, points, `match` and `incident_closed` (validated against
  `LiveStreamMessage`); `GET /api/live/status`, `GET /api/live/scenarios`; `POST /api/live/reset`;
  `POST /api/sim/launch` starts a (stubbed) child, refuses a second one with 409 and bad input
  with 422; the reveal route returns 404 for an unknown incident, 409 while open and the right
  actor and verdict once closed (truth written through `sim.writers` in a scratch truth file).
- `tests/unit/test_eval_reveal.py`: rank of the first same-actor flight per rerun; each scenario's
  expectation met and not met on hand-made results; the plain words for P1, a copycat, a swarm
  team and both new-operator flights.
- `tests/unit/test_truth_isolation.py`: `FORBIDDEN` gains `live_truth`, so no module outside
  `eval/` and `sim/writers.py` can name the table (the scan and the guard tests stay).
- `tests/unit/test_cli_live_mode.py`: `simulate --dry-run` prints the plan without the actor in its
  first line and without sending; `live reset` and `live status` on a scratch folder; `live check
  --help`; argument errors.
- `tests/unit/test_api_contract.py` and `test_docs.py` keep passing (the guide gains the new
  commands, see Documentation).
- Slow: `tests/slow/test_full_live_mode.py`: `live check --scenarios returning-prober --speed 50`
  on the full data exits 0 or 1 (never 2) and leaves no live rows.

Web:

- Vitest: `liveStore.test.ts` (incident list from `incident_opened` and `incident_closed`, status,
  reveal state), `liveDispatch.test.ts` (live messages reach the replay and match stores, a new
  incident resets them), `LiveMode.test.tsx` (launcher options per scenario, "Nothing is flying",
  open incidents show no Reveal button, the reveal card's words), `routes.test.ts` (the `/live`
  route), `CommandBar.test.tsx` (live mode shows the feed clock and hides replay controls).
- Playwright `e2e/livemode.spec.ts`: the Live page at 1440 × 900 launches `returning-prober` at
  speed 20 at BRAVO, sees an incident open and matches appear, waits for it to close, presses
  Reveal who flew and sees the operator (`P1`, `County Rd operator`) and a verdict; axe clean;
  screenshots `phase11-live-*` to `reports/figures/ui/`; then resets live data and reseeds the
  ledger. Existing replay, Director and guide specs unchanged.

## Exit-check mapping

| Criterion | Command | Evidence |
|---|---|---|
| Lint, format, fast tests, web checks | `make check` | ruff clean, pytest pass count (≥ 803 plus the new tests), Vitest count |
| Every scenario flown live and scored | `uv run kairos-defense live check --scenarios all --speed 50` | one `PASS` or `GAP` line per scenario with seed, ranks and times; exit 0 (all pass) or 1 (gaps only, soft, D-063) |
| The replay demo and the Live page work in a browser | `make e2e` | all specs pass, `livemode.spec.ts` included; screenshots in `reports/figures/ui/` |
| Gate | `python3 scripts/cloud_gate.py gate 11` | `make check`, `live check` (soft), `npm --prefix web run build`, `make e2e`, docs check; `gate-N.log` |

`EXIT_CHECK.md` records the commands with trimmed output; the per-scenario results and timings
also go into PROGRESS.md.

## Documentation to write or update

- `docs/phases/phase-11/PLAN.md` (this), `PLAN_REVIEW-k.json`, `REPORT.md`, `EXIT_CHECK.md`.
- Package READMEs: `src/kairos_defense/live/README.md`, `sim/README.md`, `api/README.md` (the
  ingest contract), `store/README.md`, `eval/README.md`, `match/README.md` (the extracted
  `match_flight` and `forget`), `config/README.md`, `src/kairos_defense/README.md` (the CLI
  modules), `web/README.md`.
- `docs/DEMO.md`: a short "Live mode" section. `docs/USER_GUIDE.md`: a short "Live mode" stub
  naming `kairos-defense simulate`, `live check`, `live reset` and `live status` (so the CLI
  coverage test passes; phase 12 writes the full section with screenshots).
- Root `README.md` Status section; `docs/PROGRESS.md` session log and exit-check evidence (not
  the Status cell); `docs/DECISIONS.md` D-171 to D-18x.

## Risks and mitigations

- **Matcher throughput at speed 50** (about 0.5 s per rerun here): reruns queue (D-175) and are
  never skipped; `live check` waits for the queue; the Playwright test allows the lag.
- **DuckDB locks**: the feed file is held by one process (the API); a second process's `live
  reset` goes through `POST /api/live/reset` (D-010 pattern). The truth file is written by the
  simulator and read by `eval.reveal`: both retry briefly on a lock.
- **Threading**: ingest writes on the feed store's own connection and lock; the worker reads
  through a cursor of the same database and holds the store lock for the matcher, as replays do.
- **Scenario expectations may miss** (for example a returning P1 at another altitude, D-079): soft
  gaps; three honest attempts, then `cloud_gate.py accept 11`.
- **Process hygiene**: every server and child is started and stopped by its owner (`live check`,
  Playwright `webServer`, the API's lifespan); tests use stub children.
- **Module size**: new modules stay under about 400 lines; the API's live routes and the hub are
  split by concern.

## Out of scope

User accounts and auth (§2), real sensor adapters (only the contract), retraining, learning swarm
choreography from live swarms, multiple simultaneous simulators, the DTW workbench and the full
live-mode guide with screenshots (phase 12).

## Review changes

<!-- filled in when a reviewer's blocking issues are resolved -->
