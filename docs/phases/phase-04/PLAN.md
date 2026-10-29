# Phase 4: DTW matcher and fusion model, plan

Autopilot plan step, 2026-10-28. Written without a human in the loop (CLAUDE.md rule 5, `phase-auto`):
every assumption below is recorded in `docs/DECISIONS.md` during the build.

## Goal

Build the real matcher (SPEC §10.4 to §10.8): a DTW re-rank of the prefilter's candidates, a calibrated
shape similarity, a logistic fusion of shape and context features trained on history only, warp ratio,
explanations, `make models`, and `kairos-defense match --method dtw`. Then run `make eval` with the DTW
matcher and write the first `reports/baseline.json`.

Phase 4 targets (SPEC §20, `scripts/check_targets.py 4`): Recall@5 at T = 120 s ≥ 0.80, DTW lift ≥ +0.10,
copycat-first ≤ 5%, the §10.9 latencies (report only, D-060), and the demo rows
`live_first_contact_local`, `live_orbit_established_s` and `live_top3_incidents`, all `pass`. At T+90 the
live top 3 must be P1-DELTA-260419, P1-ALPHA-260303 and P1-ALPHA-260502 (any order), each with a score
and reasons.

## Inputs read

- `CLAUDE.md`, `docs/PROGRESS.md` (phases 0 to 3 and their backfills), `docs/phases/TEMPLATES.md`,
  `docs/phases/phase-03/REPORT.md`, `docs/phases/gates.json`, `scripts/check_targets.py`.
