# Phase 2: Swarms, RF, Remote ID, reports and assessments, report

Status: done · Date: 2026-10-28 (built; docs backfilled the same day) · Commits: `06cc826` (phase 2)

## Summary

Phase 2 completed the synthetic dataset. `kairos-defense gen --seed 42` now also produces:

- swarms (two teams, formations and actions, 9 events);
- RF detections and Remote ID (`on`, `off`, `spoofed`), with the terrain mask applied to every
  sensor;
- incidents that span all sensors;
- 956 reports from the Appendix A templates, with a clue model and `clue_truth`;
- 1,876 assessments, with the 20% prober mislabel and `assessment_truth`;
- the planted story: the DELTA report naming the white pickup on County Rd 12, the wrong
  `hobbyist` label, and the GOLF and ECHO swarm events.

It also resolved D-033 with option (b), so the live orbit now forms at T+79 s. Phase 2 was built by
hand in a Claude Code cloud session: 286 fast and 4 slow tests. These documents were reconstructed
on 2026-10-28. The exit check passes again today with identical data.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Formations | line abreast, V, triangle and trail in a heading-fixed swarm frame; `rotate`, `expand`, `split` and `orbit_target` as offset transforms; smoothstep blends and holds; the centroid path (D-035) | `sim/formations.py` |
| Swarms | random events per team (S1 after the live encore, D-009) plus the planted `swarm_events`; center plans flown by the §8.3 engine through a `choreography` hook; drones = center + offset + a 2 m OU wander | `sim/swarm.py`, hooks in `sim/kinematics.py` and `sim/patterns.py` |
| RF and Remote ID | RF at 0.5 Hz within 4 km, with family → band, bearing noise and an SNR falling with range (D-036). Remote ID at 1 Hz within 3 km: a stable `SN-` serial and an operator within 10 m of launch for `on`; a new serial and an operator 1 to 3 km away for `spoofed`; nothing for `off` (D-037). The terrain mask applies to all three sensors | `sim/sensors.py` |
| Incidents | `FlightResult` (plan, truth, radar, RF, Remote ID) and `sense`. `group_incidents` requires a radar track and spans every sensor's detections; swarm drones share one incident (D-028, D-038) | `sim/incidents.py` |
| Tables | the raw and truth frames for incidents, track points, RF and Remote ID | `sim/tables.py` |
| Facts | what the paperwork may know about an incident, plus the truth its clues are scored against; stable per-actor lights, sound and launch-site profiles | `sim/facts.py` |
| Lexicon | the clue vocabulary, `find_clues` (reads clues back out of text, case-insensitive) and `forbidden` (the guardrail scan, D-045) | `sim/lexicon.py` |
| Reports | sources, delays and grades (§8.8); narrative, blotter and terse base styles; the Appendix A templates and the hobbyist variant; the clue model; swarm wording; the planted report (D-040) | `sim/reports.py` |
| Assessments | label rules, the 20% prober mislabel, correct labels, the planted assessment (D-042) | `sim/assessments.py` |
| Paperwork | per incident: the planted paperwork or generated reports and an assessment; none for live incidents (D-041); the paraphrase flag stops `gen` (D-043) | `sim/paperwork.py` |
| Pipeline | single flights and swarm centers flown in one batch, then swarm drones, then sensing, incidents, paperwork, tables and the live timing with `radar_lag_s` (D-039); a `nights=` option for tests | `sim/generate.py`, `sim/scenario.py` |
| World | `unjittered_assets`: the live P1 target keeps its template place (D-033 (b)) | `sim/world.py` |
| Data card | swarm incidents, sensors, reports (sources, grades, counts per actor type, the delay histogram, styles), clue rates, the assessment confusion table, planted items, live timing; swarm snapshot figures | `sim/datacard.py`, `sim/datacard_paper.py`, `sim/datacard_util.py`, `sim/figures.py`, `reports/data_card.md`, `reports/figures/swarm_S{1,2}.png` |
| CLI | the `gen` summary adds Remote ID rows, swarm incidents, drones flown and drones not tracked | `cli.py` |

Since phase 2, nothing under `sim/` or `config/` has changed except `sim/README.md`, which phase 1's
backfill added (`git diff --stat 06cc826 HEAD`). Phase 3 added commands to `cli.py`, appended
fixtures to `tests/conftest.py` and added tests to `tests/unit/test_cli.py`. It changed no phase 2
behavior.

