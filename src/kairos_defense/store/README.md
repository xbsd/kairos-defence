# kairos_defense.store

Storage adapters: DuckDB and LanceDB behind the ports in `kairos_defense.ports`, plus the
truth-isolation guard every app connection goes through.

## Responsibilities

- Refuse the ground-truth file to all app code, however its path is spelled (`guard.py`; CLAUDE.md
  rule 2, SPEC §7.6).
- Hold the DDL for the raw, derived and truth tables (`ddl.py`; §7.1 to §7.3).
- Implement `TrackStore` over DuckDB, including the §11 context joins and the bulk queries the index
  build needs (`duck.py`).
- Implement `VectorStore` over LanceDB. All LanceDB calls live here (`lance.py`, D-014).
- Business logic imports the ports, never these modules directly (rule 6). Only index builds and
  composition roots such as `cli.py` construct the adapters (D-053).

## Public API

- `guard.connect_app_db(path, app, *, read_only=False) -> duckdb.DuckDBPyConnection`: opens an app
  DuckDB file or `:memory:`. Raises `TruthAccessError` if `path` is the truth file (relative, `..`,
  symlink or hard link). Creates the parent folder.
- `guard.is_truth_path(path, app) -> bool`.
- `guard.TruthAccessError(PermissionError)`.
- `ddl.RAW_DDL`, `ddl.TRUTH_DDL` and `ddl.DERIVED_DDL` (`dict[name, CREATE TABLE]`),
  `ddl.DERIVED_COLUMNS`, and `ddl.columns(ddl) -> list[str]`.
- `duck.DuckTrackStore(path, app, *, read_only=True)`: context manager.
  - Port methods:
    - `track_points(track_id)`: rows ordered by `ts`; meters in the region frame.
    - `features(track_id)`: 1 Hz rows from `track_features`.
    - `features_many(track_ids)`: the same for many tracks, ordered by `track_id`, `t_s` (D-072).
    - `sensor_context_until(track_id, until) -> dict`: `rf_family`, `rid_serials`,
      `rid_operator_xy` from track points, RF, Remote ID and concurrent tracks at or before
      `until` only (§10.5 partial signatures, D-071, D-072).
    - `signature(track_id) -> dict`: one `track_signatures` row.
    - `tracks_before(ts, exclude_incident=None)`: signatures of tracks that started **strictly
      before** `ts` (§11.3, rule 3).
    - `context_asof(track_id)`: per second, the as-of weather and the active base events (§11.1).
    - `sql(query, params)`.
  - Extras:
    - `base_events_during(track_id)`.
    - `tracks()`: one row per track.
    - `rf_association(track_ids=None, until=None)` (§11.2: ±30 s, with a 15° bearing gate when
      tracks overlap, D-048).
    - `rid_association(track_ids=None, until=None)` (±5 s and 100 m).
    - `sensor_context(track_ids=None, until=None) -> dict[track_id, SensorContext]`.
    - `until` (naive UTC) bounds the track's points, the detections and the concurrency spans:
      a track that has not appeared by `until` cannot gate anything. `None` (the default, used by
      `index`) is phase 3's behavior.
    - `write_table(name, df) -> int`: drops and recreates one §7.2 derived table. The columns must
      match the DDL.
- `lance.LanceVectorStore(uri)`:
  - `search(table, vector, where, k)`: always `prefilter=True`; returns `_distance`, squared L2 on
    unit vectors.
  - `upsert(table, rows)`, keyed by `KEYS` (`window_id`, `incident_id`, `report_id`).
  - `replace(table, data) -> int`: a full rewrite, which also creates the scalar indexes in
    `SCALAR_INDEXES`.
  - `tables()`, `has()`, `count(table, where)`, `to_pandas(table, columns)`.

## Data in and out

- `data/kairos_defense.duckdb`:
  - raw tables (§7.1), written by `sim.writers`: `regions`, `installations`, `assets`, `roads`,
    `parks`, `sensors`, `incidents`, `track_points`, `rf_detections`, `remote_id`, `weather`,
    `base_events`, `public_events`, `reports`, `assessments`;
  - derived tables (§7.2), written by `kairos-defense index`, history tracks only (D-049):
    `track_features`, `track_signatures`.
- `data/truth.duckdb` (§7.3): `track_truth`, `true_paths`, `clue_truth`, `assessment_truth`.
  Only `sim.writers` writes it and only `kairos_defense.eval` reads it; this package defines the
  DDL only.
- `data/lancedb/`: `flight_windows`, with scalar indexes on `window_s`, `start_ts_ms` and
  `incident_id`. `reports` and `swarm_windows` are keyed here for phases 5 and 9.

## How it works

- `connect_app_db` compares resolved paths, then `os.path.samefile`, so symlinks and hard links to
  the truth file are caught.
- The RF and Remote ID window joins bucket time by the window width. Each track point is repeated for
  its own bucket and both neighbors, the join is an equi-join on (installation, bucket), and the exact
  filter runs after it. DuckDB 2.0 plans the naive range join about 100 times slower (`_bucket`).
- `context_asof` uses DuckDB's `ASOF LEFT JOIN` on `weather` per region (§11.1).
- LanceDB filters use plain columns only. Times are int64 epoch milliseconds (`*_ts_ms`, §7.5).

## Configuration

- `app.paths.duckdb`, `app.paths.truth` (the guard reads it so it can refuse it), `app.paths.lancedb`.

## Tests

- `tests/unit/test_truth_isolation.py`: the §7.6 scan and the guard against every path spelling.
- `tests/unit/test_duck_store.py`: the RF bearing gate on concurrent tracks, Remote ID ±5 s / 100 m,
  as-of weather, events, strict `tracks_before`, truth refused; `sensor_context_until` ignores
  everything heard after `until`, concurrency uses only tracks seen by `until`, `features_many`
  equals `features` per track.
- `tests/unit/test_index.py` and `tests/unit/test_no_lookahead.py` exercise both adapters end to end.
- Run: `uv run pytest tests/unit -q -k "truth or duck or index or lookahead"`.

## Gotchas

- Do not open DuckDB with `duckdb.connect` in app code. Use `connect_app_db`, or the scan and the
  guard tests will (rightly) fail.
- `DuckTrackStore` opens read-only by default. Pass `read_only=False` to write derived tables.
- DuckDB allows one writer per file. Close stores (use `with`) before another process writes.
- `tracks_before` is strict (`<`). A track never matches itself or anything that started after it.
- `_distance` is squared L2, not cosine. The two rank the same only because window vectors are unit
  length.
- `sensor_context_until` runs the RF association SQL for one track: about 17 ms on the laptop,
  once per live query. A KDB-X adapter (§22) needs `features_many` and `sensor_context_until` too.

## Changelog

- Phase 0: `guard.py` (D-008).
- Phase 1: `ddl.py`, the §7.1 raw and §7.3 truth DDL.
- Phase 3: §7.2 derived DDL, `duck.py` (`DuckTrackStore`, §11 joins, D-048) and `lance.py`
  (`LanceVectorStore`, D-052).
- Phase 4: `features_many`, `sensor_context_until` and the `until` bound on the association
  queries (D-071, D-072).
