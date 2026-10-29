# Phase 5: exit-check evidence

Run on the dev laptop (Apple Silicon, macOS) on 2026-10-28, from about 22:58 local, after the
phase 5 code was final. Data: the seed-42 dataset from `make data` (unchanged since phase 2);
models: the phase 4 `models/fusion_v1.json` (hash `418c5edf`). The SPEC §20 chain is
`make index && make eval && uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105`.
`make eval` exits non-zero on the demo row accepted as a gap in phase 4 (`live_top3_incidents`,
`docs/phases/accepted_gaps.json`), so the `&&` chain would stop there; each command was run on its
own and every exit code is recorded, as the plan foresaw and as the gate runs it.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Reports indexed with FTS | `make index` | pass: 956 history reports (0 live), `report_clues` 82 rows (road 40, vehicle 42, in 68 reports), embedder `hashing-v1-384`, FTS on `text`; track index unchanged (1,898 tracks; windows 57,462 / 51,297 / 27,507); exit 0 |
| Report linkage ≥ 0.70 | `make eval` | pass: **1.000** (65 of 65 true-clue reports of the top 3 matched incidents, 23 prober queries at T = 120 s) |
| Forecast median ≤ 400 m | `make eval` | pass: **340 m** at T = 90 s (P80 495 m; 23 queries, none without a forecast); T = 120 s 346 m (P80 532 m) |
| Demo: DELTA report rank 1 for the DELTA match (T+120) | `make eval` | pass: `R-P1-DELTA-260419-1 rank 1 of 1 for P1-DELTA-260419 (match #1)`; clues white pickup, County Rd 12 (linked: "County Rd 12 runs through tonight's predicted zone.") |
| Demo: forecast error ≤ 400 m (T+105) | `make eval` | pass: **139 m** (radius 370 m; analogs ALPHA-260303, HOTEL-250818, FOXTROT-251215; roads County Rd 12) |
| SPEC's last command | `uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105` | pass, exit 0: center 2,164 m at 320° (northwest) of BRAVO's fuel farm, radius 370 m, roads crossing the zone: County Rd 12 |
| "County Rd 12 intersects the zone" (§20 test) | `forecast` above, and `make test-all` (`test_full_demo_recall_and_forecast`) | pass: printed by `forecast`; asserted on the full data by the slow test (509 passed) |
| Demo T+120 beat, for the record | `uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120` | pass, exit 0: keyword text "drone orbit fuel farm vehicle road launch northwest"; DELTA report rank 1 for match #1; link sentence printed |
| Gate targets (cumulative) | `python3 scripts/check_targets.py 5` | 12 PASS, 1 WARN (the accepted `live_top3_incidents`), exit 0 |
| Anchor rule (D-090) | `uv run python -m kairos_defense.eval.forecast_choice` | `target` median 502 m / P80 1,000 m; `match_kind` 311 m / 492 m (36 training queries); verdict `match_kind` (shipped), exit 0 |
| No regression against phase 4's baseline | `make eval` | no regression line printed; every phase 4 metric identical; latency keys within ±2% (below) |
| Regression reference | `uv run kairos-defense eval --baseline` | exit 0: `reports/baseline.json` now carries `report_linkage` 1.0 and `forecast_median_t90_m` 340.4 |
| Quality floor | `make check`, `make test-all` | pass: ruff clean, **497 fast passed** (443 at the start of the run), web lint, typecheck, Vitest 5/5; `make test-all` **509 passed** in 3 min 12 s |

## make index
```text
$ make index
uv run kairos-defense index
kairos-defense index
│ tracks                         │                                                          1,904 │
│ history tracks indexed         │                                                          1,898 │
│ live tracks skipped            │                                                              6 │
│ track_features rows            │                                                        800,148 │
│ track_signatures rows          │                                                          1,898 │
│ flight_windows 60 s            │                                                         57,462 │
│ flight_windows 120 s           │                                                         51,297 │
│ flight_windows 300 s           │                                                         27,507 │
│ reports indexed (live skipped) │                                                        956 (0) │
│ report_clues rows              │                        road 40, vehicle 42 (82, in 68 reports) │
│ embedder                       │             hashing-v1-384 (384 dims); full-text index on text │
│ elapsed                        │                                          7.1 s + reports 0.1 s │
wrote track_features, track_signatures and report_clues to …/data/kairos_defense.duckdb,
flight_windows and reports to …/data/lancedb
exit 0
```

