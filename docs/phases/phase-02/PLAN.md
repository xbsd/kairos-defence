# Phase 2: Swarms, RF, Remote ID, reports and assessments, plan

> **Backfilled 2026-10-28, as built.** Phase 2 was built by hand in a Claude Code cloud session
> before the autopilot existed, and no plan file was kept. This plan is reconstructed from commit
> `06cc826` (`phase 2: swarms, RF, Remote ID, reports and assessments`), the phase 2 entry in
> `docs/PROGRESS.md`, D-033 (resolved) and D-035 to D-045 in `docs/DECISIONS.md`, and the code. It
> describes what was planned and built, not a plan for new work.

## Goal

Complete the synthetic dataset (SPEC §20, phase 2):

- swarms with formations and actions, random and planted;
- RF detections and Remote ID (`on`, `off`, `spoofed`);
- reports from the Appendix A templates with a clue model and `clue_truth`;
- assessments with the planted error and `assessment_truth`;
- the planted story: the DELTA report, the wrong DELTA label, and the GOLF and ECHO swarm events.

`kairos-defense gen --seed 42` still writes everything from scratch, and `reports/data_card.md`
gains report counts and delays, clue rates and swarm incidents. Features and indexes wait for
phase 3.

## Inputs read

- `CLAUDE.md`:
  - rule 1 (synthetic only) and rule 9 (link flights, never people): reports carry vehicle colors
    and types, roads, lights, sound, launch sites and departure directions, never names, plates
    or addresses;
  - rule 2 (truth isolation): `clue_truth` and `assessment_truth` go to `truth.duckdb` through
    `sim/writers.py`;
  - rule 4 (determinism): every new draw gets its own `rng_for` name;
  - rule 5 (offline): no LLM paraphrase.
- SPEC:
  - §6.3: `actors.yaml`, mainly `swarms` (S1 and S2, their choreographies), `rf_family`,
    `rid_on_prob` and `clues`;
  - §6.4: `scenario_demo.yaml`'s planted DELTA report and assessment, `swarm_events` and
    `expectations`;
  - §7.1 and §7.3: the `incidents`, `rf_detections`, `remote_id`, `reports` and `assessments`
    tables, and `clue_truth` and `assessment_truth`;
  - §8.6: RF, Remote ID and terrain masks for all sensors. §8.7: swarms. §8.8: reports, clues and
    assessments;
  - §8.10 (planted scenario), §8.11 (writers, data card, expected volumes), Appendix A (report
    templates), and the §20 phase 2 block.
- `docs/DECISIONS.md` D-001 to D-034, mainly:
  - D-003: T+0 is first radar contact, and a flight nobody detects makes no incident;
  - D-009: S1's random events fall after 2026-06-14;
  - D-011: P1-DELTA-260419 gets only its planted report; the other P1 flights get normal paperwork;
  - D-028: phase 2 must recompute incident spans across radar, RF and Remote ID;
  - D-030: the track-point volume runs below §8.11 by design;
  - D-033: open, BRAVO's seeded layout puts the live orbit at T+94 s.
