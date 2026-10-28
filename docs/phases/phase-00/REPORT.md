# Phase 0: Scaffold, report

Status: done · Date: 2026-10-28 (built; docs backfilled the same day) · Commits: `f9258de` (phase 0),
after the kit commit `1a98829`

## Summary

Phase 0 laid down the skeleton every later phase builds on. On the Python side: uv project, Makefile,
ruff and pytest, pydantic models for the five YAML files, the §4.1 ports, seeded random streams, geometry
helpers, the truth-isolation guard and scan, and a Typer CLI whose 14 commands are stubs. On the web
side: Vite 8, React 19.3.1, strict TypeScript, Tailwind 4 locked to the §17.1 tokens, self-hosted B612
fonts and a placeholder Live watch screen with the command bar. It was built by hand in a Claude Code
cloud session. These documents were reconstructed on 2026-10-28, and the exit check passes again
today, after phases 1 to 3.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Project tooling | uv project (src layout, §3 dependencies as lower bounds), lockfile, Python 3.12 and Node 22 pins, ignore rules | `pyproject.toml`, `uv.lock`, `.python-version`, `.nvmrc`, `.gitignore` |
| Makefile | every §5 target plus `help`. `check` = ruff check, ruff format check, fast pytest, `npm --prefix web run check`. Node 22 first on PATH when Homebrew's keg exists (D-002) | `Makefile` |
| `kairos_defense.config` | one frozen, strict pydantic model per YAML file; YAML 1.2 loader; cross-file checks; `load_config()` | `config/__init__.py`, `app.py`, `world.py`, `actors.py`, `scenario.py`, `scoring.py`, `_types.py`, `_yaml.py`; `config/*.yaml` (verbatim §6) |
| `kairos_defense.ports` | §4.1 Protocols the business logic depends on (rule 6) | `ports.py` |
| `kairos_defense.rng` | §8.9 per-component streams: `stable_int`, `rng_for` (rule 4) | `rng.py` |
| `kairos_defense.geo` | bearings, wraps, clockwise rotation, rectangles, installation ↔ region ↔ target frames (D-007) | `geo.py` |
| `kairos_defense.store.guard` | `connect_app_db` refuses the truth file however it is spelled (rule 2, §7.6) | `store/guard.py` |
| `kairos_defense.eval` | empty package; the only place allowed to read truth | `eval/__init__.py` |
| CLI | Typer app, `--version`, 14 stubs that name their phase and exit 0 (D-022) | `cli.py` |
| `web/` | Vite, React, TS strict, Tailwind 4 via `@tailwindcss/vite`, ESLint (no hex, no `any`), Prettier, Vitest; tokens, fonts, motion helpers; placeholder Live watch | `web/package.json`, `vite.config.ts`, `eslint.config.js`, `src/theme/{tokens.css,fonts.ts,motion.ts}`, `src/app/{App,CommandBar}.tsx` |

Since phase 0, later commits have changed only these phase 0 files:

- `cli.py`: four stubs became real commands.
- `test_cli.py`.
- `tests/conftest.py`: shared generator and index fixtures were added.
- `pyproject.toml`: a ruff ignore for `scripts/`.
- `.gitignore`: `.autopilot/`.
- `docs/PROGRESS.md` and `docs/DECISIONS.md`.

Phase 3 also added new modules to `eval/`. Every other phase 0 file is byte-identical to `f9258de`
(`git diff --stat f9258de HEAD -- $(git show --name-only --format= f9258de)`), and the web build
output is the same size.

## Decisions and deviations from SPEC

- [D-015](../../DECISIONS.md): the kit was committed before phase 0 so the build could run in the cloud.
- [D-016](../../DECISIONS.md): `config.py` became the `config/` package (§5 shows a single module).
- [D-017](../../DECISIONS.md): the loader uses YAML 1.2 booleans. Fields `is_true` and `build` carry
  the aliases `true` and `construct`.
- [D-018](../../DECISIONS.md): validation rules, cross-file checks, and paths resolved against the
  project root.
- [D-019](../../DECISIONS.md): web pins, TypeScript 6.0 rather than 7.0 and jsdom 29 rather than 30.
  three.js, R3F and the rest wait for phase 7.
- [D-020](../../DECISIONS.md): library versions verified. Phase 4 must call `use_c=True`.
- [D-021](../../DECISIONS.md): tokens are the only styling vocabulary. Tailwind defaults are reset and
  the lint rejects hex literals.
- [D-022](../../DECISIONS.md): CLI stubs pass options through; `test-all`, `clean`, `web` and `dev` are
  Makefile-only; ruff ignores `*.md`.
