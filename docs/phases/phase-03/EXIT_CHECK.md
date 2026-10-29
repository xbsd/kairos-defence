# Phase 3: exit-check evidence

Rerun on 2026-10-28 (evening, America/New_York) during the documentation backfill. It ran at
`53134b8` (HEAD, after phase 3 and the phase 0 to 2 backfills) on the dev laptop (Apple M4 Max,
16 cores, macOS arm64, Python 3.12.12, uv 0.13.5), after `make clean && make data`, as phase 3's
own run was. The original run on 2026-10-28 at `e494995` (cloud sandbox, 4 threads) is in
`docs/PROGRESS.md`. It passed in 87.1 s.

Phase 3's code is unchanged since `e494995` except `eval/report.py`'s latency tolerance (D-060),
which only affects the regression gate against a `baseline.json` that does not exist yet (D-056).
`sim/` and `config/` are unchanged, so `make data` produced the same data as phase 2's and 3's
runs. The results match phase 3's run exactly except for the latencies and elapsed times, as
explained under the table.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Features, signatures and windows built | `make index` | pass: 1,904 tracks; 1,898 history tracks indexed; 6 live skipped; 800,148 `track_features` rows (7.9% gap seconds); 1,898 signatures; `flight_windows` 57,462 / 51,297 / 27,507 (60 / 120 / 300 s); 7.2 s |
| Eval report shows baseline Recall@5, MRR, time to match and latency | `make eval` | pass: Recall@5 0.435, MRR 0.302, time to match 26%, copycat-first 57%; latency p50 / p95 query build 4 / 4 ms, prefilter 13 / 15 ms, end to end 17 / 19 ms; `reports/eval_2026-10-29.md` and `.json` |
| Whole chain | `make index && make eval` | **exit 0, 13.8 s wall** |
| Baseline recorded in PROGRESS.md | `docs/PROGRESS.md` | pass: phase 3 entry (original) and this backfill's entry |
| Extra: same results as phase 3 | JSON comparison (below) | pass: `counts`, `recall_by_t`, `per_actor`, `demo`, `pending` and all 198 outcomes identical apart from latency fields |
| Extra: the matcher from the CLI | `uv run kairos-defense match --method euclidean --incident DEMO-BRAVO-0828 --at 90` | pass: window 60 s, target `BRAVO-fuel_farm`, 50 candidates, 28 ms; exit 0 |
| Extra: phase 3's own tests | `pytest` on the nine phase 3 unit files, the three new `test_cli.py` tests and the slow file | pass: 81, 3 and 3 passed |
| Extra: all fast checks | `make check` | pass: ruff clean, 100 files formatted, 367 passed, 7 deselected; eslint, Prettier, tsc, Vitest 5/5; 14.5 s |
| Extra: slow tests | `make test-all` | pass: 374 passed in 42.8 s |
| Extra: D-058 still holds | one-off ranks of the earlier P1 flights (below) | ranks identical to D-058's |

How today's numbers differ from phase 3's:

- **Latency** is lower on the laptop: prefilter p95 15 ms against 83 ms, end to end 19 ms against
  117 ms. Every rank is the same, so this is the machine, not the method. On the laptop the
  prefilter is inside §10.9's 50 ms budget (D-057 was measured on the cloud sandbox).
- **Wall time** is 13.8 s against 87.1 s (`index` 7.2 s against 55.0 s, `eval` 3.8 s against
  23.1 s). Only the machine differs.
- **The report file is `eval_2026-10-29`**, not `eval_2026-10-28`. `write_reports` names the file
  after the run's UTC date, and the run was at 00:07 UTC. The committed `eval_2026-10-28.*` files
  are phase 3's original run and are left as they were.
- **The figure** `reports/figures/eval_recall_by_t.png` was rewritten. Its points and lines are the
  same; only the typeface differs (DejaVu Sans on the laptop), because `eval/report.py` sets no font
  family, the same cause as D-065. The laptop render is committed.

