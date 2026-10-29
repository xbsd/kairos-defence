# Phase 2: exit-check evidence

Rerun on 2026-10-28 during the documentation backfill, at `ba703ec` (HEAD, after phase 3 and the
phase 0 and 1 backfills), on the dev laptop (macOS arm64, Python 3.12.12, uv 0.13.5), from
`make clean`. The original run on 2026-10-28 at `06cc826` (cloud machine) is in `docs/PROGRESS.md`.
It passed in 31.0 s with 109 selected tests.

`src/kairos_defense/sim/`, `config/` and phase 2's eight test files are byte-identical to `06cc826`
(`git diff --stat 06cc826 HEAD` lists only `sim/README.md` under `sim/`). The data is therefore the
same as at phase 2, and every count below matches phase 2's run. The only differences are the
selected-test count and the wall time, both explained under the table.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Data generates with swarms, RF, Remote ID and paperwork | `make data` | pass: `gen --seed 42` in 5.1 s; 1,878 incidents (9 swarms), 1,904 tracks, 414,999 RF detections, 686,263 Remote ID rows, 956 reports, 1,876 assessments; 1,904 drones flown, 0 not tracked |
| Swarm, RF, Remote ID, report, assessment and planted tests | `uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"` | pass: **116 passed**, 251 deselected |
| Whole chain | the `&&` chain below | **exit 0, 10.9 s wall** |
| Data card updated | `make data` → `reports/data_card.md` | pass: swarm incidents, sensors, reports (sources, grades, counts per actor type, delay histogram, styles), clue rates, assessments, planted items; byte-identical to the committed card |
| Planted items present | read back from both DuckDB files (below) | pass: DELTA report with "white pickup", "County Rd 12", "21:20" and "22:05" and four true `clue_truth` rows; DELTA assessment `hobbyist`, truth `probing`; `S1-GOLF-260503` (history) and `DEMO-SWARM-ECHO-0614` (live), 5 tracks each |
| Extra: live timing (§1.2) | `make data` summary | pass: first contact 21:40:06 (window 21:39:30 to 21:40:30), orbit T+79 s (window T+65 to 100 s), as at phase 2 |
| Extra: phase 2's own test files | `pytest` on the eight new files, the 3 tests phase 2 added or renamed in phase 1 files, and the slow file | pass: 103, 3 and 4 passed |
| Extra: all fast checks | `make check` | pass: ruff clean, 100 files formatted, 367 passed, 7 slow deselected; eslint, Prettier, tsc and Vitest 5/5 |
| Extra: slow tests | `make test-all` | pass: 374 passed in 43.5 s |
| Extra: figures | `git status` after `make data` | pass: `swarm_S1.png`, `swarm_S2.png` and the seven pattern figures are byte-identical to the committed laptop renders (D-065) |

How today's numbers differ from phase 2's:

- **Selected tests** are 116, not 109. The 7 extra are phase 3 tests whose names match the `-k`
  filter: `test_duck_store.py::test_rf_bearing_gate_separates_concurrent_tracks` ("rf"),
  `test_duck_store.py::test_rid_within_5s_and_100m` ("rid"), and the five
  `test_index.py::test_p1_planted_signatures[...]` cases ("planted"). Both files were added in
  `e494995` (phase 3). Collecting the same filter at `06cc826` in a temporary worktree gives
  `109/286 tests collected (177 deselected)`, so phase 2's 109 are all among today's 116.
- **Wall time** is 10.9 s against 31.0 s, and `gen` takes 5.1 s against 19.5 s. Only the machine
  differs (the laptop against the cloud machine); the outputs are identical.

## make clean && make data && uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"
```text
$ time (make clean && make data && uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted")
rm -rf data exports web/dist .pytest_cache .ruff_cache
uv run kairos-defense gen --seed 42
kairos-defense gen --seed 42
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Item                   ┃    Value ┃  Expected (§8.11) ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ incidents              │    1,878 │            ≈1,900 │
│ tracks                 │    1,904 │            ≈1,950 │
│ track_points           │  560,884 │        ≈1,000,000 │
│ rf_detections          │  414,999 │          ≈500,000 │
│ reports                │      956 │            ≈1,000 │
│ assessments            │    1,876 │            ≈1,900 │
│ remote_id              │  686,263 │                   │
│ swarm incidents        │        9 │                   │
│ drones flown           │    1,904 │                   │
│ drones not tracked     │        0 │                   │
│ live first contact     │ 21:40:06 │ 21:39:30-21:40:30 │
│ live orbit established │   T+79 s │        T+65-100 s │
│ elapsed                │    5.1 s │                   │
└────────────────────────┴──────────┴───────────────────┘
wrote /Users/ndkx/work/kairos_defence/data/kairos_defense.duckdb, the truth file and
/Users/ndkx/work/kairos_defence/reports/data_card.md
116 passed, 251 deselected in 4.42s
( make clean && make data && uv run pytest tests/unit -q -k ; )  3.93s user 0.32s system 39% cpu 10.884 total
exit=0
```