- `docs/PROGRESS.md`, the phase 1 entry: `gen`, the world, the calendar, every single-drone flight,
  the radar and the truth writer are in place; open items D-024, D-028, D-030 and D-033. No phase 1
  REPORT.md existed then (it was backfilled later).

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md`:

- **D-033 (resolved, option (b), chosen by the product owner):** the live P1 flight's target
  (BRAVO's fuel farm) keeps its template position. Its jitter is still drawn, so no other stream
  moves (`world.unjittered_assets`). The live orbit forms at T+79 s instead of T+94 s.
- **D-035**, swarm choreography, schedule and geometry:
  - the swarm frame is fixed to the travel heading. Line abreast lies across the heading, trail
    along it, the V has a 45° half-angle with drone 0 at the apex, and the triangle sits on an
    equilateral lattice;
  - actions transform the current offsets and follow a smoothstep. Formation changes blend, then
    hold;
  - the center creeps to the orbit, orbits clockwise during `orbit_target`, then holds. Drones add
    a smooth OU wander (σ 2 m, τ 10 s);
  - each event draws its own time warp in [0.7, 1.4], an approach bearing and ±10% step factors.
    It launches 2 km out and its launch time is uniform in 20:00 to 01:00;
  - swarms broadcast no Remote ID.
- **D-036**, RF: one detection per scan at 0.5 Hz while airborne, within 4 km and outside the mask.
  SNR is 40 dB at 100 m minus 20 dB per decade. Planted outages stay radar-only. An unknown family
  is an error.
- **D-037**, Remote ID: serials are `SN-` plus 16 hex digits. With `on`, a drone keeps its serial
  on every flight, and the operator is within 10 m of launch. With `spoofed`, the serial is new
  each flight and the operator is 1 to 3 km away. Broadcasts are 1 Hz within 3 km.
- **D-038**: an incident needs a radar point. Its span is the first to the last detection by any
  sensor. Sensors log every flown drone; swarm drones share one incident.
- **D-039**: the live T+0 stays first radar contact. `LiveTiming.radar_lag_s` measures the gap to
  the first detection by any sensor (0 s at seed 42, because the mask hides RF too).
- **D-040**, reports:
  - the source mix, delays and grades;
  - `event_ts` and the report position;
  - a terse security-forces line for the four bases Appendix A does not style, and upper-case
    blotters;
  - the clue model and per-actor clue profiles;
  - the planted report gets the lights and departure clauses the narrative template needs, so its
    text matches Appendix A's example.
- **D-041**: live incidents get no reports or assessments. `assessment_truth` still holds their
  correct labels.
- **D-042**: a "stable serial" means mode `on` with at least one broadcast received. The 20%
  mislabel applies to prober incidents only. Correct labels: copycats are `probing` and swarms are
  `swarm`.
- **D-043**: `reports_llm_paraphrase: true` stops `gen` with an error naming phase 9.
- **D-044**, deviation: RF detections come in at about 415 k against ≈0.5 M. Kept and reported.
- **D-045**, the guardrail scan: world vocabulary and serials are removed first, then the scan
  flags plates, plate and registration words, addresses, phones, e-mail, titles before names,
  words describing a person, and a lexicon of about 300 names.

## Work breakdown

1. **D-033 (b).** `sim/world.py`: `unjittered_assets(cfg)`, derived from the scenario like D-031.
   `build_world` still draws the jitter but does not apply it to those assets.
   `test_live_target_is_not_jittered`.
2. **Formations and actions.** `sim/formations.py`:
   - `formation(kind, n, spacing_m)` (line abreast, V, triangle, trail), centered on the centroid;
   - `resolve_steps` (±10% factors);
   - the `Timeline` of offsets per second: `rotate` cw or ccw, `expand`, `split` (centroid fixed),
     `orbit_target`, smoothstep blends and holds;
   - `to_region`, `first_orbit_radius` and `centroid_path`, which creeps from the entry point to
     the orbit, orbits clockwise and holds.
3. **Swarms.** `sim/swarm.py`:
   - `swarm_plans`: random events (S1 after 2026-06-14, D-009) plus the planted `swarm_events`,
     each a center `FlightPlan` with a `choreography` pattern;
   - `drone_paths`: center plus offset plus wander per drone;
   - `drone_plans`.
   - `kinematics.py` and `patterns.py` gain a `choreography` hook so the §8.3 engine flies swarm
     centers. Existing flights do not change.
4. **RF and Remote ID.** `sim/sensors.py`: `rf_band`, `rf_track` (D-036), `stable_serial`, and
   `rid_track` with the modes `on`, `spoofed` and `off` (D-037). The terrain mask applies to all
   three sensors.
5. **Incidents across sensors.** `sim/incidents.py`: `FlightResult` (plan, true path, radar, RF,
   Remote ID), `sense`, and `group_incidents`. An incident needs a radar track; its span covers all
   sensors; tracks are `T1…Tn` per drone; planted ids are kept (D-028, D-038). Also `heard_only`.
   The incident code moved here from `generate.py`.
6. **Tables.** `sim/tables.py`: the `incidents`, `track_points`, `rf_detections` and `remote_id`
   frames and the truth tables, plus `build_tables`. The table code moved here from `generate.py`.
7. **Facts and lexicon.** `sim/facts.py`: `IncidentFacts`. It holds what the paperwork may know:
   the times, the mean radar position and median altitude, what the drone was near, and the serial
   received. It also holds the truth that clues are scored against: the actor's vehicle, the road,
   the departure direction toward the recovery point, the lights, the sound and the launch site.
   Also `actor_profile` (lights, sound and launch site per actor) and `nearest_road`.
   `sim/lexicon.py`: the clue vocabulary, `compass8`, `park_name`, `find_clues` (reads clues back
   out of text, case-insensitive) and `forbidden` (the guardrail scan, D-045).
8. **Reports.** `sim/reports.py`:
   - sources drawn without repeats, with delays and grades per §8.8;
   - base styles (narrative, blotter, terse) and the Appendix A templates, plus the hobbyist
     variant;
   - the clue model, with every clue in the text written to `clue_truth`;
   - swarm wording;
   - `planted_report` (D-040).
9. **Assessments.** `sim/assessments.py`: the rules (Remote ID `on` and heard → hobbyist, swarm →
   swarm, else unknown), the 20% prober mislabel, `correct_label`, `planted_assessment` and
   `assessment_truth` (D-042).
10. **Paperwork.** `sim/paperwork.py`: for every incident, take its facts, then either its planted
    paperwork or its generated reports (stream `paperwork/<key>/reports`) and assessment (stream
    `paperwork/<key>/assessment`). Live incidents get none (D-041). The paraphrase flag stops
    generation (D-043).
11. **Pipeline.** `sim/generate.py`:
    - single flights and swarm centers are flown in one batch, then swarm drones are derived and
      every drone is sensed;
    - then incidents, paperwork, tables and the live timing (`radar_lag_s`, D-039, in
      `scenario.py`);
    - a `nights=` option alongside `window=` lets tests fly only the planted nights.
    - `actors._disc` is renamed `disc_offset` so swarms can reuse it.
12. **Data card and figures.** `sim/datacard.py` gains swarm incidents, sensors, planted items with
    swarm events, and the live timing with `radar_lag_s`. `sim/datacard_paper.py` covers reports
    (sources, grades, counts per actor type, the delay histogram, styles), clue rates and the
    assessment confusion table. `sim/datacard_util.py` has the shared helpers. `sim/figures.py`
    holds phase 1's pattern plots and the new swarm snapshots (`swarm_S1.png`, `swarm_S2.png`).
    The split keeps every module under 400 lines.
13. **CLI.** The `gen` summary adds `remote_id`, swarm incidents, drones flown and drones not
    tracked.
14. **Docs.** PROGRESS.md entry, D-033's resolution, D-035 to D-045, one commit `phase 2: ...`.

## Tests

New fixtures in `tests/conftest.py`:

- `swarms`: every swarm event at seed 42, flown with its drones;
- `planted`: `generate(cfg, 42, nights=...)` for the nights of the planted ALPHA and DELTA flights
  and both planted swarm events;
- `world_names`: road, park and installation names, which the guardrail scan allows.

Fast (`tests/unit`):

- `test_swarm_formations.py` (21):
  - `test_swarm_formation_spacing_and_center[3|5|7 × line_abreast|v|triangle|trail]`;
  - `test_swarm_formation_orientation`, `test_swarm_unknown_formation_is_an_error`,
    `test_swarm_choreography_must_start_with_a_formation`;
  - `test_swarm_rotate_is_clockwise_for_cw`, `test_swarm_rotate_ccw_and_expand`,
    `test_swarm_split_keeps_the_centroid`, `test_swarm_formation_change_blends_then_holds`;
  - `test_swarm_timeline_from_config_with_jitter`,
    `test_swarm_centroid_path_creeps_then_orbits_clockwise`.
- `test_swarm.py` (7): `test_swarm_schedule` (counts, bases, D-009),
  `test_swarm_same_choreography_with_jitter` (±10%),
  `test_swarm_spacing_within_20_percent` (every hold of every event), `test_swarm_rotation_direction`,
  `test_swarm_orbit_target` (radius), `test_swarm_drones_are_plausible` (speeds),
  `test_adding_a_swarm_team_changes_no_other_event`.
- `test_rf.py` (14): `test_rf_band_from_family[7 families]`, `test_rf_unknown_family_is_an_error`,
  `test_rf_family_per_actor`, `test_rf_rate_while_airborne_and_in_range`, `test_rf_bearing_noise`,
  `test_rf_snr_falls_with_range`, `test_rf_honors_the_terrain_mask`, `test_rf_same_stream_same_hits`.
- `test_rid.py` (7): `test_rid_stable_serial_per_drone`, `test_rid_on_broadcasts_serial_and_operator`,
  `test_rid_spoofed_serial_changes_every_flight`, `test_rid_off_broadcasts_nothing`,
  `test_rid_range_ground_and_mask`, `test_rid_unknown_mode_is_an_error`, `test_rid_modes_per_actor`.
- `test_reports.py` (10):
  - `test_reports_every_clue_has_a_truth_row` (and every truth row's clue is in the text);
  - `test_reports_delays_within_source_ranges`, `test_reports_grades_from_source_lists`;
  - `test_reports_count_per_actor_type`, `test_reports_hobbyist_rate_and_variant`;
  - `test_reports_clue_rates` (on 3,000 synthetic incidents),
    `test_reports_actor_without_a_vehicle_gets_only_wrong_ones`;
  - `test_reports_base_styles`, `test_reports_swarm_texts_say_formation`,
    `test_reports_llm_paraphrase_needs_phase_9`.
- `test_reports_lexicon.py` (31):
  - `test_reports_have_no_forbidden_content` (every generated text, more than 1,000);
  - `test_reports_scanner_catches_offenders[12 made-up offenders]`;
  - `test_reports_scanner_allows_world_vocabulary[7]`, `test_reports_name_lexicon_avoids_world_words`;
  - `test_reports_find_clues_reads_capitals`, `test_reports_compass8[8]`, `test_reports_park_names`.
- `test_assessments.py` (5): `test_assessments_one_per_history_incident`,
  `test_assessments_recorded_2_to_36_h_after_the_end`, `test_assessments_label_rules`,
  `test_assessments_mislabel_rate`, `test_assessments_truth_labels`.
- `test_planted.py` (8):
  - `test_planted_delta_report` (contains "white pickup", "County Rd 12", "21:20" and "22:05";
    source, grade and time as configured; its only report; true `clue_truth` rows);
  - `test_planted_wrong_assessment`, `test_planted_other_p1_flights_get_normal_paperwork`;
  - `test_planted_swarm_events[GOLF history | ECHO live]`;
  - `test_planted_live_incidents_have_no_paperwork`, `test_planted_rf_families`,
    `test_planted_live_t0_is_first_radar_contact` (D-039).
- Changes to phase 1 files:
  - `test_generate.py`: `test_incident_spans_its_detections` becomes `..._by_any_sensor` (D-028),
    and `test_tracks_per_incident` is new;
  - `test_world.py`: `test_live_target_is_not_jittered` is new (D-033).

Slow (`tests/slow/test_full_generation.py`): `test_full_swarms_and_paperwork` (report and assessment
volumes, the swarm count, paperwork coverage). The existing determinism tests hash every table, so
they now cover the new ones too.

In all, phase 2 adds 103 tests in eight new files, plus 2 new tests in phase 1 files: 181 → 286
fast tests, and 3 → 4 slow tests.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it produces |
|---|---|---|
| Data generates with swarms, RF, Remote ID and paperwork | `make data` (`kairos-defense gen --seed 42`) | the rich summary: incidents, tracks, track points, RF detections, reports, assessments, Remote ID rows, swarm incidents, drones flown and not tracked, live timing |
| Swarm, RF, Remote ID, report, assessment and planted tests pass | `uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"` | `N passed` |
| Data card updated | `make data`, then `reports/data_card.md` | new sections: swarm incidents, sensors, reports (sources, counts per actor type, delay histogram, styles), clue rates, assessments; swarm figures |
| Planted items present | read back from `data/kairos_defense.duckdb` and `data/truth.duckdb`, and the data card's planted section | the DELTA report text, its `clue_truth` rows, the `hobbyist` assessment with truth `probing`, and the `S1-GOLF-260503` and `DEMO-SWARM-ECHO-0614` incidents with 5 tracks each |

