# kairos_defense.forecast

The analog forecast (SPEC §13): where tonight's drone will be recovered, predicted from the
matched past flights whose recovery point is known.

## Responsibilities

- Turn tonight's query and its `MatchResult` into a recovery zone (center, radius), a predicted
  exit path and the roads crossing the zone (`analog.py`).
- Use only what was known at T: analogs whose flight had ended by the replay time, through the
  ports (rule 3, rule 6). Never read truth; the error is computed in `kairos_defense.eval`.

## Public API

- `analog.forecast(store, q, result, scoring) -> Forecast | None` (None when no match has a known
  recovery point).
- `analog.Forecast`: `at_s`, `target_asset_id`, `anchor`, `center_x_m`, `center_y_m`, `radius_m`
  (m), `path` `(60, 2)` region meters, `roads`, `analogs`; `to_dict()` (the §16.3 `forecast`
  message fields plus the analogs, JSON-safe).
- `analog.Analog`: `incident_id`, `track_id`, `score`, `target_kind`, `recovery_rel_m` (the
  match's own, target-relative), `rotation_deg`, `anchor_asset_id`, `aligned_t_s` (j*),
  `recovery_x_m`, `recovery_y_m` (mapped into tonight's frame), `remainder_points`.
- Pure helpers (numpy, meters):
  - `combine(points (n, 2), weights (n,), min_radius, factor) -> (center (2,), radius)`;
  - `rotation_for(tonight_deg, match_deg) -> deg` (0 within 30° or when unknown) and
    `rotate_rel(xy, deg)` (clockwise);
  - `aligned_index(live (n, c), seg (m, c), weights, mode="fixed", scales=None) -> j*`;
  - `remainder(features, j, recovery_rel) -> (k, 2)`;
  - `resample_path(xy, n=60) -> (n, 2)` (even by arc length);
  - `anchor_target(target, site, analog_kind, mode) -> Target`;
  - `roads_crossing(center, radius, lines) -> list[str]`; `road_lines(store, region_id)`.

## Data in and out

- In (through `TrackStore`): the matches' `track_signatures` (or the matcher's copy in
  `MatchResult.signatures`), their `track_features`, and the `roads` of tonight's region.
- Out: a `Forecast` object; nothing is written.

## How it works

1. Walk the fused ranking; keep the first `top_k` (3) matches with a known recovery point (§9.4)
   whose flight ended by the replay time (D-087).
2. j*: the segment row paired with tonight's last row on the DTW warping path (relaxed ends, the
   shape distance's `dtw.normalize` scaling), mapped onto the matched track.
3. Remainder: the match's target-relative positions after j*, ending at its recovery point.
4. Rotate clockwise by the approach-bearing difference when it exceeds 30°, then add the anchor:
   tonight's target centroid, or with `forecast.anchor: match_kind` and tonight still reading the
   fence, tonight's asset of the analog's kind (D-090).
5. Center = score-weighted mean of the mapped recovery points; radius = max(150 m, 1.5 × weighted
   RMS distance).
6. Exit path = the top analog's mapped remainder, 60 points by arc length.
7. Roads of tonight's region intersecting the circle (feeds the §12.4 clue links).

## Configuration

- `scoring.forecast`: `top_k` (3), `min_radius_m` (150), `radius_factor` (1.5), `anchor`
  (`match_kind`, D-090).
- `scoring.dtw.normalize`, `scoring.dtw.anchor_before/after`, `scoring.features.channel_weights`
  and `channel_scales` (the alignment for j*).

## Tests

- `tests/unit/test_forecast.py`: `combine` and the weighted center (known answers), rotation only
  beyond 30° (north turns east for +90°), j* on a shifted copy (± 2 s, also with noise), the exit
  path (60 points, ends at the recovery, gaps dropped), roads 10 m outside the radius not listed,
  the anchor modes, top k counts only known recoveries and ended flights, None without one, the
  live forecast on the P1 nights (and the same result through the ports).
- `tests/unit/test_no_lookahead.py::test_forecast_and_recall_ignore_points_after_t`.
- Slow: `tests/slow/test_full_models.py::test_full_demo_recall_and_forecast` (T+105 error ≤ 400 m,
  County Rd 12 in the zone).
- Run: `uv run pytest tests/unit -q -k forecast`.

## Gotchas

- Only 2 of the 5 earlier P1 flights have a known recovery point (their last radar point is below
  30 m, D-003), so the demo forecast also uses rotated flights of other actors (HOTEL-250818,
  FOXTROT-251215 at T+105). A ranking change can move it; the slow test and the eval demo row
  catch that.
- j* changes only the exit path; the center and radius use the recovery points alone.
- `match_kind` and `target` give identical forecasts once tonight's target is an asset (the live
  track reads BRAVO's fuel farm from T+90).

## Changelog

- Phase 5: the package (`analog.py`); D-087, D-090.
