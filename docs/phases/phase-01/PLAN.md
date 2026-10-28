# Phase 1: World, flights and radar, plan

> **Backfilled 2026-10-28, as built.** Phase 1 was built by hand in a Claude Code cloud session
> before the autopilot existed, and no plan file was kept. This plan is reconstructed from commit
> `1a13664` (`phase 1: world, calendar, flights and radar with truth`), the phase 1 entry in
> `docs/PROGRESS.md` and D-023 to D-034 in `docs/DECISIONS.md`. It describes what was planned and
> built, not a plan for new work.

## Goal

Generate the world, the calendar and every non-swarm flight with radar tracks, plus ground truth
(SPEC §20, phase 1). `kairos-defense gen --seed 42` writes `data/kairos_defense.duckdb` (§7.1 raw
tables) and `data/truth.duckdb` (§7.3), the first version of `reports/data_card.md` and one sample
figure per pattern type. Swarms, RF, Remote ID, reports and assessments wait for phase 2.

## Inputs read

- `CLAUDE.md`: rules 1 (synthetic only), 2 (truth isolation), 4 (determinism), 6 (ports), code
  conventions (meters, seconds, bearings clockwise from north, region-frame ENU).
- SPEC §6.2 (`world.yaml`: regions, installation template, sensors, parks, roads, terrain masks),
  §6.3 (`actors.yaml`: hobbyists, probers P1 to P6, copycats C1 and C2), §6.4
  (`scenario_demo.yaml`: the six P1 flights, the live flag, expectations), §7.1 and §7.3 (raw and
  truth DDL), §8.1 to §8.6 with radar only (world, calendar, kinematics, patterns, time warp,
  sensors), §8.9 (`rng.py`), §8.10 (planted scenario, P1 flights only), §8.11 (writers, data card,
  expected volumes), §20 phase 1 block.
- `docs/DECISIONS.md` D-001 to D-022, mainly:
  - D-003: BRAVO terrain mask, P1 at 15 m/s, live launch 21:38:45 with `jitter: none`, T+0 = first
    radar contact, a flight nobody detects makes no incident;
  - D-004: P1 orbits at 3°/s;
  - D-005: launch points pushed 300 m outside the fence, one launch park per installation 2.2 km out;
  - D-006: County Rd 12 as straight segments densified to 50 m, snap within 500 m;
  - D-007: true bearings, clockwise `rotation_deg`;
  - D-008: the truth scan allows `sim/writers.py`.
