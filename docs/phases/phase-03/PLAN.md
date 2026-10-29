# Phase 3: Features, windows, Euclidean baseline and eval skeleton, plan

> **Backfilled 2026-10-28, as built.** Phase 3 was built by hand in a Claude Code cloud session
> before the autopilot existed, and no plan file was kept. This plan is reconstructed from commit
> `e494995` (`phase 3: features, signatures, PAA windows, Euclidean baseline and eval skeleton`),
> the phase 3 entry in `docs/PROGRESS.md`, D-046 to D-058 in `docs/DECISIONS.md`, and the code. It
> describes what was planned and built, not a plan for new work.

## Goal

Turn the raw synthetic data into something a matcher can search, and measure a first baseline
(SPEC §20, phase 3):

- a feature store (`track_features`, 1 Hz) and one signature per track (`track_signatures`);
- PAA window vectors in LanceDB `flight_windows`, history tracks only;
- the §11 context joins in the DuckDB adapter;
- a Euclidean baseline matcher with a no-look-ahead prefilter:
  `kairos-defense match --method euclidean --incident <id> --at <s>`;
- the evaluation skeleton: query sets, the §19.2 protocol, Recall@5, MRR, time to match and
  latency, written to `reports/eval_<date>.md` and `.json`.

There are no targets yet. The numbers are recorded in PROGRESS.md as the baseline that phase 4's
DTW lift is measured against.

## Inputs read

- `CLAUDE.md`:
  - rule 2 (truth isolation): only `kairos_defense.eval` reads `truth.duckdb`;
  - rule 3 (no look-ahead): every search for past flights filters to tracks that started before
    the query, and a test enforces it **before** the matcher is written (the phase 3 manual
    prompt says so);
  - rule 6 (ports and adapters): matching depends on `TrackStore` and `VectorStore`, never on
    DuckDB or LanceDB;
  - the library notes for DuckDB 2.0 (`ASOF LEFT JOIN`, window joins) and LanceDB 0.40
    (`search(...).where(..., prefilter=True)`, `_distance`).
- SPEC:
  - §7.2 (derived tables) and §7.5 (`flight_windows` columns, `*_ts_ms` integers, plain-column
    filters);
  - §9.1 to §9.5 (resampling, target and frames, channels, signatures, windows and vectors);
  - §10.1 to §10.3 (pipeline, Euclidean baseline, prefilter) and §10.8 (`Match`);
  - §11.1 to §11.3 (as-of weather and base events, RF within ±30 s, tracks before a time);
  - §19.1 to §19.4 (query sets, protocol, metrics, outputs and the `--baseline` gate);
  - `config/scoring.yaml` (§6.5): `features`, `windows`, `prefilter`, `live.min_track_s`;
  - the §20 phase 3 block.
- `docs/DECISIONS.md` D-001 to D-045, mainly:
  - D-003: T+0 is first radar contact; launch and recovery are target-relative and may be unknown;
  - D-009: a query with no earlier same-actor track cannot be answered;
  - D-014: the LanceDB call lives in `store/lance.py` behind `VectorStore.search`;
  - D-024: §9.4's `loiter_dir` is `ccw` when the bearing rate is **negative**;
  - D-037: a copycat's Remote ID flights share one serial;
  - D-038: an incident's `start_ts` is its first detection by any sensor, usually RF at takeoff.
