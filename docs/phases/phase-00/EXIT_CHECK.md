# Phase 0: exit-check evidence

Rerun on 2026-10-28 during the documentation backfill, at `911aba1` (HEAD, after phases 1 to 3), on the
dev laptop (macOS arm64, Python 3.12.12, uv 0.13.5). `node` on PATH is 26.12.1 and Node 22.23.4 is at
`/opt/homebrew/opt/node@22/bin`, which the Makefile puts first. The original run on 2026-10-28 at
`f9258de` (cloud machine) is in `docs/PROGRESS.md`. It passed in 12.0 s with 89 Python tests.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Dependencies install | `uv sync && npm --prefix web install` | pass: 101 packages resolved; npm up to date, 0 vulnerabilities (EBADENGINE warning, see note) |
| All Python and web checks pass | `make check` | pass: ruff clean, 100 files formatted; **367 passed**, 7 slow deselected; eslint, Prettier and `tsc` clean; Vitest 5/5 |
| Help lists every command | `uv run kairos-defense --help` | pass: all 14 commands listed (gen, index, match and eval are now real; 10 stubs) |
| The placeholder screen builds | `npm --prefix web run build` | pass: `index-*.js` 222.56 kB (gzip 69.63 kB), CSS 10.45 kB, 6 B612 font files, built in 370 ms |
| Whole chain | the `&&` chain below | **exit 0, 18.7 s wall** |
| Extra: slow tests | `make test-all` | pass: 374 passed in 51.0 s |
| Extra: phase 0's own tests | `pytest tests/unit/test_{config,geo,rng,truth_isolation,cli}.py` | pass: 90 passed (36 + 26 + 6 + 5 + 17) |
| Extra: UI review | built app at 1920×1080 in Playwright | pass: B612 400/700 and B612 Mono 400 loaded; only same-origin requests; no scroll overflow (one favicon 404, see note) |

## uv sync && npm --prefix web install && make check && uv run kairos-defense --help && npm --prefix web run build
```text
$ uv sync && npm --prefix web install && make check && uv run kairos-defense --help && npm --prefix web run build
Resolved 101 packages in 3ms
Checked 76 packages in 1ms
npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'kairos-defense-web@0.0.1',
npm warn EBADENGINE   required: { node: '>=22 <23' },
npm warn EBADENGINE   current: { node: 'v26.12.1', npm: '11.20.0' }
up to date, audited 251 packages in 487ms
found 0 vulnerabilities
uv run ruff check .
All checks passed!
uv run ruff format --check .
100 files already formatted
uv run pytest -m "not slow" -q
367 passed, 7 deselected in 12.58s
npm --prefix web run check
> eslint . --max-warnings 0 && prettier --check .
All matched files use Prettier code style!
> tsc --noEmit -p tsconfig.json
> vitest run
 Test Files  2 passed (2)
      Tests  5 passed (5)

 Usage: kairos-defense [OPTIONS] COMMAND [ARGS]...
 Kairos Defense: cross-installation drone pattern memory (demo; synthetic data only).
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ models           Train the fusion model and calibrate DTW. (phase 4)         │
│ recall           Retrieve past reports for an incident's matches (hybrid     │
│                  search). (phase 5)                                          │
│ forecast         Forecast the recovery area of an incident from its analogs. │
│                  (phase 5)                                                   │
│ replay           Replay a live incident; --precompute and --reset. (phase 7) │
│ memory           Case memory: seed, verify or reseed the ledger. (phase 6)   │
│ export           Export a signed evidence package for a case (needs          │
│                  approval). (phase 6)                                        │
│ verify-evidence  Verify an evidence package's hashes, signature and chain.   │
│                  (phase 6)                                                   │
│ fetch-models     Download optional embedding models for offline use. (phase  │
│                  5)                                                          │
│ api              Serve the FastAPI backend (REST and WebSocket);             │
│                  --dump-openapi. (phase 7)                                   │
│ mcp              Run the MCP server over stdio. (phase 9)                    │
│ gen              Generate the synthetic world, flights, swarms, sensors,     │
│                  paperwork and truth (seeded).                               │
│ index            Build features, signatures and LanceDB windows for every    │
│                  history track (reports: phase 5).                           │
│ match            Match an incident's track, seen T seconds in, against every │
│                  earlier track (no look-ahead).                              │
│ eval             Run the evaluation harness (§19) and write                  │
│                  reports/eval_<date>.md and .json.                           │
╰──────────────────────────────────────────────────────────────────────────────╯
> tsc --noEmit -p tsconfig.json && vite build
vite v8.3.5 building client environment for production...
✓ 21 modules transformed.
dist/index.html                                          0.44 kB │ gzip:  0.28 kB
dist/assets/b612-latin-700-normal-BinQrnoB.woff2        13.24 kB
dist/assets/b612-mono-latin-400-normal-BDgzQEaT.woff2   19.04 kB
dist/assets/b612-latin-400-normal-CC98FVm_.woff2        21.16 kB
dist/assets/index-bDojSV5r.css                          10.45 kB │ gzip:  3.12 kB
dist/assets/index-oNMpsbi0.js                          222.56 kB │ gzip: 69.63 kB
✓ built in 370ms
( uv sync && npm --prefix web install && make check && uv run kairos-defense )  1.47s user 0.23s system 9% cpu 18.716 total
exit=0
```

