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
- `windows.window_vectors(raw (n, c), size, offsets, weights, segments, scales=None) -> (k, c ×
  segments) float32`, unit length; `window_vector(raw, weights, segments, scales=None) -> (c ×
  segments,)`. `scales` (c,) divides each channel by a fixed unit (no centering); None
  z-normalizes per window. `vector_scales(scoring)` picks the argument from `windows.normalize`.
- `windows.fill_nan(z (n, c)) -> (n, c)`: linear interpolation along time, 0 for an all-NaN
  column (shared with the DTW re-rank).
- `windows.iter_windows(features, scoring) -> Iterator[Window]` (`window_s`, `offset_s`,
  `vector`).
- `windows.query_window_size(n_seconds, scoring) -> int` and `query_vector(features, scoring) ->
  (vector (80,), W, rows used)`.
- `build.build_index(cfg) -> IndexSummary` (counts, target kinds, loiter directions, failures,
  swarm counts, elapsed); `build.windows_table(rows, vectors, dim) -> pyarrow.Table`.
  `kairos-defense index` runs `build_index` and then `recall.index.build_reports_index` (phase 5,
  D-089). Phase 9: `build.build_swarm_index(cfg, store, summary)` (called by `build_index`) and
  `build.swarm_windows_table(rows, vectors, dim)`.
- `swarm_features` (phase 9, SPEC §14, D-149), pure functions over numpy and pandas:
  - `drone_grid(points, max_gap_s) -> (t_s (n,) int, track_ids, positions (d, n, 3))`: every drone
    track of one incident resampled (§9.1) onto the incident's common 1 Hz grid, region meters,
    NaN where a drone has no position;
  - `detect_swarm(xy (d, n, 2), min_drones, max_spacing_m, min_duration_s) -> (bool, run_s)`;
  - `swarm_descriptors(t_s, positions, target_xy, min_drones) -> DataFrame` with
    `DESCRIPTOR_COLUMNS` (the §7.2 `swarm_features` columns: `t_s`, `n_drones`,
    `centroid_x_rel_m`, `centroid_y_rel_m`, `centroid_speed_ms`, `spread_m`, `pd_q25_m`,
    `pd_q50_m`, `pd_q75_m`, `axis_angle_deg`, `rot_rate_dps`) for seconds with at least
    `min_drones` drones;
  - `swarm_series(desc) -> (n, 6)`: `SERIES_COLUMNS` z-normalized (a constant channel is zeros);
  - `swarm_vector(series, segments) -> (6 × segments,) float32`, PAA, channel-major, unit norm;
  - `principal_axis_deg`, `unwrap_axis`, `pairwise_distances`, `longest_run`, `centered_mean`;
  - `SwarmFlight` (incident ids, `start_ts`, `track_ids`, `t_s`, `positions`, `target`,
    `descriptors`, `is_swarm`, `together_s`; `n_drones`, `relative_positions()`), built by
    `build_flight(meta, points, site, scoring)` or `load_swarm(store, incident_id, scoring,
    until_s=None)` (raw points through the port, only up to `until_s`).

## Data in and out

- In (through `DuckTrackStore`): `track_points`, `incidents`, `installations`, `regions`,
  `assets`, `rf_detections`, `remote_id`, `sensors` (§7.1).
- Out (`build.py` only):
  - DuckDB `track_features` (1 Hz, gaps marked) and `track_signatures` (§7.2), history tracks
    only;
  - LanceDB `flight_windows` (§7.5): `window_id` (`<track>:<W>:<offset>`), `track_id`,
    `incident_id`, `installation_id`, `region_id`, `window_s`, `offset_s`, `start_ts_ms` (first
    radar point), `win_ts_ms`, `rf_family`, `tod_minutes`, `vector` float32[80].
  - DuckDB `swarm_features` (§7.2, phase 9): one row per described second of each history swarm
    incident;
  - LanceDB `swarm_windows` (§7.5, phase 9): one row per history swarm incident with
    `incident_id`, `installation_id`, `start_ts_ms`, `n_drones` and the 96-d `vector`, plus
    `region_id`, `duration_s`, `together_s` and `is_swarm` (D-149).
- At seed 42: 800,148 feature rows, 1,898 signatures, 57,462 / 51,297 / 27,507 windows of 60 / 120
  / 300 s; 8 history swarm incidents (all detected), the live `DEMO-SWARM-ECHO-0614` skipped.

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
- **Windows (§9.5, D-051, D-068).** Every 10 s for each size, skipping windows with more than 20%
  gap seconds: scale and weight each channel, fill NaN by linear interpolation (all-NaN channel →
  0), average into 16 segments with exact fractional weights, flatten channel-major and
  L2-normalize. One batch per size (strided view, one einsum). Scaling follows
  `windows.normalize`: `fixed` (the default since phase 4) divides by `features.channel_scales`
  (5 m/s, 10 °/s, 200 m, 30 m, 1 m/s) without centering, so the orbit radius, speeds and altitude
  survive into the vector; `window` z-normalizes per window (§9.3 as written, phase 3), which made
  the planted P1 flights rank 855 to 953 of 1,882 for the live query at T+90 (D-058).
