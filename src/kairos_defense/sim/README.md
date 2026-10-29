# kairos_defense.sim

The seeded synthetic data generator (SPEC §8). It builds the world, the calendar, every flight and
swarm, what the sensors saw, the paperwork, and the ground truth.

## Responsibilities

- Build the world in region-frame ENU meters: 12 installations in 3 regions, jittered assets,
  sensors, launch parks and County Rd 12 (§8.1, D-005, D-006, D-031, D-033).
- Build the calendar: 549 nights (19:00 to 03:00 local), hourly weather, base events and public
  events (§8.2, D-023).
- Plan and fly every flight. Hobbyists, probers P1 to P6, copycats C1 and C2, the six planted P1
  flights and the swarm centers all go through one batched 10 Hz point-mass model (§8.3 to §8.5,
  D-024 to D-026).
- Derive each swarm drone from its center and the team's choreography (§8.7, D-035).
- Sense each drone with radar, RF and Remote ID, honoring terrain masks (§8.6, D-027, D-036,
  D-037), and group the drones into incidents (D-028, D-038).
- Write reports, clues and assessments, including the planted DELTA report and the wrong label
  (§8.8, §8.10, D-040 to D-042, D-045).
- Write the raw tables (§7.1) and the truth tables (§7.3). `writers.py` is the **only** module that
  opens `data/truth.duckdb` (rule 2, D-008, D-029).
- Write `reports/data_card.md` and its figures (§8.11, D-034).
- Draw every random value from `rng_for(seed, …)` streams named by stable keys, so the same seed
  gives identical table hashes and adding an actor changes no other flight (rule 4, §8.9).

## Public API

- `generate.generate(cfg, seed=None, window=None, nights=None) -> Generated`: builds everything in
  memory. `window=(first_night, last_night)` or `nights=[date, …]` flies only those nights (the
  tests use three weeks, or the four planted nights), while scheduling still runs over the full
  calendar, so a window holds exactly the flights the full run has on those nights. `Generated`
  holds:
  - `world`, `calendar`, `incidents` and `paper`;
  - `results`: every drone flown, as a `FlightResult`;
  - `tables`: raw `DataFrame`s by §7.1 name; `truth`: §7.3 `DataFrame`s;
  - `live`: a `LiveTiming`.
- `writers.write_all(app_cfg, raw, truth) -> {"raw": counts, "truth": counts}`: drops and recreates
  both DuckDB files and deletes `memory.duckdb`.
- `writers.table_hashes(path) -> dict[table, sha256]`: rows ordered by every column.
- `datacard.write_data_card(cfg, g, figures=True) -> Path`. Also `datacard.volumes(g)` and
  `datacard.EXPECTED` (§8.11).
- World and calendar:
  - `world.build_world(cfg, seed) -> World`, with `sites[id]` (`Site`: fence polygon, assets,
    sensors, mask), `roads`, `parks` and `tables()` (the six §7.1 world tables).
  - Helpers: `push_out`, `snap_to_road`, `ray_exit_distance`, `nominal_launch`,
    `unjittered_assets`.
  - `calendar.build_calendar(cfg, world, seed) -> Calendar`: `nights`, weather per region-night
    (wind m/s, "blows from" degrees, visibility km), base and public events. Time helpers:
    `local_to_utc_ms` and `utc_ms_to_local` use fixed offsets with no daylight saving.
- Flights:
  - `plan.FlightPlan` (frozen): one flight's drawn parameters, in region meters, true bearings and
    nominal (unwarped) values. `key` names every stream of the flight.
  - `actors.make_flight(cfg, world, spec, key, base, launch_local, rng, *, time_warp, jitter,
    target_override, incident_id)`: a prober or copycat plan. Also `actors.schedule(cfg, world, cal,
    seed)` and `actors.hobbyist_plans(...)`.
  - `scenario.p1_plans(cfg, world, seed)`: the six planted P1 flights.
    `scenario.orbit_established_s(...)` and `scenario.live_timing(...) -> LiveTiming` measure the
    §1.2 acceptance numbers.
  - `swarm.swarm_plans(cfg, world, cal, seed)`, `swarm.drone_paths(plan, center, seed)` and
    `formations.*`: the choreography geometry in the swarm frame.
  - `patterns.*`: the seven §8.4 patterns. Each returns a `PatternPath` (polyline `(n, 2)` m, speed
    per segment m/s, optional durations s and altitudes m).
  - `kinematics.fly_plans(plans, world, cal, seed) -> list[FlightPath]`: `t_s (n,)` s after launch
    at 1 Hz, `xyz (n, 3)` m, `phase (n,)` int8.
