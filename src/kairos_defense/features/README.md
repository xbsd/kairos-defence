# kairos_defense.features

Features and signatures (SPEC §9): 1 Hz resampling, the target and its frame, the matching
channels, one signature per track, and PAA window vectors. `build.py` runs them for
`kairos-defense index`.

## Responsibilities

- Resample a track's radar points to whole seconds and derive speed, climb rate, heading and turn
  rate, marking gaps instead of bridging them (`resample.py`, §9.1).
- Choose the target the drone lingers over and express the track relative to it, so tracks at
  different bases line up (`channels.py`, §9.2, D-046).
- Provide the five matching channels and their z-normalization with weights (`channels.py`, §9.3).
- Summarize a track as one `track_signatures` row (`signatures.py`, §9.4, D-047).
- Turn windows of a track into unit-length 80-number PAA vectors, the same way for the index and
  for a live query (`windows.py`, §9.5, D-050, D-051).
- Build every derived table from the raw tables, history tracks only (`build.py`, D-049).

Everything except `build.py` is a pure function over numpy and pandas. `load_site` reads geometry
through the `TrackStore` port.

## Public API

- `resample.resample(points, max_interp_gap_s=10.0) -> DataFrame`. `points` has `ts` (naive UTC),
  `x_m`, `y_m`, `alt_m` and `quality`. Returns one row per whole second with `FEATURE_COLUMNS`:
  `t_s` (int s since the first row), `ts`, `x_m`, `y_m`, `alt_m` (m), `speed_ms`, `vspeed_ms`
  (m/s), `heading_deg` (clockwise from north, [0, 360)), `turn_rate_dps` (deg/s, ±60, negative
  for a counter-clockwise turn) and `in_gap` (bool; values there are NaN).
- `resample.epoch_seconds(ts) -> (n,) float64` and `resample.epoch_ms(ts) -> int` (LanceDB
  `*_ts_ms`).
- `channels.Target`: `asset_id`, `kind` (`fence` for the pseudo-asset), `polygon`, `centroid`
  `(2,)`; `radius_m`; `distance(xy (n, 2)) -> (n,)` m (to the polygon, 0 inside; to the fence line
  for the fence).
- `channels.SiteGeometry`: `installation_id`, `region_id`, `utc_offset_hours`, `targets` (assets in
  id order, then the fence), `fence`; `target(asset_id)`.
- `channels.load_site(store: TrackStore, installation_id) -> SiteGeometry` and
  `site_from_rows(installation, assets, utc_offset_hours)`.
- `channels.in_flight_mask(alt_m (n,)) -> (n,) bool`: False on takeoff and landing.
- `channels.choose_target(site, xy (n, 2), speed_ms (n,), alt_m (n,)) -> Target` (D-046).
- `channels.add_target_columns(features, target)`: adds `x_rel_m`, `y_rel_m`, `dist_target_m`
  and `bearing_rel_deg`.
- `channels.track_features(points, site, scoring) -> (features, Target)`: resample, choose the
  target, add target columns. Uses only the points given, so a truncated live track sees nothing
  after T.
- `channels.channel_matrix(features, scoring) -> (n, 5) float64` in `scoring.features.channels`
  order, and `normalize(matrix (n, c), weights (c,)) -> (n, c)` (σ floor `SIGMA_FLOOR` = 1e-3).
- `signatures.SensorContext`: `rf_family`, `rid_serials` (most frequent first),
  `rid_operator_xy`; `rid_stable` (exactly one serial).
- `signatures.signature(f, target, first_point, last_point, site, ctx, ids) -> dict`: one row with
  `SIGNATURE_COLUMNS`. Launch and recovery are target-relative meters or None.
- `signatures.tod_minutes(start_utc, utc_offset_hours) -> int` (01:00 local → 1500),
  `approach_bearing(f)`, `loiter_mask(f)`, `loiter_direction(f, loiter) -> "cw" | "ccw" | "none"`.
- `windows.paa_weights(n, segments) -> (segments, n) float64` (cached, read-only).
- `windows.window_vectors(raw (n, c), size, offsets, weights, segments) -> (k, c × segments)
  float32`, unit length; `window_vector(raw, weights, segments) -> (c × segments,)`.
- `windows.iter_windows(features, scoring) -> Iterator[Window]` (`window_s`, `offset_s`,
  `vector`).
- `windows.query_window_size(n_seconds, scoring) -> int` and `query_vector(features, scoring) ->
  (vector (80,), W, rows used)`.
- `build.build_index(cfg) -> IndexSummary` (counts, target kinds, loiter directions, failures,
  elapsed); `build.windows_table(rows, vectors, dim) -> pyarrow.Table`.

## Data in and out

- In (through `DuckTrackStore`): `track_points`, `incidents`, `installations`, `regions`,
  `assets`, `rf_detections`, `remote_id`, `sensors` (§7.1).
