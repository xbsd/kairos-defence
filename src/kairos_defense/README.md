# kairos_defense

The top-level package: the CLI entry point and the four core modules every other package uses
(`ports`, `rng`, `geo` and `config`, which is documented in `config/README.md`).

## Responsibilities

- `cli.py`: the `kairos-defense` Typer app, and the composition root that builds the store adapters.
  Commands not built yet are stubs that name their phase (D-022). `cli_recall.py` holds the
  phase 5 commands (`forecast`, `recall`, `fetch-models`), registered on the same app (D-091).
- `ports.py`: the §4.1 Protocols business logic depends on, instead of DuckDB or LanceDB (rule 6).
- `rng.py`: per-component random streams derived from the global seed (rule 4, §8.9).
- `geo.py`: geometry in local ENU meters. Bearings are clockwise from north in [0, 360) (D-007).

## Public API

- `cli.app`: the Typer app (script `kairos-defense`).
  - Real commands: `gen` (phase 1, extended in phase 2), `index` (phase 3; from phase 5 it also
    builds the LanceDB `reports` table with its full-text index and the DuckDB `report_clues`
    table, D-089), `models` (phase 4), `match --method dtw|euclidean` and
    `eval [--baseline] [--method dtw|euclidean]` (phase 3; DTW and the `dtw` default from phase
    4), and from phase 5:
    - `forecast --incident ID --at S [--track T] [--method dtw|euclidean]`: the §13 recovery zone
      (center, radius, analogs, exit path, roads crossing the zone);
    - `recall --incident ID --at S [--track T] [--matches 3] [--k 5] [--query TEXT]`: the reports
      behind the top matched incidents, with clue spans and link sentences (§12);
    - `fetch-models [--model M]`: the **only** command that downloads anything, and only when run
      by hand: the optional FastEmbed model into `paths.cache`. Without the `fastembed` extra it
      exits 1 naming `uv sync --extra fastembed`. The hashing embedder stays the offline default
      (D-084, CLAUDE.md rule 5).
  - Fix-it exits (exit 1): missing data, a missing or stale index, a missing or stale reports
    index, missing models, a missing DTW C extension, an unavailable embedder, an unknown incident,
    track or method.
  - Stubs in `STUBS`: `replay`, `memory`, `export`, `verify-evidence`, `api` and `mcp`.
  - `--version`.
- `ports`:
  - `TrackStore`: `track_points`, `features`, `features_many`, `sensor_context_until`,
    `signature`, `tracks_before`, `context_asof`, `sql` (the two phase 4 additions, D-072).
  - `VectorStore`: `upsert`, `search`.
  - `ReportIndex`: `hybrid`, `fts`. `hybrid` may raise `NotImplementedError` when the backend
    has no native hybrid search; callers then fuse the vector and FTS results themselves
    (`recall.search.hybrid_search`, §12.5, D-085). The signatures are unchanged.
  - `Embedder`: `dim`, and `embed(texts) -> (n, dim) float32`, L2-normalized.
  - `CaseMemory`: `append`, `as_of`, `diff`, and `verify_chain() -> int | None` (D-014).
  - `LLM`: `chat`.
  - `CaseSnapshot`, a dataclass.
- `cli_tables`: the `match`, `models`, `eval`, `forecast` and `recall` tables (`match_table`,
  `models_table`, `eval_table`, `analogs_table`, `recall_table`, and `marked_text`, which
  underlines clue spans and bolds linked ones); missing numbers print as `-`.
- `cli_recall`: `forecast_cmd`, `recall_cmd`, `fetch_models_cmd`, `describe_center(fc, q)` and
  `register(app)`. Shared helpers are looked up on `kairos_defense.cli` at call time.
- `rng.stable_int(name) -> int`: the first 8 bytes of SHA-256, little-endian.
- `rng.rng_for(seed, *names) -> numpy.random.Generator`: an independent stream per component, e.g.
  `rng_for(42, "P2", "flight", "7")`.
