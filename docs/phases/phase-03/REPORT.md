# Phase 3: Features, windows, Euclidean baseline and eval skeleton, report

Status: done · Date: 2026-10-28 (built; docs backfilled the same day) · Commits: `e494995` (phase 3)

## Summary

Phase 3 made the data searchable and measured a first baseline:

- `kairos-defense index` resamples every history track to 1 Hz, picks its target, and writes
  800,148 feature rows, 1,898 signatures and 136,266 PAA window vectors (60, 120 and 300 s) to
  LanceDB. Live tracks are skipped everywhere.
- `kairos-defense match --method euclidean` rebuilds a track as seen T seconds in and ranks earlier
  tracks by their nearest window, behind a no-look-ahead filter that raises if it is ever broken.
- `kairos-defense eval` runs the §19 protocol and writes `reports/eval_<date>.md` and `.json`.

The Euclidean baseline is Recall@5 0.435, MRR 0.302, time to match 26% and copycat-first 57%.
These are the reference for phase 4's DTW lift, not targets. The open issue for phase 4 is D-058:
the prefilter does not surface the planted P1 flights for the live query at T+90.

Phase 3 was built by hand in a Claude Code cloud session: 367 fast and 7 slow tests. These
documents were reconstructed on 2026-10-28. Today's rerun gives identical index counts, metrics,
ranks and demo rows; only the latencies differ (lower on the laptop).

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Resampling | 1 Hz grid, duplicate timestamps (best quality kept), gaps over 10 s marked `in_gap`, 3 s median then 3 s mean inside runs, speed, climb rate, heading and turn rate (§9.1) | `features/resample.py` |
| Target and channels | target choice where the drone lingers (D-046), target-relative frame, `dist_target_m`, `bearing_rel_deg`, the five channels, z-normalization with weights (§9.2, §9.3) | `features/channels.py` |
| Signatures | approach bearing, loiter radius and direction, dwell, median altitude, local time of night, launch and recovery, RF family, Remote ID (§9.4, D-047) | `features/signatures.py` |
| Windows | exact PAA (16 segments × 5 channels = 80 numbers), batch window vectors, query window size and vector (§9.5, D-050, D-051) | `features/windows.py` |
| Index build | `build_index` over history tracks; writes `track_features`, `track_signatures` and `flight_windows` (D-049, D-053) | `features/build.py` |
| DuckDB adapter | `DuckTrackStore`: the `TrackStore` port plus §11 joins (as-of weather, base events, RF ±30 s with the bearing gate, Remote ID ±5 s and 100 m, bucketed equi-joins, D-048) and `write_table` | `store/duck.py`, `store/ddl.py` (`DERIVED_DDL`) |
| LanceDB adapter | `LanceVectorStore`: `replace` with scalar indexes, `upsert`, pre-filtered `search` (D-052) | `store/lance.py` |
| Query | a track as seen T seconds after its first radar point, rebuilt from those points only | `match/query.py` |
| Prefilter | the §10.3 filter, nearest window per track, top 50 candidates, `LookAheadError` | `match/prefilter.py` |
| Baseline | `Match` rows from prefilter candidates, `score = 1 − d²/4` (D-054) | `match/baseline.py`, `match/types.py` |
| Evaluation | truth reader, query sets and protocol (D-055), pure metrics, demo rows, md/json report, recall figure, `--baseline` gate (D-056) | `eval/truth.py`, `eval/harness.py`, `eval/metrics.py`, `eval/demo.py`, `eval/report.py` |
| CLI | `index`, `match --method euclidean --incident --at [--track --top]`, `eval [--baseline] [--method]` | `cli.py` |

Since phase 3, only `eval/report.py` has changed among phase 3's code (`911aba1`: the latency
regression tolerance, D-060), together with one assertion each in `test_eval_harness.py` and
`test_eval_metrics.py`. `pyproject.toml` builds dtaidistance from source (D-064), which phase 3
does not use. `git diff --stat e494995 HEAD -- src tests` lists nothing else but READMEs.

## Decisions and deviations from SPEC

- [D-046](../../DECISIONS.md), **deviation**: the target is the smallest *median* distance over the
  slowest half of in-flight seconds near the fence, not the *mean* over the slowest half of all
  seconds. 93/131 tracks right instead of 48/131, every P1 flight included.