Trimmed lines: pytest progress dots only.

## Planted items, read back from the written DuckDB files
```text
$ uv run python - <<'EOF'   # read-only connections; a one-off check, not app code
reports where incident_id = 'P1-DELTA-260419'   (its only report)
  R-P1-DELTA-260419-1 · security_forces · B2 · event 2026-04-20 02:35:02 UTC · report 2026-04-20 03:40 UTC (22:40 local)
  "Security forces patrol observed a small drone near the fuel farm at about 21:35, est. 300 ft, a
   flashing white light. A white pickup was parked on County Rd 12 from 21:20 to 22:05 and left
   shortly after the drone flew northwest. The drone departed to the northwest at about 21:46. No
   contact with the operator."
clue_truth (truth.duckdb) for R-P1-DELTA-260419-1
  vehicle white pickup True · road County Rd 12 True · lights a flashing white light True · departure northwest True
assessments where incident_id = 'P1-DELTA-260419'
  A-P1-DELTA-260419 · hobbyist · "Single small drone; consistent with a recreational flight. No further action."
  · 2026-04-20 14:10 UTC (09:10 local) · DELTA BDOC
assessment_truth (truth.duckdb)
  P1-DELTA-260419 · probing
incidents
  S1-GOLF-260503       GOLF  DESERT  2026-05-04 05:10:02 → 05:20:22 UTC  n_tracks 5  is_swarm True  history
  DEMO-SWARM-ECHO-0614 ECHO  PLAINS  2026-06-15 03:50:02 → 04:03:52 UTC  n_tracks 5  is_swarm True  live
  DEMO-BRAVO-0828      BRAVO COASTAL 2026-08-29 02:40:06 → 02:48:41 UTC  n_tracks 1  is_swarm False live
distinct track_id in track_points: S1-GOLF-260503 5 · DEMO-SWARM-ECHO-0614 5
```

These match phase 2's record in `docs/PROGRESS.md` row for row. DELTA's `event_ts` (21:35:02 local)
is the first RF detection, 2 s after launch: RF hears takeoff below the radar's 15 m floor (D-036,
D-038).

## reports/data_card.md (excerpts)
```text
## Swarm incidents (§8.7)
| S1-GOLF-260503       | S1 | GOLF | 2026-05-03 22:10 | 5/5 | 0.87 | history | 2 |
| DEMO-SWARM-ECHO-0614 | S1 | ECHO | 2026-06-14 21:50 | 5/5 | 1.13 | live    | 0 |
  (9 events in all: S1 at GOLF, ECHO, ECHO, HOTEL; S2 at JULIET ×4, KILO)
## Sensors (§8.6)
- RF: 414,999 detections at 0.5 Hz; bands 2.4GHz 385,822, 5.8GHz 11,309, 900MHz 17,868. RF heard
  1,876 of 1,878 incidents before the radar's first point ...
- Remote ID: 686,263 broadcasts, 1,615 distinct serials. Drones by mode (heard / flown): on
  1,621/1,621, spoofed 12/12, off 0/271.
## Reports (§8.8, Appendix A)
| bdoc_log 92 | security_forces 477 | local_pd 345 | faa 42 |
| hobbyist 1,773 incidents, 730 reports, 0.41 each | prober 65, 143, 2.20 | copycat 30, 64, 2.13 | swarm 8, 19, 2.38 |
delay histogram: bdoc_log 88 in 0–10 min, 4 in 10–30 · security_forces 66 in 10–30, 409 in 30–90 min,
  2 in 1.5–6 h · local_pd 31 in 1.5–6 h, 133 in 6–24 h, 181 in 1–2 d · faa 7 in 1–2 d, 35 in 2–5 d
## Clue rates (§8.8)
| vehicle 42, 36% true | road 48, 83% | lights 95, 89% | sound 21, 95% | launch_site 686, 99% | departure 95, 74% |
## Assessments (§8.8)
| hobbyist  | 1,601 hobbyist | 172 unknown |
| probing   |    32 hobbyist |  63 unknown |
| swarm     |     8 swarm    |             |
Prober incidents labeled hobbyist: 18% (model 20%; the count includes the planted DELTA label).
## Planted items (scenario_demo.yaml, §8.10)
Planted assessment: **hobbyist** by DELTA BDOC at 2026-04-20 09:10 local (truth: probing).
## Live incident timing (§1.2, D-003, D-033)
- First detection by any sensor: 0 s before first radar contact (the terrain mask hides it from RF too, D-039).
- Orbit established (within 15 m of the radius for 10 s): T+79 s.

$ git status --short reports/
(nothing: the card and all nine figures are byte-identical to the committed ones)
```

