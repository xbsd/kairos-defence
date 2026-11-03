# kairos_defense.store

Storage adapters: DuckDB and LanceDB behind the ports in `kairos_defense.ports`, plus the
truth-isolation guard every app connection goes through.

## Responsibilities

- Refuse the ground-truth file to all app code, however its path is spelled (`guard.py`; CLAUDE.md
  rule 2, SPEC §7.6).
- Hold the DDL for the raw, derived and truth tables (`ddl.py`; §7.1 to §7.3).
- Implement `TrackStore` over DuckDB, including the §11 context joins and the bulk queries the index
  build needs (`duck.py`).
- Implement `VectorStore` and `ReportIndex` over LanceDB. All LanceDB calls live here (`lance.py`,
  D-014).
- Implement `CaseMemory` over DuckDB: the §15.1 ledger in `data/memory.duckdb`, one writer, rows
  only ever inserted (`ledger_duck.py`, D-092, D-093).
- Implement `LiveSink` over DuckDB (`live_duck.py`: the `live_*` scratch tables in
  `data/live.duckdb`, D-103) and `ResultCache` over JSON files (`live_cache.py`, D-104).
- Business logic imports the ports, never these modules directly (rule 6). Only index builds and
  composition roots such as `cli.py` construct the adapters (D-053).
- Live mode (phase 11, D-172): the live-mode store over `<live_mode>/feed.duckdb`
  (`live_feed.py`, the `LiveFeed` port plus `TrackStore` reads on live rows) and the history plus
  learned live history behind the same ports (`composite.py`).

## Public API

- `guard.connect_app_db(path, app, *, read_only=False) -> duckdb.DuckDBPyConnection`: opens an app
  DuckDB file or `:memory:`. Raises `TruthAccessError` if `path` is the truth file (relative, `..`,
  symlink or hard link). Creates the parent folder.
