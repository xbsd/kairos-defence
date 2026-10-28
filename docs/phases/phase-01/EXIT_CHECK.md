# Phase 1: exit-check evidence

Rerun on 2026-10-28 during the documentation backfill, at `3b0f06c` (HEAD, after phases 2 and 3),
on the dev laptop (macOS arm64, Python 3.12.12, uv 0.13.5), from `make clean`. The original run on
2026-10-28 at `1a13664` (cloud machine) is in `docs/PROGRESS.md`. It passed in 45.6 s with 53
selected tests.

Today's data includes phase 2's swarms, RF, Remote ID and paperwork, so some numbers differ from
phase 1's. Each difference is explained under the table.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Data generates, seeded | `make data` | pass: `gen --seed 42` in 5.2 s; 1,904 drones flown, 0 not tracked |
| Incident and track counts within ±15% of §8.11 | `make data` → `reports/data_card.md` | pass: incidents 1,878 (−1.2% of ≈1,900), tracks 1,904 (−2.4% of ≈1,950), both "within ±15%" |
| Figures exist for every pattern type | `make data` | pass: all 7 `reports/figures/pattern_*.png` rewritten (see the figure note) |
| World, kinematics, pattern, scenario and determinism tests | `uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"` | pass: **62 passed**, 305 deselected |
| Whole chain | the `&&` chain below | **exit 0, 12.2 s wall** |
| Extra: live timing (§1.2) | `make data` summary | pass: first contact 21:40:06 (window 21:39:30 to 21:40:30), orbit T+79 s (window T+65 to 100 s) |
| Extra: determinism across machines | `git status` after `make data` | pass: `reports/data_card.md` is byte-identical to the committed card (cloud machine, phase 2) |
| Extra: all fast checks | `make check` | pass: ruff clean, 100 files formatted, 367 passed, 7 slow deselected; eslint, Prettier, tsc and Vitest 5/5 |
| Extra: slow tests | `make test-all` | pass: 374 passed in 44.1 s |
| Extra: phase 1's own test files | `pytest tests/unit/test_{world,…,determinism}.py` and `tests/slow/test_full_generation.py` | pass: 93 fast and 4 slow passed |

How today's numbers differ from phase 1's:

- **Incidents** are 1,878, not 1,869: the extra 9 are phase 2's swarm incidents. Single-drone flights
  are unchanged: 1,773 hobbyists, 66 probers and 30 copycats, all detected.
- **Tracks** are 1,904, not 1,869: the extra 35 are swarm drones.
- **Track points** are 560,884, not 541,913 (still below §8.11, D-030).
- **Live timing** is first contact 21:40:06 and orbit T+79 s, where phase 1 had 21:39:51 and T+94 s.
  Phase 2 resolved D-033 with option (b): BRAVO's fuel farm keeps its template position. For the same
  reason P1-BRAVO-251114 is now first seen at 21:13:20 (phase 1: 21:13:08).
- **Selected tests** are 62, not 53. Two phase 2 tests now match the `-k` filter: `test_world.py`
  gained `test_live_target_is_not_jittered` (D-033), and the word "world" also selects 8 tests in
  `test_reports_lexicon.py` (`test_reports_scanner_allows_world_vocabulary[7]` and
  `test_reports_name_lexicon_avoids_world_words`). Phase 1's own 53 tests are all among the 62.

## make clean && make data && uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"
```text
$ time (make clean && make data && uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism")
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
│ elapsed                │    5.2 s │                   │
└────────────────────────┴──────────┴───────────────────┘
wrote /Users/ndkx/work/kairos_defence/data/kairos_defense.duckdb, the truth file and
/Users/ndkx/work/kairos_defence/reports/data_card.md
62 passed, 305 deselected in 4.95s

real	0m12.172s
user	0m10.506s
sys	0m0.637s
exit=0
```

Trimmed lines: pytest progress dots only.