- **Queries (D-050).** W is the largest size not above the seconds seen; before 60 s the query uses
  all its rows against the 60 s windows. `match/query.py` calls these same functions.
- **Swarms (§14, D-149).** Each drone track is resampled as above and placed on the incident's
  common grid; a second counts when at least `swarm.min_drones` drones have a position. Per
  second: the centroid (target-relative; the target is `choose_target` on the centroid path), its
  speed, the RMS spread, the pairwise-distance quartiles, the PCA principal axis (bearing,
  unwrapped with period 180°) and its rate of turn (5 s centered mean, clipped to ±20 °/s so a
  near-round formation cannot spike it). Detection: the longest run of seconds with at least
  `min_drones` drones all within `max_spacing_m` of each other must last `min_duration_s`.
- **Build (D-049, D-053).** Live tracks are skipped everywhere. The build uses the adapters
  directly (bulk RF and Remote ID association, `write_table`, `replace`); no random draws.

## Configuration

`scoring.yaml` (§6.5):

- `features.max_interp_gap_s` (10), `features.channels` (speed, turn rate, distance to target,
  altitude, climb rate), `features.channel_weights` (1.0, 1.0, 1.2, 0.6, 0.4);
- `windows.sizes_s` (60, 120, 300), `windows.stride_s` (10), `windows.paa_segments` (16),
  `windows.normalize` (`fixed` | `window`), `features.channel_scales` (one positive unit per
  channel);
- `ScoringConfig.vector_dim`, a property: channels × segments = 80;
- `swarm.min_drones` (3), `swarm.max_spacing_m` (300), `swarm.min_duration_s` (60) for §14
  detection and the described seconds; the swarm vector uses `windows.paa_segments` (6 × 16 = 96).

`app.yaml`: `paths.duckdb` and `paths.lancedb` (build only).

## Tests

- `tests/unit/test_resample.py`, `test_channels.py`, `test_signatures.py` and `test_windows.py`:
  known answers on synthetic tracks from `tests/unit/synth.py` (straight lines, circles cw and ccw,
  gaps, duplicates, orbits, hovers, far takeoffs).
- `tests/unit/test_index.py`: the six P1 nights generated and indexed (`p1_index` fixture). The
  planted P1 signatures (approach 315° ± 15°, radius 180 ± 25 m, `ccw`), the live signature from
  its points, live incidents absent everywhere, window-size filters, metadata, 1 Hz rows, a
  deterministic rebuild.
- `tests/unit/test_swarm_features.py` (phase 9): known answers on hand-made formations (a 40 m
  square's spread and quartiles, a line turning 3 °/s, permutation invariance, detection true and
  false, shapes and norms, too few drones, the common grid).
- `tests/unit/test_swarm_match.py` (phase 9, `swarm_index` fixture): `swarm_windows` and
  `swarm_features` hold the history swarms only.
- `tests/slow/test_full_index.py`: full volumes; two full builds give identical hashes.
- Run: `uv run pytest tests/unit -q -k "resample or channels or signatures or windows or index or swarm"`.

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
  (D-046). A swarm's target (its centroid's) only sets the Swarm view's frame: the matching
  series are frame-free (spread, quartiles, rotation rate, speed).
- Keep `window_vectors` the single source of vectors. `test_query_vector_equals_indexed_window`
  (and its `_both_modes` twin) fails if the query and index paths diverge.
- **Changing `windows.normalize` or `channel_scales` means rerunning `make index`.** The DTW
  matcher and `kairos-defense models` rebuild one stored window per size and refuse a stale index
  ("index is stale: run `make index`", D-075).

## Changelog

- Phase 3: the package (`resample.py`, `channels.py`, `signatures.py`, `windows.py`, `build.py`);
  D-046 to D-051, D-053.
- Phase 4: `windows.normalize` (`fixed` by default) and `features.channel_scales`; `scales` on the
  vector functions; `vector_scales`; `fill_nan` made public (D-068). Window counts unchanged.
- Phase 5: no code change. `kairos-defense index` also builds the report index after this
  package's tables (D-089).
- Phase 9: `swarm_features.py` (§14 descriptors, detection, series, vectors, `load_swarm`);
  `build.py` writes `swarm_features` and `swarm_windows` (D-149). The single-track tables are
  unchanged.