## make clean && make data (setup, as in phase 3's run)
```text
$ make clean && make data
rm -rf data exports web/dist .pytest_cache .ruff_cache
uv run kairos-defense gen --seed 42
incidents 1,878 · tracks 1,904 · track_points 560,884 · rf_detections 414,999 · reports 956
assessments 1,876 · remote_id 686,263 · swarm incidents 9 · drones flown 1,904 · not tracked 0
live first contact 21:40:06 · live orbit established T+79 s · elapsed 5.0 s
exit=0
$ git status --short reports/data_card.md
(nothing: the data card is byte-identical)
```

## make index && make eval
```text
$ time (make index && make eval)
uv run kairos-defense index
kairos-defense index
│ tracks                 │                                                          1,904 │
│ history tracks indexed │                                                          1,898 │
│ live tracks skipped    │                                                              6 │
│ track_features rows    │                                                        800,148 │
│ gap seconds            │                                                  62,850 (7.9%) │
│ track_signatures rows  │                                                          1,898 │
│ flight_windows 60 s    │                                                         57,462 │
│ flight_windows 120 s   │                                                         51,297 │
│ flight_windows 300 s   │                                                         27,507 │
│ targets                │ fence 1,800, flight_line 35, fuel_farm 19, hq 16, munitions 28 │
│ loiter direction       │                                       ccw 20, cw 1, none 1,877 │
│ RF family unknown      │                                                              0 │
│ Remote ID present      │                                                          1,634 │
│ elapsed                │                                                          7.2 s │
wrote track_features and track_signatures to .../data/kairos_defense.duckdb, flight_windows
to .../data/lancedb
uv run kairos-defense eval
kairos-defense eval · euclidean
│ prober queries (unanswerable)   │                                     23 (0) │
│ copycat queries (unanswerable)  │                                     10 (0) │
│ Recall@5 at T=120 s             │                                      0.435 │
│ MRR at T=120 s                  │                                      0.302 │
│ time to match (top 3 by T=90 s) │                                        26% │
│ copycat-first at T=120 s        │                                        57% │
│ Recall@5 at T=120 s, copycats   │                                      0.500 │
│ latency query build p50 / p95   │                                   4 / 4 ms │
│ latency prefilter p50 / p95     │                                 13 / 15 ms │
│ latency end to end p50 / p95    │                                 17 / 19 ms │
│ demo live_first_contact_local   │                       pass: 21:40:06, 71 m │
│ demo live_orbit_established_s   │                               pass: T+79 s │
│ demo live_top3_incidents        │ info (target from phase 4): 0/3 in top 3;  │
│                                 │ ranks P1-DELTA-260419 -, P1-ALPHA-260303 -, │
│                                 │ P1-ALPHA-260502 -                          │
│ demo live_rank1_report_for      │                       pending (phase 5): - │
│ demo forecast_error_max_m       │                       pending (phase 5): - │
│ demo swarm_top1                 │                       pending (phase 9): - │
│ elapsed                         │                                      3.8 s │
wrote .../reports/eval_2026-10-29.md and .../reports/eval_2026-10-29.json
( make index && make eval; )  5.84s user 8.08s system 101% cpu 13.771 total
exit=0
```

Trimmed: table borders and header rows, and the repository path (shown as `...`). No
`baseline.json` exists, so the gate checked only the demo rows (D-056), and none failed.

From `reports/eval_2026-10-29.md`:
```text
| T (s) | Window W (s) | Recall@5 probers | Top-3 probers | Recall@5 copycats |
|    30 | not run      | 0.000            | 0.000         | 0.000             |
|    45 | 60           | 0.087            | 0.087         | 0.500             |
|    60 | 60           | 0.304            | 0.217         | 0.400             |
|    90 | 60           | 0.130            | 0.087         | 0.100             |
|   120 | 60, 120      | 0.435            | 0.348         | 0.500             |
|   180 | 120          | 0.261            | 0.217         | 0.800             |
Per actor at T = 120 s (queries, Recall@5, found in top 50, median best rank):
C1 5 0.400 2 1 · C2 5 0.600 5 1 · P1 4 0.000 1 11 · P2 4 0.250 2 10
P3 5 0.600 5 3 · P4 3 1.000 3 1 · P5 4 0.500 4 5 · P6 3 0.333 3 35
```

