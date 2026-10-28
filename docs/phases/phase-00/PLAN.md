# Phase 0: Scaffold, plan

> **Backfilled 2026-10-28, as built.** Phase 0 was built by hand in a Claude Code cloud session
> before the autopilot existed, and no plan file was kept. This plan is reconstructed from commit
> `f9258de` (`phase 0: scaffold`), the phase 0 entry in `docs/PROGRESS.md` and D-015 to D-022 in
> `docs/DECISIONS.md`. It describes what was planned and built, not a plan for new work.

## Goal

A runnable skeleton (SPEC §20, phase 0): tooling, configuration models, ports and CLI stubs for
Python, and a web scaffold with the §17.1 design tokens and one placeholder screen. Nothing
generates data yet. Every later phase builds on these files.

## Inputs read

- `CLAUDE.md`: rules 1 to 10, code conventions, verified library notes.
- SPEC §2 (scope), §3 (tech stack and pinned versions), §4 and §4.1 (architecture, ports), §5
  (repository layout, Makefile targets), §6.1 to §6.5 (the five YAML files, copied verbatim), §7.6
  (truth-isolation guard and scan), §8.9 (`rng.py`), §17.1 (tokens, fonts), §21 (definition of done,
  front-end rules), §20 phase 0 block.
- `docs/DECISIONS.md` D-001 to D-015, mainly D-002 (Node 22 and Python 3.12), D-007 (frames and
  clockwise rotation), D-008 (the guard may name the truth path), D-014 (`make check` includes
  `npm --prefix web run check`) and D-015 (kit committed first so the build can run in the cloud).