- `docs/PROGRESS.md`, phase 0 entry: the scaffold, the config models and `rng.py` are in place;
  `gen` is a stub. No phase 0 REPORT.md existed then (it was backfilled later).

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md`:

- **D-023**: calendar and weather. Nine hourly rows per region-night, Weibull(k = 2) wind with mean
  5 m/s through a Gaussian AR(1) copula (ρ 0.7), direction "blows from" as a random walk, values
  rounded like a METAR and used as rounded by the flight model. Exercise, VIP and shift-change rules;
  public events on Friday and Saturday nights in public parks.
- **D-024**: pattern geometry. `ccw` means the bearing from target to drone decreases; perimeter runs
  clockwise; lawnmower and figure-eight axes follow the target's long axis; pattern sizes for the
  entry point; transit with dips. Flags that §9.4's `loiter_dir` sign must be read the other way in
  phase 3.
- **D-025**: flight model. A timed reference in nominal seconds, scaled by the time warp, smoothed
  (2 s Gaussian) and flown by guidance (feed-forward plus 0.3/s pull) with the §8.3 caps; nominal
  climb 2.8 m/s; hover jitter in the reference; pauses on transit and egress only; `jitter: none`
  also means no pauses. Batched 256 flights at a time.
- **D-026**: actor plans. Disc-uniform launch jitter and recovery offsets, radius ±8% on orbit and
  figure-eight lobes, copycats fly the mimicked actor's pattern from their own launch bearing,
  stratified "uniformly by month", one actor per hobbyist flight, 30% of hobbyists first fly 150 m
  inside the fence.
- **D-027**: radar. Slant range, `quality` = detection probability, outages measured from launch,
  dropouts as alternating geometric spells, a fixed number of variates per scan.
- **D-028**: incident ids `<BASE>-<YYMMDD>-<HHMM>` of the first detection (local), with `-2`, `-3` on
  a clash. Phase 1 spans incidents over radar points only.
- **D-029**: `gen` deletes `memory.duckdb`; `sim/writers.py` is the only truth writer; `true_paths`
  at 1 Hz from launch; `table_hashes` over rows ordered by all columns.
- **D-030**: track points come in at about 0.54 M against ≈1 M in §8.11. Kept, and reported.
- **D-031**: County Rd 12 joins P1's launch points at the bases where its planted flights target its
  own target, derived from the scenario.
- **D-032**: public events never trigger the hobbyist doubling with the shipped world; implemented
  and kept.
- **D-033**: BRAVO's seeded asset jitter puts the live orbit at T+94 s, inside the window but late
  for the T+90 beat. Left open for the product owner (resolved in phase 2).
- **D-034**: commit the data card and the seven pattern figures as exit evidence.

## Work breakdown

1. **DDL.** `src/kairos_defense/store/ddl.py`: `RAW_DDL` (§7.1) and `TRUTH_DDL` (§7.3) as
   `dict[name, CREATE TABLE]`, plus `columns()` and the column lists the writers check against.
2. **World.** `sim/world.py`: `build_world(cfg, seed)`. Rotate the installation template clockwise,
   jitter each asset center from its own stream, shift by the origin; sensors from the template;
   one launch park per base (D-005); County Rd 12 through P1's nominal launch points (D-006, D-031);
   `push_out`, `snap_to_road`, `ray_exit_distance`; the terrain mask; `world_tables()` for the six
   world tables.
3. **Calendar.** `sim/calendar.py`: `build_calendar` with 549 nights (2025-03-01 to 2026-08-31),
   hourly weather, base events and public events (D-023); local ↔ UTC helpers with fixed offsets.
4. **Patterns.** `sim/patterns.py`: `orbit`, `lawnmower`, `figure8` (lemniscate of Gerono),
   `perimeter`, `hover`, `transit_dips`, `random_walk`, plus `pattern_size`, `entry_point` and
   `fence_crossing_goal` (D-024). Pure geometry, no time warp.
5. **Kinematics.** `sim/kinematics.py`: `build_reference` (takeoff → transit → pattern → egress →
   landing, pauses), `sample_reference` (warp, 10 Hz, altitude noise, smoothing), `simulate` and
   `fly_plans` (batched point-mass model, wind as of the hour), output at 1 Hz (D-025).
6. **Plans.** `sim/plan.py` (`FlightPlan`, frozen, keyed by a stable flight key) and `sim/actors.py`:
   `make_flight` for probers and copycats, `schedule_actor` (stratified months, VIP 3× weight),
   `hobbyist_plans` (Poisson per base-night from one uniform per night), `schedule` (D-026).
7. **Scenario.** `sim/scenario.py`: `p1_plans` (the six planted flights with base, launch time, warp,
   `jitter: none`, `target_override`, `sensor_outage_s`, live status), `orbit_established_s` and
   `live_timing` for the §1.2 acceptance numbers.
8. **Radar.** `sim/sensors.py`: `radar_track` with range-dependent detection, range-dependent noise,
   the dropout chain, planted outages and the terrain mask (D-027).
9. **Pipeline and writers.** `sim/generate.py`: world → calendar → plans → flights → radar →
   incidents (D-028) → tables, with a `window` option so tests fly three weeks only.
   `sim/writers.py`: `write_all` (drop and recreate both DuckDB files, bulk insert, delete
   `memory.duckdb`) and `table_hashes` (D-029).
10. **Data card.** `sim/datacard.py`: volumes against §8.11, flights, incidents per base and actor
    type, probers and copycats, radar tracks, planted P1 flights, live timing, row counts, and three
    sample flights per pattern plotted to `reports/figures/pattern_<kind>.png` (D-034).
11. **CLI.** `kairos-defense gen --seed --config --figures/--no-figures` becomes real and prints a
    rich summary (volumes, expected values, live timing, elapsed).
12. **Docs.** PROGRESS.md entry, D-023 to D-034, one commit `phase 1: ...`.

## Tests

Shared fixtures in `tests/conftest.py`: `cfg`, `world` and `cal` at seed 42; `sample` (one flight per
actor and base plus 30 hobbyists); `g42` (the generator's output for the three weeks ending on the
live night, 2026-08-11 to 2026-08-31).

Fast (`tests/unit`):

- `test_world.py`: `test_twelve_sites_three_regions`, `test_rotation_is_clockwise`,
  `test_sensor_positions`, `test_asset_jitter_is_seeded_and_small`,
  `test_each_site_has_a_launch_park_22_km_out`, `test_county_rd_12_shape`,
  `test_road_within_250_m_of_p1_launch_with_jitter[ALPHA|BRAVO|DELTA]`,
  `test_snap_skips_far_roads`, `test_push_out_rule`, `test_ray_exit_distance`,
  `test_bravo_terrain_mask`, `test_world_tables_match_ddl`.
- `test_calendar.py`: `test_549_nights`, `test_time_helpers`, `test_weather_series`,
  `test_wind_is_hour_to_hour_correlated`, `test_wind_vector_blows_downwind`,
  `test_weather_is_seeded`, `test_shift_changes_daily_at_2200`, `test_exercise_and_vip_counts`,
  `test_public_events_on_weekends_in_public_parks`.
- `test_patterns.py`: `test_orbit[ccw|cw]` (bearing decreases for ccw), `test_lawnmower`,
  `test_figure8`, `test_perimeter_is_clockwise_at_offset`, `test_hover`, `test_transit_dips`,
  `test_random_walk_fits_budget_and_radius`, `test_fence_crossing_goal`,
  `test_entry_point_distances`.
- `test_kinematics.py`: `test_sample_covers_every_pattern`,
  `test_speed_climb_and_turn_rate_limits`, `test_altitude_within_band` (band ± 15 m),
  `test_orbit_radius_within_10_percent` (noiseless paths),
  `test_ground_starts_and_ends_on_the_ground`, `test_time_warp_scales_durations_not_shapes`,
  `test_pauses_never_inside_the_pattern`, `test_jitter_none_has_no_pauses`,
  `test_rows_are_independent_of_their_batch`, `test_wind_drift_pushes_a_hover_downwind`.
- `test_actors.py`: `test_counts_per_actor`, `test_keys_unique`, `test_bases_and_time_windows`,
  `test_time_warp_ranges`, `test_spread_uniformly_by_month`, `test_vip_nights_weighted_three_times`,
  `test_launch_points_outside_the_fence`, `test_pushed_out_launches`,
  `test_hobbyists_launch_from_their_park`, `test_cross_fence_share`, `test_per_flight_variation`.
- `test_sensors.py`: `test_dropout_chain` (≈15% of seconds lost),
  `test_detection_rate_falls_with_range[500|1800|3200]`, `test_position_noise_grows_with_range`,
  `test_nothing_below_min_altitude_or_out_of_range`, `test_planted_outage`,
  `test_terrain_mask_hides_low_targets`, `test_same_stream_same_hits`.
- `test_scenario.py`: `test_six_planted_flights_as_configured` (base, start time, warp),
  `test_every_planted_flight_is_detected`, `test_only_the_demo_flight_is_live`,
  `test_live_flight_has_no_jitter`, `test_county_rd_12_within_250_m_of_launch[5 keys]`,
  `test_charlie_keeps_its_nominal_launch`, `test_bravo_251114_outage`,
  `test_live_launch_is_in_bravo_radar_shadow`, `test_live_first_contact` (within 100 m of the fence
  and inside `live_first_contact_local`), `test_live_orbit_established`
  (`live_orbit_established_s`), `test_orbit_established_known_answer`.
- `test_generate.py`: `test_tables_match_the_ddl`, `test_incident_spans_its_detections`,
  `test_incident_ids_never_name_the_actor`, `test_truth_links_every_track`,
  `test_undetected_flights_make_no_incident`, `test_data_card`.
- `test_determinism.py`: `test_two_runs_give_identical_table_hashes` (three-week window, SHA-256 per
  table), `test_a_different_seed_gives_different_data`, `test_window_holds_the_live_flight`,
  `test_adding_an_actor_changes_no_other_flight`.
- `test_cli.py`: `gen` is no longer a stub.

Slow (`tests/slow/test_full_generation.py`, `@pytest.mark.slow`): `test_volumes_within_15_percent`,
`test_every_planted_flight_detected_and_live_on_time`, `test_full_run_is_deterministic` (two full
runs give identical hashes).

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it produces |
|---|---|---|
| Data generates from config, seeded | `make data` (`kairos-defense gen --seed 42`) | the rich summary: incidents, tracks, track points, flights not detected, live first contact and orbit, elapsed |
| Incident and track counts within ±15% of §8.11 | `make data`, then `reports/data_card.md` | "Volumes against SPEC §8.11" table: incidents and tracks "within ±15%" |
| Figures exist for every pattern type | `make data` | `reports/figures/pattern_{orbit,lawnmower,figure8,perimeter,hover,transit_dips,random_walk}.png` |
| World, kinematics, pattern, scenario and determinism tests pass | `uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"` | `N passed` |

