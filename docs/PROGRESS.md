# Progress

| Phase | Title | Status | Exit check evidence | Date |
|---|---|---|---|---|
| 0 | Scaffold | done | Exit check exit 0 in 12 s: ruff clean; pytest 89 passed; web lint, typecheck, Vitest 5 passed; help lists 14 commands; web build 223 kB JS | 2026-10-28 |
| 1 | World, flights and radar | not started | | |
| 2 | Swarms, RF, Remote ID, reports and assessments | not started | | |
| 3 | Features, windows, Euclidean baseline and eval skeleton | not started | | |
| 4 | DTW matcher and fusion model | not started | | |
| 5 | Report recall and analog forecast | not started | | |
| 6 | Case memory (Kairos-lite) | not started | | |
| 7 | Streaming API and Command Center foundation | not started | | |
| 8 | Command Center: the memorable moments | not started | | |
| 9 | Swarms, agent, MCP, hardening and runbook | not started | | |

Status values: `not started` · `in progress` · `done` · `blocked (<reason>)`

## Session log

<!-- Newest first. One entry per session:
### YYYY-MM-DD · Phase N
- Built: …
- Exit check: <command> → <key output / metrics>
- Open issues: …
- Next: …
-->

### 2026-10-28 · Phase 0
- Built: `pyproject.toml` (uv, src layout, §3 dependencies, script `kairos-defense`), `uv.lock`,
  `.python-version` (3.12), `.nvmrc` (22), `Makefile` (all §5 targets plus `help`), `.gitignore`;
  `config/*.yaml` copied byte-for-byte from §6; `kairos_defense.config` (one pydantic model per file,
  cross-file reference checks, `load_config()`, D-016 to D-018); `ports.py` (§4.1); `rng.py` (§8.9);
  `geo.py` (bearing, wrap180, wrap360, clockwise rotate, rectangle polygon, installation ↔ region ↔
  target frames); `store/guard.py` (`connect_app_db` refuses truth, however spelled); empty `eval/`;
  Typer CLI with 14 stubs that name their phase (D-022). `web/`: Vite 8, React 19.3.1, strict
  TypeScript 6.0, Tailwind 4.3 via `@tailwindcss/vite`, ESLint 10, Prettier 3, Vitest 5, self-hosted
  B612 and B612 Mono; §17.1 tokens in `theme/tokens.css` with Tailwind defaults removed (D-021);
  placeholder Live watch screen with the command bar, idle and truthful ("No replay loaded").
- Tests: `test_config.py` (shipped configs load; 29 invalid variants rejected; YAML 1.2 booleans;
  root-relative paths), `test_geo.py` (cardinals, wrap edge cases incl. −0.0 and 360, clockwise rotation,
  frame round trips), `test_rng.py` (pinned values; same names ⇒ same draws; different names, order or
  seed ⇒ different; adding a component changes nothing else), `test_truth_isolation.py` (§7.6 scan plus
  guard against relative, `..`, symlink and hard-link spellings), `test_cli.py` (help lists all 14
  commands; every stub exits 0 and names its phase). Web: command bar idle/live states, placeholder has
  no numbers, CSS time parsing.
- Exit check:
  ```bash
  uv sync && npm --prefix web install && make check && uv run kairos-defense --help && npm --prefix web run build
  ```
  → exit 0, 12.0 s wall (warm caches). Key lines:
  ```text
  Resolved 101 packages in 2ms
  up to date, audited 254 packages in 607ms · found 0 vulnerabilities
  ruff check: All checks passed! · ruff format --check: 25 files already formatted
  pytest -m "not slow": 89 passed in 2.59s
  web lint: eslint 0 warnings · All matched files use Prettier code style!
  web typecheck: tsc --noEmit clean · Vitest: Test Files 2 passed (2), Tests 5 passed (5)
  kairos-defense --help: gen index models eval match recall forecast replay memory export
                         verify-evidence fetch-models api mcp
  vite build: dist/assets/index-*.css 10.45 kB, index-*.js 222.56 kB (gzip 69.63 kB), built in 422ms
  ```
- Toolchain (cloud, D-015 check): Python 3.12.3, uv 0.11.32, Node 22.22.0, npm 10.9.4. Installed:
  duckdb 2.0.0, lancedb 0.40.0, dtaidistance 2.5.1 (C extension and OpenMP present), numpy 2.5.4,
  pandas 3.1.0, pydantic 2.14.1, typer 0.27.3 (D-019, D-020).
- UI review (pre-installed Playwright, built app, 1920×1080, 1440×900, 1100×800): B612 400/700 and
  B612 Mono load from the bundle; zero external requests; no console errors; no horizontal scroll.
  Fixed: the theater caption left "yet." alone on its own line, so the text is now balanced
  (`text-balance`). Screenshots were not committed; phase 7 sets up `reports/figures/ui/`.
- Open issues: the cloud sandbox prints a `UV_NATIVE_TLS` deprecation warning on every `uv` call. It
  comes from the environment, not the repo, and does no harm. Phase 4 must call `dtw_ndim.distance(...,
  use_c=True)`, because the default is pure Python (D-020).
- Next: phase 1 (world, flights and radar).

### 2026-10-28 · Pre-phase 0 (kit review)
- Built: no code. Kit flattened into the repo root and `git init` (D-001); Node 22 LTS installed (D-002);
  SPEC v1.1 → v1.2 with review fixes D-003 to D-014.
- Exit check: none for this session. Timing simulation of the live P1 flight (§8.3 model, 300 seeded
  wind and altitude draws): first contact 41–50 m outside BRAVO's fence; orbit established 67–94 s after
  contact (p5–p95); on the orbit at T+90 in at least 95% of draws.
- Open issues: confirm the dtaidistance C path on 2.5.1 (D-013); check every pinned library version and API
  against what actually installs (phase 0).
- Next: phase 0.
