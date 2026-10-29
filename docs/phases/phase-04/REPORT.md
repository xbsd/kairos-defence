# Phase 4: DTW matcher and fusion model, report

Status: done, with one soft gap (the live top 3 misses by one place; D-063, D-078) · Date:
2026-10-28 · Commits: the single `phase 4: DTW matcher and fusion model` commit

## Summary

Phase 4 built the real matcher:

- The prefilter now uses fixed-unit window vectors and passes 500 candidates (D-068, resolving
  D-058).
- Each candidate gets an anchored, end-relaxed DTW distance (D-069) and six context features
  against the query's partial signature (D-071).
- A logistic fusion model, trained on months 1 to 12 inside `kairos_defense.eval`, ranks them
  (D-073, D-078). The top 20 get three reasons and a pace estimate.
- `make models`, `match --method dtw` and a DTW `make eval` are real.

Against the §19.3 phase 4 targets: Recall@5 **1.000** (≥ 0.80), DTW lift **+0.522** (≥ +0.10),
copycat-first **0%** (≤ 5%). End-to-end p95 is 149 ms against a 1,500 ms budget.

One demo assertion misses by one place. At T+90 the top four are all P1 flights with reasons,
but CHARLIE-260710 (planted as "weaker match on purpose") is third, ahead of ALPHA-260502, by
0.80 in logit, mostly from a 20 m altitude difference. `check_targets.py 4` reports it as the
only GAP.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Fixed-unit vectors | `windows.normalize: fixed` divides each channel by `features.channel_scales` (no centering); `k_windows` 10,000, `candidate_tracks` 500 (D-068) | `features/windows.py`, `config/scoring.py`, `config/scoring.yaml` |
| Bounded sensor context | `until` on the RF and Remote ID association SQL; `TrackStore.features_many` and `sensor_context_until` (D-071, D-072) | `store/duck.py`, `ports.py` |
| DTW re-rank | the only dtaidistance import: `require_c`, anchors, §9.3 prepare, banded end-relaxed `shape_distance`, `shape_sim`, speed-ratio `warp_ratio`, `warp_text`, `explain_alignment` (D-069) | `match/dtw_rerank.py` |
| Partial signature | §9.4 on what was known at T (D-071) | `match/live_signature.py`, `match/query.py` (`site`, `points`, `until`) |
| Fusion | §10.5 features (vectorized), `FusionModel`, `DtwCalibration`, `ModelError` | `match/fusion.py` |
| Explanations | §10.7 reasons by contribution, at most three (D-074) | `match/explain.py` |
| Candidates | prefilter → signature → anchored DTW → context features, shared by serving and training; `check_index` (D-075) | `match/candidates.py` |
| Matcher | `DtwMatcher.match(q) -> MatchResult` (fused, prefilter order, timings); `Match.to_dict` (NaN → null) | `match/matcher.py`, `match/types.py` |
| Training | `TrainSplit`, pairs through the matcher's builder, τ, balanced logistic fit, validation, both artifacts (D-073, D-078) | `eval/training.py` |
| Evaluation | `METHODS` factories (`euclidean`, `dtw`), in-run lift, new `Outcome` fields and keys, top-3 assertion, Markdown split out, pinned font (D-076, D-077) | `eval/harness.py`, `eval/metrics.py`, `eval/report.py`, `eval/report_md.py`, `eval/demo.py` |
| CLI | `models` real; `match` and `eval` default to `dtw`; fix-it errors; tables | `cli.py`, `cli_tables.py` |
| Artifacts | the trained model, its calibration, the first baseline | `models/fusion_v1.json`, `models/dtw_calibration.json`, `reports/baseline.json` |

## Decisions and deviations from SPEC

- [D-068](../../DECISIONS.md), **deviation** from §9.3 (prefilter vectors only) and §6.5 (200 → 10,000
  windows, 50 → 500 tracks). Resolves D-058.
- [D-069](../../DECISIONS.md), **deviation** from §10.4 steps 3 and 5:
  - the anchored segment's two ends are relaxed (psi), because end to end an exact warped copy
    ranked below an unrelated flight;
  - the warp ratio is a speed ratio over the aligned rows, because the path slope was off by 0.49
    on real pairs;
  - the warp alignment uses the full matrix, because of a dtaidistance 2.5.1 C bug.