Trimmed lines: npm funding and install-scripts notices, pytest progress dots, npm script banners,
the help screen's Options panel, and the three `.woff` font fallbacks. The JS and CSS sizes match
phase 0's original build exactly (222.56 kB / 10.45 kB), so the web app has not changed since.

## make test-all
```text
$ make test-all
uv run pytest -q
374 passed in 51.01s
make test-all  54.33s user 9.60s system 124% cpu 51.475 total
exit=0
```

## Phase 0 test files
```text
$ uv run pytest tests/unit/test_config.py tests/unit/test_geo.py tests/unit/test_rng.py \
    tests/unit/test_truth_isolation.py tests/unit/test_cli.py -q
90 passed in 3.27s
test_config: 36 passed · test_geo: 26 passed · test_rng: 6 passed
test_truth_isolation: 5 passed · test_cli: 17 passed
```
Phase 0 shipped 89 of these. `test_cli.py` now has 10 stubs instead of 14 plus four tests for
the real commands, which makes 17 here instead of 16.

## UI review (built app)
```text
$ python -m http.server 4179 --directory web/dist   # background, stopped afterwards
Playwright, 1920×1080, http://127.0.0.1:4179/
title "Kairos Defense"; command bar: "Kairos Defense / Live watch", T+--:--, "No replay loaded",
  1×, Play/Pause/Restart/Director disabled; theater: "No replay loaded" and the caption, no numbers
fonts loaded: B612 400, B612 700, B612 Mono 400; body font "B612, system-ui, sans-serif"
requests: /, index-*.js, index-*.css, three B612 .woff2 (all 200, all same origin)
scrollWidth 1920 = innerWidth; scrollHeight 1080 = innerHeight
console: 1 error, "Failed to load resource: 404 /favicon.ico"
```
Screenshot reviewed by eye against §17.1 and §17.2: tokens only, glass command bar with a hairline,
centered caption on two balanced lines. Not committed; phase 7 sets up `reports/figures/ui/`.

## Notes

- **EBADENGINE.** The exit check calls `npm --prefix web install` directly, not through `make`, so it
  runs under the `node` on PATH (26.12.1), not Node 22. It is only a warning, and the install is a
  no-op against the committed lockfile. Put `/opt/homebrew/opt/node@22/bin` first on PATH to silence it
  (D-002).
- **favicon 404.** `web/index.html` declares no icon, so the browser asks for `/favicon.ico`. It is
  harmless, but it is the only console error. It belongs to phase 7's UI work (REPORT.md, follow-ups).
- **Toolchain check (D-020) on this laptop.** duckdb 2.0.0, lancedb 0.40.0, dtaidistance 2.5.1,
  numpy 2.5.4, pandas 3.1.0, pydantic 2.14.1 and typer 0.27.3, as recorded. However,
  `dtw.try_import_c()` is **False** here:
  `dtw_cc_omp` cannot load `/usr/local/lib/libomp.dylib`, `dtw.distance_fast` raises
  `CythonException`, and `dtw_ndim.distance(..., use_c=True)` logs "C-library not available, using
  the Python version" and runs pure Python. Logged as D-062 for phase 4.