- `docs/PROGRESS.md`, pre-phase-0 entry: check every pinned library version against what installs.

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md`:

- **D-016**: `kairos_defense.config` is a package (one module per YAML file, about 600 lines in all).
  The import path is unchanged.
- **D-017**: the YAML loader uses YAML 1.2 booleans, so `rid: off` stays the string `"off"` and the
  clue key `true:` becomes the string `"true"`. Fields `is_true` (alias `true`) and `build` (alias
  `construct`).
- **D-018**: every model is frozen and forbids unknown keys. Ranges must be ordered, times are `HH:MM`
  and may wrap past midnight, and bearings are in [0, 360). Cross-file reference checks run, and paths
  resolve against the project root.
- **D-019**: web pins: TypeScript `~6.0.3` (for typescript-eslint), jsdom 29 (Node 22.22.0 in the
  cloud), React exactly `19.3.1` (R3F peer). Only what the placeholder needs is installed.
- **D-020**: Python pins are lower bounds. The lockfile resolves duckdb 2.0.0, lancedb 0.40.0 and
  dtaidistance 2.5.1. The dtaidistance C path was checked on the cloud machine.
- **D-021**: `tokens.css` keeps the §17.1 `:root` block verbatim. Tailwind's defaults are reset, and
  ESLint rejects hex literals.
- **D-022**: 14 Typer stubs that accept and ignore options and name their phase. `test-all`, `clean`,
  `web` and `dev` are Makefile-only. Ruff excludes `*.md`.

## Work breakdown

1. **Python project.** `pyproject.toml` (hatchling, src layout, §3 dependencies as lower bounds,
   optional `fastembed`, dev group pytest and ruff, script `kairos-defense = kairos_defense.cli:app`,
   ruff and pytest settings with a `slow` marker), `uv.lock`, `.python-version` (3.12), `.gitignore`
   (`data/`, `exports/`, caches, `web/node_modules`, `web/dist`).
2. **Makefile.** All §5 targets plus `help`. `check` runs `ruff check .`, `ruff format --check .`,
   `pytest -m "not slow" -q` and `npm --prefix web run check`. The Makefile puts
   `/opt/homebrew/opt/node@22/bin` first on PATH when it exists (D-002).
3. **Configuration.** `config/{app,world,actors,scenario_demo,scoring}.yaml` copied byte for byte from
   §6. Models in `src/kairos_defense/config/` (`app.py`, `world.py`, `actors.py`, `scenario.py`,
   `scoring.py`, shared `_types.py` and `_yaml.py`). `__init__.py` holds `Config`, the cross-file
   checks, `ConfigError` and `load_config()`.
4. **Core modules.** `ports.py` (§4.1 Protocols: `TrackStore`, `VectorStore`, `ReportIndex`,
   `Embedder`, `CaseMemory`, `LLM`, plus the `CaseSnapshot` dataclass), `rng.py` (§8.9 verbatim),
   `geo.py` (bearing, wrap180, wrap360, heading vector, destination, clockwise rotate, rectangle
   polygon, installation ↔ region ↔ target frames).
5. **Truth isolation.** `store/guard.py` (`connect_app_db`, `is_truth_path`, `TruthAccessError`,
   refusing relative, `..`, symlink and hard-link spellings). `eval/__init__.py` (empty package, the
   only allowed truth reader).
6. **CLI.** `cli.py`: Typer app with `--version` and 14 stubs (`gen`, `index`, `models`, `eval`,
   `match`, `recall`, `forecast`, `replay`, `memory`, `export`, `verify-evidence`, `fetch-models`,
   `api`, `mcp`). Each stub prints the phase that implements it and exits 0.
7. **Web scaffold.** `web/package.json` (engines Node 22, scripts `dev`, `build`, `lint`,
   `typecheck`, `test`, `check`), `package-lock.json`, `vite.config.ts` (React plugin,
   `@tailwindcss/vite`, `/api` proxy to :8000, Vitest jsdom), `tsconfig.json` (strict),
   `eslint.config.js` (typescript-eslint strict, react-hooks, no `any`, no hex literals), Prettier,
   `index.html`. In `src/`: `theme/tokens.css`, `theme/fonts.ts` (B612 400/700, B612 Mono 400 via
   `@fontsource`), `theme/motion.ts` (`parseCssTimeMs`, `durationMs`, `prefersReducedMotion`),
   `app/CommandBar.tsx`, `app/App.tsx` (placeholder Live watch: "No replay loaded"), `main.tsx`,
   `index.css`.
8. **Docs.** PROGRESS.md entry, D-016 to D-022, one commit `phase 0: scaffold`.

## Tests

Python (`tests/unit`, fast):

- `test_config.py`
  - `test_shipped_config_loads`: the five shipped files load.
  - `test_decision_values_survive_loading`: values fixed by D-003, D-004 and D-006 survive loading
    (P1 cruise 15 m/s, orbit 3°/s, BRAVO terrain mask, the County Rd 12 road).
  - `test_yaml_12_booleans`: `rid: off` is `"off"`; the clue key `true:` is `"true"`.
  - `test_paths_resolve_against_project_root`.
  - `test_models_are_frozen`.
  - `test_invalid_config_is_rejected`: 29 parametrized bad variants (unknown keys, reversed ranges,
    bad `HH:MM`, bearings outside [0, 360), unknown bases, targets, roads and teams, and others).
  - `test_missing_file_is_reported`, `test_unparsable_yaml_is_reported`.
- `test_geo.py`
  - `test_bearing_cardinals`, `test_bearing_vectorized_and_coincident`,
    `test_bearing_just_west_of_north_stays_below_360`.
  - `test_wrap` (edge cases), `test_wrap360_never_returns_360_or_negative_zero`.
  - `test_destination_and_heading`, `test_rotate_is_clockwise`, `test_rotate_adds_to_bearing`.
  - `test_rectangle_polygon`, `test_rectangle_rotation_matches_point_rotation`.
  - `test_installation_region_round_trip`, `test_polygon_to_region`,
    `test_target_frame_is_shift_only`.
- `test_rng.py`
  - `test_stable_int_is_pinned`, `test_draws_are_pinned`.
  - `test_same_names_same_draws`, `test_different_names_different_draws`.
  - `test_name_order_and_seed_matter`, `test_adding_a_component_leaves_others_unchanged`.
- `test_truth_isolation.py`
  - `test_source_scan`: the §7.6 string scan over `src/kairos_defense/**/*.py`, with the D-008
    allow-list.
  - `test_scan_would_catch_an_offender`.
  - `test_guard_refuses_truth_however_spelled`: relative and `..` spellings.
  - `test_guard_refuses_symlink_and_hard_link`, `test_guard_allows_app_databases`.
- `test_cli.py`
  - `test_help_lists_every_command`.
  - `test_stub_names_its_phase`: parametrized over every stub.
  - `test_version`.

Web (`web/tests`, Vitest):

- `CommandBar.test.tsx`
  - The idle state shows "No replay loaded" and `T+--:--`, with every control disabled.
  - The live state enables the controls and shows "Live".
  - The placeholder App renders the Live theater with no numbers.
- `motion.test.ts`: `parseCssTimeMs` reads `ms` and `s` and rejects anything that is not a time.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it produces |
|---|---|---|
| Dependencies install | `uv sync && npm --prefix web install` | `Resolved … packages`, `found 0 vulnerabilities` |
| All Python and web checks pass | `make check` | ruff clean; `N passed` for pytest; eslint, Prettier, `tsc` and Vitest pass |
| Help lists every command | `uv run kairos-defense --help` | all 14 command names in the Commands panel |
| The placeholder screen builds | `npm --prefix web run build` | `dist/assets/index-*.js`, CSS and B612 font files, `built in …` |

The whole check runs as a single `&&` chain and must exit 0. A manual UI review of the built app
(fonts load from the bundle, no external requests, no horizontal scroll) adds to the gate.

## Documentation to write or update

- `docs/PROGRESS.md`: the phase 0 session-log entry and the exit-check evidence line.
- `docs/DECISIONS.md`: D-016 to D-022.
- Package READMEs did not exist as a convention yet. They are backfilled now; see REPORT.md.

## Risks and mitigations

- **Version drift from the pinned majors** (TypeScript 7, jsdom 30, React 19.4). Mitigation: pin the
  exact working set and log it (D-019).
- **YAML 1.1 booleans corrupt `rid: off` and `true:` keys.** Mitigation: a custom loader and a test
  (D-017).
- **Truth leaks through an odd path spelling.** Mitigation: the guard compares resolved paths and
  `os.path.samefile`, with tests for relative, `..`, symlink and hard-link spellings.
- **Ruff rewrites code blocks in the spec.** Mitigation: `extend-exclude = ["*.md"]` (D-022).
- **The cloud machine has no `/opt/homebrew` Node 22.** Mitigation: the Makefile falls back to PATH,
  and the Node version was checked there (D-015).
- **dtaidistance's C path is missing.** Mitigation: checked on the cloud machine (D-020). On the dev
  laptop it does not load; this was found during the 2026-10-28 backfill (D-062).

## Out of scope

Any data generation, store adapters beyond the guard, real CLI commands, three.js, R3F, Motion, D3,
Zustand, Playwright (phase 7), and committed UI screenshots (phase 7 sets up `reports/figures/ui/`).

## Review changes

None. The plan was approved by the user in the interactive session; there was no autopilot reviewer.