- Sensing and incidents:
  - `incidents.sense(plan, path, world, seed) -> FlightResult`, holding `hits` (radar), `rf` and
    `rid`. `group_incidents(results, world) -> list[Incident]`.
  - `sensors.radar_track(path, site, rng, outage_s)`, `rf_track(...)`, `rid_track(...)` and
    `stable_serial(seed, actor_id, drone)`.
- Paperwork:
  - `paperwork.paperwork(cfg, world, incidents, seed) -> Paperwork`: facts, reports, assessments
    and their truth.
  - `reports.make_reports`, `assessments.assess`, `facts.incident_facts`.
  - `lexicon.find_clues(text, roads, parks)` reads clues back out of report text, case-insensitive.
  - `lexicon.forbidden(text, allowed)` is the guardrail scan (§23, D-045).

## Data in and out

- In: `config/world.yaml`, `actors.yaml`, `scenario_demo.yaml`, and `app.yaml` (paths, and
  `reports_llm_paraphrase`). Nothing is read from disk besides config.
- Out, `data/kairos_defense.duckdb` (§7.1): `regions`, `installations`, `assets`, `roads`, `parks`,
  `sensors`, `incidents`, `track_points`, `rf_detections`, `remote_id`, `weather`, `base_events`,
  `public_events`, `reports`, `assessments`.
- Out, `data/truth.duckdb` (§7.3): `track_truth`, `true_paths` (1 Hz from launch), `clue_truth`,
  `assessment_truth`.
- Out, `reports/data_card.md` and `reports/figures/`: `pattern_<kind>.png` for the seven patterns,
  plus `swarm_S1.png` and `swarm_S2.png`. They are committed (D-034).
- `gen` deletes `data/memory.duckdb` (D-029).
- At seed 42 (`gen` output): 1,878 incidents (9 swarms), 1,904 tracks, 560,884 track points,
  414,999 RF detections, 686,263 Remote ID rows, 956 reports and 1,876 assessments. Live first
  contact is 21:40:06 and the orbit is established at T+79 s.

## How it works

1. `build_world`, then `build_calendar`.
2. `p1_plans`, `schedule` and `swarm_plans` produce `FlightPlan`s. Every plan's streams are
   `rng_for(seed, "flight", key, …)`.
3. `kinematics.build_reference` builds a timed reference in nominal seconds: takeoff → transit to
   the entry point → pattern → egress → landing, with pauses on transit and egress only. The time
   warp then scales durations by `w` and speeds by `1/w`. The reference is smoothed and flown 256
   flights at a time: lag τ 1.5 s, turn ≤ 45°/s, climb ≤ 4 m/s, ground = air + 0.3 × wind (D-025).
4. Swarm drones are the center plus the choreography offset plus a smooth 2 m wander (§8.7).
5. `sense` runs radar, RF and Remote ID per drone, each from its own stream. Radar scans draw a fixed
   number of variates, so what is visible never shifts a stream (D-027).
6. `group_incidents`: an incident needs a radar track. It spans the first to the last detection by
   any sensor. Ids are `<BASE>-<YYMMDD>-<HHMM>`; planted incidents keep theirs (D-028, D-038).
7. `paperwork` writes reports, clues and assessments from what was observed. The truth goes to
   `clue_truth` and `assessment_truth`. Live incidents get no paperwork (D-041).
8. `build_tables`, then `write_all`, then `write_data_card`.

## Configuration