The check runs from `make clean` as one `&&` chain and must exit 0. `make check` and the slow tests
(`make test-all`) add to it.

## Documentation to write or update

- `docs/PROGRESS.md`: the phase 1 session-log entry and the exit-check evidence line.
- `docs/DECISIONS.md`: D-023 to D-034.
- `reports/data_card.md` and `reports/figures/pattern_*.png` (committed, D-034).
- Package READMEs did not exist as a convention yet. `sim/README.md` is backfilled now; see
  REPORT.md.

## Risks and mitigations

- **The live flight misses the §1.2 timing windows** (first contact 21:39:30 to 21:40:30, orbit
  T+65 to 100 s). Mitigation: a timed reference makes timing independent of wind (D-025),
  `jitter: none` turns off pauses on the live flight, and tests assert both windows. Residual risk:
  BRAVO's seeded layout gives T+94 s, inside the window but late for T+90 (D-033, open).
- **Random streams shift when something is added.** Mitigation: every stream is named by a stable
  flight key (`rng_for(seed, "flight", key, ...)`), radar scans draw a fixed number of variates, and
  `test_adding_an_actor_changes_no_other_flight` checks it.
- **Kinematic limits broken by warp or smoothing.** Mitigation: nominal climb 2.8 m/s so a warp of
  0.7 stays under 4 m/s; hover jitter goes into the reference; the limits are tested on the output.
- **Truth leaks into app code.** Mitigation: only `sim/writers.py` opens the truth file, and the §7.6
  scan (phase 0) enforces it.
- **Volumes off target.** Mitigation: launch parks inside radar range (D-005), measured in the data
  card. Track points stay below ≈1 M by design (D-030).
- **Slow generation.** Mitigation: flights flown in numpy batches of 256 (about 13 s for 1,869
  flights on the cloud machine); tests fly a three-week window.

## Out of scope

Swarms, RF, Remote ID, reports, clues, assessments and the planted DELTA paperwork (phase 2);
incident spans across sensors (phase 2, D-028); features, signatures and indexes (phase 3); the
`loiter_dir` sign fix (phase 3, D-024).

## Review changes

None. The plan was approved by the user in the interactive session; there was no autopilot reviewer.
