# kairos_defense.match

The matching engine (SPEC §10). Phase 3 built the query, the no-look-ahead prefilter and the
Euclidean baseline; phase 4 adds the DTW re-rank, fusion and explanations.

## Responsibilities

- Build a query: a track as it looked T seconds after its first radar point, rebuilt from the
  points up to T only (`query.py`, D-050).
- Find candidate past tracks: the nearest PAA windows among tracks that started strictly before the
  query, excluding its own incident, best window per track, top 50 (`prefilter.py`, §10.3).
  Refuse any result that breaks that rule (`LookAheadError`, CLAUDE.md rule 3).
- Rank candidates by window distance alone, the reference for "DTW lift" (`baseline.py`, §10.2,
  D-054).
- Define the `Match` result (`types.py`, §10.8).

Business logic here depends only on the `TrackStore` and `VectorStore` ports (rule 6). The LanceDB
call itself lives in `store/lance.py` (D-014).

## Public API

- `query.Query` (frozen): `track_id`, `incident_id`, `installation_id`, `start_ts` (first radar
  point, naive UTC), `at_s`, `features` (1 Hz, points up to `at_s` only), `target`, `vector`
  `(80,) float32`, `window_s` (W searched), `rows_used`; `start_ms` (epoch ms).
- `query.query_at(points, site, at_s, scoring, ids) -> Query`: from raw points; `ids` holds
  `track_id` and `incident_id`.
- `query.load_query(store: TrackStore, track_id, at_s, scoring) -> Query`: the same for a stored
  track, history or live. Raises `KeyError` for an unknown track.
- `prefilter.window_filter(window_s, start_ms, exclude_incident) -> str`:
  `window_s = W AND start_ts_ms < start AND incident_id != '<id>'`. The id must match
  `[A-Za-z0-9_.:-]+`, else `ValueError`.
- `prefilter.prefilter(q, store: VectorStore, scoring) -> DataFrame`: candidate tracks, nearest
  first, at most `prefilter.candidate_tracks`. Columns are those of `flight_windows` (without
  `vector`) plus `_distance` (squared L2 in [0, 4]). Raises `LookAheadError`.
- `prefilter.best_per_track(hits, n) -> DataFrame`: each track's nearest window, then the `n`
  nearest tracks; ties by `window_id`, then `track_id`.
- `prefilter.LookAheadError(RuntimeError)`.
- `baseline.euclidean_matches(q, store, scoring) -> list[Match]` and
  `baseline.rank_candidates(q, candidates) -> list[Match]`. `MODEL_VERSION = "euclidean-v1"`.
- `types.Match` (frozen): `query_incident_id`, `track_id`, `incident_id`, `installation_id`,
  `start_ts`, `score` (0..1), `shape_sim`, `features`, `reasons`, `warp_ratio`,
  `window_offset_s`, `model_version`.

## Data in and out

- In:
  - raw `track_points` and site geometry through `TrackStore` (`load_query`, `load_site`);
  - LanceDB `flight_windows` through `VectorStore.search` (written by `kairos-defense index`).
- Out: `Match` lists, printed by `kairos-defense match` and ranked by `eval/harness.py`. Nothing is
  written.

## How it works

- `query_at` keeps the points with `ts ≤ first + T`, then runs `features.channels.track_features`
  (resample, target, target columns) and `features.windows.query_vector` (W = the largest window
  size not above the seconds seen; before 60 s, every row against the 60 s windows).
- `prefilter` searches `k_windows` (200) windows of size W with the filter above, always with
  `prefilter=True`. It checks every returned row (`start_ts_ms < q.start_ms`, different incident)
  and raises `LookAheadError` otherwise, then keeps each track's nearest window and the 50 nearest
  tracks.
- `rank_candidates` maps each candidate's `_distance` d² to `score = shape_sim = 1 − d²/4`, which
  is cosine similarity on unit vectors mapped to 0..1. `features` holds `euclidean_d2` and
  `window_s`; `reasons` stays empty and `warp_ratio` NaN (D-054).
- The CLI: `uv run kairos-defense match --method euclidean --incident <id> --at <s>
  [--track <tid>] [--top N]`. Below `live.min_track_s` (45 s) it warns that the live matcher
  would wait, and still runs.

## Configuration

`scoring.yaml` (§6.5): `prefilter.k_windows` (200), `prefilter.candidate_tracks` (50),
`windows.sizes_s`, `features.*` (through the query) and `live.min_track_s` (CLI warning only).

## Tests

- `tests/unit/test_no_lookahead.py` (written before the matcher): the filter text; every result
  started before the query for every track at T = 45, 90 and 180; later P1 flights never returned;
  the first track has no history; points after T do not change the query; a leaky store raises
  `LookAheadError`.
- `tests/unit/test_cli.py`: `test_match_runs_on_the_p1_nights`, `test_match_dtw_is_phase_4`.
- `tests/unit/test_eval_harness.py` and `tests/slow/test_full_index.py::test_full_eval` run the
  baseline through the §19 protocol.
- Run: `uv run pytest tests/unit -q -k "lookahead or match"`.

## Gotchas

- T counts from the track's **first radar point**, not the incident's `start_ts` (usually RF at
  takeoff, D-038). The no-look-ahead filter uses the same clock on both sides (D-050).
- A past track that started earlier but was still flying contributes all its windows (the spec
  rule as written). One drone per actor at a time means this cannot help a same-actor match.
- `_distance` is squared L2, not cosine. Ranking by it is right only because vectors are unit
  length.
- Never pass a store that ignores filters: `prefilter` raises rather than return its rows. When
  adding a store (KDB-X, §22), test it with `test_prefilter_refuses_a_leaky_store`'s pattern.
- **D-058 (open for phase 4):** for the live query at T+90 the three planted P1 flights rank 1,149
  to 1,194 of 1,882 earlier tracks, outside the 50 candidates, so a DTW re-rank of these candidates
  cannot put them in the top 3. Per-window z-normalization probably erases the orbit radius and
  speeds that make P1 distinctive.

## Changelog

- Phase 3: `query.py`, `prefilter.py`, `baseline.py`, `types.py`, and `kairos-defense match
  --method euclidean` (D-050, D-054).