## Phase 2 test files
```text
$ uv run pytest tests/unit/test_{swarm_formations,swarm,rf,rid,reports,reports_lexicon,assessments,planted}.py -q
103 passed in 2.87s
   (swarm_formations 21 · swarm 7 · rf 14 · rid 7 · reports 10 · reports_lexicon 31 · assessments 5 · planted 8)
$ uv run pytest tests/unit/test_generate.py::test_tracks_per_incident \
    tests/unit/test_generate.py::test_incident_spans_its_detections_by_any_sensor \
    tests/unit/test_world.py::test_live_target_is_not_jittered -q
3 passed in 1.43s
$ uv run pytest tests/slow/test_full_generation.py -q
4 passed in 9.54s
$ git worktree add --detach /tmp/kd_p2 06cc826     # removed afterwards
$ PYTHONPATH=/tmp/kd_p2/src .venv/bin/python -m pytest tests/unit -k "swarm or rf or rid or reports or assessments or planted" --collect-only -q
109/286 tests collected (177 deselected)
```

No phase 2 test was removed, skipped or weakened. Phase 3 changed `tests/conftest.py` (new
fixtures appended) and `tests/unit/test_cli.py`; it changed no phase 2 test file.

## make check and make test-all
```text
$ make check
uv run ruff check .                 All checks passed!
uv run ruff format --check .        100 files already formatted
uv run pytest -m "not slow" -q      367 passed, 7 deselected in 17.41s
npm --prefix web run check          eslint 0 warnings · All matched files use Prettier code style! · tsc clean
                                    Test Files 2 passed (2), Tests 5 passed (5)
exit=0 (34.6 s)
$ make test-all
uv run pytest -q
374 passed in 43.53s
exit=0
```

## Restoring the working state
```text
$ make index          # make clean removed phase 3's derived tables and LanceDB
tracks 1,904 · history tracks indexed 1,898 · live tracks skipped 6 · track_features rows 800,148
gap seconds 62,850 (7.9%) · flight_windows 60 s 57,462 · 120 s 51,297 · 300 s 27,507
targets fence 1,800, flight_line 35, fuel_farm 19, hq 16, munitions 28
loiter direction ccw 20, cw 1, none 1,877 · RF family unknown 0 · Remote ID present 1,634
elapsed 7.4 s · exit=0
$ npm --prefix web run build   # make clean removed web/dist
dist/assets/index-*.css 10.77 kB · index-*.js 222.56 kB (gzip 69.63 kB) · built in 265ms · exit=0
```

The index counts match phase 3's exit check exactly (PROGRESS.md), and the web build matches phase
1's backfill. Phase 4 starts from the same data it would have had without this backfill.

## Notes

- **Swarm figures reviewed by eye** (`reports/figures/swarm_S1.png`, `swarm_S2.png`). S1 shows the
  line abreast lying across the heading, then the clockwise quarter turn bringing drone 0 (ringed)
  to the front. It then shows the 2 + 3 split about 250 m apart and the V with drone 0 at the apex.
  S2 shows the triangle, the expansion by 2, the counter-clockwise half turn, and the trail with
  drone 0 leading. In S2's path panel, the dark-edged rectangle at the far end of the track is the
  munitions target: `figures.py` gives the target asset an ink edge. It is not a stray marker. No
  text collides.
- **Determinism across machines.** The laptop regenerated the card that the cloud machine wrote at
  phase 2, byte for byte. Phase 1's backfill had already committed the laptop's figure renders
  (D-065), so `make data` leaves `reports/` untouched.