- SPEC §1.2 (T+90 beat: "flown ~18% slower"), §6.5, §7.2, §7.5, §8.10, §9 (§9.3's normalization), §10
  (all), §19 (all), §20 phase 4.
- `docs/DECISIONS.md`, in particular D-003, D-013, D-020, D-046, D-047, D-048, D-049, D-050, D-051,
  D-053 to D-060, D-062 to D-064 and D-067. Next free number: **D-068**.
- Code: `match/` (query, prefilter, baseline, types), `features/windows.py`, `features/channels.py`,
  `features/signatures.py`, `store/duck.py`, `store/lance.py`, `ports.py`, `config/scoring.py`,
  `eval/` (harness, metrics, demo, report, truth), `cli.py`, and the tests that touch them
  (`test_cli.py`, `test_eval_harness.py`, `test_no_lookahead.py`, `test_windows.py`,
  `test_truth_isolation.py`, `tests/slow/test_full_index.py`).

### Facts checked during planning (read-only; nothing in the repo or `data/` was written)

1. **The C path works on the laptop (D-062 resolved by D-064).** `dtw.try_import_c()` is True.
   `dtw_ndim.distance(L, S, window=60, use_c=True)` on 120×5 against 240×5 takes 0.064 ms.
   `dtw_ndim.warping_paths(..., use_c=True)` (or `warping_paths_fast`) plus `dtw.best_path` takes
   0.4 ms. Without `use_c` it takes 36 ms, so every call must pass `use_c=True`.
2. **LanceDB returns many candidate tracks cheaply.** For the live query at T+90 (W = 60, filtered),
   `k` = 200 / 2,000 / 5,000 / 10,000 windows gives 185 / 1,102 / 1,545 / 1,728 distinct tracks in about
   14 / 18 / 21 / 25 ms. Loading all 800,148 `track_features` rows takes 46 ms (58 MB). 50 separate
   `features()` calls take 76 ms.
3. **D-058's cause is the per-window z-normalization, and option (a) fixes most of it.** A brute-force
   rebuild of the 60 s and 120 s windows in memory with fixed per-channel scales (speed 5 m/s, turn
   10 °/s, distance 200 m, altitude 30 m, climb 1 m/s; times the §6.5 weights; then PAA and L2) instead
   of per-window z-normalization gives:

   | Same-actor track among the candidates (23 prober queries) | per-window z (phase 3) | fixed scales |
   |---|---:|---:|
   | top 50 at T = 90 s | 0.70 | 0.91 |
   | top 50 at T = 120 s | 0.74 | 0.83 |
   | top 200 at T = 120 s | 0.78 | 0.96 |
   | live T+90: ranks of DELTA, ALPHA-0303, ALPHA-0502 among 1,882 tracks | 855 / 953 / 564 | 318 / 23 / 436 |

4. **The full pipeline, prototyped, reaches the targets with a wide candidate list (D-058 (a) + (b)).**
   This was a scratch prototype: §10.4 anchored segments with per-series z-normalized banded DTW, the
   seven §10.5 features, τ = median same-actor `d_norm`, and `LogisticRegression(class_weight="balanced")`
   trained on months 1 to 12 (54 prober and copycat queries at T = 60, 90, 120). It was evaluated on the
   23 month 13 to 18 prober queries.

   | Prefilter vectors, candidates | Recall@5 T=120 | top 3 T=90 | copycat-first T=120 | Euclidean Recall@5 T=120 | live T+90 ranks DELTA / ALPHA-0303 / ALPHA-0502 |
   |---|---:|---:|---:|---:|---|
   | fixed, 50 | 0.83 | 0.91 | 0.13 | 0.43 | – / 1 / – |
   | fixed, 200 | 0.96 | 0.96 | 0.00 | 0.43 | – / 1 / – |
   | **fixed, 500** | **1.00** | **0.96** | **0.00** | **0.43** | **1 / 2 / 4** (CHARLIE 3rd) |
   | per-window z, 500 | 0.91 | 0.91 | 0.09 | 0.48 | – / – / – |
   | dataset σ (global z), 500 | 1.00 | 1.00 | 0.00 | 0.61 | 2 / 3 / 5 (BRAVO-251114 1st, CHARLIE 4th) |
   | fixed, 500, DTW on fixed scales too | 1.00 | 0.96 | 0.00 | 0.43 | 4 / 1 / 20 |
   | fixed, 500, extra `target_match` feature | 1.00 | 0.96 | 0.00 | 0.43 | 5 / 17 / 20 |

   With the best setting the live top 3 misses by one place: CHARLIE-260710, the planted "weaker match
   on purpose", is third, and ALPHA-0502 is fourth. Both are true P1 flights. **Disclosure:** these
   planning numbers looked at the month 13 to 18 queries and the demo. The build chooses its settings
   by the training-split rule in "Assumptions" A3, not by these tables.
5. **§10.4's warp ratio cannot work as literally written.** Aligning a W-row live matrix end to end
   with a 2W-row anchored segment forces the path slope to about 1.7 whatever the true warp: a synthetic
   flight warped by 1.0 / 1.22 / 0.95 / 0.8 gives slopes 1.67 / 1.74 / 1.65 / 1.63. Normalizing each
   series over itself also biases it, even with relaxed ends: 1.38 / 1.58 / 1.31 / 1.06. With **both**
   series normalized by the live window's μ and σ **and** psi relaxation on the segment's two ends
   (`psi = (0, 0, m − n, m − n)`, best end column of the last row, `dtw.best_path(paths, row=n, col=j)`),
   the slopes are 1.002 / 1.221 / 0.95 / 0.80 / 1.40 for W = 60 and W = 120. A warp of 1.22 then gives
   "18% slower", which is the §1.2 beat.

## Assumptions and decisions

Each one becomes a `docs/DECISIONS.md` entry during the build (numbers are provisional).

- **A1 · D-068 · D-058 resolved: fixed-unit window vectors plus a wide candidate list.**
  - `features.channel_scales: [5.0, 10.0, 200.0, 30.0, 1.0]` (m/s, °/s, m, m, m/s) and
    `windows.normalize: fixed` are new keys in `config/scoring.yaml`. `fixed` means
    `raw / scale × weight`, with no centering, the D-051 NaN interpolation, then PAA and L2. `window`
    keeps phase 3's per-window z-normalization (§9.3 as written) for comparison and for the phase 3
    unit tests.
  - `prefilter.k_windows: 10000` and `prefilter.candidate_tracks: 500`.
  - This deviates from §9.3 (normalization "over the series being compared") for the prefilter vectors
    only; DTW keeps §9.3 (A2). It also deviates from §6.5's 200 / 50.
  - Why: fact 3 and fact 4. Per-window z-normalization erases the orbit radius, the speeds and the
    altitude that make P1 distinctive. The DTW plus fusion cost of 500 candidates is about 30 ms.
  - `make index` must be rerun. A self-check refuses a stale index (A8).
- **A2 · D-069 · DTW details (§10.4).**
  - Shape distance as written: anchored segment `[o − 0.5W, o + 1.5W]` clipped to the track; each series
    z-normalized over itself and weighted (§9.3); NaN interpolated, an all-NaN channel set to 0;
    `dtw_ndim.distance(L, S, window=int(0.25 × max(n, m)), use_c=True)`;
    `d_norm = d / sqrt(n)`; `shape_sim = exp(−d_norm / τ)`.
  - The C path is mandatory (D-013, D-020): `require_c()` raises `DtwUnavailable` when
    `dtw.try_import_c()` is False. Every call passes `use_c=True`.
  - Warp ratio (fact 5): a second alignment with L and S both scaled by L's μ and σ (weighted), psi
    relaxation `(0, 0, m − n, m − n)` when `m > n` (none otherwise), and the same band. Take the best
    end column of the last row, then `dtw.best_path`. `k` is the least-squares slope of segment index
    against live index. It is computed for the top `EXPLAIN_TOP = 20` fused matches only (the ones shown
    and explained); the others keep `warp_ratio = NaN` (no invented numbers, D-054).
  - Text (§10.4 step 5): `k > 1.1` → "flown X% slower" with X = round((1 − 1/k) × 100); `k < 0.9` →
    "flown X% faster" with X = round((1/k − 1) × 100). §10.4 gives only the slower formula; the faster one
    is its mirror.
  - Step 6: `explain_alignment()` wraps `subsequence_alignment` on the `dist_target_m` channel and is
    tested now. The phase 8 Match Explainer will call it.
  - The optional LB_Keogh pruning is not built: 500 DTW calls take about 30 ms, and `lb_keogh` needs
    equal lengths while L and S differ.
- **A3 · D-070 · Settings are chosen on the training split only.** If the build needs to choose among
  pre-registered alternatives, it uses months 1 to 12 alone, with nights 2026-01-01 to 2026-02-28
  held out from the fit. The criterion is the Recall@5 at T = 120 s of the fused ranker on those
  held-out training queries, ties broken by candidate recall. The alternatives are:
  - prefilter scaling: fixed units, dataset σ, or per-window z;
  - `candidate_tracks`: 200, 500 or 1,000;
  - training T grid: {60, 90, 120} or {45, 60, 90, 120, 180}.

  The defaults are fixed units, 500 and {45, 60, 90, 120, 180}. Months 13 to 18 and the demo are never
  a selection criterion. No setting is special-cased for an incident, actor or base.
- **A4 · D-071 · Partial live signature (§10.5 "live signatures are partial").** The query signature is
  `features.signatures.signature()` run on the query's own features, its first point and its last
  point at or before T, plus a sensor context bounded to T. RF and Remote ID detections, the track's
  own points and the other tracks' spans (the concurrency test, D-048) all count only up to T. Unknown
  fields give 0.5 in fusion, as §10.5 says. Candidate signatures come from `TrackStore.tracks_before`
  (§11.3), one call per query.
- **A5 · D-072 · Two read-only `TrackStore` port methods.** `sensor_context_until(track_id, until) ->
  dict` (`rf_family`, `rid_serials`, `rid_operator_xy`) and `features_many(track_ids) -> DataFrame`.
  They are implemented in `DuckTrackStore` by giving the existing `rf_association` and
  `rid_association` SQL an optional `until` bound. It defaults to None, so phase 3's calls and tests
  are unchanged. This is a deviation from §4.1. Without them, `match/` would hold SQL text, or
  pay one round trip per candidate (fact 2). The KDB-X swap (§22) needs these two in its adapter. The
  matcher keeps a per-process cache of candidate features: history features never change between
  index builds.
- **A6 · D-073 · Fusion training (§10.6).**
  - `kairos_defense.eval.training` builds the pairs, and is the only place that reads truth for them.
  - Queries: history prober, copycat and swarm-drone tracks on nights before 2026-03-01 (months 1 to 12),
    at T ∈ {45, 60, 90, 120, 180}. The candidates are exactly what the matcher's prefilter returns:
    same code, `start < q.start`, own incident excluded.
  - Label: same `actor_id` (a swarm drone's actor is its team). Hobbyists and copycats are the
    negatives. Queries with no positive pair still add negatives.
  - τ = median `d_norm` of the positive pairs. `shape_sim` is then computed with that τ.
  - `LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000, C=1.0)`, feature order
    from `scoring.fusion.features`, on rows sorted by (query, T, candidate) so the fit is deterministic.
  - Validation: the same build on months 13 to 18, recording pair counts, ROC AUC, log loss and the
    validation Recall@5 at T = 120 s. These are reported only and never used for selection (A3).
  - Artifacts:
    - `models/dtw_calibration.json`: `version`, `created_at`, `tau`, `n_pairs`, `n_positive`,
      same-actor and other `d_norm` p10 / p50 / p90, `band_fraction`, `anchor`, `training_hash`.
    - `models/fusion_v1.json`: `version` `fusion-v1`, `created_at`, `features`, `coefficients`,
      `intercept`, `tau`, `training_hash`, `train_split`, `validation`.
    - `training_hash` is SHA-256 over the sorted pair keys, X and y. It is deterministic;
      `created_at` is the only field that changes.
  - A numeric `scoring.dtw.tau` overrides the calibration. `auto` reads `dtw_calibration.json`.
  - The split dates are parameters (`TrainSplit`) with the §10.6 defaults, so unit tests can train
    on the P1 nights.
- **A7 · D-074 · Explanations (§10.7).**
  - Contribution = `coef_i × x_i`. Reasons are the features whose §10.7 condition holds, ordered by
    contribution, at most three.
  - The warp reason ("Same shape, flown 18% slower") ranks with `shape_sim`'s contribution and needs a
    warp ratio outside 0.9 to 1.1.
  - Values in the text are the past flight's signature values: family, bearing rounded to 5°, radius
    rounded to 10 m.
- **A8 · D-075 · Stale-index and missing-model guards.** `models`, `eval --method dtw` and `match
  --method dtw` rebuild one stored window's vector from `features_many` with the current config and
  search for it with `window_id = '<id>'`, k = 1. A `_distance` above 1e-6 means the index was built
  with another vector recipe, so they stop with "index is stale: run make index". Without
  `models/fusion_v1.json`, `eval` and `match --method dtw` stop with "no fusion model: run make models".
  All of these exit 1.
- **A9 · D-076 · Evaluation (§19).**
  - `eval` and `match` default to `--method dtw`. `--method euclidean` still runs (§10.2).
  - **DTW lift is measured in the same run, on the same index and queries:** the Euclidean ranks are
    the prefilter order of the same candidates, which is the §10.2 baseline. New `Outcome` fields:
    `baseline_rank`, `baseline_copycat_rank` and `dtw_ms`.
  - New metric keys: `recall_at_5_t120_baseline`, `dtw_lift`, `latency_dtw_p50_ms`,
    `latency_dtw_p95_ms` (all candidates, 500, not §10.9's 50: the harder case) and
    `candidate_tracks`. The REPORT also states the lift over phase 3's frozen 0.435.
  - `dtw_lift` and `latency_dtw_p95_ms` join `GATED` and leave `PENDING`.
  - The demo row `live_top3_incidents` becomes an assertion: `pass` when all three expected incidents
    are in the top 3 and each has a score and at least one reason, else `fail`.
  - D-056's question: the §19.4 5% rule stays as written, with no absolute floor. `gates.json`
    tolerates a non-zero `make eval`, and `check_targets.py` judges the targets.
  - The JSON's `method` is `dtw`. Its title reads "DTW + fusion".
- **A10 · D-077 · Font pinned in `eval/report.py`** (the D-065 and D-067 follow-up, since this phase
  edits the file): `plt.rc_context({"font.family": "DejaVu Sans"})` around the figure, so the figure is
  the same on every machine. `sim/figures.py` is not touched (phase 4 does not change `sim/`).
- **A11 · Module size.** If `eval/report.py` (286 lines) or `cli.py` (307 lines) would go past about 400
  lines, the Markdown writer moves to `eval/report_md.py` and the match and models table printers move to
  `cli_tables.py`.

## Work breakdown

Each step ends with `make check` green.

1. **Config and vectors (D-068).**
   - `src/kairos_defense/config/scoring.py`: `FeaturesConfig.channel_scales: list[Pos]`, one per
     channel (validated); `WindowsConfig.normalize: Literal["window", "fixed"]`.
   - `config/scoring.yaml`: `channel_scales`, `normalize: fixed`, `k_windows: 10000`,
     `candidate_tracks: 500`, with comments citing D-068.
   - `src/kairos_defense/features/windows.py`: `window_vectors(..., scales=None)` (None means per-window
     z, phase 3 behavior); `iter_windows` and `query_vector` pass the scales when `normalize == "fixed"`.
     The function is still shared by the index and the query (D-051).
   - Tests: `test_config.py` invalid variants, and the new `test_windows.py` tests.
   - Then run `make index`. The window counts must equal phase 3's (57,462 / 51,297 / 27,507).
2. **Ports and adapter (D-071, D-072).**
   - `src/kairos_defense/ports.py`: `TrackStore.sensor_context_until(track_id, until)` and
     `features_many(track_ids)`.
   - `src/kairos_defense/store/duck.py`: `rf_association` and `rid_association` take an optional
     `until`. It bounds the points and the detections to `ts ≤ until`, and the concurrency spans to
     tracks whose first point is at or before `until`, with their points clipped to `until`. Add
     `sensor_context_until(track_id, until)` (one track) and `features_many`. The bulk
     `sensor_context(track_ids=None)`, used by `index` and by phase 3's tests, keeps its name and
     behavior (adapter-only, D-053).
   - Tests: `test_duck_store.py` additions.
3. **DTW re-rank (D-069).** `src/kairos_defense/match/dtw_rerank.py` (about 200 lines):
   - `require_c()` and `DtwUnavailable`;
   - `anchor_bounds(offset_s, W, n_rows, before, after) -> (lo, hi)`;
   - `prepare(raw, weights) -> (n, 5)`: §9.3 normalization plus NaN fill;
   - `shape_distance(L_raw, S_raw, scoring) -> d_norm`;
   - `shape_sim(d_norm, tau)`;
   - `warp_ratio(L_raw, S_raw, scoring) -> float`;
   - `warp_text(k) -> str | None`;
   - `explain_alignment(live_dist, full_dist) -> (start, end, value)`.

   These are pure functions over numpy arrays, and the only `dtaidistance` import in the package.
   Tests: `test_dtw_rerank.py`.
4. **Partial signature and fusion features (D-071).**
   - `src/kairos_defense/match/live_signature.py`: `query_signature(store, q) -> dict`, from points up
     to T and `store.sensor_context_until(track_id, until=q.start_ts + T)`.
   - `src/kairos_defense/match/fusion.py`:
     - `fusion_features(qsig, csig, shape_sim) -> dict[str, float]` (§10.5 formulas, 0.5 for unknowns);
     - `feature_matrix(rows, order) -> (n, 7) float64`;
     - frozen `FusionModel` with `predict(X) -> (n,)` (sigmoid of `X @ coef + b`), `contributions(x)`,
       `to_json()`, `load(path, expected_features)` and `save(path)`;
     - frozen `DtwCalibration` with `load` and `save`.
   - Tests: `test_live_signature.py`, `test_fusion.py`.
5. **Explanations (D-074).** `src/kairos_defense/match/explain.py`:
   `reasons(features, model, warp_ratio, csig) -> list[str]` (§10.7 table, top three by contribution).
   Tests: `test_explain.py`.
6. **Matcher (§10.1, §10.8).** `src/kairos_defense/match/matcher.py` (about 220 lines):
   - `DtwMatcher(store, vstore, scoring, models_dir)` loads the model and calibration and checks
     `require_c`. It keeps the feature cache and caches the stale-index check per process.
   - `match(q) -> MatchResult`, with `matches: list[Match]` (fused score order),
     `baseline: list[Match]` (prefilter order, for the in-run lift) and
     `timings: dict[str, float]` (`prefilter_ms`, `signature_ms`, `dtw_ms`, `fusion_ms`,
     `explain_ms`, `total_ms`).
   - `Match.features` holds the seven fusion features plus `d_norm`, `euclidean_d2` and `window_s`.
     `model_version` comes from the model file.
   - `check_index(store, vstore, scoring)` implements A8.
   - Update `match/__init__.py` and `baseline.py` (the shared `rank_candidates` stays).
   - Tests: `test_matcher.py`, plus the DTW test in `test_no_lookahead.py`.
7. **Training (D-073).** `src/kairos_defense/eval/training.py` (about 250 lines):
   - `TrainSplit`;
   - `training_queries(store, truth, split)`;
   - `build_pairs(cfg, store, vstore, truth, queries, t_grid) -> Pairs` (keys, X without
     `shape_sim`, `d_norm`, y);
   - `calibrate_tau(pairs)`;
   - `fit(pairs, tau, order)`;
   - `validate(model, pairs)`;
   - `train_models(cfg, store, vstore, truth, split=DEFAULT) -> TrainSummary` (writes both artifacts).

   It reuses `DtwMatcher`'s candidate and feature code through a `features_only=True` path, so training
   and serving cannot drift. Tests: `test_training.py`.
8. **CLI.** `src/kairos_defense/cli.py`:
   - `models` leaves `STUBS`. It is real and prints queries, pairs, positives, τ, coefficients,
     validation AUC and Recall@5, the artifact paths and the elapsed time.
   - `match --method dtw|euclidean`, default `dtw`, shows a table: #, track, base, start (local), score,
     shape, warp, reasons. A line shows the model version, the candidate count and the stage timings.
   - `eval --method dtw|euclidean`, default `dtw`, adds rows for the DTW lift and the DTW latency.
   - Tests: `test_cli.py` changes.
9. **Eval (D-076, D-077).**
   - `eval/harness.py`: `dtw_ranker` in `METHODS`, one `DtwMatcher` per `evaluate`, the new `Outcome`
     fields filled.
   - `eval/metrics.py`: `dtw_lift`.
   - `eval/report.py`: the new keys, `GATED` and `PENDING`, a DTW latency row, a DTW-lift row, the
     title, the method in the figure title, the pinned font, and the split into `report_md.py` if needed.
   - `eval/demo.py`: `live_top3_incidents` becomes an assertion, with each expected match's score,
     rank and first reason in `observed`.
   - Tests: `test_eval_metrics.py`, `test_eval_harness.py`.
10. **Slow tests.** `tests/slow/test_full_models.py`: full data, train twice, the copycat check, and
    a DTW eval. `make test-all`.
11. **Exit check, gate dry run and documentation** (sections below). Then a single commit,
    `phase 4: DTW matcher and fusion model`.

If the first `make eval` misses a target, the build may try the A3 alternatives, judged on the training
split. It records each attempt and its numbers in REPORT.md, and stops tuning after that. The gate's
soft-target rule then applies (D-063).

## Tests

Fast tests (`tests/unit`) unless marked slow. The passing fast count at the start of the run is 367.
Two stub-era assertions are replaced (marked "replaces"), never deleted without a stronger successor.

`test_windows.py`

- `test_fixed_scaling_keeps_levels`: two windows with the same shape but distances of 180 m and 1,800
  m give the same vector under `window` and different vectors under `fixed`.
- `test_query_vector_equals_indexed_window_fixed`: the query vector equals the indexed window in
  `fixed` mode, for W = 120 and for T = 45.
- Every existing test still passes (they call `window_vector` without `scales`, which means phase 3
  mode).

`test_config.py`

- Invalid variants for: `channel_scales` of the wrong length, a scale ≤ 0, and an unknown `normalize`.

`test_duck_store.py`

- `test_sensor_context_until_is_bounded`: RF detections and Remote ID broadcasts after `until` do not
  change `rf_family`, serials or the operator. Before `until` they do.
- `test_features_many_matches_features`: the same rows as `features()` per track.

`test_dtw_rerank.py`

- `test_require_c_fails_loudly`: with `try_import_c` monkeypatched to False, `DtwUnavailable` is
  raised.
- `test_self_distance_is_zero`: a series against itself gives d ≈ 0 and shape_sim ≈ 1, and the C
  result equals pure Python on a small case.
- `test_band_window`: the window is `int(0.25 × max(n, m))`.
- `test_anchor_bounds_clip_to_the_track`: known answers at the start, middle and end of a track.
- `test_nan_and_missing_channel`: NaN is interpolated and an all-NaN channel gives zeros.
- `test_time_warped_copy_scores_high_and_reports_its_warp`, for warp in {0.8, 0.95, 1.0, 1.22, 1.4},
  W in {60, 120}: on a synthetic five-channel flight, the warped copy's shape_sim (with the fixture τ)
  is above that of an unrelated flight, and `|warp_ratio − warp| ≤ 0.03`.
- `test_warp_text`: 1.22 gives "flown 18% slower", 0.8 gives "flown 25% faster", 1.05 gives None.
- `test_short_segment_has_no_relaxation`: with `m ≤ n` the result is finite and no psi is used.
- `test_explain_alignment_finds_the_window`: the segment is within ±3 s of the true location.

`test_fusion.py`

- `test_rf_match_rules`: same family 1.0; same band (a family's first digit, D-036) or either
  `unknown` 0.5; otherwise 0.0. FAM-07 against FAM-30 (P1 against C1) gives 0.0.
- `test_bearing_and_tod_similarity`: Δ 0° gives 1, Δ 180° gives 0, Δ 90° gives 0.5. tod 1,430 against
  1,450 (wrap) matches a 20 min difference.
- `test_launch_radius_alt_and_unknowns`: 0 m gives 1, 1,000 m gives e⁻¹, a missing launch gives 0.5, a
  missing loiter gives 0.5, altitude known answers.
- `test_feature_order_follows_config`.
- `test_model_round_trip`: save, then load, gives the same coefficients. `predict` equals sklearn's
  `predict_proba[:, 1]` to 1e-12. The JSON has every §10.6 key.
- `test_model_feature_order_mismatch_is_refused`.
- `test_copycat_fuses_lower_than_true_p1`: with the fixture model, a C1-like candidate (same shape,
  FAM-30, another launch area, another time of night) scores below a true P1 candidate.

`test_explain.py`

- `test_top_three_reasons_by_contribution`.
- `test_reasons_need_their_condition`: a feature below its threshold gives no reason.
- `test_warp_reason_text`.
- `test_reason_values_come_from_the_past_flight`: "Same RF family (FAM-07)", "Same approach bearing
  (315°)", "Same orbit radius (~180 m)".

`test_live_signature.py` (p1_index)

- `test_full_length_query_signature_matches_the_index`: at T = the track's duration + 30 s (so the
  ±30 s RF window agrees with the index's), the fields equal the stored signature. Bearing and radius may differ by at most 1° and 1 m.
- `test_query_signature_ignores_everything_after_T`: tampering with points, RF and Remote ID after T
  leaves the signature unchanged.
- `test_live_p1_signature_at_t90`: FAM-07, approach 315° ± 15°, fuel-farm target.

`test_matcher.py` (p1_index plus a `toy_models` fixture written to a temporary models folder)

- `test_dtw_matches_fields_and_order`: scores are in [0, 1] and non-increasing. Every `Match` field is
  filled, `features` keys equal the config order plus extras, and `model_version` is `fusion-v1`. The
  top 20 have a finite `warp_ratio`.
- `test_dtw_matcher_is_deterministic`: two runs give identical matches.
- `test_timings_are_reported`.
- `test_stale_index_is_refused`: a window vector perturbed in a copy of the LanceDB table makes
  `check_index` raise.
- `test_missing_models_are_refused`.
- `test_live_top3_are_p1_on_the_p1_nights`: at T+90 the top 3 are all P1 incidents. This is a fixture
  check; the exact three are the eval and gate's job.

`test_no_lookahead.py`

- `test_dtw_results_never_start_after_the_query`: for every track at T = 45, 90 and 180 with
  `DtwMatcher`, every match started before the query, the own incident is excluded, and later P1
  flights are never returned.

`test_training.py` (in `tests/unit`; it may read truth, because it tests `kairos_defense.eval`)

- `test_pairs_respect_time_and_split`: with a split on the P1 nights, every query night is in the train
  split, every pair has `c.start < q.start`, labels equal truth actor equality, and there are no live
  tracks.
- `test_tau_is_the_median_same_actor_d_norm`: a known answer.
- `test_training_is_deterministic`: same hash, same coefficients.
- `test_artifacts_written_and_loadable`: both JSON files, the §10.6 keys, and `FusionModel.load`
  succeeds.

`test_eval_metrics.py`

- `test_dtw_lift_known_answer`.

`test_eval_harness.py`

- `test_dtw_summary_keys`: `method` is `dtw`. `dtw_lift`, `recall_at_5_t120_baseline`,
  `latency_dtw_p50_ms` and `latency_dtw_p95_ms` are numbers.
- `test_demo_top3_is_an_assertion`: the status is `pass` or `fail`, never `info`.
- `test_cli_eval` (replaces the stub assertion `eval --method dtw` → "phase 4"):
  - without models, `eval --method dtw` exits 1 and names `make models`;
  - with `toy_models` it exits 0;
  - `eval --method euclidean --baseline`, then `eval --method euclidean`, still exit 0.

`test_cli.py`

- `BUILT` gains `models`. `test_stub_names_its_phase` loses the `models` case.
- `test_match_dtw_needs_models` replaces `test_match_dtw_is_phase_4`.
- New:
  - `test_match_dtw_runs_on_the_p1_nights`: the reasons column, the model version, and P1 rows;
  - `test_models_needs_index`;
  - `test_models_cli_trains_on_the_p1_nights`: the split is monkeypatched and both files are
    written.

Slow (`tests/slow/test_full_models.py`, `@pytest.mark.slow`)

- `test_full_models_are_deterministic`: two `train_models` runs give the same `training_hash`,
  coefficients and τ.
- `test_full_copycat_fuses_lower_than_p1`: for the live query at T = 120 s, every C1 track that
  appears scores below the lowest of DELTA, ALPHA-0303 and ALPHA-0502.
- `test_full_eval_dtw`: a DTW eval runs on full data. Every §19.3 phase 4 key is a number and every
  demo row has a status. This asserts structure, not the targets, which are the gate's job.

The existing `test_full_index.py` still runs (with fixed vectors) and must still pass.

Expected fast count: 367 − 2 (replaced) + 2 (replacements) + about 50 new, so about 417.

## Exit-check mapping

Run on the dev laptop from the build's working tree, after `make index`, which the new vectors
require. Each command is timed with `/usr/bin/time -p` or the shell's `time`, and its output trimmed
into `EXIT_CHECK.md`. The SPEC §20 exit check is run exactly as written. If `make eval` exits 1 (a
demo assertion or a regression), the `&&` chain stops, so `match` is then run on its own and both
outcomes are recorded.

```bash
make index
make models && make eval && uv run kairos-defense match --method dtw --incident DEMO-BRAVO-0828 --at 90
uv run kairos-defense eval --baseline
python3 scripts/check_targets.py 4; echo "check_targets exit $?"
make check && make test-all
```

| Criterion (SPEC §20 phase 4) | Command | Evidence it will produce |
|---|---|---|
| Index rebuilt with fixed-unit vectors | `make index` | Window counts 57,462 / 51,297 / 27,507 (unchanged), 1,898 history tracks, elapsed |
| `make models` trains and calibrates | `make models` | Queries, pairs and positives, τ, coefficients, validation AUC and Recall@5, `models/fusion_v1.json` and `models/dtw_calibration.json` written, elapsed |
| Recall@5 ≥ 0.80 | `make eval` | `metrics.recall_at_5_t120` in `reports/eval_<date>.json` and the eval table |
| DTW lift ≥ +0.10 | `make eval` | `metrics.dtw_lift` = DTW Recall@5 − Euclidean Recall@5 on the same run (`recall_at_5_t120_baseline`) |
| Copycat-first ≤ 5% | `make eval` | `metrics.copycat_first_t120` |
| Latency within §10.9 (report only, D-060) | `make eval` | `latency_prefilter_p95_ms`, `latency_dtw_p95_ms` (500 candidates), `latency_end_to_end_p95_ms` |
| Demo rows | `make eval` | `live_first_contact_local`, `live_orbit_established_s`, `live_top3_incidents`, each pass or fail with its observation |
| Live top 3 with reasons | `match --method dtw --incident DEMO-BRAVO-0828 --at 90` | Table rows 1 to 3 with incident, score, shape, warp and reasons. ALPHA-0303 should read "flown 18% slower" |
| Baseline written | `eval --baseline` | `reports/baseline.json` (method `dtw`) |
| Targets judged | `check_targets.py 4` | PASS, WARN or GAP lines and the exit code (0, or 1 for soft gaps only) |
| Quality floor | `make check`, `make test-all` | Ruff clean, fast count about 417, slow passed, web check passes |

Gate dry run (the build simulates `docs/phases/gates.json` phase 4 on the committed tree):
`make check`, `make models`, `make eval || echo …`, `uv run kairos-defense match --method dtw
--incident DEMO-BRAVO-0828 --at 90`, then `python3 scripts/check_targets.py 4`. `reports/baseline.json`
and both model files are committed, so the gate finds them. The gate does not run `make index`: it
reuses the build's `data/`. The A8 guard turns a stale index into a clear failure rather than wrong
numbers.

## Documentation to write or update

- `docs/phases/phase-04/EXIT_CHECK.md` and `REPORT.md` (templates). REPORT's Metrics compare phase 3
  (Euclidean, per-window z), the in-run Euclidean on fixed vectors, and DTW plus fusion. It shows
  per-actor Recall@5, the live ranks of all five earlier P1 flights at T+90, and any A3 attempts.
- `src/kairos_defense/match/README.md`: the pipeline, the new modules, the API, the timings, the
  model files, the guards and the gotchas (`use_c=True` everywhere; warp only for the top 20; psi).
- `src/kairos_defense/eval/README.md`: training, `TrainSplit`, the new metric keys, the in-run lift,
  the demo assertion, `baseline.json`, the font pin.
- `src/kairos_defense/features/README.md`: `normalize`, `channel_scales`, and the fact that the index
  must be rebuilt.
- `src/kairos_defense/store/README.md`: the two new port methods and `until`.
- `src/kairos_defense/config/README.md`: the new keys.
- `src/kairos_defense/README.md`: the ports and the CLI (`models`, the method defaults).
- Root `README.md` "Status": phase 4 row, and the "Works today" line gains `make models`, `make eval`
  (DTW) and `match --method dtw`.
- `docs/PROGRESS.md`: a session-log entry and the one-line evidence (the Status cell is left to the
  autopilot).
- `docs/DECISIONS.md`: D-068 to D-077 as above. D-058 and D-062 are each marked resolved, by D-068 and
  D-064, in their new entries.

## Risks and mitigations

1. **The live top 3 may miss by one place.** The prototype has CHARLIE-260710 third and ALPHA-0502
   fourth (fact 4). Both are true P1 flights; CHARLIE is planted as weaker.
   - Mitigation: build the real partial signature (A4); add swarm drones and the wider T grid to
     training (A6); try only the A3 alternatives, judged on the training split.
   - The build must never special-case incidents, bases or the demo, and never edit the demo
     assertion or the query sets.
   - If it still misses, it is a soft GAP (D-063), shown in REPORT.md with the ranks and fused
     contributions of the five P1 flights.
2. **A copycat outranks a true match.** C1 copies P1's shape. The fusion's RF family, launch area and
   time of night must separate them: a fast test with the fixture model and a slow test on full data.
3. **Look-ahead through the partial signature.** RF and Remote ID heard after T, or the concurrency
   test using later tracks, would leak. Mitigation: everything is bounded by `until`, with a tamper
   test, plus the new DTW no-look-ahead test.
4. **Truth leakage into the matcher.** Only `eval/training.py` labels pairs. `match/` receives plain
   arrays and JSON files, and the §7.6 scan (`test_truth_isolation.py`) covers the new modules.
5. **A stale index at gate time** (the gate does not run `make index`). Mitigation: the A8 guard, and
   the build runs `make index` before the exit check.
6. **A dtaidistance API quirk** (silent pure Python, psi and `best_path` semantics). Mitigation: one
   adapter module (`dtw_rerank.py`), `require_c()`, `use_c=True` on every call, and known-answer tests
   for warps 0.8 to 1.4.
7. **Latency.** Bounded sensor-context SQL per query, 500 candidates and the feature cache's cold
   start. All of it is measured per stage and reported only (D-060). Expected end to end is well under
   1.5 s, from facts 1 and 2. Training builds about 200,000 pairs, in about 1 to 3 minutes.
8. **Fixture data cannot train a real model.** The P1 nights have few positives in months 1 to 12.
   Mitigation: `TrainSplit` parameters in tests and a hand-set `toy_models` fixture for matcher tests.
   Real training is covered by the slow tests and the exit check.
9. **The passing test count must not drop.** Two stub assertions are replaced, never deleted, and the
   `models` stub case leaves with the stub. About 50 new tests are added.
10. **Overfitting the time of night.** The prototype's `tod_sim` coefficient is large: probers keep
    schedules, hobbyists do not. That is an honest signal in this synthetic world. It is reported in
    REPORT.md and not suppressed.
11. **Module size and the 5% gate.** Splits as planned in A11. Copycat-first at 0 turns any single copycat
    query into a "regression" under §19.4. Accepted: the gate tolerates `make eval`'s exit code (A9).

## Out of scope

- Swarm matching and `swarm_top1` (phase 9). Time to match ≥ 70% (phase 9's gate; reported now).
- Report recall, clue extraction and the analog forecast (phase 5).
- `match_proposed` ledger events and model-version recording in the ledger (phase 6). The model
  version is already on every `Match`.
- Streaming, `replay --precompute` and the UI Match Explainer (phases 7 and 8);
  `explain_alignment` is built now for phase 8.
- LB_Keogh pruning (A2), and D-046's P6 and C2 target choice (not needed for the targets).
- Pinning the font in `sim/figures.py` (D-065): phase 4 does not change `sim/`.

## Review changes

None yet.