- `docs/PROGRESS.md`, the phase 2 entry: the full dataset, the planted story and the open items
  D-024, D-038, D-040 and D-044.

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md`:

- **D-046**, target choice: §9.2's rule (smallest mean distance over the slowest 50% of seconds)
  picked the fence for P1 at ALPHA, because the radar sees takeoff and landing 2 km out. Candidate
  seconds are now in flight (leading and trailing seconds below 0.8 × the median altitude are
  dropped), have a speed, and lie within 500 m of the fence (all in-flight seconds if fewer than
  10). The slowest half vote and the smallest **median** distance wins. 93 of 131 prober, copycat
  and swarm tracks get their true target (48 with the spec rule); every P1 flight is right. Still
  wrong: P6, C2 and swarm drones.
- **D-047**, signature details: the loiter radius is the median distance from the target
  centroid; `loiter_dir` sums the bearing change outside the target polygon (`none` under 180°,
  `ccw` when negative); dwell, median altitude in flight, approach bearing at the first second
  within 1,000 m, `tod_minutes` wrapping before noon; launch from a single heard Remote ID serial's
  operator, else a first point below 30 m; recovery from a last point below 30 m.
- **D-048**, RF and Remote ID association: ±30 s at the same base, with the 15° bearing gate when
  another track is within ±60 s; Remote ID ±5 s and 100 m; most frequent family and serial win.
  Both joins bucket time so DuckDB plans an equi-join (RF 1.6 s, Remote ID 0.9 s instead of 19 s
  and 38 s).
- **D-049**: derived tables hold history tracks only. A live track's features and signature are
  computed from its points up to T.
- **D-050**: a track starts at its first radar point on both sides of the filter, and T counts from
  it. The query is rebuilt from the points up to T. Before 60 s the query uses all its rows against
  the 60 s windows; below `min_track_s` (T = 30) the matcher does not run. The prefilter raises
  `LookAheadError` on any row that did not start strictly earlier.
- **D-051**: exact fractional PAA weights; NaN filled by linear interpolation after normalizing
  (all-NaN channel → 0); one function builds both indexed and query vectors; windows of one size
  are built in a batch.
- **D-052**: the LanceDB 0.40 adapter (`replace` with scalar indexes, `upsert` by key column,
  `search` always pre-filters, `list_tables().tables`).
- **D-053**: the index build uses the adapters directly; matching and evaluation use only the ports.
- **D-054**: the Euclidean `Match` fills only what it computes (`score = 1 − d²/4`, no reasons,
  `warp_ratio` NaN, `model_version` `euclidean-v1`).
- **D-055**: evaluation definitions (months 13 to 18 as local nights, query sets, time to match,
  copycat-first, MRR with no hit = 0, latency stages, demo rows).
- **D-056**: `eval --baseline` and the 5% gate are built, but phase 3 writes no `baseline.json`;
  phase 4's exit check does.
- **D-057**: prefilter p95 was 83 ms on the cloud sandbox, above the 50 ms budget; no tuning in a
  phase without targets.
- **D-058** (open, found at the end): at T+90 the planted P1 flights rank 1,149 to 1,194 in the
  Euclidean prefilter, outside its 50 candidates. Left for phase 4 with three options.

## Work breakdown

1. **No-look-ahead test first.** `tests/unit/test_no_lookahead.py` against the planned prefilter
   API: filter text, every result started before the query, later P1 flights never returned,
   points after T do not change the query, a leaky store raises.
2. **Resampling (§9.1).** `features/resample.py`: sort, drop duplicate timestamps (keep the highest
   `quality`), whole UTC seconds, gaps over `max_interp_gap_s` marked `in_gap`, a 3 s median then
   a 3 s mean inside gap-free runs (closed-form median of three), central differences, heading in
   [0, 360), turn rate wrapped and clipped to ±60 °/s. Also `epoch_ms` for LanceDB.
3. **Target, frame and channels (§9.2, §9.3).** `features/channels.py`: `Target` (asset polygon or
   fence line), `SiteGeometry`, `load_site` through `TrackStore.sql`, `in_flight_mask`,
   `choose_target` (D-046), `add_target_columns` (`x_rel_m`, `y_rel_m`, `dist_target_m`,
   `bearing_rel_deg`), `track_features`, `channel_matrix` and `normalize` (σ floor 1e-3, weights).
4. **Signatures (§9.4).** `features/signatures.py`: `SensorContext`, `tod_minutes`,
   `approach_bearing`, `loiter_mask`, `loiter_direction` (D-024, D-047) and `signature`, one §7.2
   row.
5. **Windows (§9.5).** `features/windows.py`: `paa_weights`, `window_vectors` (strided batch, one
   einsum), `window_vector`, `iter_windows` (stride 10 s, skip windows over 20% gap),
   `query_window_size` and `query_vector` (D-050, D-051).
6. **Stores.** `store/ddl.py` gains `DERIVED_DDL` for `track_features` and `track_signatures`.
   `store/duck.py`: `DuckTrackStore` (`track_points`, `features`, `signature`, strict
   `tracks_before`, `context_asof` with `ASOF LEFT JOIN` and active base events, `sql`, plus
   `tracks`, `rf_association`, `rid_association`, `sensor_context` and `write_table`), D-048.
   `store/lance.py`: `LanceVectorStore` (`replace`, `upsert`, `search`, `count`, `to_pandas`),
   D-052.
7. **Index build.** `features/build.py`: `build_index(cfg) -> IndexSummary`. It reads raw tables,
   skips live tracks (D-049), runs the pure functions per track, writes both derived tables and
   replaces `flight_windows`. CLI `kairos-defense index` prints a summary table.
8. **Matching.** `match/query.py` (`Query`, `query_at`, `load_query`; rebuilt from points up to
   T), `match/prefilter.py` (`window_filter` with a validated incident id, `best_per_track`,
   `prefilter`, `LookAheadError`), `match/baseline.py` (`rank_candidates`, `euclidean_matches`,
   D-054), `match/types.py` (§10.8 `Match`). CLI `kairos-defense match --method euclidean
   --incident --at [--track --top]`; `--method dtw` names phase 4.
9. **Evaluation.** `eval/truth.py` (the only truth reader), `eval/harness.py` (query sets, protocol
   over `T_GRID`, the Euclidean ranker, D-055), `eval/metrics.py` (pure metric functions),
   `eval/demo.py` (demo rows from `scenario_demo.yaml`, pending ones named by phase),
   `eval/report.py` (markdown, JSON, the recall-by-T figure, regressions, `gate`, D-056). CLI
   `kairos-defense eval [--baseline] [--method]`.
10. **Docs.** PROGRESS.md entry, D-046 to D-058, the eval report and figure, one commit
    `phase 3: ...`.

## Tests

New helpers: `tests/unit/synth.py` (synthetic points and sites with known answers) and, in
`tests/conftest.py`, `P1_NIGHTS`, `tmp_config` and the session fixture `p1_index` (the six P1
nights generated, written and indexed in a temporary folder).

Fast (`tests/unit`):

- `test_resample.py` (11): `test_straight_line_speed_heading_turn`,
  `test_circle_speed_and_turn_rate[ccw → negative | cw → positive]`, `test_climb_rate`,
  `test_duplicates_keep_highest_quality`, `test_short_gaps_are_interpolated_long_gaps_marked`,
  `test_smoothing_does_not_cross_gaps`, `test_fractional_timestamps_go_to_whole_seconds`,
  `test_spike_is_suppressed`, `test_empty_and_single_point`, `test_epoch_ms`.
- `test_channels.py` (8): `test_orbit_picks_its_asset`, `test_perimeter_run_picks_the_fence`,
  `test_target_columns`, `test_fence_target_centroid_and_radius`, `test_normalize_known_answer`,
  `test_channel_order_follows_config`, `test_in_flight_mask_drops_takeoff_and_landing`,
  `test_takeoff_far_away_does_not_steal_the_target`.
- `test_signatures.py` (11): `test_orbit_signature[ccw | cw]`, `test_hover_has_no_direction`,
  `test_short_pass_is_not_a_loiter`, `test_tod_wraps_past_midnight[4 cases]`,
  `test_launch_and_recovery_rules`, `test_remote_id_operator_is_the_launch_when_serial_is_stable`,
  `test_alt_median_skips_takeoff_and_landing`.
- `test_duck_store.py` (6): `test_rf_bearing_gate_separates_concurrent_tracks`,
  `test_rid_within_5s_and_100m`, `test_context_asof_and_events`,
  `test_tracks_before_is_strict_and_excludes_incident`, `test_write_table_checks_columns`,
  `test_adapter_refuses_truth`.
- `test_windows.py` (16): `test_paa_weights_known_answers`,
  `test_window_vector_shape_norm_and_channel_order`, `test_weights_scale_channels`,
  `test_nan_handling`, `test_window_offsets_and_sizes`, `test_gappy_windows_are_skipped`,
  `test_query_window_size[9 cases]`, `test_query_vector_equals_indexed_window`.
- `test_index.py` (13), on `p1_index`:
  - `test_p1_planted_signatures[5 history P1 flights]`: approach 315° ± 15°, radius 180 ± 25 m,
    `ccw`;
  - `test_live_p1_signature_computed_from_points`;
  - `test_live_incidents_are_absent_everywhere` (derived tables and LanceDB);
  - `test_filter_returns_only_the_requested_window_size[60 | 120 | 300]`;
  - `test_window_metadata_matches_signatures`, `test_features_are_one_hz_per_track`,
    `test_rebuild_is_deterministic`.
- `test_no_lookahead.py` (5): `test_filter_text`, `test_results_never_start_after_the_query` (every
  track at T = 45, 90 and 180), `test_first_track_has_no_history`,
  `test_query_ignores_points_after_t`, `test_prefilter_refuses_a_leaky_store`.
- `test_eval_metrics.py` (6): `test_recall_at_k`, `test_mrr`, `test_time_to_match`,
  `test_copycat_first`, `test_percentiles`, `test_regressions_respect_direction`.
- `test_eval_harness.py` (5): `test_night_of`, `test_query_sets`, `test_protocol_and_demo`,
  `test_outputs_and_gate`, `test_cli_eval`.
- `test_cli.py`: `BUILT` gains `index`, `match` and `eval` (their three stub cases go), plus
  `test_index_needs_data`, `test_match_dtw_is_phase_4` and `test_match_runs_on_the_p1_nights`.

Slow (`tests/slow/test_full_index.py`, 3): `test_full_index_volumes`,
`test_full_index_is_deterministic` (two builds, identical hashes), `test_full_eval` (a full eval
passes the gate).

In all, phase 3 adds 84 fast tests (81 in nine new files, 3 in `test_cli.py`) and retires 3 stub
cases: 286 → 367 fast tests, and 4 → 7 slow tests.

SPEC §20's named tests map as follows: resampling on straight lines and circles →
`test_resample.py`; P1 planted signatures → `test_index.py::test_p1_planted_signatures`; no
look-ahead → `test_no_lookahead.py`; live incidents absent from LanceDB →
`test_live_incidents_are_absent_everywhere`; LanceDB filters return only the requested window size
→ `test_filter_returns_only_the_requested_window_size`.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it produces |
|---|---|---|
| Features, signatures and windows built | `make index` (`kairos-defense index`) | summary: tracks, history tracks indexed, live tracks skipped, `track_features` rows and gap seconds, `track_signatures` rows, `flight_windows` per size, targets, loiter directions, RF unknown, Remote ID present |
| Eval report with baseline Recall@5, MRR, time to match and latency | `make eval` (`kairos-defense eval`) | the console table and `reports/eval_<date>.md` / `.json`: query sets, the four metrics, copycat-first, latency p50/p95 per stage, demo rows |
| Baseline recorded | `docs/PROGRESS.md` | the phase 3 entry's "Euclidean baseline (phase 3, no targets)" line |
| The matcher runs from the CLI | `uv run kairos-defense match --method euclidean --incident DEMO-BRAVO-0828 --at 90` | query line (window, target, candidates, ms) and the top 10 |

The check runs after `make clean && make data` as one `&&` chain and must exit 0. `make check` and
the slow tests (`pytest tests/slow`) add to it.

## Documentation to write or update

- `docs/PROGRESS.md`: the phase 3 session-log entry and the exit-check evidence line.
- `docs/DECISIONS.md`: D-046 to D-058.
- `reports/eval_<date>.md`, `.json` and `reports/figures/eval_recall_by_t.png` (committed).
- Package READMEs were not a convention yet. The `store/` and `eval/` READMEs written in phase 0's
  backfill already cover phase 3; this backfill adds `features/README.md` and `match/README.md`
  (see REPORT.md).

## Risks and mitigations

- **Look-ahead through any path.** Mitigation: the filter is mandatory and built in one place;
  `LookAheadError` on any row not strictly earlier; derived tables hold no live track (D-049); the
  query is rebuilt from points up to T. The test file was written first and includes a leaky fake
  store and a tampering test.
- **Target choice puts similar flights in different frames.** Mitigation: rules compared on all
  131 prober, copycat and swarm tracks before choosing D-046; the planted-signature tests pin P1.
- **Query and index vectors drift apart.** Mitigation: one function builds both
  (`test_query_vector_equals_indexed_window`).
- **Slow joins and index build.** Mitigation: bucketed equi-joins (D-048), batched PAA and a
  closed-form median (index 96 s → 55 s on the cloud machine).
- **LanceDB API differences in 0.40.** Mitigation: a thin adapter (D-052) and tests through it.
- **Truth leaks into the matcher.** Mitigation: `eval/truth.py` is the only reader; the §7.6 scan
  covers the new modules; truth labels outcomes only after ranking.
- **Nondeterministic builds.** Mitigation: no random draws in `index`; ties broken by id;
  `test_rebuild_is_deterministic` and the slow full-volume hash test.
- **Gate noise.** With 23 prober queries one query moves Recall@5 by 0.043 (D-056).

## Out of scope

- DTW re-rank, fusion, calibration and explanations: phase 4 (§10.4 to §10.7).
- `baseline.json`: written by phase 4's exit check (D-056).
- `report_clues` and the LanceDB `reports` table: phase 5. `swarm_features` and `swarm_windows`:
  phase 9.
- Latency tuning toward §10.9 (D-057): phase 4 or 9.

## Review changes

None. Phase 3 was planned and built in an interactive Claude Code session (CLAUDE.md, "How we
work", rule 2); no plan file or reviewer record survives, and there was no autopilot reviewer.