## Today's eval against phase 3's
```text
$ uv run python - <<'EOF'   # /tmp copy of the committed eval_2026-10-28.json vs today's
metric differs latency_end_to_end_p50_ms   92.536 → 17.420
metric differs latency_end_to_end_p95_ms  116.958 → 19.235
metric differs latency_prefilter_p50_ms    64.249 → 13.208
metric differs latency_prefilter_p95_ms    82.976 → 14.876
metric differs latency_query_build_p50_ms  24.762 →  3.704
metric differs latency_query_build_p95_ms  38.419 →  3.995
counts same · recall_by_t same · per_actor same · demo same · pending same
outcomes 198 198 identical apart from latency
created_at 2026-10-28T22:30:16 (elapsed 23.1 s) → 2026-10-29T00:07:01 (elapsed 3.8 s)
$ diff eval_2026-10-28.md eval_2026-10-29.md
only the title date, the run time (23 s → 4 s) and the three latency rows differ
```

The `outcomes` comparison drops the `*_ms` fields and compares every other field of all 198 rows
(33 queries × 6 values of T): `track_id`, `actor_id`, `actor_type`, `at_s`, `ran`, `true_rank`,
`copycat_rank`, `window_s` and `top`.

## match --method euclidean
```text
$ time uv run kairos-defense match --method euclidean --incident DEMO-BRAVO-0828 --at 90
query DEMO-BRAVO-0828-T1 at T+90 s · 91 s seen · window 60 s (60 s used) · target BRAVO-fuel_farm
· first contact 2026-08-28 21:40 local · 50 candidates · 28 ms
euclidean matches for DEMO-BRAVO-0828
│  # │ track                  │ base    │ start (local)    │ score │    d² │ window       │
│  1 │ FOXTROT-260422-2012-T1 │ FOXTROT │ 2026-04-22 20:12 │ 0.875 │ 0.499 │ 60 s @ 130 s │
│  2 │ ALPHA-251130-1937-T1   │ ALPHA   │ 2025-11-30 19:37 │ 0.874 │ 0.503 │ 60 s @ 480 s │
│  3 │ ECHO-260315-2123-T1    │ ECHO    │ 2026-03-15 21:23 │ 0.863 │ 0.549 │ 60 s @ 240 s │
│  4 │ BRAVO-250518-1925-T1   │ BRAVO   │ 2025-05-18 19:25 │ 0.859 │ 0.563 │ 60 s @ 230 s │
│  5 │ LIMA-260706-2159-T1    │ LIMA    │ 2026-07-06 22:00 │ 0.858 │ 0.568 │ 60 s @ 200 s │
│ .. │ (rows 6-10: GOLF, FOXTROT, KILO, HOTEL and BRAVO tracks, scores 0.854 to 0.849)  │
real 0.913 s · exit=0
$ uv run kairos-defense match --method euclidean --incident DEMO-BRAVO-0828 --at 45 --top 3
query DEMO-BRAVO-0828-T1 at T+45 s · 46 s seen · window 60 s (46 s used) · target BRAVO-fence · ...
│ 1 │ FOXTROT-251002-1908-T1 │ ... │ 0.897 │ 0.413 │ 60 s @ 60 s  │
exit=0
```

At T+45 the live flight is still inbound, so its target is the fence and the query uses all 46 s
seen against the 60 s windows (D-050). By T+90 it is orbiting the fuel farm (D-046). Phase 3's
record says 164 ms on the cloud sandbox; the 28 ms here is the query build plus the search.

