# Phase 1: World, flights and radar, report

Status: done · Date: 2026-10-28 (built; docs backfilled the same day) · Commits: `1a13664` (phase 1)

## Summary

Phase 1 made `kairos-defense gen --seed 42` real. It builds the seeded world: 12 installations in 3
regions with jittered assets, sensors, launch parks and County Rd 12. It builds an 18-month calendar
with weather and events, schedules every hobbyist, prober and copycat flight plus the six planted P1
flights, and flies them through a batched 10 Hz point-mass model. Each flight is sensed with radar,
and the raw tables go to `data/kairos_defense.duckdb` and the truth tables to `data/truth.duckdb`.
At phase 1: 1,869 incidents and tracks (within ±15% of §8.11), live first contact 21:39:51 and
orbit at T+94 s, and 181 fast plus 3 slow tests. It was built by hand in a Claude Code cloud session.
These documents were reconstructed on 2026-10-28, and the exit check passes again today, after
phases 2 and 3.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| DDL | §7.1 raw and §7.3 truth `CREATE TABLE` statements, plus column lists the writers check | `store/ddl.py` |
| World | installations rotated clockwise and shifted, asset jitter per stream, sensors, one launch park per base (D-005), County Rd 12 through P1's launch points (D-006, D-031), push-out and road snapping, terrain mask, world tables | `sim/world.py` |
| Calendar | 549 nights, hourly weather (Weibull wind through an AR(1) copula), exercises, VIP visits, shift changes, public events (D-023) | `sim/calendar.py` |
| Patterns | the seven §8.4 patterns as pure geometry, pattern size and entry point (D-024) | `sim/patterns.py` |
| Kinematics | timed reference, time warp, pauses, altitude noise and smoothing; a batched 10 Hz point-mass model with the §8.3 caps and wind drift; 1 Hz output (D-025) | `sim/kinematics.py` |
| Plans | `FlightPlan` keyed by a stable flight key; prober and copycat plans with per-flight jitter; stratified monthly schedule with VIP weighting; hobbyists per base-night (D-026) | `sim/plan.py`, `sim/actors.py` |
| Scenario | the six planted P1 flights (`jitter: none`, override target, outage, live flag); orbit-established and live-timing measures | `sim/scenario.py` |
| Radar | range-dependent detection and noise, dropout chain, planted outages, terrain mask, fixed variates per scan (D-027) | `sim/sensors.py` |
| Pipeline | world → calendar → plans → flights → radar → incidents (ids D-028) → tables; a `window` option for tests | `sim/generate.py` |
| Writers | drop and recreate both DuckDB files, bulk insert, delete `memory.duckdb`; the only truth writer; `table_hashes` (D-029) | `sim/writers.py` |
| Data card | volumes against §8.11, flights, incidents per base and actor type, probers, radar tracks, planted flights, live timing, row counts; three sample flights per pattern (D-034) | `sim/datacard.py`, `reports/data_card.md`, `reports/figures/pattern_*.png` |
| CLI | `gen --seed --config --figures/--no-figures` with a rich summary | `cli.py` |

Since phase 1, phase 2 extended the package. Phase 3 changed only `store/ddl.py` (the §7.2
derived DDL).

- **New phase 2 modules:** `formations.py`, `swarm.py`, `incidents.py`, `tables.py`, `facts.py`,
  `lexicon.py`, `reports.py`, `assessments.py`, `paperwork.py`, `figures.py`, `datacard_paper.py`
  and `datacard_util.py`.
- **Phase 1 modules phase 2 changed:**
  - `sensors.py`: RF and Remote ID.
  - `generate.py`: swarms, all-sensor incidents and paperwork. The incident code moved to
    `incidents.py` and the table code to `tables.py`.
  - `datacard.py`: the paperwork sections, with the figures split out.
  - `world.py`: `unjittered_assets`, D-033.
  - `scenario.py`: `radar_lag_s`, D-039.
  - `actors.py`: `_disc` renamed `disc_offset` for reuse.
  - `kinematics.py` and `patterns.py`: a `choreography` hook each.

Besides those, `git diff --stat 1a13664 HEAD` over phase 1's files lists:

- `cli.py`, `store/ddl.py` and `tests/conftest.py`;
- `test_cli.py`, `test_generate.py`, `test_world.py` and the slow test;
- the docs, and the regenerated card and figures.

`calendar.py`, `plan.py`, `writers.py`, `sim/__init__.py` and the other seven phase 1 test files are
byte-identical to `1a13664`.

## Decisions and deviations from SPEC

- [D-023](../../DECISIONS.md): calendar and weather model (correlated hourly wind, "blows from",
  METAR rounding, event timing).
- [D-024](../../DECISIONS.md): pattern geometry. `ccw` means the bearing from the target decreases,
  which flagged §9.4's sign for phase 3. Resolved there in D-047.