- Out (`build.py` only):
  - DuckDB `track_features` (1 Hz, gaps marked) and `track_signatures` (§7.2), history tracks
    only;
  - LanceDB `flight_windows` (§7.5): `window_id` (`<track>:<W>:<offset>`), `track_id`,
    `incident_id`, `installation_id`, `region_id`, `window_s`, `offset_s`, `start_ts_ms` (first
    radar point), `win_ts_ms`, `rf_family`, `tod_minutes`, `vector` float32[80].
- At seed 42: 800,148 feature rows, 1,898 signatures, 57,462 / 51,297 / 27,507 windows of 60 / 120
  / 300 s.

## How it works

- **Resampling (§9.1).** Interpolate x, y and altitude onto whole seconds; seconds inside a gap of
  more than 10 s are NaN and `in_gap`. A 3 s median (closed form for three values) then a 3 s mean
  run inside gap-free runs only; derivatives are central differences, one-sided at run edges.
- **Target (§9.2, D-046).** Candidate seconds are in flight (leading and trailing seconds below
  0.8 × the median altitude are takeoff and landing), have a speed and lie within 500 m of the
  fence (all in-flight seconds if fewer than 10). The slowest half vote; the smallest median
  distance wins; ties go to the earlier target. The frame is shifted, never rotated.
- **Signatures (§9.4, D-047).** Loiter seconds are slower than 1.2 × the median speed and within
  600 m (at least 10, else no loiter). The radius is their median distance from the target
  centroid. The direction sums the bearing change over consecutive loiter seconds outside the
  polygon: `none` under 180°, `ccw` when negative (D-024). Launch is the single heard Remote ID
  serial's operator position, else a first point below 30 m; recovery is a last point below 30 m.
- **Windows (§9.5, D-051).** Every 10 s for each size, skipping windows with more than 20% gap
  seconds: z-normalize and weight per window, fill NaN by linear interpolation (all-NaN channel →
  0), average into 16 segments with exact fractional weights, flatten channel-major and
  L2-normalize. One batch per size (strided view, one einsum).
- **Queries (D-050).** W is the largest size not above the seconds seen; before 60 s the query uses
  all its rows against the 60 s windows. `match/query.py` calls these same functions.
- **Build (D-049, D-053).** Live tracks are skipped everywhere. The build uses the adapters
  directly (bulk RF and Remote ID association, `write_table`, `replace`); no random draws.

## Configuration

`scoring.yaml` (§6.5):

- `features.max_interp_gap_s` (10), `features.channels` (speed, turn rate, distance to target,
  altitude, climb rate), `features.channel_weights` (1.0, 1.0, 1.2, 0.6, 0.4);
- `windows.sizes_s` (60, 120, 300), `windows.stride_s` (10), `windows.paa_segments` (16);
- `ScoringConfig.vector_dim`, a property: channels × segments = 80.

`app.yaml`: `paths.duckdb` and `paths.lancedb` (build only).

## Tests

- `tests/unit/test_resample.py`, `test_channels.py`, `test_signatures.py` and `test_windows.py`:
  known answers on synthetic tracks from `tests/unit/synth.py` (straight lines, circles cw and ccw,
  gaps, duplicates, orbits, hovers, far takeoffs).
- `tests/unit/test_index.py`: the six P1 nights generated and indexed (`p1_index` fixture). The
  planted P1 signatures (approach 315° ± 15°, radius 180 ± 25 m, `ccw`), the live signature from
  its points, live incidents absent everywhere, window-size filters, metadata, 1 Hz rows, a
  deterministic rebuild.
- `tests/slow/test_full_index.py`: full volumes; two full builds give identical hashes.
- Run: `uv run pytest tests/unit -q -k "resample or channels or signatures or windows or index"`.

## Gotchas

- `turn_rate_dps` is negative for a counter-clockwise turn, and `loiter_dir` is `ccw` when the
  bearing from the target *decreases* (D-024). Do not "fix" either sign.
- Do not slice a live query out of full-track features: the target, smoothing and derivatives at
  T depend on the points up to T only. Rebuild from points (`track_features` on the truncated
  points).
- `dist_target_m` is 0 inside an asset polygon but measures to the fence *line* for the fence, so
  it is positive inside the base too.
- The target can change as a live track grows (the live P1 flight picks the fence while inbound
  and the fuel farm from about T+90).
- 1,800 of 1,898 tracks have the fence as target: hobbyists launch from parks 2.2 km out and never
  come within 500 m of the fence. Target choice is still wrong for P6, C2 and swarm drones
  (D-046).
- Keep `window_vectors` the single source of vectors. `test_query_vector_equals_indexed_window`
  fails if the query and index paths diverge.

## Changelog

- Phase 3: the package (`resample.py`, `channels.py`, `signatures.py`, `windows.py`, `build.py`);
  D-046 to D-051, D-053.