## D-058 recheck: where the earlier P1 flights rank for the live query
```text
$ uv run python - <<'EOF'   # one-off, read-only: load_query, search with k = 1,000,000, best_per_track
T+45:  W=60  target=BRAVO-fence      earlier tracks=1882  P1 ranks: ALPHA-260303 865, ALPHA-260502 501,
                                                           BRAVO-251114 1775, CHARLIE-260710 979, DELTA-260419 1447
T+60:  W=60  target=BRAVO-fence      earlier tracks=1882  ALPHA-260303 53, ALPHA-260502 8, BRAVO-251114 789,
                                                           CHARLIE-260710 281, DELTA-260419 197
T+90:  W=60  target=BRAVO-fuel_farm  earlier tracks=1882  ALPHA-260303 1194, ALPHA-260502 1149, BRAVO-251114 1521,
                                                           CHARLIE-260710 176, DELTA-260419 1164
T+120: W=120 target=BRAVO-fuel_farm  earlier tracks=1841  ALPHA-260303 84, ALPHA-260502 1489, BRAVO-251114 1583,
                                                           CHARLIE-260710 59, DELTA-260419 644
```

These are D-058's numbers. At T+90 the three flights the demo expects in the top 3 (DELTA,
ALPHA 03-03, ALPHA 05-02) rank 1,149 to 1,194, outside the 50 candidates. No truth was read: the P1
incident ids come from `scenario_demo.yaml`.

## Phase 3 test files
```text
$ for f in resample channels signatures duck_store windows index no_lookahead eval_metrics eval_harness; do uv run pytest tests/unit/test_$f.py -q; done
resample 11 · channels 8 · signatures 11 · duck_store 6 · windows 16 · index 13 · no_lookahead 5
eval_metrics 6 · eval_harness 5        (all passed)
$ uv run pytest <the nine files> -q
81 passed in 4.69s
$ uv run pytest tests/unit/test_cli.py::test_index_needs_data tests/unit/test_cli.py::test_match_dtw_is_phase_4 \
    tests/unit/test_cli.py::test_match_runs_on_the_p1_nights -q
3 passed in 2.16s
$ time uv run pytest tests/slow/test_full_index.py -q
3 passed in 25.50s
```

Phase 3 added 84 fast tests (81 + 3) and turned 3 stub cases in `test_cli.py` into real commands,
so the fast count went from 286 to 367. No phase 3 test was removed, skipped or weakened. D-060
later changed one assertion each in `test_eval_harness.py` and `test_eval_metrics.py` (latency
tolerance); both tests still require a real latency regression to fail the gate.

## make check and make test-all
```text
$ time make check
uv run ruff check .                 All checks passed!
uv run ruff format --check .        100 files already formatted
uv run pytest -m "not slow" -q      367 passed, 7 deselected in 10.67s
npm --prefix web run check          All matched files use Prettier code style! · tsc clean
                                    Test Files 2 passed (2), Tests 5 passed (5)
make check  13.32s user 1.52s system 102% cpu 14.481 total · exit=0
$ time make test-all
uv run pytest -q
374 passed in 42.79s
make test-all  45.83s user 9.46s system 128% cpu 43.138 total · exit=0
```

## Restoring the working state
```text
$ npm --prefix web run build   # make clean removed web/dist
dist/assets/index-*.css 10.77 kB · index-*.js 222.56 kB (gzip 69.63 kB) · built in 81ms · exit=0
```

`make index` had already rebuilt `data/` (above), with counts identical to phase 3's. The web build
matches the phase 1 and 2 backfills. Phase 4 starts from the same data and index it would have
had without this backfill.

## Notes

- **Figure reviewed by eye** (`reports/figures/eval_recall_by_t.png`, today against the committed
  render). The same points at T = 45, 60, 90, 120 and 180 for both series, the same legend and end
  labels, T = 30 omitted. No text collides. Only the typeface differs.
- **Determinism.** `index` makes no random draws and breaks ties by id, so a laptop build matches
  the cloud build; `test_rebuild_is_deterministic` and `test_full_index_is_deterministic` (two full
  builds, identical hashes) pass today.