The check runs from `make clean` as one `&&` chain and must exit 0. `make check` and the slow tests
(`make test-all`) add to it.

## Documentation to write or update

- `docs/PROGRESS.md`: the phase 2 session-log entry and the exit-check evidence line.
- `docs/DECISIONS.md`: D-033's resolution, D-035 to D-045.
- `reports/data_card.md`, the regenerated pattern figures, and the new `swarm_S1.png` and
  `swarm_S2.png` (committed, D-034).
- Package READMEs were not a convention yet. The `sim/README.md` written in phase 1's backfill
  covers phase 2; this backfill adds the phase 2 fixtures to it (see REPORT.md).

## Risks and mitigations

- **D-033's fix moves the live timing out of its windows.** Mitigation: (a), (b) and (c) were
  measured before choosing (first contact and orbit for each). With (b), first contact is 21:40:06
  and 71 m out, and the orbit is at T+79 s, inside both §1.2 windows. `test_scenario.py` and
  `test_live_target_is_not_jittered` guard it.
- **Swarm formations become meaningless or implausible.** Mitigation: a frame tied to the
  approach heading; smooth blends with a speed-based minimum; tests on spacing (±20% during every
  hold of every event), rotation sense, orbit radius and drone speeds. The swarm figures were
  reviewed by eye.