## make eval
```text
$ make eval
uv run kairos-defense eval
kairos-defense eval · dtw
│ prober queries (unanswerable)                   │ 23 (0)
│ copycat queries (unanswerable)                  │ 10 (0)
│ model · candidates per query                    │ fusion-v1 · 500
│ Recall@5 at T=120 s                             │ 1.000
│ Recall@5 at T=120 s, Euclidean order (same run) │ 0.478
│ DTW lift                                        │ 0.522
│ MRR at T=120 s                                  │ 1.000
│ time to match (top 3 by T=90 s)                 │ 96%
│ copycat-first at T=120 s                        │ 0%
│ report linkage (T=120 s, top 3, k=5)            │ 1.000 (65 of 65)
│ forecast error T=90 s median / P80              │ 340 / 495 m
│ forecast error T=120 s median / P80             │ 346 / 532 m
│ latency prefilter p50 / p95                     │ 27 / 30 ms
│ latency dtw p50 / p95                           │ 32 / 55 ms
│ latency end to end p50 / p95                    │ 96 / 123 ms
│ latency forecast p50 / p95                      │ 8 / 9 ms
│ latency recall p50 / p95                        │ 5 / 6 ms
│ demo live_first_contact_local │ pass: 21:40:06, 71 m
│ demo live_orbit_established_s │ pass: T+79 s
│ demo live_top3_incidents      │ fail: 2/3 in top 3; P1-DELTA-260419 #1; P1-ALPHA-260303 #2;
│                               │       P1-ALPHA-260502 #5   (accepted gap, phase 4 GAPS.md)
│ demo live_rank1_report_for    │ pass: R-P1-DELTA-260419-1 rank 1 of 1 for P1-DELTA-260419 (match
│                               │ #1, score 0.0328); clues: white pickup; County Rd 12 (County Rd 12
│                               │ runs through tonight's predicted zone.)
│ demo forecast_error_max_m     │ pass: 139 m (radius 370 m; analogs P1-ALPHA-260303,
│                               │ HOTEL-250818-2126, FOXTROT-251215-2125; roads County Rd 12)
│ demo swarm_top1               │ pending (phase 9): -
│ elapsed                       │ 35.7 s
wrote …/reports/eval_2026-10-29.md and …/reports/eval_2026-10-29.json
demo assertion failed: live_top3_incidents (2/3 in top 3; …)
make: *** [eval] Error 1        (exit 2 from make; the CLI exited 1 for the accepted row only)
```

Against phase 4's `reports/baseline.json` (before it was refreshed):

```text
key                         phase 4      phase 5
dtw_lift                     0.5217       0.5217   +0.0%
recall_at_5_t120             1            1        +0.0%
mrr_t120                     1            1        +0.0%
time_to_match_t90            0.9565       0.9565   +0.0%
copycat_first_t120           0.0          0.0
latency_prefilter_p95_ms     29.74        29.85    +0.4%
latency_dtw_p95_ms           55.56        55.34    -0.4%
latency_end_to_end_p95_ms    123.9        122.6    -1.0%
latency_query_build_p95_ms   4.241        4.212    -0.7%
report_linkage               (absent)     1.0      skipped by the gate
forecast_median_t90_m        (absent)     340.4    skipped by the gate
```

## uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105
```text
$ uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105
query DEMO-BRAVO-0828-T1 at T+105 s · target BRAVO-fuel_farm · method dtw · 500 candidates
center (21,253, -4,178) m region frame · 2,164 m at 320° (northwest) of BRAVO-fuel_farm · radius 370 m · anchor
match_kind
analogs (top matches with a known recovery point)
┃ # ┃ incident            ┃ score ┃ recovery rel. (m) ┃ rotation ┃ anchor          ┃ j* (s) ┃ mapped recovery (m) ┃
│ 1 │ P1-ALPHA-260303     │ 1.000 │ (-1,442, 1,320)   │      +0° │ BRAVO-fuel_farm │    191 │ (21,207, -4,511)    │
│ 2 │ HOTEL-250818-2126   │ 0.993 │ (2,197, -284)     │    -133° │ BRAVO-fuel_farm │    231 │ (21,347, -4,040)    │
│ 3 │ FOXTROT-251215-2125 │ 0.990 │ (2,334, -243)     │    -134° │ BRAVO-fuel_farm │    233 │ (21,206, -3,981)    │
exit path: 60 points from (22,518, -5,698) to (21,207, -4,511) m
roads crossing the zone: County Rd 12
exit 0
```

## uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120
```text
$ uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120
query DEMO-BRAVO-0828-T1 at T+120 s · keyword text: 'drone orbit fuel farm vehicle road launch northwest'
forecast zone: center (21,237, -4,318) m, radius 324 m, roads: County Rd 12
match #1 P1-DELTA-260419 (score 1.000)
┃ # ┃ report              ┃ source          ┃ grade ┃ event (local)    ┃  score ┃ text
│ 1 │ R-P1-DELTA-260419-1 │ security_forces │ B2    │ 2026-04-19 21:35 │ 0.0328 │ Security forces patrol observed a
│   │                     │                 │       │                  │        │ small drone near the fuel farm … A
│   │                     │                 │       │                  │        │ white pickup was parked on County Rd
│   │                     │                 │       │                  │        │ 12 from 21:20 to 22:05 …
  link: County Rd 12 runs through tonight's predicted zone.
match #2 P1-ALPHA-260303 (score 1.000)
│ 1 │ R-P1-ALPHA-260303-2 │ security_forces │ B3    │ 2026-03-03 21:52 │ 0.0328 │ … near Ridge Rd …
│ 2 │ R-P1-ALPHA-260303-1 │ bdoc_log        │ B2    │ 2026-03-03 21:52 │ 0.0323 │ 21:52 BDOC: UAS detected …
│ 3 │ R-P1-ALPHA-260303-3 │ local_pd        │ C4    │ 2026-03-03 21:52 │ 0.0317 │ Deputy responded …
match #3 P1-CHARLIE-260710 (score 0.999)
│ 1 │ R-P1-CHARLIE-260710-2 │ security_forces │ B3  │ 2026-07-10 21:30 │ 0.0328 │ 21:30 SF: patrol observed sUAS …
│ 2 │ R-P1-CHARLIE-260710-3 │ local_pd        │ C4  │ 2026-07-10 21:30 │ 0.0323 │ Deputy responded …
│ 3 │ R-P1-CHARLIE-260710-1 │ bdoc_log        │ A2  │ 2026-07-10 21:30 │ 0.0159 │ 21:30 BDOC: UAS detected …
exit 0
```

## python3 scripts/check_targets.py 5
```text
$ python3 scripts/check_targets.py 5
PASS  Recall@5 at T=120 s (§19.3): 1 (target >= 0.8)
PASS  DTW lift over the Euclidean baseline (§19.3): 0.5217 (target >= 0.1)
PASS  Copycat-first rate (§19.3): 0 (target <= 0.05)
PASS  Prefilter p95 ms (§10.9): 29.85 (target <= 50)
PASS  DTW re-rank of 50 candidates p95 ms (§10.9): 55.34 (target <= 800)
PASS  End-to-end live update p95 ms (§10.9): 122.6 (target <= 1500)
PASS  Report linkage (§19.3): 1 (target >= 0.7)
PASS  Forecast median error at T=90 s, m (§19.3): 340.4 (target <= 400)
PASS  demo forecast_error_max_m: pass
PASS  demo live_first_contact_local: pass
PASS  demo live_orbit_established_s: pass
PASS  demo live_rank1_report_for: pass
WARN  demo live_top3_incidents: fail

All targets met (accepted gaps shown as WARN).
exit 0
```

## uv run python -m kairos_defense.eval.forecast_choice
```text
$ uv run python -m kairos_defense.eval.forecast_choice
forecast anchor on nights 2025-03-01 to 2026-02-28, T = 90 s
  target     median     502 m  P80    1000 m  queries 36  missing 0
  match_kind median     311 m  P80     492 m  queries 36  missing 0
rule: match_kind iff median at least 50 m lower and P80 not higher
verdict: match_kind (current forecast.anchor: match_kind)
wrote …/reports/forecast_choice.json
exit 0
```

## uv run kairos-defense eval --baseline
```text
$ uv run kairos-defense eval --baseline
… (the same table as `make eval`)
wrote …/reports/eval_2026-10-29.md and …/reports/eval_2026-10-29.json
wrote …/reports/baseline.json
exit 0
```

## make check, make test-all
```text
$ make check
uv run ruff check .            All checks passed!
uv run ruff format --check .   … files already formatted
uv run pytest -m "not slow" -q 497 passed, 12 deselected
npm --prefix web run check     lint, typecheck, Vitest: 2 files, 5 tests passed
$ make test-all
509 passed in 192.26s (0:03:12)
```
