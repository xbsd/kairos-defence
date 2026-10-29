# Phase 4: exit-check evidence

Run on the dev laptop (Apple Silicon, macOS) on 2026-10-28, from 21:25 local, after the phase 4
code was final. Data: the seed-42 dataset from `make data` (unchanged since phase 2). The SPEC
§20 chain was run exactly as written. `make eval` exits 1 on one demo assertion, so the `&&` chain
stopped there and `match` was then run on its own, as the plan foresaw.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Index rebuilt with fixed-unit vectors (D-068) | `make index` | pass: 1,898 history tracks, 6 live skipped, windows 57,462 / 51,297 / 27,507 (unchanged), 7.0 s |
| `make models` trains and calibrates | `make models` | pass: 62 queries, 123,404 pairs (1,128 same actor), τ 1.6453, validation AUC 0.998, both model files written, 44.4 s |
| Recall@5 ≥ 0.80 | `make eval` | pass: **1.000** |
| DTW lift ≥ +0.10 | `make eval` | pass: **+0.522** (fused 1.000 against 0.478 for the prefilter order of the same candidates, same run) |
| Copycat-first ≤ 5% | `make eval` | pass: **0%** |
| Latency within §10.9 (reported, D-060) | `make eval` | pass: prefilter p95 30 ms, DTW of 500 candidates p95 81 ms, end to end p95 149 ms |
| Match top 3 are DELTA-260419, ALPHA-260303, ALPHA-260502, with reasons | `match --method dtw --incident DEMO-BRAVO-0828 --at 90` | **fail by one place**: DELTA #1, ALPHA-260303 #2, CHARLIE-260710 #3, ALPHA-260502 #4; all four are P1 with a score and three reasons |
| Demo rows | `make eval` | first contact pass, orbit pass, `live_top3_incidents` **fail** (2/3); `make eval` exit 1 |
| Baseline written | `eval --baseline` | pass: `reports/baseline.json` (method `dtw`, model `fusion-v1`), exit 0 |
| Targets judged | `check_targets.py 4` | 8 PASS, 1 GAP (`demo:live_top3_incidents`), exit 1 (soft gaps only, D-063) |
| Quality floor | `make check`, `make test-all` | pass: ruff clean, 431 fast passed (367 at the start of the run), web lint, typecheck, Vitest 5/5; `make test-all` 441 passed in 3 min 31 s |

## make index
```text
$ time make index
uv run kairos-defense index
│ tracks                 │                                                          1,904 │
│ history tracks indexed │                                                          1,898 │
│ live tracks skipped    │                                                              6 │
│ track_features rows    │                                                        800,148 │
│ track_signatures rows  │                                                          1,898 │
│ flight_windows 60 s    │                                                         57,462 │
│ flight_windows 120 s   │                                                         51,297 │
│ flight_windows 300 s   │                                                         27,507 │
│ targets                │ fence 1,800, flight_line 35, fuel_farm 19, hq 16, munitions 28 │
│ loiter direction       │                                       ccw 20, cw 1, none 1,877 │
│ elapsed                │                                                          7.0 s │
make index  8.76s user 0.25s system 113% cpu 7.935 total
```

## make models && make eval && uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90
```text
$ time (make models && make eval && uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90)
uv run kairos-defense models
│ training nights                         │ 2025-03-01 to 2026-02-28 │
│ T grid (s)                              │     45, 60, 90, 120, 180 │
│ training queries                        │                       62 │
│ training pairs (same actor)             │          123,404 (1,128) │
│ τ (median same-actor d_norm)            │                   1.6453 │
│ d_norm p10/p50/p90 same actor           │    1.438 / 1.645 / 1.881 │
│ d_norm p10/p50/p90 others               │    1.482 / 1.689 / 1.986 │
│ coefficient shape_sim                   │                   +4.219 │
│ coefficient rf_match                    │                  +18.664 │
│ coefficient bearing_sim                 │                   +2.646 │
│ coefficient tod_sim                     │                  +26.215 │
│ coefficient launch_sim                  │                   +9.785 │
│ coefficient radius_sim                  │                   +0.654 │
│ coefficient alt_sim                     │                   +5.269 │
│ intercept                               │                  -51.963 │
│ validation queries / pairs (same actor) │      33 / 82,500 (1,379) │
│ validation ROC AUC                      │                    0.998 │
│ validation Recall@5 T=120 s (probers)   │                    1.000 │
│ training hash                           │         318e1b4cde4bb19f │
│ elapsed                                 │                   44.4 s │
wrote …/models/fusion_v1.json and …/models/dtw_calibration.json
uv run kairos-defense eval
kairos-defense eval · dtw
│ prober queries (unanswerable)                   │     23 (0) │
│ copycat queries (unanswerable)                  │     10 (0) │
│ model · candidates per query                    │ fusion-v1 · 500 │
│ Recall@5 at T=120 s                             │      1.000 │
│ Recall@5 at T=120 s, Euclidean order (same run) │      0.478 │
│ DTW lift                                        │      0.522 │
│ MRR at T=120 s                                  │      1.000 │
│ time to match (top 3 by T=90 s)                 │        96% │
│ copycat-first at T=120 s                        │         0% │
│ Recall@5 at T=120 s, copycats                   │      1.000 │
│ latency query build p50 / p95                   │   4 / 4 ms │
│ latency prefilter p50 / p95                     │ 27 / 30 ms │
│ latency dtw p50 / p95                           │ 55 / 82 ms │
│ latency end to end p50 / p95                    │ 118 / 149 ms │
│ demo live_first_contact_local                   │ pass: 21:40:06, 71 m │
│ demo live_orbit_established_s                   │ pass: T+79 s │
│ demo live_top3_incidents                        │ fail: 2/3 in top 3; P1-DELTA-260419 #1 (1.00, 'Same time of night'); P1-ALPHA-260303 #2 (0.99, 'Same time of night'); P1-ALPHA-260502 #4 (0.98, 'Same time of night') │
│ elapsed                                         │     38.9 s │
wrote …/reports/eval_2026-10-29.md and …/reports/eval_2026-10-29.json
demo assertion failed: live_top3_incidents (2/3 in top 3; …)
make: *** [eval] Error 1
( make models && make eval && uv run kairos-defense match --method dtw   --at)  109.85s user 28.62s system 159% cpu 1:26.92 total
chain exit 2
```

## uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90 (on its own)
```text
$ time uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90
query DEMO-BRAVO-0828-T1 at T+90 s · 91 s seen · window 60 s (60 s used) · target BRAVO-fuel_farm · first contact
2026-08-28 21:40 local · 500 candidates · 233 ms
model fusion-v1 · τ 1.645 · ms: prefilter 33 · signature 23 · dtw 157 · features 2 · fusion 0 · explain 6 · total 225
dtw matches for DEMO-BRAVO-0828
 #  track                   base     start (local)     score  shape  warp  reasons
 1  P1-DELTA-260419-T1      DELTA    2026-04-19 21:35  0.999  0.359  0.84  Same time of night; Same RF family (FAM-07); Same approach bearing (315°)
 2  P1-ALPHA-260303-T1      ALPHA    2026-03-03 21:52  0.995  0.363  1.03  Same time of night; Same RF family (FAM-07); Same approach bearing (315°)
 3  P1-CHARLIE-260710-T1    CHARLIE  2026-07-10 21:30  0.993  0.386  0.90  Same time of night; Same RF family (FAM-07); Same approach bearing (315°)
 4  P1-ALPHA-260502-T1      ALPHA    2026-05-02 22:05  0.985  0.374  0.80  Same time of night; Same RF family (FAM-07); Same approach bearing (315°)
 5  FOXTROT-251215-2125-T1  FOXTROT  2025-12-15 21:25  0.956  0.365  1.08  Same time of night; Same RF family (FAM-07); Same orbit radius (~240 m)
 6  HOTEL-250818-2126-T1    HOTEL    2025-08-18 21:26  0.943  0.337  1.05  Same time of night; Same RF family (FAM-07)
 7  HOTEL-260220-2126-T1    HOTEL    2026-02-20 21:27  0.905  0.377  0.73  Same time of night; Same RF family (FAM-07); Same shape, flown 37% faster
 8  ECHO-260323-2034-T1     ECHO     2026-03-23 20:34  0.904  0.361  0.72  Same time of night; Same RF family (FAM-07); Same shape, flown 38% faster
 9  FOXTROT-260802-2020-T1  FOXTROT  2026-08-02 20:20  0.894  0.380  0.68  Same time of night; Same RF family (FAM-07); Same shape, flown 48% faster
10  HOTEL-250314-2030-T1    HOTEL    2025-03-14 20:30  0.881  0.365  1.17  Same time of night; Same RF family (FAM-07); Same shape, flown 15% slower
uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90  1.08s user 0.23s system 96% cpu 1.368 total
match exit 0
```
(The table is reflowed from rich's 120-column box drawing; the values are verbatim. Rows 5 to 10
are P3 flights, which share P1's RF family and time of night.)

## uv run kairos-defense eval --baseline
```text
$ time uv run kairos-defense eval --baseline
… (the same metrics and demo rows as `make eval` above) …
wrote …/reports/eval_2026-10-29.md and …/reports/eval_2026-10-29.json
wrote …/reports/baseline.json
uv run kairos-defense eval --baseline  48.42s user 9.73s system 142% cpu 40.670 total
baseline exit 0
$ python -c "…json.load(open('reports/baseline.json'))…"
dtw fusion-v1 0.5217391304347826
```

## python3 scripts/check_targets.py 4
```text
$ python3 scripts/check_targets.py 4; echo "check_targets exit $?"
PASS  Recall@5 at T=120 s (§19.3): 1 (target >= 0.8)
PASS  DTW lift over the Euclidean baseline (§19.3): 0.5217 (target >= 0.1)
PASS  Copycat-first rate (§19.3): 0 (target <= 0.05)
PASS  Prefilter p95 ms (§10.9): 29.7 (target <= 50)
PASS  DTW re-rank of 50 candidates p95 ms (§10.9): 81.28 (target <= 800)
PASS  End-to-end live update p95 ms (§10.9): 149 (target <= 1500)
PASS  demo live_first_contact_local: pass
PASS  demo live_orbit_established_s: pass
GAP   demo live_top3_incidents: fail

Targets not met:
GAP demo:live_top3_incidents: status 'fail', observed 2/3 in top 3; P1-DELTA-260419 #1 (1.00, 'Same time of night'); P1-ALPHA-260303 #2 (0.99, 'Same time of night'); P1-ALPHA-260502 #4 (0.98, 'Same time of night')
check_targets exit 1
```

## make check and make test-all
```text
$ make check
uv run ruff check .            → All checks passed!
uv run ruff format --check .   → 116 files already formatted
uv run pytest -m "not slow" -q → 431 passed, 10 deselected
npm --prefix web run check     → lint, typecheck, Vitest: 2 files, 5 tests passed
$ make test-all
uv run pytest -q
441 passed in 210.74s (0:03:30)
make test-all  256.63s user 60.84s system 150% cpu 3:31.14 total
```