- Backfill only: [D-061](../../DECISIONS.md) (what this backfill documents) and
  [D-062](../../DECISIONS.md) (dtaidistance's C library does not load on the dev laptop).

## Tests

At `f9258de`: 89 fast Python tests and 5 Vitest tests, all passing.

- `test_config.py`, 36 tests: the shipped configs load, decision values survive, YAML 1.2 booleans,
  root-relative paths, frozen models, 29 invalid variants rejected, missing and unparsable files.
- `test_geo.py`, 26 tests: cardinal bearings, wrap edge cases including −0.0 and 360, clockwise rotation,
  rectangles, frame round trips.
- `test_rng.py`, 6 tests: pinned values; same names give the same draws; different names, order or seed
  give different draws; adding a component changes nothing else.
- `test_truth_isolation.py`, 5 tests: the §7.6 scan; the guard refuses relative, `..`, symlink and
  hard-link spellings and allows app databases.
- `test_cli.py`, 16 tests at the time: help lists all 14 commands; every stub exits 0 and names its
  phase; `--version`.
- Web: `CommandBar.test.tsx` (idle and live states; the placeholder shows no numbers) and
  `motion.test.ts` (CSS time parsing).

Today (`911aba1`): the same files give 90 passed (`test_cli.py` has 17 now that four commands are
real). The whole fast suite gives 367 passed with 7 slow deselected; `make test-all` gives 374 passed in
51 s. No phase 0 test was removed, skipped or weakened.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| All Python and web checks pass | pass | `make check`: ruff clean, 367 passed, eslint, Prettier, tsc and Vitest 5/5 |
| Help lists every command | pass | all 14 commands in `kairos-defense --help` |
| The placeholder screen builds | pass | `vite build`: JS 222.56 kB (gzip 69.63 kB), CSS 10.45 kB |
| Whole chain | pass | exit 0 in 18.7 s (originally 12.0 s on the cloud machine) |

Full output is in [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Not applicable. Phase 0 has no evaluation numbers. Build sizes: JS 222.56 kB (gzip 69.63 kB) and CSS
10.45 kB, the same then and now.

## Known issues and follow-ups

- **D-062: dtaidistance's C path is unavailable on the dev laptop (phase 4 must handle it).**
  `dtw.try_import_c()` is False because the wheel's OpenMP modules link
  `/usr/local/lib/libomp.dylib`, which is not installed. `distance_fast` raises; `dtw_ndim.distance(...,
  use_c=True)` silently falls back to pure Python. D-020's "fail loudly" rule would stop the phase 4
  matcher on this machine. Options are in D-062.
- **EBADENGINE warning.** The exit check runs `npm --prefix web install` under the `node` on PATH
  (26.12.1), not Node 22. It is harmless; put `/opt/homebrew/opt/node@22/bin` first on PATH (D-002).
- **favicon 404.** `web/index.html` has no icon link, so the browser logs one 404 for `/favicon.ico`.
  Phase 7 should add a token-colored inline SVG icon or `<link rel="icon" href="data:,">`.
- **D-019 follow-up:** move to TypeScript 7 once typescript-eslint supports it.
- **Branch history:** phase 0's commit first lived on branch `claude/charming-einstein-iyqxsd`. Phase 1
  fast-forwarded onto it, so `main` now has it in line (PROGRESS.md, phase 1 entry).
- **Old cloud warning:** the cloud sandbox printed a `UV_NATIVE_TLS` deprecation warning on every `uv`
  call. It came from the environment, not the repo, and does not occur on the laptop.

## How to debug this phase

- **Config errors.** `uv run python -c "from kairos_defense.config import load_config; load_config()"`.
  A `ConfigError` names the file and the first pydantic errors; cross-file problems say
  `cross-file check failed`. Always load YAML through `kairos_defense.config.load_yaml` (D-017).
- **Truth isolation.** `uv run pytest tests/unit/test_truth_isolation.py -q`. A failing scan lists
  `file: string` offenders. The allow-list is `eval/`, `sim/writers.py` and `store/guard.py` (D-008).
- **Determinism.** `rng_for(seed, *names)` depends only on the seed and the names.
  `tests/unit/test_rng.py` pins the values; if they change, the numpy `SeedSequence` behavior changed.
- **CLI.** `uv run kairos-defense --help`. Stubs live in `STUBS` in `cli.py`, and `test_cli.py` asserts
  that every command is listed.
- **Web.** `npm --prefix web run check` (lint, typecheck, Vitest) and `npm --prefix web run build`.
  An off-token class fails the build, because Tailwind's defaults are reset. A hex literal fails ESLint.
  To look at the screen, serve `web/dist` on a spare port, or run `make web` for Vite on :5173.
- **Node version.** `make` uses `/opt/homebrew/opt/node@22/bin` if it exists. Direct `npm` calls use
  PATH.

## Fix attempts

None. The autopilot did not gate this phase; it was built by hand and its documents were backfilled.