## reports/data_card.md (excerpts)
```text
## Volumes against SPEC §8.11
| incidents     | 1,878   | ≈1,900     | within ±15% |
| tracks        | 1,904   | ≈1,950     | within ±15% |
| track_points  | 560,884 | ≈1,000,000 | outside ±15% (56%) |
## Flights
| hobbyist     | 1,773 | 1,773 | 0 |
| prober       |    66 |    66 | 0 |
| copycat      |    30 |    30 | 0 |
| swarm drones |    35 |    35 | 0 |
## Planted items (scenario_demo.yaml, §8.10)
| P1-BRAVO-251114   | BRAVO   | 2025-11-14 21:12:00 | 2025-11-14 21:13:20 | 1.00 | 272 | history |
| P1-ALPHA-260303   | ALPHA   | 2026-03-03 21:52:00 | 2026-03-03 21:52:07 | 1.22 | 520 | history |
| P1-DELTA-260419   | DELTA   | 2026-04-19 21:35:00 | 2026-04-19 21:35:06 | 1.00 | 494 | history |
| P1-ALPHA-260502   | ALPHA   | 2026-05-02 22:05:00 | 2026-05-02 22:05:06 | 0.95 | 523 | history |
| P1-CHARLIE-260710 | CHARLIE | 2026-07-10 21:30:00 | 2026-07-10 21:30:06 | 1.00 | 452 | history |
| DEMO-BRAVO-0828   | BRAVO   | 2026-08-28 21:38:45 | 2026-08-28 21:40:06 | 1.00 | 438 | live |
## Live incident timing (§1.2, D-003, D-033)
- Launch 21:38:45; first radar contact (T+0) 21:40:06, 81 s after launch, 71 m outside the fence.
- Orbit established (within 15 m of the radius for 10 s): T+79 s.

$ git status --short reports/
 M reports/figures/pattern_figure8.png      (and the other 6 pattern figures, swarm_S1.png, swarm_S2.png)
$ ls reports/figures/pattern_*.png
pattern_figure8.png pattern_hover.png pattern_lawnmower.png pattern_orbit.png
pattern_perimeter.png pattern_random_walk.png pattern_transit_dips.png
```

`reports/data_card.md` does not appear in `git status`. The laptop regenerated the same card,
byte for byte, as the cloud machine did at phase 2. That card includes every count, the planted
rows and the live timing.

## Phase 1 test files
```text
$ uv run pytest tests/unit/test_world.py … tests/unit/test_determinism.py -q   # one file at a time
world 15 · calendar 9 · patterns 10 · kinematics 10 · actors 11 · sensors 9 · scenario 15
generate 10 · determinism 4
$ uv run pytest tests/unit/test_{world,calendar,patterns,kinematics,actors,sensors,scenario,generate,determinism}.py -q
93 passed in 5.36s
$ uv run pytest tests/slow/test_full_generation.py -q
4 passed in 9.46s
```
At `1a13664` these files had 91 fast and 3 slow tests. Phase 2 made the following changes:

- added `test_live_target_is_not_jittered` (world) and `test_tracks_per_incident` (generate);
- renamed `test_incident_spans_its_detections` to `..._by_any_sensor` (D-028);
- added the slow `test_full_swarms_and_paperwork`.

No phase 1 test was removed, skipped or weakened.

## make check and make test-all
```text
$ make check
uv run ruff check .                 All checks passed!
uv run ruff format --check .        100 files already formatted
uv run pytest -m "not slow" -q      367 passed, 7 deselected in 10.82s
npm --prefix web run check          Prettier clean · tsc clean · Test Files 2 passed (2), Tests 5 passed (5)
exit=0
$ make test-all
uv run pytest -q
374 passed in 44.05s
exit=0
```

## Restoring the working state
```text
$ make index          # make clean removed phase 3's derived tables and LanceDB
history tracks indexed 1,898 · live tracks skipped 6 · flight_windows 60 s 57,462 · 120 s 51,297
· 300 s 27,507 · loiter direction ccw 20, cw 1, none 1,877 · elapsed 7.3 s · exit=0
$ npm --prefix web run build   # make clean removed web/dist
dist/assets/index-*.js 222.56 kB (gzip 69.63 kB) · CSS 10.77 kB · built in 235ms · exit=0
```
The index counts match phase 3's exit check exactly (PROGRESS.md). Phase 4 starts from the same
data it would have had without this backfill.

## Notes

- **Figures: same data, different font.** `make data` rewrites the nine committed PNGs (seven
  patterns, two swarms). Their pixels differ from the committed cloud renders (for example
  `pattern_orbit.png`: 42,501 pixels differ, and the file shrinks from 82,315 to 72,821 bytes). The
  paths, points and markers are the same: the two versions were compared side by side, and the card
  built from the same data is byte-identical. Only the typeface differs. `sim/figures.py` sets no
  font family, so matplotlib's default `sans-serif` list applies. On the laptop that is DejaVu Sans
  from matplotlib's bundled `matplotlibrc`; the cloud renders use a different sans-serif. Following
  D-034 ("commit them again when they change"), the backfill commits the laptop renders, because
  every later `make data` here (the autopilot's phase 9 `make clean`, `make data`) produces them.
  Follow-up: pin a font so the figures are byte-stable across machines (D-065).
- **Speed.** Generation takes 5.2 s here against 23.6 s on the cloud machine, and the index takes
  7.3 s against 55.0 s. Only wall time differs; the outputs are identical.
- **Web CSS 10.77 kB** against 10.45 kB in the phase 0 backfill. The JS is unchanged. The only new
  non-ignored file under `web/` since then is `web/README.md`. Tailwind 4's automatic source
  detection scans it, so utility names in the README probably add rules. This is harmless and has
  nothing to do with phase 1, but phase 7 may want to exclude docs from the scan with `@source not`.