- [D-047](../../DECISIONS.md), **deviation**: `loiter_radius_m` is the median distance from the
  target centroid (the spec's "distance + target radius" gives about 250 m for CHARLIE's 180 m
  orbit). Also the loiter direction, dwell, altitude, approach, time-of-night, launch and recovery
  details.
- [D-048](../../DECISIONS.md): RF and Remote ID association, the bearing gate and the bucketed
  joins.
- [D-049](../../DECISIONS.md): derived tables hold history tracks only.
- [D-050](../../DECISIONS.md): first radar point as start and T = 0, query rebuilt from points up to
  T, early queries, `LookAheadError`.
- [D-051](../../DECISIONS.md): PAA weights and NaN handling.
- [D-052](../../DECISIONS.md): the LanceDB 0.40 adapter.
- [D-053](../../DECISIONS.md): the index build uses the adapters; matching and evaluation use the
  ports.
- [D-054](../../DECISIONS.md): the Euclidean baseline's `Match` fields.
- [D-055](../../DECISIONS.md): evaluation definitions.
- [D-056](../../DECISIONS.md): `baseline.json` waits for phase 4.
- [D-057](../../DECISIONS.md): prefilter p95 83 ms on the cloud sandbox against the 50 ms budget.
  Today on the laptop it is 15 ms (see Metrics).
- [D-058](../../DECISIONS.md), **open for phase 4**: the Euclidean prefilter does not surface P1 for
  the live query at T+90. Reconfirmed today with identical ranks.
- Backfill only: [D-067](../../DECISIONS.md) records how this backfill was done, why the eval
  report is dated 2026-10-29, and the laptop latencies.

## Tests

At `e494995`: 367 fast Python tests (7 slow deselected) and 5 Vitest tests, all passing. Phase 3
added 84 fast tests and retired 3 stub cases (286 → 367), and added 3 slow tests (4 → 7):

- `test_resample.py`, 11: straight line (speed, heading, zero turn), circles cw and ccw (speed and
  turn rate, ccw negative), climb rate, duplicates, short gaps interpolated and long gaps marked,
  smoothing does not cross gaps, fractional timestamps, a spike suppressed, empty and single-point
  input, `epoch_ms`.
- `test_channels.py`, 8: an orbit picks its asset, a perimeter run picks the fence, target columns,
  the fence target's centroid and radius, `normalize` known answer, channel order from config, the
  in-flight mask, a far takeoff does not steal the target.
- `test_signatures.py`, 11: cw and ccw orbits, a hover has no direction, a short pass is not a
  loiter, `tod_minutes` wraps past midnight (4 cases), launch and recovery rules, the Remote ID
  operator as launch when the serial is stable, median altitude skips takeoff and landing.
- `test_duck_store.py`, 6: the RF bearing gate separates concurrent tracks, Remote ID ±5 s and
  100 m, as-of weather and events, strict `tracks_before` excluding the incident, `write_table`
  checks columns, the adapter refuses truth.
- `test_windows.py`, 16: PAA weights known answers, vector shape, norm and channel order, weights
  scale channels, NaN handling, offsets and sizes, gappy windows skipped, query window size (9
  cases), the query vector equals the indexed window.
- `test_index.py`, 13: the five history P1 signatures (approach 315° ± 15°, radius 180 ± 25 m,
  `ccw`), the live P1 signature from its points, live incidents absent from every derived table and
  LanceDB, filters return only the requested window size (60, 120, 300), window metadata matches
  signatures, features are 1 Hz per track, a rebuild is deterministic.
- `test_no_lookahead.py`, 5 (written before the matcher): the filter text; every result started
  before the query for every track at T = 45, 90 and 180, and later P1 flights are never returned;
  the first track has no history; points after T do not change the query; a leaky store raises.
- `test_eval_metrics.py`, 6 and `test_eval_harness.py`, 5: known-answer metrics, regressions by
  direction, query sets, protocol and demo rows, outputs and the gate, the CLI.
- `test_cli.py`: `index`, `match` and `eval` leave the stub list (−3); `test_index_needs_data`,
  `test_match_dtw_is_phase_4`, `test_match_runs_on_the_p1_nights` (+3).