- `guard.is_truth_path(path, app) -> bool`; `guard.refuse_truth(path, app)` raises
  `TruthAccessError` for the truth file (for code that reaches a file without `connect_app_db`,
  such as the ledger's `ATTACH` copy).
- `guard.TruthAccessError(PermissionError)`.
- `ddl.RAW_DDL`, `ddl.TRUTH_DDL` and `ddl.DERIVED_DDL` (`dict[name, CREATE TABLE]`),
  `ddl.DERIVED_COLUMNS`, and `ddl.columns(ddl) -> list[str]`. `ddl.LEDGER_DDL`,
  `ddl.LEDGER_ASOF_MACRO` (verbatim §15.1) and `ddl.LEDGER_COLUMNS`.
- `ddl.LIVE_DDL`, `ddl.LIVE_SOURCES`, `ddl.LIVE_COLUMNS`: `live_points`, `live_rf`, `live_rid`
  with the columns of `track_points`, `rf_detections`, `remote_id` (§16.2, D-103).
- `live_duck.DuckLiveSink(path, app)` (the `LiveSink` port): `append(table, rows) -> IngestStat`
  (one insert, timed; `statement` like `INSERT INTO live_points … 3 rows`), `count(table)`,
  `reset() -> {table: rows removed}` (only the `live_*` tables). `live_duck.statement(table, n)`.
- `live_cache.FileResultCache(root)` (the `ResultCache` port): `get(incident, name)`, `put(incident,
  name, doc)` (atomic, strict JSON), `clear(incident)`; names like `manifest`, `features`, `t0045`.
- `ledger_duck.reseed_ledger(path, app, store, scenario) -> SeedSummary` (seed a temp file, verify,
  close, drop stale WAL files, `os.replace`; raises `LedgerLocked` when another process holds the
  file) and `ledger_duck.check_unlocked(path, app)`: shared by `memory reseed` and
  `POST /api/admin/reseed` (D-010, D-104).
- `ledger_duck.DuckCaseMemory(path, app, *, read_only=False)` (the `CaseMemory` port, §15):
  context manager. Creates the table and macro if missing; refuses a different schema ("run
  `memory reseed`"); `read_only=True` on a missing file raises `LedgerError` ("run `memory
  seed`"); a file held by another process raises `LedgerLocked`.
  - Port: `append(event) -> seq`, `append_many(events) -> seqs` (validated, sealed and inserted in
    one transaction, all or nothing), `events(after=None, until=None)` (rows with
    `after < recorded_at <= until`, seq order, `object_json` parsed), `as_of`, `diff`,
    `verify_chain` (the pure functions in `kairos_defense.memory`).
  - Extras: `head() -> Head | None`, `count()`, `rows_for_seqs(seqs)`, `checkpoint()`,
    `copy_from(path)` (copies another ledger's rows unchanged into this empty one through
    `ATTACH … (READ_ONLY)`; the demo's scratch copy).
  - One connection behind an `RLock`: appends from several threads get contiguous seqs.
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
    `SCALAR_INDEXES` and the full-text index in `FTS_COLUMNS` (`reports.text`, with token
    positions for phrase queries, D-085).
  - `tables()`, `has()`, `count(table, where)`, `to_pandas(table, columns)`.
- `lance.LanceReportIndex(uri, table="reports")` (the `ReportIndex` port, §12):
  - `hybrid(text, vector, where, k)`: LanceDB's native hybrid search, pre-filtered on both sides,
    fused by `ReportRRF` (`RRFReranker`, K = 60, equal scores ordered by `report_id`); returns
    `REPORT_COLUMNS` plus `_relevance_score`. Raises `NotImplementedError` when the installed
    LanceDB cannot run it (§12.5, D-085).
  - `fts(text, where, k)`: native BM25 keyword search; `REPORT_COLUMNS` plus `_score`. A quoted
    phrase matches exactly; the tokenizer lowercases.
  - Empty results keep the columns.
- `lance.REPORTS_TABLE`, `lance.REPORT_COLUMNS` (§7.5 without the vector), `lance.FTS_COLUMNS`.
- Phase 11:
  - `live_feed.DuckFeedStore(folder, app, sensors=None)` (a `DuckTrackStore` over
    `feed.duckdb`, one connection behind an `RLock`): `append(table, rows) -> IngestStat`
    (`live_points`, `live_rf`, `live_rid`), `put_incident(row)`, `put_track(row)`,
    `learn(features, signatures)`, `add_result(row)`, `results(incident)`, `incidents()`,
    `incident(id)`, `live_tracks(incident=None)`, `count(table)`, `counts()`, `reset()`,
    `reader()` (a `DuckTrackStore` on its own cursor, for the live worker). Views
    `track_points`, `rf_detections`, `remote_id` and `incidents` over the live tables, and a copy
    of `sensors`. `RESET_TABLES`, `FEED_FILE`, `VECTORS_DIR`.
  - `composite.CompositeTrackStore(main, live)` and `composite.CompositeVectorStore(main,
    live)`: unions and merges (`tracks_before` by start time, `search` by `_distance`); `LIVE-`
    ids belong to the live side; `upsert` writes the live side only. `composite.is_live_id`.
  - `duck.DuckTrackStore.over(con, path)`; `live_duck.append_rows(con, table, cols, rows)`;
    `lance.LanceVectorStore.upsert` stores a `vector` key as a fixed-size float32 list;
    `LanceVectorStore.drop(table)`.

## Data in and out

- `data/kairos_defense.duckdb`:
  - raw tables (§7.1), written by `sim.writers`: `regions`, `installations`, `assets`, `roads`,
    `parks`, `sensors`, `incidents`, `track_points`, `rf_detections`, `remote_id`, `weather`,
    `base_events`, `public_events`, `reports`, `assessments`;
  - derived tables (§7.2), written by `kairos-defense index`, history tracks only (D-049):
    `track_features`, `track_signatures`, `report_clues` (phase 5, history reports, D-089) and
    `swarm_features` (phase 9, §7.2: one row per described second of each history swarm
    incident, D-149).
- `data/truth.duckdb` (§7.3): `track_truth`, `true_paths`, `clue_truth`, `assessment_truth`.
  Only `sim.writers` writes it and only `kairos_defense.eval` reads it; this package defines the
  DDL only.
- `data/memory.duckdb` (§7.4, §15.1): table `ledger` and macro `ledger_asof(t)`, written only by
  `DuckCaseMemory` (insert only, rule 7).
- `data/lancedb/`: `flight_windows`, with scalar indexes on `window_s`, `start_ts_ms` and
  `incident_id`; `reports` (§7.5, phase 5) with a full-text index on `text`; `swarm_windows`
  (§7.5, phase 9: one 96-d vector per history swarm incident, keyed by `incident_id`, with the
  §7.5 columns plus `region_id`, `duration_s`, `together_s` and `is_swarm`, D-149).
- Phase 11: `<live_mode>/feed.duckdb` (`live_points`, `live_rf`, `live_rid`, `sensors`,
  `live_incidents`, `live_tracks`, `track_features`, `track_signatures`, `live_results`) and
  `<live_mode>/vectors` (`flight_windows` of learned live tracks).

## How it works

- `connect_app_db` compares resolved paths, then `os.path.samefile`, so symlinks and hard links to
  the truth file are caught.
- The RF and Remote ID window joins bucket time by the window width. Each track point is repeated for
  its own bucket and both neighbors, the join is an equi-join on (installation, bucket), and the exact
  filter runs after it. DuckDB 2.0 plans the naive range join about 100 times slower (`_bucket`).
- `context_asof` uses DuckDB's `ASOF LEFT JOIN` on `weather` per region (§11.1).
- LanceDB filters use plain columns only. Times are int64 epoch milliseconds (`*_ts_ms`, §7.5).

## Configuration

- `app.paths.duckdb`, `app.paths.truth` (the guard reads it so it can refuse it), `app.paths.lancedb`,
  `app.paths.memory` (via the CLI).

## Tests

- `tests/unit/test_truth_isolation.py`: the §7.6 scan and the guard against every path spelling.
- `tests/unit/test_duck_store.py`: the RF bearing gate on concurrent tracks, Remote ID ±5 s / 100 m,
  as-of weather, events, strict `tracks_before`, truth refused; `sensor_context_until` ignores
  everything heard after `until`, concurrency uses only tracks seen by `until`, `features_many`
  equals `features` per track.
- `tests/unit/test_index.py` and `tests/unit/test_no_lookahead.py` exercise both adapters end to end.
- `tests/unit/test_recall_index.py` (phase 5): the `reports` schema, an exact phrase through FTS,
  filters on base and time for hybrid, FTS and vector search, `report_clues`, the stale guard;
  `tests/unit/test_recall_search.py`: native hybrid equals the §12.5 fallback row for row.
- `tests/unit/test_memory_ledger.py` (phase 6): tamper tests caught at the exact seq, atomic
  batches, concurrent appends, validation, the `ledger_asof` macro against `active_rows`, read-only
  and truth refusal, schema refusal, `copy_from`; `test_memory_append_only.py` scans `src/` for
  ledger mutations.
- Run: `uv run pytest tests/unit -q -k "truth or duck or index or lookahead or recall or memory"`.
Phase 11: `tests/unit/test_live_stores.py` (views and the §11.2 SQL on live rows, state rows,
reset, truth refused, composite unions and the vector merge).

## Gotchas

- Do not open DuckDB with `duckdb.connect` in app code. Use `connect_app_db`, or the scan and the
  guard tests will (rightly) fail.
- `DuckTrackStore` opens read-only by default. Pass `read_only=False` to write derived tables.
- DuckDB allows one writer per file. Close stores (use `with`) before another process writes.
  While a process holds `memory.duckdb` read-write, no other process can open it, even read-only
  (checked on DuckDB 2.0.0).
- The ledger's `object_json` is stored as canonical JSON text and hashed as a parsed object; the
  insert goes through a pyarrow table so NULLs stay NULL (a pandas float column would turn them
  into NaN).
- `tracks_before` is strict (`<`). A track never matches itself or anything that started after it.
- `_distance` is squared L2, not cosine. The two rank the same only because window vectors are unit
  length.
- `sensor_context_until` runs the RF association SQL for one track: about 17 ms on the laptop,
  once per live query. A KDB-X adapter (§22) needs `features_many` and `sensor_context_until` too.
- LanceDB filters reject a float literal on an int64 column (`event_ts_ms < 9e15` fails): write
  integers.
- `create_fts_index` (CLAUDE.md's library note) is deprecated in LanceDB 0.40; `replace` uses
  `create_index(col, config=FTS(with_position=True))` (D-085).

## Changelog

- Phase 0: `guard.py` (D-008).
- Phase 1: `ddl.py`, the §7.1 raw and §7.3 truth DDL.
- Phase 3: §7.2 derived DDL, `duck.py` (`DuckTrackStore`, §11 joins, D-048) and `lance.py`
  (`LanceVectorStore`, D-052).
- Phase 4: `features_many`, `sensor_context_until` and the `until` bound on the association
  queries (D-071, D-072).
- Phase 5: `report_clues` DDL; the `reports` FTS index; `LanceReportIndex` and `ReportRRF`
  (D-085, D-089).
- Phase 6: the §15.1 ledger DDL and macro; `ledger_duck.py` (`DuckCaseMemory`); `guard.refuse_truth`
  (D-092, D-093, D-102).
- Phase 7: `LIVE_DDL`; `live_duck.py` (`DuckLiveSink`), `live_cache.py` (`FileResultCache`);
  `reseed_ledger` and `check_unlocked` moved here from the CLI (D-103, D-104). DuckDB 2.0: fetch a
  result fully (`fetchall`) before `register()`.
- Phase 9: `swarm_features` DDL (the §7.2 columns); `swarm_windows` written through
  `LanceVectorStore.replace` (D-149).
- Phase 11: `live_feed.py`, `composite.py`; `DuckTrackStore.over`, `live_duck.append_rows`,
  `LanceVectorStore.upsert` (fixed-size vectors) and `drop` (D-172).