## Decisions and deviations from SPEC

- [D-033](../../DECISIONS.md), **resolved**: option (b), chosen by the product owner. BRAVO's fuel
  farm keeps its template place, so the live flight is first seen at 21:40:06, 71 m out, and the
  orbit forms at T+79 s, on the orbit at T+90. Options (a) and (c) were measured too.
- [D-035](../../DECISIONS.md): the swarm frame, formation layouts, action transforms, blends and
  holds, the centroid path, the wander, and the schedule (each event has its own warp; launches 2 km
  out between 20:00 and 01:00). Swarms broadcast no Remote ID.
- [D-036](../../DECISIONS.md): the RF model (no detection probability, free-space SNR, outages
  radar-only).
- [D-037](../../DECISIONS.md): the Remote ID serial form and stability. A copycat's `on` flights
  share one serial.
- [D-038](../../DECISIONS.md): incidents need a radar track; sensors log every flown drone.
- [D-039](../../DECISIONS.md): the live T+0 stays first radar contact; `radar_lag_s` is 0 s at
  seed 42.
- [D-040](../../DECISIONS.md): the report details and actor clue profiles. This covers the source
  mix, event time and place, the terse style for four bases, upper-case blotters, the true road
  probability of 0.8, and the departure truth.
- [D-041](../../DECISIONS.md): live incidents get no reports or assessments.
- [D-042](../../DECISIONS.md): a "stable serial" means `on` and heard. The mislabel applies to
  probers only, and copycats' correct label is `probing`.
- [D-043](../../DECISIONS.md): the LLM paraphrase waits for phase 9.
- [D-044](../../DECISIONS.md), **deviation**: about 415 k RF detections against ≈0.5 M (83%). Kept,
  for the same reason as D-030.
- [D-045](../../DECISIONS.md): the guardrail scan for generated text.
- Backfill only: [D-066](../../DECISIONS.md) records how this backfill was done and why the
  selected-test count is 116 today.

## Tests

At `06cc826`: 286 fast Python tests (4 slow deselected) and 5 Vitest tests, all passing. Phase 2
added 103 fast tests in eight new files, plus 2 new fast tests and 1 renamed test in phase 1
files, and 1 slow test (181 → 286 fast, 3 → 4 slow):

- `test_swarm_formations.py`, 21: spacing and center for every formation at 3, 5 and 7 drones;
  orientation; errors for unknown formations and for a choreography that does not start with a
  formation; `rotate` cw and ccw; `expand`; `split` keeps the centroid; blend then hold; the
  timeline from config with jitter; the centroid creeps, then orbits clockwise.
- `test_swarm.py`, 7:
  - the schedule, including D-009; the same choreography with ±10% jitter;
  - spacing within ±20% during every hold of every event;
  - rotation sense, orbit radius and plausible drone speeds;
  - adding a team changes no other event.
- `test_rf.py`, 14: band from family (7 cases), unknown family, family per actor, rate while
  airborne and in range, bearing noise, SNR falling with range, the terrain mask, same stream same
  hits.
- `test_rid.py`, 7: a stable serial per drone; `on` broadcasts the serial and the operator;
  `spoofed` changes the serial every flight; `off` broadcasts nothing; range, ground and mask; an
  unknown mode; modes per actor.
- `test_reports.py`, 10:
  - every clue in the text has a `clue_truth` row, and every row's clue is in the text;
  - delays and grades per source;
  - counts per actor type; the hobbyist rate and template;
  - clue rates on 3,000 synthetic incidents; an actor without a vehicle gets only wrong ones;
  - base styles, swarm wording, and the paraphrase flag.
- `test_reports_lexicon.py`, 31:
  - a forbidden-content scan of every generated text (more than 1,000);
  - the scanner catches 12 made-up offenders (plates, names, titles, a person description, an
    address, a phone, an e-mail, "registration");
  - it allows world vocabulary (7 cases), and the name lexicon shares no world word;
  - `find_clues` reads capitals; `compass8` (8 cases); park names.
- `test_assessments.py`, 5: one per history incident, recorded 2 to 36 h after the end, the label
  rules, the mislabel rate, truth labels.