- [D-070](../../DECISIONS.md): settings are chosen on the training split only.
- [D-071](../../DECISIONS.md): partial live signatures, bounded to T.
- [D-072](../../DECISIONS.md), **deviation** from §4.1: two read-only port methods.
- [D-073](../../DECISIONS.md): fusion training details.
- [D-074](../../DECISIONS.md): explanation rules.
- [D-075](../../DECISIONS.md): stale-index and missing-model guards.
- [D-076](../../DECISIONS.md): evaluation in phase 4. The lift is measured in one run, the DTW
  default, the top-3 assertion, and D-056 settled with no absolute floor.
- [D-077](../../DECISIONS.md): figure font pinned in `eval/report.py`.
- [D-078](../../DECISIONS.md), **deviation** from §10.6: swarm drones are candidates but not
  training queries. Registered before evaluation, and adopted by the pre-registered rule on a tie.

### Plan changes during the build (honest list)

- A2 said "shape distance as written". The build relaxed the segment's ends after the §20 test
  failed for the literal reading (D-069).
- A2's warp alignment ("both series scaled by the live window's μ and σ") passed on synthetic data
  but gave warps of 0.00 to 0.5 on real flights (near-constant channels blow up). It was replaced
  by the speed ratio, chosen among five estimators on the training split.
- `test_time_warped_copy_scores_high_and_reports_its_warp` uses a 5% relative tolerance, not the
  planned ±0.03. The synthetic copy now follows §8.5 physics (rates divided by the warp).
- The planned `warp_text` and the "Same shape" reason are unchanged. Warps outside 0.5 to 2.0
  become NaN.
- Training queries exclude swarm drones (D-078); the plan had included them.
- Reviewer suggestions applied:
  1. `test_cli_eval` runs DTW in its own reports folder, and the Euclidean top-3 row stays `info`.
  2. A3 says the shipped model is refit on all of months 1 to 12 (D-070).
  3. A DECISIONS entry was written before trying the alternative (D-078).
  4. The stale-index probe is deterministic (the earliest track, the first window of each size),
     and the test perturbs every vector.
  5. Warp NaN shows as `-` in the CLI and as null in `Match.to_dict()`.
  6. The `models` CLI gets truth through `eval.truth.track_truth`.
  7. D-071 notes that a candidate still flying contributes its later windows.
  8. Fact 4's disclosure is under Metrics.
  9. The test-count arithmetic is under Tests.
  10. The contribution breakdown is under Metrics.

## Tests

- Fast: **431 passed** (367 at the start of the run), 10 slow deselected (7 before). `make test-all`: **441
  passed** in 3 min 31 s.
- New files:
  - `test_dtw_rerank.py`, 22 tests. C required; self-distance 0 and C equals Python; band;
    anchors; NaN and missing channel; warped copies at 0.8, 0.95, 1.0, 1.22 and 1.4, W = 60 and
    120 (10 cases: shape above an unrelated flight by 1.3×, warp within 5%); the warp text; the
    credible range; no psi for a short segment; banded C with psi equals Python; relaxed ends rank
    the copy first; C paths equal Python without a band; `explain_alignment`.
  - `test_fusion.py`, 8 tests: RF rules, bearing and time-of-night, launch, radius, altitude and
    unknowns, vectorized frame, feature order, model round trip (equals scikit-learn to 1e-12),
    order mismatch and missing or corrupt files refused, a copycat fuses below P1.
  - `test_explain.py`, 4 tests: top three by contribution, conditions, warp text, values from the
    past flight.
  - `test_live_signature.py`, 4 tests: the full-length query signature matches the index (two P1
    flights); tampering after T changes nothing, and sensors are asked only up to T; the live P1
    signature at T+90.
  - `test_matcher.py`, 6 tests: fields and order, determinism, timings, stale index refused
    (another recipe, and every vector perturbed), missing models refused, top 3 P1 on the P1
    nights.
  - `test_training.py`, 4 tests: pairs respect time and the split, the τ known answer,
    determinism, the artifacts.