- [D-025](../../DECISIONS.md): flight model. The timed reference makes time warp exact and keeps the
  planted timing independent of wind. Nominal climb is 2.8 m/s, and there are no pauses with
  `jitter: none`.
- [D-026](../../DECISIONS.md): actor plan details (disc jitter, copycats, stratified months, unique
  hobbyist actors).
- [D-027](../../DECISIONS.md): radar details (slant range, `quality`, outage from launch, fixed
  variates).
- [D-028](../../DECISIONS.md): incident ids `<BASE>-<YYMMDD>-<HHMM>`. Phase 2 recomputed spans across
  all sensors.
- [D-029](../../DECISIONS.md): writers, truth paths, `memory.duckdb` deleted by `gen`.
- [D-030](../../DECISIONS.md): **deviation**: about 0.54 M track points against ≈1 M in §8.11. This
  is by design; the phase 1 check covers incidents and tracks.
- [D-031](../../DECISIONS.md): County Rd 12's bases are derived from the scenario.
- [D-032](../../DECISIONS.md): the public-event doubling is implemented but never triggers with the
  shipped world.
- [D-033](../../DECISIONS.md): **open at phase 1**: BRAVO's seeded jitter puts the live orbit at
  T+94 s. Phase 2 resolved it with option (b), and the orbit is now at T+79 s.
- [D-034](../../DECISIONS.md): the data card and pattern figures are committed.
- Backfill only: [D-065](../../DECISIONS.md): the figures' font depends on the machine, and the
  laptop renders are committed.

## Tests

At `1a13664`: 181 fast Python tests (3 slow deselected) and 5 Vitest tests, all passing. The slow
tests gave 3 passed in 46 s. Phase 1 added 91 fast tests in nine files and 3 slow tests:

- `test_world.py`, 14:
  - 12 sites in 3 regions; clockwise rotation; sensor positions; seeded small jitter;
  - launch parks 2.2 km out;
  - County Rd 12's shape, and the road within 250 m of P1's launch at ALPHA, BRAVO and DELTA;
  - snap, push-out and ray-exit rules; BRAVO's terrain mask; world tables match the DDL.
- `test_calendar.py`, 9: 549 nights; time helpers; weather ranges; hour-to-hour wind correlation;
  "blows from"; seeded weather; shift changes; exercise and VIP counts; public events on weekends.
- `test_patterns.py`, 10: orbit direction (ccw decreases the bearing), lawnmower, figure-eight,
  clockwise perimeter at the offset, hover, transit with dips, random-walk budget and radius,
  fence-crossing goal, entry-point distances.
- `test_kinematics.py`, 10:
  - every pattern is sampled;
  - speed, climb and turn-rate caps; altitude within the band ± 15 m; orbit radius within ±10% on
    noiseless paths;
  - flights start and end on the ground; warp scales durations, not shapes;
  - no pauses inside patterns, none with `jitter: none`;
  - batch independence; wind drift.
- `test_actors.py`, 11: counts per actor, unique keys, bases and time windows, warp ranges, monthly
  spread, 3× VIP weighting, launches outside the fence, push-out, hobbyist parks, cross-fence share,
  per-flight variation.
- `test_sensors.py`, 9: the dropout chain, detection rate falling with range (3 ranges), noise
  growing with range, nothing below the minimum altitude or out of range, planted outage, terrain
  mask, same stream gives the same hits.
- `test_scenario.py`, 15:
  - the six flights as configured; all detected; only the demo is live;
  - the live flight has no jitter; County Rd 12 within 250 m of five launches; CHARLIE keeps its
    nominal launch;
  - BRAVO-251114's outage; the live launch is in the radar shadow;
  - live first contact (within 100 m of the fence, inside `live_first_contact_local`); live orbit
    established (inside `live_orbit_established_s`); an orbit-established known answer.
- `test_generate.py`, 9: tables match the DDL, incident spans, ids never name the actor, truth links
  every track, undetected flights make no incident, the data card, the window trims calendar tables
  (3).
- `test_determinism.py`, 4: two runs give identical SHA-256 per table; another seed differs; the
  window holds the live flight; adding an actor changes no other flight.
- `test_cli.py`: `gen --help` and config errors (2 new tests); `gen` left `STUBS`.
- Slow `test_full_generation.py`, 3: full volumes within ±15%, every planted flight detected and the
  live flight on time, two full runs give identical hashes.

Today (`3b0f06c`):

- The same nine files give 93 passed. Phase 2 added `test_live_target_is_not_jittered` and
  `test_tracks_per_incident`, and renamed the incident-span test for D-028.
- The slow file gives 4 passed (phase 2 added the swarm and paperwork volumes).
- The whole fast suite gives 367 passed with 7 slow deselected, and `make test-all` gives 374 passed
  in 44 s.

