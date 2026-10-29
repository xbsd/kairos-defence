# kairos_defense.config

Pydantic models for the five YAML files in `config/` and the one loader that validates them together.

## Responsibilities

- One frozen, strict model per YAML file (SPEC §6, D-016). Unknown keys are an error.
- Parse YAML with YAML 1.2 booleans, so `rid: off` stays the string `"off"` (D-017).
- Check references across files: bases, targets, roads, swarm teams and P1 flights (D-018).
- Resolve `app.paths.*` and `signing.key_path` against the project root, so every command works from
  any directory.

## Public API

- `load_config(config_dir="config") -> Config`: loads and validates all five files. Raises
  `ConfigError` naming the file and the first problems.
- `Config`: `root: Path` (project root), `app: AppConfig`, `world: WorldConfig`,
  `actors: ActorsConfig`, `scenario: ScenarioConfig`, `scoring: ScoringConfig`.
- `ConfigError(ValueError)`: a file is missing, cannot be parsed or is invalid.
- `load_yaml(path) -> Any`: the YAML 1.2 loader. Use it instead of `yaml.safe_load`.
- `CONFIG_FILES`: model name → file name (`scenario` → `scenario_demo.yaml`).
- Per-file models:
  - `app.py`: `AppConfig`, `PathsConfig`, `EmbeddingsConfig`, `LlmConfig`, `SigningConfig`,
    `ReplayConfig`.
  - `world.py`: `WorldConfig` (with `installation(id)`, `region_of(id)` and `installation_ids()`),
    `Region`, `Road`, `Park`, `Installation`, `InstallationTemplate`, `Asset`, `TerrainMask`,
    `RadarSensor`, `RfSensor`, `RidSensor`, `CalendarConfig`.
  - `actors.py`: `ActorsConfig`, `Hobbyists`, `Prober`, `Copycat`, `Swarm`, the pattern models,
    `Launch`, `Clues`, `FormationStep`, `ActionStep`.
  - `scenario.py`: `ScenarioConfig`, `P1Flight`, `SwarmEvent`, `PlantedReport`, `PlantedAssessment`,
    `ReportClue` (field `is_true`, alias `true`), `Expectations`.
  - `scoring.py`: `ScoringConfig` (with `vector_dim`, the PAA window length = channels × segments,
    80 by default), `FeaturesConfig`, `WindowsConfig`, `PrefilterConfig`,
    `DtwConfig`, `FusionConfig`, `LiveConfig`, `RecallConfig`, `ForecastConfig`,
    `SwarmScoringConfig`.
- `_types.py`: shared field types. `Bearing` is in [0, 360); `Range` and `IntRange` must be ordered
  `[lo, hi]`; `HHMM` is a local time; `TimeWindow` may wrap past midnight; `Pos`, `NonNeg` and `Prob`.
  Also `StrictModel` and `unique_ids()`.

## Data in and out

- In: `config/app.yaml`, `world.yaml`, `actors.yaml`, `scenario_demo.yaml` and `scoring.yaml`, which
  are byte-for-byte copies of SPEC §6.1 to §6.5.
- Out: an immutable `Config` object. Nothing is written.

## How it works

1. `_read` loads each file with `load_yaml`. The `_Yaml12Loader` drops PyYAML's YAML 1.1 boolean
   resolver and accepts only `true` and `false`. `_string_keys` turns boolean mapping keys into
   `"true"` and `"false"`.
2. `_resolve_paths` makes `paths.*` and `signing.key_path` absolute against the parent of `config/`.
3. Each file is validated with its model. A `ValidationError` becomes a `ConfigError` that names the
   file.
4. The root `Config` model runs `_cross_refs`:
   - actor bases exist;
   - targets are template assets or `fence`;
   - `snap_to_road` names a road, and each road's actor is a prober;
   - P1 exists and its scenario flights use P1's bases;
   - swarm events name a known team on one of its bases.

## Configuration

This package defines every key. See SPEC §6 for meanings and defaults.

Phase 4 additions and changed values in `scoring.yaml` (D-068):

- `features.channel_scales`: one positive unit per channel, `[5.0, 10.0, 200.0, 30.0, 1.0]` (m/s,
  °/s, m, m, m/s); validated to match `channels` in length.
- `windows.normalize`: `fixed` (divide by `channel_scales`) or `window` (per-window z, §9.3).
- `prefilter.k_windows` 10,000 (§6.5 says 200) and `prefilter.candidate_tracks` 500 (§6.5 says 50).
- `dtw.tau`: `auto` reads `models/dtw_calibration.json`; a positive number overrides it.
- `dtw.normalize`: `series` (§9.3), `floored` or `fixed` (the default since the first gate fix,
  D-079): how the DTW shape distance scales each channel. Changing it needs `make models`.

## Tests

- `tests/unit/test_config.py`, 40 tests: the shipped files load; decision values survive (D-003,
  D-004, D-006); YAML 1.2 booleans; root-relative paths; frozen models; 33 invalid variants rejected
  (phase 4 added `channel_scales` of the wrong length or not positive, and unknown
  `windows.normalize` and `dtw.normalize` values); missing and unparsable files reported.
- Run: `uv run pytest tests/unit/test_config.py -q`.

## Gotchas

- Never use `yaml.safe_load` on these files. `rid: off` would become `False`.
- Two fields are renamed in Python but keep their YAML names: `Road.build` (YAML `construct`, which
  would shadow `BaseModel.construct`) and `ReportClue.is_true` (YAML `true`).
- Models are frozen. For a variant in tests, use `cfg.model_copy(update=...)`, as `tests/conftest.py`
  does with `tmp_config`.
- Paths in `cfg.app.paths` are absolute strings. `cfg.root` is the project root.
- Truth path: only `eval/`, `sim/writers.py` and `store/guard.py` may mention it (§7.6, D-008).

## Changelog

- Phase 0: package created (D-016 to D-018).
- Phase 4: `features.channel_scales`, `windows.normalize`; prefilter widened to 10,000 windows and
  500 tracks (D-068). Changing either vector key needs `make index`.
- Phase 4 gate fix 1: `dtw.normalize` (D-079).