- `test_planted.py`, 8:
  - the DELTA report contains "white pickup", "County Rd 12", "21:20" and "22:05", with the
    configured source, grade and time; it is DELTA's only report; its `clue_truth` rows are true;
  - the wrong assessment; the other P1 flights get normal paperwork;
  - the GOLF (history) and ECHO (live) swarm events;
  - no paperwork for live incidents; RF families; the live T+0 is first radar contact.
- Phase 1 files: `test_tracks_per_incident` (new), `test_incident_spans_its_detections_by_any_sensor`
  (renamed for D-028), `test_live_target_is_not_jittered` (new, D-033).
- Slow: `test_full_swarms_and_paperwork` (report and assessment volumes, the swarm count, paperwork
  coverage). The determinism tests hash every table, so they cover the new ones.

Today (`ba703ec`):

- The eight phase 2 files give 103 passed. The three tests in phase 1 files give 3 passed, and
  the slow file gives 4 passed.
- The whole fast suite gives 367 passed with 7 slow deselected. `make test-all` gives 374 passed
  in 43.5 s.

No phase 2 test was removed, skipped or weakened.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| Data generates with swarms, RF, Remote ID and paperwork | pass | `make data` from `make clean` in 5.1 s: 9 swarm incidents, 414,999 RF, 686,263 Remote ID, 956 reports, 1,876 assessments |
| Selected tests | pass | 116 passed today (109 at phase 2; the extra 7 are phase 3 tests the `-k` filter matches) |
| Data card updated | pass | swarm, sensor, report, delay, clue-rate and assessment sections; byte-identical to the committed card |
| Planted items present | pass | DELTA report text and four true clues; `hobbyist` label with truth `probing`; GOLF and ECHO swarms with 5 tracks each |
| Live timing (§1.2) | pass | first contact 21:40:06, orbit T+79 s (unchanged since phase 2) |
| Whole chain | pass | exit 0 in 10.9 s (originally 31.0 s on the cloud machine) |

