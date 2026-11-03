# kairos_defense.match

The matching engine (SPEC §10, §14). Phase 3 built the query, the no-look-ahead prefilter and the
Euclidean baseline. Phase 4 added the DTW re-rank, the partial live signature, fusion,
explanations and the `DtwMatcher`. Phase 9 added swarm choreography matching (`swarm.py`). Phase 12
added the matcher trace (`trace.py`) that the DTW workbench replays.

## Responsibilities

- Build a query: a track as it looked T seconds after its first radar point, rebuilt from the
  points up to T only (`query.py`, D-050).
- Find candidate past tracks: the nearest PAA windows among tracks that started strictly before the
  query, excluding its own incident, best window per track, top 500 (`prefilter.py`, §10.3, D-068).
  Refuse any result that breaks that rule (`LookAheadError`, CLAUDE.md rule 3).
- Rank candidates by window distance alone, the reference for "DTW lift" (`baseline.py`, §10.2).
- Compute each candidate's anchored DTW distance and the six context features against the query's
  partial signature (`candidates.py`, `dtw_rerank.py`, `live_signature.py`, `fusion.py`).
- Fuse them with the trained logistic model, explain the top matches and estimate their pace
  (`matcher.py`, `explain.py`).
- Refuse a stale index, missing models and a missing C extension (`candidates.check_index`,
  `fusion.ModelError`, `dtw_rerank.require_c`; D-075, D-013).
- Record, on request, what one match call computed, for the DTW workbench (`trace.py`, D-187),
  without changing any result.
- Rank earlier swarms against a swarm incident by choreography (`swarm.py`, §14, D-150): the
  `swarm_windows` prefilter (started before the query), then multichannel DTW on the descriptor
  series against candidate prefixes over `swarm.pace_range`.

Business logic depends only on the `TrackStore` and `VectorStore` ports (rule 6). `dtw_rerank.py`
is the only module that imports dtaidistance; serving never imports scikit-learn and never reads
truth (training lives in `kairos_defense.eval.training`).

## Public API

- `query.Query` (frozen): `track_id`, `incident_id`, `installation_id`, `start_ts` (first radar
  point, naive UTC), `at_s`, `features` (1 Hz, points up to `at_s` only), `target`, `vector`
  `(80,) float32`, `window_s`, `rows_used`, `site`, `points` (raw points up to T); `start_ms`,
  `until` (= `start_ts + at_s`).
- `query.query_at(points, site, at_s, scoring, ids)` and `query.load_query(store, track_id, at_s,
  scoring) -> Query`.
- `prefilter.prefilter(q, store, scoring) -> DataFrame` (columns of `flight_windows` plus
  `_distance`, squared L2), `window_filter`, `best_per_track`, `LookAheadError`, `WINDOWS_TABLE`.
- `baseline.euclidean_matches(q, store, scoring)`, `baseline.rank_candidates(q, candidates)`;
  `MODEL_VERSION = "euclidean-v1"`.
- `matcher.DtwMatcher.match(q, trace=False) -> MatchResult`: with `trace=True`,
  `MatchResult.trace` is the D-187 record (a JSON-safe dict); otherwise `None`.
- `trace.TraceRecorder(scoring, paths=TRACE_PATHS)` (called by `CandidateBuilder.build` and
  `DtwMatcher.match`), `trace.downsample_path`, `trace.thumbnail`, `trace.curve`; constants
  `TRACE_PATHS` 50, `MAX_POINTS` 48, `THUMB` 12, `TRACE_CHANNEL` `dist_target_m`, `TOP` 10.
- `dtw_rerank.alignment(live, seg, weights, mode, scales) -> (path, cost)`: the full-matrix
  alignment with relaxed segment ends and its accumulated cost; `warp_path` returns its path.