- Changed files:
  - `test_windows.py`: +4 (fixed scaling keeps levels; query equals index in both modes, 2
    cases; fixed-mode NaN).
  - `test_config.py`: +3 invalid variants.
  - `test_duck_store.py`: +3 (`sensor_context_until` bounded, concurrency up to `until`,
    `features_many`).
  - `test_eval_metrics.py`: +1 (`dtw_lift`).
  - `test_eval_harness.py`: +2 (`test_dtw_summary_keys`, `test_demo_top3_is_an_assertion`).
  - `test_no_lookahead.py`: +1 (the DTW matcher, every track at T = 45, 90 and 180).
  - `test_cli.py`: +4 (`test_match_dtw_runs_on_the_p1_nights`, `test_models_needs_index`,
    `test_models_cli_trains_on_the_p1_nights`, and `test_match_dtw_needs_models`, which replaces
    `test_match_dtw_is_phase_4`).
- Slow, new file `tests/slow/test_full_models.py`, 3 tests in 140 s: full training twice gives the
  same hash, coefficients and τ; at T+120 every C1 track scores below all three expected P1
  flights; a full DTW eval has every key.
- Test-count arithmetic: the `models` case of the parametrized `test_stub_names_its_phase` left
  with the stub (−1). `test_match_dtw_is_phase_4` became `test_match_dtw_needs_models` (0).
  `test_cli_eval` was rewritten in place (0). 65 tests were added (48 in new files, 17 in
  changed ones): 367 − 1 + 65 = 431.
- Adapted, not weakened:
  - `test_outputs_and_gate` skips `None` latencies when doubling (the Euclidean run has no DTW
    latency).
  - `test_match_runs_on_the_p1_nights` passes `--method euclidean`, since `dtw` is now the
    default.
  - `test_cli_eval` checks the Euclidean baseline and no regression as before, plus the DTW
    paths. `tmp_config` also gives tests their own `models` folder.
- No test was skipped, marked xfail or deleted.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| `make models` | pass | 62 queries, 123,404 pairs, τ 1.6453, validation AUC 0.998, 44.4 s |
| Recall@5 ≥ 0.80 | pass | 1.000 |
| DTW lift ≥ +0.10 | pass | +0.522 (1.000 against 0.478 for the same candidates in prefilter order) |
| Copycat-first ≤ 5% | pass | 0% |
| Latency (§10.9, reported) | pass | prefilter p95 30 ms, DTW (500 candidates) p95 81 ms, end to end p95 149 ms |
| Top 3 at T+90 are DELTA, ALPHA-0303, ALPHA-0502, with reasons | **fail (soft gap)** | DELTA #1, ALPHA-0303 #2, CHARLIE #3, ALPHA-0502 #4; each with three reasons |
| `eval --baseline` | pass | `reports/baseline.json`, method `dtw`, exit 0 |
| `check_targets.py 4` | 8 PASS, 1 GAP | exit 1, soft gaps only |
| `make check`, `make test-all` | pass | 431 fast; 441 in all |

The SPEC chain `make models && make eval && match …` stops at `make eval` (exit 1 from the demo
assertion), so `match` was run on its own (exit 0). Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Probers unless noted (23 prober queries, 10 copycat queries, none unanswerable).