- **New draws shift existing streams.** Mitigation: every new component draws from its own name.
  These are `rng_for(seed, <team>, "schedule")`, `("flight", key, "plan" | "wander" | "rf" |
  "rid")`, `("rid-serial", actor, drone)`, `("profile", actor)` and `("paperwork", key, "reports" |
  "assessment")`. Radar keeps `("flight", key, "radar")`, so existing flights are unchanged.
  `test_adding_a_swarm_team_changes_no_other_event` and phase 1's determinism tests (SHA-256 of
  every table, now including the new ones) check it.
- **Paperwork leaks real-looking personal data.** Mitigation: clue types limited to §8.8's list,
  serials shaped `SN-…`, and the D-045 scan over every text, tested on made-up offenders and on
  world vocabulary that must pass.
- **Clue truth incomplete.** Mitigation: `find_clues` reads every report back, and the test
  requires a `clue_truth` row for each clue found, and the reverse.
- **Live paperwork leaks the future.** Mitigation: no reports or assessments for live incidents
  (D-041), tested.
- **Incidents without tracks** (heard by RF only). Mitigation: an incident needs a radar point
  (D-038). The data card counts drones heard but never tracked (0 at seed 42).
- **Modules grow past 400 lines.** Mitigation: the incident and table code left `generate.py`,
  and the data card split into `datacard.py`, `datacard_paper.py`, `datacard_util.py` and
  `figures.py`.

## Out of scope

- Features, signatures, windows, RF and Remote ID association, and the `loiter_dir` sign: phase 3
  (D-024 → D-047).
- Clue extraction into `report_clues`: phase 5 (case-insensitive, D-040).
- The LLM paraphrase: phase 9 (D-043).
- Swarm features and swarm matching: phase 9.

## Review changes

None. The plan was approved by the user in the interactive session, including the choice of
D-033 (b). There was no autopilot reviewer.