- Slow, `test_full_index.py`, 3: full volumes, two full builds give identical hashes, a full eval
  passes the gate.

Today (`53134b8`, dev laptop):

- The nine phase 3 unit files give 81 passed; the three new `test_cli.py` tests give 3 passed; the
  slow file gives 3 passed in 25.5 s.
- `make check`: 367 passed, 7 deselected. `make test-all`: 374 passed in 42.8 s.

No phase 3 test was removed, skipped or weakened. Since phase 3, D-060 changed one assertion each in
`test_eval_harness.py::test_outputs_and_gate` and `test_eval_metrics.py::test_regressions_respect_direction`
to match the looser latency tolerance; both still check that a real regression fails the gate.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| `make index` builds features, signatures and windows | pass | 1,898 history tracks indexed, 6 live skipped; 800,148 feature rows; 136,266 windows (57,462 / 51,297 / 27,507); 7.2 s |
| `make eval` reports baseline Recall@5, MRR, time to match and latency | pass | Recall@5 0.435, MRR 0.302, time to match 26%, copycat-first 57%; latency p95 query 4 ms, prefilter 15 ms, end to end 19 ms |
| Whole chain | pass | `make index && make eval` exit 0 in 13.8 s after `make clean && make data` (originally 87.1 s on the cloud machine) |
| Same results as phase 3 | pass | index counts identical; every metric, rank, per-actor row and demo row in the JSON identical; only latencies differ |
| Demo rows | pass | first contact 21:40:06, 71 m; orbit T+79 s; live top 3 is info (0/3, D-058) |
| `match --method euclidean` | pass | `DEMO-BRAVO-0828` at T+90: window 60 s, target BRAVO fuel farm, 50 candidates, 28 ms |
| `make check`, `make test-all` | pass | 367 and 374 passed |

Full output is in [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Euclidean baseline, probers unless noted. No targets apply in phase 3; the §19.3 targets start in
phase 4 and are shown for reference.

| Metric | Phase 3 (`e494995`, cloud) | Today (`53134b8`, laptop) | v1 target (phase 4+) |
|---|---:|---:|---|
| Prober queries (unanswerable) | 23 (0) | 23 (0) | — |
| Copycat queries (unanswerable) | 10 (0) | 10 (0) | — |
| Recall@5 at T = 120 s | 0.435 | 0.435 | ≥ 0.80 |
| MRR at T = 120 s | 0.302 | 0.302 | report only |
| Time to match (top 3 by T = 90 s) | 26% | 26% | ≥ 70% |
| Copycat-first at T = 120 s | 57% | 57% | ≤ 5% |
| Recall@5 at T = 120 s, copycats | 0.500 | 0.500 | report only |
| Latency query build p50 / p95 | 25 / 38 ms | 4 / 4 ms | — |
| Latency prefilter p50 / p95 | 64 / 83 ms | 13 / 15 ms | p95 ≤ 50 ms |
| Latency end to end p50 / p95 | 93 / 117 ms | 17 / 19 ms | p95 ≤ 1,500 ms |
| `index` elapsed | 55.0 s | 7.2 s | — |
| `eval` elapsed | 23.1 s | 3.8 s | — |

Recall@5 by T (probers): T=30 not run, 45 0.087, 60 0.304, 90 0.130, 120 0.435, 180 0.261.
Copycats: 45 0.500, 60 0.400, 90 0.100, 120 0.500, 180 0.800. Per actor at T = 120: P4 1.00,
P3 0.60, C2 0.60, P5 0.50, C1 0.40, P6 0.33, P2 0.25, P1 0.00.

Index shape: targets fence 1,800, flight line 35, fuel farm 19, HQ 16, munitions 28; loiter
direction ccw 20, cw 1, none 1,877; RF family unknown 0; Remote ID present 1,634; gap seconds
62,850 (7.9%).

## Known issues and follow-ups

- **D-058 (phase 4 must start here):** best-window ranks of the earlier P1 flights for the live
  query, among 1,882 earlier tracks, rechecked today: T+60 ALPHA 05-02 8, ALPHA 03-03 53, DELTA 197;
  T+90 CHARLIE 176, ALPHA 05-02 1,149, DELTA 1,164, ALPHA 03-03 1,194; T+120 CHARLIE 59,
  ALPHA 03-03 84, DELTA 644. At T+90 none of the three expected flights is among the 50 candidates
  DTW would see. Options (a) to (c) are in D-058.
- **D-057 is a cloud-sandbox number.** On the dev laptop, where the autopilot runs, the prefilter
  p95 is 15 ms, inside §10.9's 50 ms. D-059's note that phase 4 "must speed it up" does not apply
  there. Phase 4 may still choose per-size tables or a brute force for D-058's larger candidate
  lists.
- **D-046:** target choice is still wrong for P6 (the flight line on every flight), C2 (mostly the
  fence) and swarm drones (mixed). 1,800 of 1,898 tracks have the fence as target, mostly
  hobbyists that launch from parks 2.2 km out.
- **D-056:** `reports/baseline.json` does not exist yet; phase 4's exit check writes it. One prober
  query moves Recall@5 by 0.043, close to the 5% gate.
- **D-055:** copycat-first (57%) counts queries whose own actor is not in the 50 candidates at all,
  so it falls as recall rises.
- **D-065 also applies to the eval figure:** `eval/report.py` sets no font family, so
  `eval_recall_by_t.png` renders in DejaVu Sans on the laptop. The data is identical. The laptop
  render is committed. Pin a font when `eval/report.py` next changes.
- **Report file dates are UTC.** `eval_<date>` uses the run's UTC date, so an evening run in
  America/New_York writes the next day's file (today's is `eval_2026-10-29`).