| Metric | Phase 3 (Euclidean, per-window z, 50) | Phase 4, same run, prefilter order (fixed units, 500) | Phase 4 DTW + fusion | Target |
|---|---:|---:|---:|---|
| Recall@5 at T = 120 s | 0.435 | 0.478 | **1.000** | ≥ 0.80 |
| DTW lift | – | – | **+0.522** (+0.565 over phase 3's frozen 0.435) | ≥ +0.10 |
| MRR at T = 120 s | 0.302 | – | 1.000 | report |
| Time to match (top 3 by T = 90 s) | 26% | – | 96% | ≥ 70% (phase 9) |
| Copycat-first at T = 120 s | 57% | – | **0%** | ≤ 5% |
| Recall@5 at T = 120 s, copycats | 0.500 | – | 1.000 | report |
| Prefilter p50 / p95 | 13 / 15 ms (laptop) | – | 27 / 30 ms | p95 ≤ 50 ms |
| DTW p50 / p95 (500 candidates) | – | – | 55 / 81 ms | p95 ≤ 800 ms (for 50) |
| End to end p50 / p95 | 17 / 19 ms | – | 118 / 149 ms | p95 ≤ 1,500 ms |

Recall@5 by T (probers), DTW + fusion against the same run's prefilter order: T=45 0.826 (0.478),
60 0.913 (0.435), 90 0.957 (0.478), 120 1.000 (0.478), 180 1.000 (0.478). Copycat queries: 45
0.8, then 1.0 from T=60. Per actor at T = 120 s: every actor (C1, C2, P1 to P6) has Recall@5 1.0
and a median best rank of 1.

Training (`make models`): 62 queries (months 1 to 12), 123,404 pairs, 1,128 same actor. τ 1.6453;
`d_norm` same-actor p10 / p50 / p90 1.438 / 1.645 / 1.881, others 1.482 / 1.689 / 1.986.
Coefficients: `shape_sim` +4.22, `rf_match` +18.66, `bearing_sim` +2.65, `tod_sim` +26.22,
`launch_sim` +9.79, `radius_sim` +0.65, `alt_sim` +5.27, intercept −51.96. Validation (months 13
to 18, 33 queries): AUC 0.998, log loss 0.056, Recall@5 1.000.

**Live query, fused rank (prefilter rank) of the five earlier P1 flights:**

| T | DELTA-260419 | ALPHA-260303 | ALPHA-260502 | CHARLIE-260710 | BRAVO-251114 |
|---|---|---|---|---|---|
| +45 | 2 (29) | 3 (114) | 5 (106) | 4 (69) | 1 (9) |
| +60 | 2 (64) | 3 (84) | 5 (233) | 4 (67) | 1 (150) |
| +90 | **1** (122) | **2** (7) | **4** (314) | 3 (5) | – (not a candidate) |
| +120 | 1 (94) | 2 (12) | 4 (314) | 3 (16) | – |

**Why CHARLIE outranks ALPHA-0502 at T+90** (value and contribution `coef × x` per feature):

| Rank | Incident | Score | shape_sim | rf_match | bearing_sim | tod_sim | launch_sim | radius_sim | alt_sim | Logit |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | P1-DELTA-260419 | 0.9986 | 0.359 (+1.51) | 1 (+18.66) | 0.999 (+2.64) | 1.000 (+26.21) | 0.5 (+4.89) | 0.279 (+0.18) | 0.833 (+4.39) | +6.54 |
| 2 | P1-ALPHA-260303 | 0.9948 | 0.363 (+1.53) | 1 (+18.66) | 1.000 (+2.65) | 0.999 (+26.20) | 0.5 (+4.89) | 0.280 (+0.18) | 0.588 (+3.10) | +5.25 |
| 3 | P1-CHARLIE-260710 | 0.9931 | 0.386 (+1.63) | 1 (+18.66) | 1.000 (+2.65) | 1.000 (+26.20) | 0.5 (+4.89) | 0.202 (+0.13) | 0.526 (+2.77) | +4.97 |
| 4 | P1-ALPHA-260502 | 0.9847 | 0.374 (+1.58) | 1 (+18.66) | 1.000 (+2.65) | 0.997 (+26.14) | 0.5 (+4.89) | 0.189 (+0.12) | 0.397 (+2.09) | +4.17 |
| 5 | FOXTROT-251215 (P3) | 0.9559 | 0.365 (+1.54) | 1 (+18.66) | 0.153 (+0.41) | 0.999 (+26.19) | 0.5 (+4.89) | 0.801 (+0.52) | 0.536 (+2.82) | +3.08 |

Tonight's median altitude is 90 m. CHARLIE flew at 110 m and ALPHA-0502 at 118 m (§8.5's
per-flight altitude band), which accounts for 0.68 of the 0.80 gap. `launch_sim` is 0.5 for
everyone because the live launch is not seen. `radius_sim` is low because the orbit has just
begun at T+90 (250 m read, 187 m by T+120).

**Attempts, in order (D-078, judged on the training split only):**