No phase 1 test was removed, skipped or weakened.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| Data generates, seeded | pass | `make data` from `make clean`: 1,904 drones flown, 0 not tracked, 5.2 s |
| Incident and track counts within ±15% of §8.11 | pass | data card: incidents 1,878 (−1.2%), tracks 1,904 (−2.4%); phase 1 had 1,869 and 1,869 (−1.6%, −4.2%) |
| Figures for every pattern type | pass | the 7 `reports/figures/pattern_*.png` written |
| Selected tests | pass | 62 passed today (53 at phase 1; the extra 9 are phase 2 tests the `-k` filter matches) |
| Live timing (§1.2) | pass | first contact 21:40:06, orbit T+79 s (phase 1: 21:39:51, T+94 s, before D-033 (b)) |
| Whole chain | pass | exit 0 in 12.2 s (originally 45.6 s on the cloud machine) |

Full output is in [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

No evaluation metrics; phase 1 has no §19 targets. Volumes against §8.11:

| Metric | Phase 1 (`1a13664`) | Today (`3b0f06c`, with phase 2) | Expected |
|---|---:|---:|---:|
| incidents | 1,869 | 1,878 | ≈1,900 ±15% |
| tracks | 1,869 | 1,904 | ≈1,950 ±15% |
| track points | 541,913 | 560,884 | ≈1,000,000 (D-030) |
| flights not detected | 0 | 0 | counted (D-003) |
| live first contact | 21:39:51, 47 m out | 21:40:06, 71 m out | 21:39:30 to 21:40:30, within 100 m |
| live orbit established | T+94 s | T+79 s | T+65 to 100 s |
| `gen` elapsed | 23.6 s (cloud) | 5.2 s (laptop) | — |

## Known issues and follow-ups

- **D-030 (accepted):** track points stay at about 56% of §8.11's ≈1 M. Raise radar `rate_hz` to
  stress-test larger volumes.
- **D-032 (accepted):** the public-event rules never fire with the shipped parks.
- **D-065, figures depend on the machine's fonts:** `sim/figures.py` sets no font family, so a
  `make data` on another machine rewrites the committed PNGs with only the typeface changed. Pin a
  font (for example DejaVu Sans, which matplotlib bundles) in a later phase that touches `sim/`.
- **Resolved later:** D-033 (phase 2, option (b)); D-028 spans across all sensors (phase 2); D-024's
  `loiter_dir` sign (phase 3, D-047).
- **Unchanged by later phases:** the single-drone flight counts (1,773 hobbyists, 66 probers, 30
  copycats, all detected) and the timing of the four non-BRAVO P1 flights are the same as at phase 1.
  The live and P1-BRAVO-251114 timings moved because D-033 (b) moved BRAVO's fuel farm. This backfill
  did not compare individual tracks between `1a13664` and today.

## How to debug this phase

- **Regenerate quickly.** `uv run kairos-defense gen --seed 42 --no-figures` skips the figures. In
  Python, `generate(cfg, 42, window=(date(2026, 8, 11), date(2026, 8, 31)))` from
  `kairos_defense.sim.generate` builds three weeks in memory without writing anything. That is the
  `g42` test fixture. `g.results` holds every flown drone (plan, 1 Hz true path, radar hits),
  `g.tables` and `g.truth` the DataFrames, and `g.live` the live timing.
- **One flight.** Build a `FlightPlan` with `actors.make_flight(cfg, world, spec, key, base,
  launch_local, rng)`, or take one from `scenario.p1_plans`. Fly it with
  `kinematics.fly_plans([plan], world, cal, seed)` and sense it with `incidents.sense`. The
  `sample` fixture in `tests/conftest.py` flies one plan per actor and base.
- **Live timing out of its window.** Read `g.live` (`LiveTiming`: first contact, distance outside the
  fence, orbit established). The usual causes are changes to BRAVO's layout, the mask, P1's speed or
  radius, or the live launch time. Timing does not depend on wind (D-025). Tests:
  `uv run pytest tests/unit/test_scenario.py -q`.
- **Determinism broken.** `uv run pytest tests/unit/test_determinism.py -q`.
  `writers.table_hashes(path)` gives one SHA-256 per table, so compare two databases table by table.
  The usual cause is a new draw on an existing stream: add a new `rng_for(seed, ...)` name instead.
  Radar scans must keep drawing a fixed number of variates.
- **Writer errors.** `<table>: columns [...] do not match the DDL` means an in-memory table drifted
  from `store/ddl.py`. `test_world_tables_match_ddl` and `test_tables_match_the_ddl` catch it.
- **Truth isolation.** Only `sim/writers.py` may open `data/truth.duckdb`. The §7.6 scan in
  `tests/unit/test_truth_isolation.py` fails on any other module that names it.
- **Figures.** They are written by `sim/figures.py` (phase 1's plotting moved there in phase 2). If
  only the PNG bytes change after `make data`, check the font first (D-065).

## Fix attempts

None. The autopilot did not gate this phase; it was built by hand and its documents were backfilled.