- `world.yaml`: `seed`, `calendar`, `regions` (installations, origins, rotations, terrain masks,
  parks, roads), `installation_template`, `sensors_template`.
- `actors.yaml`: `hobbyists`, `probers`, `copycats`, `swarms`.
- `scenario_demo.yaml`: `live_incident`, `p1_flights`, `swarm_events`, `expectations`.
- `app.yaml`: `paths.duckdb`, `paths.truth`, `paths.memory`, `reports_llm_paraphrase` (true stops
  generation until phase 9, D-043).
- CLI: `kairos-defense gen [--seed N] [--config DIR] [--figures/--no-figures]`. `make data` passes
  `--seed 42`.

## Tests

- Phase 1 (fast): `test_world`, `test_calendar`, `test_patterns`, `test_kinematics`, `test_actors`,
  `test_sensors`, `test_scenario`, `test_generate` and `test_determinism`.
- Phase 2 (fast): `test_swarm_formations`, `test_swarm`, `test_rf`, `test_rid`, `test_reports`,
  `test_reports_lexicon`, `test_assessments` and `test_planted`.
- Fixtures in `tests/conftest.py`:
  - `world` and `cal` at seed 42;
  - `sample`: one flight per actor and base, plus 30 hobbyists;
  - `g42`: three weeks ending on the live night;
  - `swarms`: every swarm event at seed 42, flown with its drones (phase 2);
  - `planted`: the nights of the planted ALPHA and DELTA flights and both planted swarm events
    (phase 2);
  - `world_names`: road, park and installation names, which the guardrail scan allows (phase 2).
- Slow: `tests/slow/test_full_generation.py`. It checks full volumes, every planted item, live
  timing, and that two full runs give identical hashes.
- Run:
  - `uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"`
    (phase 1's exit check);
  - `uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"`
    (phase 2's);
  - `make test-all`.

## Gotchas

- Never draw from an existing stream for something new. Add a new name to
  `rng_for(seed, …)`, or every later draw on that stream shifts and the hashes change.
- `ccw` means the bearing from the target to the drone *decreases* (D-024). Bearings are true,
  clockwise from north. `rotation_deg` turns the template clockwise (D-007).
- The live timing (first contact 21:39:30 to 21:40:30, within 100 m of the fence; orbit T+65 to
  100 s) depends on geometry: BRAVO's layout, the mask, P1's speed and radius, and the live launch
  time. It does not depend on wind. Re-run `test_scenario.py` after changing any of these.
- Live incidents (`DEMO-BRAVO-0828`, `DEMO-SWARM-ECHO-0614`) are written to DuckDB for the replay.
  They have no paperwork, and later phases exclude them from indexes and history queries.
- Blotter reports are upper case, so clue matching must be case-insensitive (D-040).
- The figures set no font family, so their PNG bytes depend on the machine's fonts. The data does
  not (D-065).
- Track points (≈0.56 M) and RF detections (≈0.41 M) come in below §8.11 by design (D-030, D-044).
- Keep modules under about 400 lines. `world.py` (391) and `kinematics.py` (374) are near the limit.

## Changelog

- Phase 1:
  - `world.py`, `calendar.py`, `patterns.py`, `kinematics.py`, `plan.py`, `actors.py`,
    `scenario.py`;
  - `sensors.py` (radar), `generate.py`, `writers.py`, `datacard.py`;
  - `gen` became real (D-023 to D-034).
- Phase 2:
  - new modules: `formations.py`, `swarm.py`, `incidents.py`, `tables.py`, `facts.py`, `lexicon.py`,
    `reports.py`, `assessments.py`, `paperwork.py`, `figures.py`, `datacard_paper.py`,
    `datacard_util.py`;
  - `sensors.py` gained RF and Remote ID;
  - incidents now span all sensors;
  - `world.unjittered_assets` (D-033 (b)) (D-035 to D-045).
- Backfill (2026-10-28): this README; D-065 notes the figures' font.
- Phase 2 backfill (2026-10-28): checked against the code at `ba703ec`; added the `nights=` option
  and the phase 2 fixtures (D-066). No code changes.