## How to debug this phase

- **Rebuild and rerun.** `make index` (7 s) then `make eval` (4 s). Both need `make data` first;
  `index` exits with "make data" if the raw tables are missing.
- **One track's features.** In Python: `DuckTrackStore(cfg.app.paths.duckdb, cfg.app)` as `st`,
  `pts = st.track_points(tid)`, `site = load_site(st, pts.installation_id[0])`,
  `f, target = track_features(pts, site, cfg.scoring)`. `st.features(tid)` and `st.signature(tid)`
  read what `index` stored (history tracks only). Synthetic tracks with known answers are in
  `tests/unit/synth.py`.
- **Wrong target.** Call `choose_target(site, xy, speed, alt)` and compare
  `[np.median(t.distance(xy[sel])) for t in site.targets]` over the same selection
  (`in_flight_mask`, near the fence, slowest half). The rules and their constants (0.8, 500 m,
  10 s) are at the top of `channels.py`.
- **Wrong loiter direction.** Remember D-024: a decreasing bearing from the target is `ccw`. Check
  `loiter_mask(f)` has at least 10 seconds and that the swept angle outside the polygon reaches
  180°.
- **A query that matches nothing, or the wrong thing.** `uv run kairos-defense match --method
  euclidean --incident <id> --at <s> [--track <tid>] [--top 50]` prints the window size, rows used,
  target and timing. `load_query(st, tid, T, cfg.scoring)` gives the `Query`; search with a large
  `k` and `best_per_track(hits, 10_000)` to see where a given track ranks (the D-058 recheck in
  [EXIT_CHECK.md](EXIT_CHECK.md) does exactly this).
- **`LookAheadError`.** A store returned a row whose `start_ts_ms` is not strictly before the
  query's first radar point, or from the query's own incident. Check the filter from
  `window_filter` and that `flight_windows` was built by `index` (one `start_ts_ms` per track).
- **Eval numbers move.** Compare `outcomes` in two `reports/eval_*.json` files: each row has
  `track_id`, `at_s`, `true_rank`, `copycat_rank` and the latencies. A change of 0.043 in Recall@5
  is one prober query.
- **Slow `index`.** Time `store.sensor_context()` (the bucketed RF and Remote ID joins, 1.6 s and
  0.9 s on the cloud machine, D-048) separately from the per-track loop. If the joins take tens of
  seconds, DuckDB has planned a range join: keep the bucket arithmetic inside the CTE (`_bucket`).
- **Truth isolation.** Only `eval/truth.py` opens `truth.duckdb`. The §7.6 scan in
  `tests/unit/test_truth_isolation.py` fails on any other module that names it.

## Fix attempts

None. The autopilot did not gate this phase; it was built by hand and its documents were backfilled.