1. Planned defaults with swarm-drone queries: Recall@5 1.000, lift +0.522, copycat-first 0%,
   MRR 0.942. Live top 3: 1/3 (ALPHA-0303 #5, ALPHA-0502 #13), with `bearing_sim` −1.03. The
   held-out training nights (11 queries) scored 1.000 / 1.000 (Recall@5 at T = 120 s / MRR at
   T = 90 s).
2. F1, prober and copycat queries only (registered in D-078 first): the held-out nights scored
   1.000 / 1.000, a tie, so F1 was adopted by the rule. Full data: the same metrics, MRR 1.000,
   live top 3 2/3 (ALPHA-0502 #4).
3. A3 T grid {60, 90, 120} on top of F1: held-out 1.000 / 1.000, a tie, so the default stays.
   Prefilter scaling and candidate count were not tried, since they cannot change the order of
   flights that are already candidates. Tuning stopped.

**Disclosure (plan fact 4):** the default settings (fixed units, 500 candidates, the wide T grid)
were first seen working, during planning, on the month 13 to 18 queries and on the demo. The build
did not choose among them on those data; its two choices (D-069's warp estimator, D-078) used the
training split only.

## Known issues and follow-ups

- **Soft gap: `live_top3_incidents`** (above). Options for a later phase, none tried here:
  - an altitude band rather than a point similarity (§8.5 draws altitude within a band per
    flight);
  - weighting `alt_sim` less when the live track is young;
  - accepting the miss: CHARLIE is a true P1 flight and §1.2 only requires "all three are actor
    P1".
- **The §1.2 caption "ALPHA 2026-03-03 (flown ~18% slower)" does not appear.** The matcher reads a
  warp of 1.03 for ALPHA-0303 at T+90 (truth 1.22). Warp estimates for P1 are weak (median error
  about 0.3) because the best window often sits at another flight phase. Phase 8's time-warp lens
  should align on `explain_alignment` or on the whole partial track.
- `make eval` exits 1 while the gap stands (a failed demo assertion). `gates.json` tolerates it,
  and `check_targets.py` judges.
- The training coefficients are large (`tod_sim` +26, `rf_match` +19), so many scores sit near
  1.0. Ranking is what matters, but a UI should show the rank and reasons, not "99.5%".
- P3 shares P1's RF family and time of night. Without the approach bearing it would crowd the
  demo; any change that weakens `bearing_sim` should be checked against the live query.
- `reports/eval_2026-10-29.*` now holds the phase 4 DTW run. The phase 3 backfill's Euclidean
  rerun with the same name is in git at `dc38d34` (UTC file dates, D-067).
- D-046 (P6, C2 and swarm targets) and D-065 (`sim/figures.py` font) remain open.

## How to debug this phase

- **Rebuild everything:** `make index` (7 s), `make models` (45 s), `make eval` (39 s). A changed
  `windows.normalize` or `channel_scales` needs `make index`; the matcher says so ("index is
  stale").
- **One live query, with stage timings and reasons:** `uv run kairos-defense match --incident
  DEMO-BRAVO-0828 --at 90 --top 20`. Add `--method euclidean` for the prefilter order alone.
- **Why is X ranked there?** In Python, build `DtwMatcher(store, lance, cfg.scoring, "models")`,
  then `r = m.match(load_query(store, tid, T, cfg.scoring))`. `m.model.contributions(match.features)`
  gives each feature's `coef × x`. `match.features["d_norm"]` and `["euclidean_d2"]` give the raw
  distances, and `r.baseline` gives the prefilter order.
- **Partial signature:** `query_signature(store, q)`. Compare it with `store.signature(tid)` for a
  history track at `T = duration + 30`.
- **Training pairs:** `CandidateBuilder` plus `eval.training.build_pairs` with a small `TrainSplit`
  (the unit tests use the P1 nights). `Pairs.keys` holds `query`, `at_s`, `track_id` and
  `answerable`.
- **Likely failures:**
  - `DtwUnavailable`: dtaidistance built without its C extension (D-064: `uv sync` with libomp).
  - `ModelError`: run `make models`; the feature order must match `scoring.fusion.features`.
  - `IndexStale`: run `make index`.
  - `LookAheadError`: a store returned a later track.
- **Eval numbers move:** compare `outcomes` in two `reports/eval_*.json`. Each row has
  `true_rank`, `baseline_rank`, `copycat_rank`, `dtw_ms` and `candidates`.

## Fix attempts

None yet.
