# kairos_defense

The top-level package: the CLI entry point and the four core modules every other package uses
(`ports`, `rng`, `geo` and `config`, which is documented in `config/README.md`).

## Responsibilities

- `cli.py`: the `kairos-defense` Typer app, and the composition root that builds the store adapters.
  Commands not built yet are stubs that name their phase (D-022).
- `ports.py`: the §4.1 Protocols business logic depends on, instead of DuckDB or LanceDB (rule 6).
- `rng.py`: per-component random streams derived from the global seed (rule 4, §8.9).
- `geo.py`: geometry in local ENU meters. Bearings are clockwise from north in [0, 360) (D-007).

## Public API

- `cli.app`: the Typer app (script `kairos-defense`).
  - Real commands: `gen` (phase 1, extended in phase 2), `index` (phase 3), `models` (phase 4),
    `match --method dtw|euclidean` and `eval [--baseline] [--method dtw|euclidean]` (phase 3; DTW
    and the `dtw` default from phase 4). `match`, `models` and `eval` exit 1 with a fix-it message
    for missing data, a missing or stale index, missing models or a missing DTW C extension.
  - Stubs in `STUBS`: `recall`, `forecast`, `replay`, `memory`, `export`, `verify-evidence`,
    `fetch-models`, `api` and `mcp`.
  - `--version`.
- `ports`:
  - `TrackStore`: `track_points`, `features`, `features_many`, `sensor_context_until`,
    `signature`, `tracks_before`, `context_asof`, `sql` (the two phase 4 additions, D-072).
  - `VectorStore`: `upsert`, `search`.
  - `ReportIndex`: `hybrid`, `fts`.
  - `Embedder`: `dim`, and `embed(texts) -> (n, dim) float32`, L2-normalized.
  - `CaseMemory`: `append`, `as_of`, `diff`, and `verify_chain() -> int | None` (D-014).
  - `LLM`: `chat`.
  - `CaseSnapshot`, a dataclass.
- `cli_tables`: the `match`, `models` and `eval` tables (`match_table`, `models_table`,
  `eval_table`); missing numbers print as `-`.
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

None directly. `cli.py` reads `config/` and wires `store`, `sim`, `features`, `match` and `eval`.

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

## Tests

- `tests/unit/test_cli.py`: help lists every command; each stub exits 0 and names its phase;
  `--version`; the real commands' error and happy paths (`match` with both methods, `models` on
  the P1 nights, missing data, index and models).
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