- `geo`: all arrays are `(..., 2) float64` meters and scalars broadcast.
  - Angles: `wrap360` (into [0, 360), never 360.0 or −0.0) and `wrap180` (into [−180, 180)).
  - `bearing(from_xy, to_xy) -> (...)` degrees. Coincident points give 0.
  - `heading_vector(bearing_deg)` and `destination(origin, bearing, distance_m)`.
  - `rotate(xy, deg, about)`: clockwise, so it adds `deg` to a vector's bearing.
  - `rectangle_polygon(center, size, rotation_deg) -> shapely.Polygon`.
  - Frame transforms:
    - `installation_to_region` and `region_to_installation`: rotate clockwise, then shift;
    - `polygon_to_region`;
    - `region_to_target` and `target_to_region`: shift only, §9.2.

## Data in and out

None directly. `cli.py` reads `config/` and wires `store`, `sim`, `features`, `match`, `recall`,
`forecast` and `eval`.

## How it works

- `rng_for` builds `SeedSequence(seed, spawn_key=(stable_int(n) for n in names))`. A stream depends
  only on the seed and its names, so adding an actor never shifts another actor's draws.
- The geo frames:
  - installation-local, the template frame;
  - region, which is installation-local rotated clockwise by `rotation_deg`, then shifted by
    `origin_m`;
  - target-relative, which is region shifted so the target centroid is at the origin (§6.2, §9.2).
- The CLI prints user errors through `rich`, never as raw tracebacks (§21). Typer's pretty exceptions
  are off.

## Configuration

`cli.py` takes `--config <folder>` (default `config`) on its real commands. The others read nothing.
Phase 5 added `paths.cache` (the FastEmbed cache, `app.yaml`) and `forecast.anchor`
(`scoring.yaml`); see `config/README.md`.

## Tests

- `tests/unit/test_cli.py`: help lists every command; each of the six stubs exits 0 and names its
  phase; `--version`; the real commands' error and happy paths (`match` with both methods,
  `models` on the P1 nights, missing data, index and models). Phase 5:
  `test_forecast_cli_runs_on_the_p1_nights`, `test_recall_cli_runs_on_the_p1_nights`,
  `test_recall_needs_reports_index` (also `eval`), `test_forecast_unknown_incident_exits_1`,
  `test_forecast_needs_models`, `test_fetch_models_without_fastembed_exits_1`.
- `tests/unit/test_rng.py`: pinned values and stream independence.
- `tests/unit/test_geo.py`: cardinals, wrap edges, clockwise rotation, rectangles, frame round trips.
- Run: `uv run pytest tests/unit -q -k "cli or rng or geo"`.

## Gotchas

- Never call `np.random.default_rng()` without a seed, and never use the global `np.random`. Take a
  `Generator` from `rng_for` and pass it in explicitly.
- `shapely.affinity.rotate` turns counter-clockwise for positive angles. `geo` negates the angle, so
  use the `geo` helpers.
- Nothing here may depend on DuckDB or LanceDB. Add a port method instead (rule 6, §22).

## Changelog

- Phase 0: `cli.py` (14 stubs), `ports.py`, `rng.py`, `geo.py`.
- Phase 1: `gen` became real.
- Phase 2: `gen` gained the swarm, RF, Remote ID and paperwork counts.
- Phase 3: `index`, `match --method euclidean` and `eval [--baseline]` became real.
- Phase 4: `models` became real; `match` and `eval` default to `--method dtw`; `cli_tables.py`;
  `TrackStore.features_many` and `sensor_context_until` (D-072, D-076).
- Phase 5: `recall`, `forecast` and `fetch-models` became real (`cli_recall.py`); `index` also
  builds the `reports` index and `report_clues`; `eval` needs the reports index; forecast and
  recall tables in `cli_tables.py`.