- `dtw_rerank` (pure functions over raw `(n, 5)` channel arrays):
  - `require_c()` / `DtwUnavailable`; `band_window(n, m, band_fraction)`;
    `anchor_bounds(offset_s, window_s, n_rows, before, after) -> (lo, hi)`; `relaxation(n, m)`;
  - `prepare(raw, weights, mode="series", scales=None) -> (n, c)`: `series` (§9.3 z over the
    series), `floored` (σ floored at the unit) or `fixed` (raw / unit, no centering), weighted, NaN
    filled (D-079);
  - `shape_distance(live, seg, weights, band_fraction, mode="series", scales=None) -> d_norm`;
    `shape_sim(d_norm, tau)`;
  - `warp_path(live, seg, weights, mode="series", scales=None) -> (p, 2) int` (the forecast's j*
    passes the shape distance's `dtw.normalize` and scales, D-087);
    `warp_ratio(live, seg, weights, speed_col=0)`
    (NaN outside `WARP_RANGE` 0.5–2.0); `warp_text(k) -> "flown X% slower" | "... faster" | None`;
  - `explain_alignment(live_dist, full_dist) -> (first row, last row, value)` (used by
    `GET /api/explain`, phase 8).
- `live_signature.query_signature(store, q) -> dict`: the §9.4 fields from what was known at T.
- `fusion`: `rf_match(a, b)`; `context_frame(qsig, csigs) -> DataFrame` (columns `CONTEXT`:
  `rf_match`, `bearing_sim`, `tod_sim`, `launch_sim`, `radius_sim`, `alt_sim`);
  `fusion_features(qsig, csig, shape_sim)`; `feature_matrix(rows, order) -> (n, k)`;
  `FusionModel` (`predict(X) -> (n,)`, `contributions(x)`, `to_json`, `save`, `load(path,
  expected_features)`); `DtwCalibration` (`save`, `load`); `ModelError`; `MODEL_FILE`
  (`fusion_v1.json`), `CALIBRATION_FILE` (`dtw_calibration.json`).
- `explain.reasons(features, model, warp_ratio, csig) -> list[str]` (at most three).
- `explain.contribution_table(features, model) -> dict` (§10.7, the Match explainer, D-135):
  `rows` (feature, value, coefficient, contribution = coefficient × value) for the model's
  features only, by |contribution|; `intercept`, `logit` = intercept + Σ, `score` = sigmoid(logit).
- `candidates.CandidateBuilder(store, vstore, scoring)`: `build(q) -> Candidates` (rows in
  prefilter order with `d_norm` and the context features, the query signature, the candidates'
  signatures, timings), `raw_channels(ids)`, `segment(track_id, offset_s, window_s)`.
  `candidates.check_index(store, vstore, scoring) -> probe track` / `IndexStale`.
- `matcher.DtwMatcher(store, vstore, scoring, models_dir, *, verify_index=True)`:
  `match(q) -> MatchResult` (`matches` by fused score, `baseline` in prefilter order, `timings`
  in ms: `prefilter_ms`, `signature_ms`, `dtw_ms`, `features_ms`, `fusion_ms`, `explain_ms`,
  `total_ms`; from phase 5 also `signature`, the query's partial signature, and `signatures`, the
  candidates' stored signatures by track id, which the forecast and recall reuse; both are None
  for the Euclidean baseline, D-087); `model`, `tau`, `model_version`.
  `matcher.load_models(models_dir, scoring)`.
  `EXPLAIN_TOP = 20`.
- `types.Match` (frozen, §10.8) and `Match.to_dict()` (JSON-safe: NaN becomes None).
- `swarm.SwarmMatcher(store, vstore, scoring)` (phase 9, §14, D-150): `match(incident_id,
  at_s=None, k=5) -> SwarmResult` (`query` a `features.swarm_features.SwarmFlight`, `matches` a
  list of `SwarmMatch` best first, `paths` incident → DTW path `[(i, j)…]`, `timings` in ms:
  `load_ms`, `prefilter_ms`, `dtw_ms`, `total_ms`; `aligned(incident_id)` → for each described query
  second, the matched descriptor row); `candidate_descriptors(incident_id)`.
  `SwarmMatch` (`rank`, `incident_id`, `installation_id`, `region_id`, `start_ts`, `n_drones`,
  `duration_s`, `distance`, `similarity` = 1 / (1 + distance), `warp_ratio`, `matched_s`;
  `to_dict()`). `swarm.prefix_dtw`, `prefix_lengths`, `dtw_band`, `warping_path`;
  `SwarmIndexMissing`; `MODEL_VERSION = "swarm-dtw-v1"`.
- `dtw_rerank.series_distance(a, b, window)` and `series_path(a, b)` (phase 9): banded C distance
  and the full-matrix optimal path between two prepared multichannel series (the swarm matcher's
  only dtaidistance calls, so `dtw_rerank` stays the only importer).

- `lens.lens_payload(query, candidate, *, channel, band_fraction, warp_ratio, match_track_id)`
  (phase 7, D-117): one channel, raw units, `(n,)` and `(m,)`; PAA to ≤ 128 points; band
  `max(|n − m| + 1, ceil(band_fraction × max(n, m)))`; returns `query`, `candidate`, `path`
  (`dtw.best_path`), `cost` (the accumulated `warping_paths` matrix without padding, float32 LE
  base64) with `shape`, `band`, `dtw_distance`, `euclid_distance` (first `overlap` samples),
  `warp_ratio`, `warp_text`. `lens.paa`, `lens.band`, `lens.encode_f32`, `lens.decode_f32`.
- Phase 11: `swarm.SwarmMatcher.match_flight(query, k=5, t0=None)` (the ranking of an already
  built `SwarmFlight`; `match` calls it, results unchanged) and
  `candidates.CandidateBuilder.forget(ids)` / `cached_ids()` (live reset).

## Data in and out

- In: raw `track_points`, `rf_detections`, `remote_id` and site geometry through `TrackStore`
  (`load_query`, `sensor_context_until`); `track_signatures` (`tracks_before`) and
  `track_features` (`features_many`); LanceDB `flight_windows` through `VectorStore.search`;
  `models/fusion_v1.json` and `models/dtw_calibration.json` (written by `kairos-defense models`).
- Out: `MatchResult` / `Match` lists, printed by `kairos-defense match`, ranked by
  `eval/harness.py`, and handed to `forecast.analog.forecast` and `recall.search.ReportRecall`
  (phase 5). Nothing is written.

## How it works

1. **Prefilter** (§10.3): the query vector (fixed-unit PAA, D-068) against `k_windows` = 10,000
   windows of size W, filtered to earlier tracks of other incidents; best window per track; the
   500 nearest tracks.
2. **Signature** (§10.5, D-071): `query_signature` runs §9.4 on the query's own features and its
   first and last points up to T, with RF and Remote ID heard up to T only (the adapter's `until`
   bound). Candidate signatures come from `tracks_before(q.start_ts)` (§11.3).
3. **Anchored DTW** (§10.4, D-069, D-079): for each candidate, rows `[o − 0.5W, o + 1.5W]`
   around its best window; both series in fixed units (`dtw.normalize: fixed`: raw /
   `channel_scales` × weight, the prefilter's recipe) rather than §9.3's per-series z, which turned
   the radar noise of near-constant orbit channels into shape; banded C `dtw_ndim` with the
   segment's two ends relaxed (psi); `d_norm = d / sqrt(n)`, `shape_sim = exp(−d_norm / τ)`. On the
   training split this raised the shape's same-actor AUC from 0.58 to 0.80.
4. **Fusion** (§10.5, §10.6): seven features in `scoring.fusion.features` order, `sigmoid(x · coef
   + b)` with the trained coefficients. Ties keep prefilter order.
5. **Explain** (§10.7, D-074): for the top 20, the warp ratio (tonight's mean speed over the past
   flight's mean speed on the rows the alignment matches; §8.5 makes that the time warp) and up to
   three reasons by contribution.

Measured on the dev laptop with the default dataset (eval, 165 searches): prefilter p95 30 ms,
DTW of 500 candidates p95 57 ms, end to end p95 124 ms.

**Swarms (§14, D-150).** The query swarm is rebuilt from raw points up to `at_s` (whole flight by
default). Its z-normalized descriptor series (spread, three pair-distance quartiles, rotation rate,
centroid speed) gives a 96-d PAA vector for the `swarm_windows` prefilter (`start_ts_ms <` the
query's first radar point; every earlier swarm is re-ranked, there are few). Each candidate's
indexed descriptors (`swarm_features`) are compared as prefixes of m = n × pace seconds, pace over
`swarm.pace_range` in 15 steps, each prefix z-normalized on its own, banded C DTW with
`dtw.band_fraction`; distance = min `d / sqrt(n + m)`. The best prefix gives the pace (`m / n`)
and the full-matrix alignment for the Swarm view.

## Configuration

`scoring.yaml` (§6.5): `prefilter.k_windows` (10,000) and `candidate_tracks` (500);
`windows.normalize` (`fixed`) and `features.channel_scales`; `features.channel_weights`;
`dtw.band_fraction` (0.25), `anchor_before` (0.5), `anchor_after` (1.5), `tau` (`auto` reads the
calibration, a number overrides it), `normalize` (`fixed`; `series` and `floored` for comparison,
D-079; retrain with `make models` after changing it); `fusion.features` (the model's order is checked);
`live.min_track_s` (CLI warning). `app.paths.models` (where the model files live). Swarms:
`swarm.pace_range` ([0.7, 1.4]) and `dtw.band_fraction`; `windows.paa_segments` for the vector.

## Tests

- `tests/unit/test_dtw_rerank.py`: C path required, self-distance 0, band, anchors, NaN, warped
  copies (0.8–1.4 at W = 60 and 120) score above an unrelated flight and report their warp, in
  `series` and in the configured `fixed` mode; the three `prepare` modes' known answers; relaxed
  ends, credible range, C and Python agree, `explain_alignment`.
- `tests/unit/test_fusion.py`, `test_explain.py`, `test_live_signature.py`: §10.5 formulas,
  model round trip (equals scikit-learn to 1e-12), feature-order refusal, a copycat fuses below
  P1; §10.7 reasons; partial signatures ignore everything after T.
- `tests/unit/test_matcher.py` (P1 nights, hand-set `toy_models`): fields and order,
  determinism, timings, stale index refused, missing models refused, top 3 are P1.
- `tests/unit/test_no_lookahead.py`: both matchers, every track at T = 45, 90 and 180.
- `tests/unit/test_swarm_match.py` (phase 9, `swarm_index` fixture): the demo swarm's top 1 is
  `S1-GOLF-260503` (§20), no look-ahead (earlier incidents only; points up to `at_s`), the path is
  monotone, covers both ends and costs exactly the full DTW distance, an S1 event ranks S1 first,
  short queries, unknown incidents and a missing index.
- `tests/unit/test_matcher_trace.py` (phase 12): results identical with and without the trace
  (two queries at T = 60, 120, 180), its order, counts and fields, the 50-path cutoff plus the
  final top 10, down-sampling and thumbnails, and the measured overhead (printed).
- `tests/slow/test_full_models.py`: full-data copycat check and DTW eval.
- Run: `uv run pytest tests/unit -q -k "dtw or fusion or explain or matcher or signature or
  lookahead"`.

## Gotchas

- **The shape distance is in fixed units now** (D-079): altitude and speed levels count, as
  `alt_sim` and `radius_sim` do. A flight at the other end of its actor's altitude band scores a
  lower shape, which is why ALPHA 2026-05-02 ranks fifth at T+90.
- **Partial signatures report target-dependent fields too early** (D-081). The loiter radius of a
  track seen T seconds in is off from its final radius by a median of 1.1 km at T = 90 s, and its
  target can still be transient (the live P1 reads "fence" until T+80). So `radius_sim` and the
  "Same orbit radius" reason are unreliable early. Planned follow-up: treat them as unknown until
  the loiter is established.
- **`use_c=True` everywhere.** dtaidistance silently falls back to pure Python (500x slower)
  without it; `require_c()` runs when a matcher is built.
- **dtaidistance 2.5.1's C `warping_paths` with a `window` returns a wrong paths matrix** near the
  band edge (the distance is right). The warp alignment therefore uses the full matrix (D-069,
  `test_c_paths_match_python_without_band`).
- **Warp ratios beyond the top 20 are NaN**, and so is any estimate outside 0.5–2.0. Use
  `Match.to_dict()` for JSON: `json.dumps` would write invalid `NaN`.
- **Warp estimates for P1 are weak** (median error about 0.3 against truth): the best window often
  sits at another flight phase, approach against orbit. For ALPHA 2026-03-03 the matcher reads
  1.03, not the planted 1.22 (REPORT phase 4).
- **Changing `windows.normalize` or `channel_scales` needs `make index`**; the matcher refuses a
  stale index with "index is stale: run `make index`".
- T counts from the track's first radar point (D-050). A past track that started earlier but was
  still flying contributes all its windows (rule 3 filters on start; D-050, D-071).
- `_distance` is squared L2, not cosine; ranking by it is right only because vectors are unit
  length.
- The trace's path is the unbanded full-matrix alignment (`warp_path`'s recipe, D-069) while the
  distance is banded: the workbench labels it so and draws no band. `total_ms` and `dtw.ms`
  exclude the trace's own work; `trace_ms` is that work.

## Changelog

- Phase 3: `query.py`, `prefilter.py`, `baseline.py`, `types.py`, and `kairos-defense match
  --method euclidean` (D-050, D-054).
- Phase 4: `dtw_rerank.py`, `live_signature.py`, `fusion.py`, `explain.py`, `candidates.py`,
  `matcher.py`; `Query.site`, `points`, `until`; `Match.to_dict`; 500 candidates on fixed-unit
  vectors; `match --method dtw` is the default (D-068 to D-076, D-078).
- Phase 4 gate fix 1: `dtw.normalize` (`fixed` adopted on the training split, D-079).
- Phase 5: `MatchResult.signature` and `signatures`; `warp_path` takes the scaling mode (D-087).
- Phase 7: `lens.py`, the time-warp lens payload of the `dtw` message (D-117).
- Phase 8: `explain.contribution_table` for the Match explainer (D-135).
- Phase 9: `swarm.py` (§14 swarm matching, D-150); `dtw_rerank.series_distance` and
  `series_path`. The single-track matcher is unchanged.
- Phase 11: `SwarmMatcher.match_flight` and `CandidateBuilder.forget` for live mode; a second
  `DtwMatcher` over the composite ports serves live mode (D-175, D-176).
- Phase 12: `trace.py` and `DtwMatcher.match(trace=True)` (D-187); `dtw_rerank.alignment`;
  `CandidateBuilder.build(q, recorder=None)` times each candidate when recording.
