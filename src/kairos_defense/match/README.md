# kairos_defense.match

The matching engine (SPEC §10). Phase 3 built the query, the no-look-ahead prefilter and the
Euclidean baseline. Phase 4 added the DTW re-rank, the partial live signature, fusion,
explanations and the `DtwMatcher`.

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
  - `explain_alignment(live_dist, full_dist) -> (first row, last row, value)` (for phase 8).
- `live_signature.query_signature(store, q) -> dict`: the §9.4 fields from what was known at T.
- `fusion`: `rf_match(a, b)`; `context_frame(qsig, csigs) -> DataFrame` (columns `CONTEXT`:
  `rf_match`, `bearing_sim`, `tod_sim`, `launch_sim`, `radius_sim`, `alt_sim`);
  `fusion_features(qsig, csig, shape_sim)`; `feature_matrix(rows, order) -> (n, k)`;
  `FusionModel` (`predict(X) -> (n,)`, `contributions(x)`, `to_json`, `save`, `load(path,
  expected_features)`); `DtwCalibration` (`save`, `load`); `ModelError`; `MODEL_FILE`
  (`fusion_v1.json`), `CALIBRATION_FILE` (`dtw_calibration.json`).
- `explain.reasons(features, model, warp_ratio, csig) -> list[str]` (at most three).
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

## Configuration

`scoring.yaml` (§6.5): `prefilter.k_windows` (10,000) and `candidate_tracks` (500);
`windows.normalize` (`fixed`) and `features.channel_scales`; `features.channel_weights`;
`dtw.band_fraction` (0.25), `anchor_before` (0.5), `anchor_after` (1.5), `tau` (`auto` reads the
calibration, a number overrides it), `normalize` (`fixed`; `series` and `floored` for comparison,
D-079; retrain with `make models` after changing it); `fusion.features` (the model's order is checked);
`live.min_track_s` (CLI warning). `app.paths.models` (where the model files live).

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

## Changelog

- Phase 3: `query.py`, `prefilter.py`, `baseline.py`, `types.py`, and `kairos-defense match
  --method euclidean` (D-050, D-054).
- Phase 4: `dtw_rerank.py`, `live_signature.py`, `fusion.py`, `explain.py`, `candidates.py`,
  `matcher.py`; `Query.site`, `points`, `until`; `Match.to_dict`; 500 candidates on fixed-unit
  vectors; `match --method dtw` is the default (D-068 to D-076, D-078).
- Phase 4 gate fix 1: `dtw.normalize` (`fixed` adopted on the training split, D-079).
- Phase 5: `MatchResult.signature` and `signatures`; `warp_path` takes the scaling mode (D-087).