Full output is in [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

No evaluation metrics; phase 2 has no §19 targets. Volumes against §8.11. Phase 2 and today give the
same values, because `sim/` and `config/` have not changed.

| Metric | Phase 2 (`06cc826`) and today (`ba703ec`) | Expected | Against §8.11 |
|---|---:|---:|---|
| incidents | 1,878 (9 swarms) | ≈1,900 | −1.2%, within ±15% |
| tracks | 1,904 | ≈1,950 | −2.4%, within ±15% |
| track points | 560,884 | ≈1,000,000 | 56% (D-030) |
| RF detections | 414,999 | ≈500,000 | 83% (D-044) |
| reports | 956 | ≈1,000 | −4.4%, within ±15% |
| assessments | 1,876 | ≈1,900 | −1.3%, within ±15% |
| Remote ID broadcasts | 686,263 | — | 1,615 distinct serials |
| live first contact | 21:40:06, 71 m out | 21:39:30 to 21:40:30 | pass |
| live orbit established | T+79 s | T+65 to 100 s | pass (phase 1: T+94 s) |
| `gen` elapsed | 19.5 s (cloud) / 5.1 s (laptop) | — | — |

Paperwork shape at seed 42, from the data card:

- Reports per incident: hobbyist 0.41, prober 2.20, copycat 2.13, swarm 2.38. §8.8 asks for 0–1
  (60% none), 1–3, 1–3 and 2–3.
- Clues true: vehicle 36% of 42, road 83% of 48, lights 89%, sound 95%, launch site 99%, departure
  74%. Vehicles are true only for probers that have a vehicle in their profile.
- Assessments: 18% of prober incidents are labeled `hobbyist` (model 20%, including the planted
  label). No history incident is labeled `probing`.

## Known issues and follow-ups

- **D-044 and D-030 (accepted):** RF detections and track points come in below §8.11. To stress-test
  larger volumes, raise the RF and radar `rate_hz`.
- **D-040, for phase 5:** blotter reports are upper case, so clue extraction must be
  case-insensitive (`lexicon.find_clues` already is). Vehicle clues are mostly false outside
  probers, by design, so report recall should not trust a vehicle on its own.
- **D-043, for phase 9:** `reports_llm_paraphrase: true` stops `gen` until phase 9's `llm.py`
  exists.
- **D-037:** a copycat's Remote ID flights share one serial (the same drone). Phase 3's
  `rid_serial` links them, which is true, and worth knowing when reading eval results.
- **D-035, for phase 9:** during S1's split, the gap between groups reaches about 300 m, which is
  §14's `max_spacing_m`. Every event still has other windows of 60 s or more below it.
- **D-038:** RF hears takeoff below the radar's 15 m floor, so 1,876 of 1,878 incidents start at an
  RF detection rather than at a radar point. Phase 3's no-look-ahead filter compares `start_ts`,
  which is consistent across flights.
- **D-065 (open from phase 1's backfill):** `sim/figures.py` sets no font, so the swarm figures'
  PNG bytes depend on the machine. The laptop renders are committed and reproduced byte for byte
  today. Pin a font in the next phase that touches `sim/`.
- **Found downstream (D-046, phase 3):** target choice in `features/` is wrong for swarm drones
  (and for P6 and C2). That is a phase 3 feature issue, not a generator issue: the swarms fly to
  their configured targets (flight line for S1, munitions for S2), as the figures show.
- **Resolved by phase 2:** D-033 (option (b)); D-028 spans across all sensors. **Resolved later:**
  D-024's `loiter_dir` sign (phase 3, D-047).

## How to debug this phase

- **Regenerate quickly.** `uv run kairos-defense gen --seed 42 --no-figures`. In Python,
  `generate(cfg, 42, nights=[date(2026, 4, 19)])` from `kairos_defense.sim.generate` flies one
  night. That is enough for the planted DELTA paperwork. The `planted` test fixture flies the four
  planted nights, and `g42` flies three weeks. `g.paper` holds `facts`, `reports` and
  `assessments`; `g.tables["reports"]` and `g.truth["clue_truth"]` hold the frames.
- **One swarm event.** `swarm.swarm_plans(cfg, world, cal, 42)` lists every event's center plan;
  fly it with `kinematics.fly_plans([plan], world, cal, 42)`, then `swarm.drone_paths(plan, center,
  42)`. `formations.timeline(steps, n)` gives the offsets per second and `Timeline.hold(i)` each
  step's hold window. `uv run pytest tests/unit/test_swarm*.py -q`. To check by eye, look at
  `reports/figures/swarm_S1.png` and `swarm_S2.png`.
- **A report with a clue but no truth row**, or the reverse: `test_reports_every_clue_has_a_truth_row`
  fails. Run `lexicon.find_clues(text, roads, parks)` on the text and compare it with that report's
  `clue_truth` rows. The usual cause is a template phrase that names a vocabulary word outside the
  clue model.
- **Guardrail failures.** Run `lexicon.forbidden(text, allowed)` on the text: it returns the
  offending tokens. A new world name (a road, park or installation) must be in `allowed` (the
  `world_names` fixture), and a new given name or surname must not collide with world vocabulary
  (`test_reports_name_lexicon_avoids_world_words`).
- **Planted DELTA paperwork wrong.** The planted rows come from `scenario_demo.yaml`
  (`p1_flights[2].reports` and `.assessment`) via `reports.planted_report` and
  `assessments.planted_assessment`. `uv run pytest tests/unit/test_planted.py -q`.
- **Incident spans or ids shift.** Spans cover radar, RF and Remote ID (`FlightResult.detection_ms`);
  generated ids take the minute of the first detection by any sensor, usually RF at takeoff (D-038).
  The live T+0 is first radar contact; `g.live.radar_lag_s` must stay 0 at seed 42 (D-039).
- **Determinism broken after adding a draw.** Give the new draw its own `rng_for` name (see the
  stream list in [PLAN.md](PLAN.md), "Risks"). `writers.table_hashes(path)` compares two databases
  table by table. Tests: `test_determinism.py` and
  `test_adding_a_swarm_team_changes_no_other_event`.
- **Truth isolation.** `clue_truth` and `assessment_truth` are written only by `sim/writers.py`.
  The §7.6 scan in `tests/unit/test_truth_isolation.py` fails on any other module that names the
  truth file.

## Fix attempts

None. The autopilot did not gate this phase; it was built by hand and its documents were backfilled.
