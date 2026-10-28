# Progress

| Phase | Title | Status | Exit check evidence | Date |
|---|---|---|---|---|
| 0 | Scaffold | done | Exit check exit 0 in 12 s: ruff clean; pytest 89 passed; web lint, typecheck, Vitest 5 passed; help lists 14 commands; web build 223 kB JS | 2026-10-28 |
| 1 | World, flights and radar | done | Exit check exit 0 in 46 s from `make clean`: 1,869 incidents and 1,869 tracks (≈1,900 / ≈1,950, within ±15%); figures for all 7 patterns; 53 selected tests pass; live first contact 21:39:51, orbit T+94 s | 2026-10-28 |
| 2 | Swarms, RF, Remote ID, reports and assessments | done | Exit check exit 0 in 31 s from `make clean`: 1,878 incidents (9 swarms), 956 reports, 1,876 assessments; planted DELTA report, wrong label and both swarm events present; 109 selected tests pass; live orbit T+79 s (D-033 b) | 2026-10-28 |
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

### 2026-10-28 · Phase 2
- Built: D-033 resolved with option (b): BRAVO's fuel farm (the live target) keeps its template
  place (`world.unjittered_assets`). `sim/`: `formations.py` (formations, actions, timeline, swarm
  center path, D-035), `swarm.py` (schedule, center plans, drone paths), RF and Remote ID in
  `sensors.py` (D-036, D-037), `incidents.py` (sensing, incidents across all sensors, ids, D-038),
  `tables.py` (raw and truth tables), `facts.py` (what the paperwork knows, actor clue profiles,
  D-040), `lexicon.py` (clue vocabulary, clue scanner, guardrail scan, D-045), `reports.py`
  (sources, delays, grades, base styles, Appendix A templates, clue model, D-040, D-041),
  `assessments.py` (rules, 20% mislabel, truth labels, D-042), `paperwork.py` (planted report and
  assessment, D-011, D-043), `figures.py` and `datacard_paper.py` (data card split to stay under
  400 lines). `generate.py` flies single flights and swarm centers in one batch; `gen` prints the
  new counts. Kinematics gained one hook (the `choreography` pattern); existing flights are unchanged.
- Tests: `test_swarm_formations` (layouts, spacing, rotate direction, expand, split, blend and hold,
  center path), `test_swarm` (schedule incl. D-009, jitter ±10%, spacing ±20% on every event, rotation
  sense, orbit radius, plausible speeds, adding a team changes no other event), `test_rf` (family
  per actor, bands, rate, airborne only, range, mask, bearing noise, SNR), `test_rid` (on / off /
  spoofed, stable serials, operator positions, range, mask), `test_reports` (every clue in the text
  has a `clue_truth` row and back, delays and grades per source, counts per actor type, hobbyist
  rate and template, clue rates on 3,000 synthetic incidents, styles, swarm wording, paraphrase
  flag), `test_reports_lexicon` (forbidden-content scan over >1,000 texts; the scanner catches
  made-up plates, names, titles, addresses, phones and e-mail and allows world vocabulary; name
  lexicon shares no world word), `test_assessments` (one per history incident, 2–36 h, rules,
  mislabel rate, truth labels), `test_planted` (DELTA report and wrong label, other P1 paperwork,
  swarm events, no paperwork for live incidents, RF families, live T+0 = first radar contact),
  `test_generate` (incident span over all sensors, swarm tracks, no-radar flights make no incident),
  `test_world` (D-033), slow test (report and assessment volumes, swarm count, paperwork coverage).
- Exit check (after `make clean`):
  ```bash
  make data && uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"
  ```
  → exit 0, 31.0 s wall. Key lines:
  ```text
  kairos-defense gen --seed 42
  incidents 1,878 (≈1,900) · tracks 1,904 (≈1,950) · track_points 560,884 (≈1,000,000, D-030)
  rf_detections 414,999 (≈500,000, D-044) · reports 956 (≈1,000) · assessments 1,876 (≈1,900)
  remote_id 686,263 · swarm incidents 9 · drones flown 1,904 · drones not tracked 0
  live first contact 21:40:06 (21:39:30-21:40:30) · live orbit established T+79 s (T+65-100 s)
  elapsed 19.5 s
  109 passed, 177 deselected in 9.07s
  ```
  Planted items, read back from the written DuckDB files:
  ```text
  reports  R-P1-DELTA-260419-1 security_forces B2 2026-04-20 03:40 UTC (22:40 local):
    "Security forces patrol observed a small drone near the fuel farm at about 21:35, est. 300 ft,
     a flashing white light. A white pickup was parked on County Rd 12 from 21:20 to 22:05 and left
     shortly after the drone flew northwest. The drone departed to the northwest at about 21:46.
     No contact with the operator."
  clue_truth  vehicle white pickup True · road County Rd 12 True · lights True · departure True
  assessments  P1-DELTA-260419 hobbyist, DELTA BDOC, 2026-04-20 14:10 UTC (09:10 local)
  assessment_truth  P1-DELTA-260419 probing
  incidents  S1-GOLF-260503 GOLF 5 tracks swarm history · DEMO-SWARM-ECHO-0614 ECHO 5 tracks swarm live
  ```
  `reports/data_card.md` now has swarm incidents, sensors, reports (sources, counts per actor type,
  delay histogram, styles), clue rates, an assessment confusion table, planted items and live
  timing; figures `reports/figures/swarm_S1.png` and `swarm_S2.png` are new.
  `make check`: ruff clean, 286 passed (4 slow deselected), web lint, typecheck and Vitest pass.
  `pytest tests/slow`: 4 passed in 39 s (full volumes, swarms and paperwork; two full runs give
  identical hashes).
- Figures reviewed by eye: swarm snapshots show line abreast across the heading, the cw quarter turn
  carrying drone 0 to the front, the split, the V apex leading; S2's triangle, expand, ccw half
  turn and trail. Fixed: the pattern-figure legend overlapped the middle panel's axis label (also in
  phase 1's figures).
- Open issues:
  - D-024 (still open): phase 3 must read §9.4's `loiter_dir` as `ccw` when the bearing rate is negative.
  - D-044: RF detections ≈415 k against ≈0.5 M (83%), the same cause as D-030.
  - D-038: RF hears takeoff, so most incidents now start at launch, before the first track point;
    phase 3's no-look-ahead filter compares `start_ts`, which is consistent across flights.
  - D-040: blotter reports are upper case; phase 5's clue extraction must be case-insensitive.
  - D-037: a copycat's Remote ID flights share one serial (same drone); fine for eval, worth knowing.
- Next: phase 3 (features, windows, Euclidean baseline and eval skeleton).

### 2026-10-28 · Phase 1
- Built: `store/ddl.py` (§7.1 and §7.3 DDL, column lists). `sim/`: `world.py` (sites, jittered
  assets, sensors, launch parks, County Rd 12 per D-006/D-031, push-out rule, terrain mask, world
  tables), `calendar.py` (549 nights, hourly weather, base and public events, D-023), `patterns.py`
  (all seven patterns, D-024), `kinematics.py` (timed reference, warp, pauses, batched 10 Hz model,
  D-025), `plan.py`, `actors.py` (hobbyists, P2–P6, C1, C2, D-026), `scenario.py` (six P1 flights,
  live timing helpers), `sensors.py` (radar, D-027), `generate.py` (pipeline, incident ids D-028),
  `writers.py` (the only truth writer, table hashes, D-029), `datacard.py` (data card and figures).
  `kairos-defense gen --seed --config --figures/--no-figures` is real, with a rich summary.
- Tests: `test_world`, `test_calendar`, `test_patterns`, `test_kinematics` (speed, climb and turn
  caps; band ± 15 m; orbit ±10%; warp scales time not shape; no pauses in patterns; batch
  independence; wind drift), `test_actors`, `test_sensors`, `test_scenario` (planted flights, road
  within 250 m, outage, live first contact and orbit windows), `test_generate`, `test_determinism`
  (three-week window twice ⇒ identical SHA-256 per table; extra actor changes no other flight;
  other seed differs), `tests/slow/test_full_generation.py` (full volumes and full determinism).
- Exit check (after `make clean`):
  ```bash
  make data && uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"
  ```
  → exit 0, 45.6 s wall. Key lines:
  ```text
  kairos-defense gen --seed 42
  incidents 1,869 (≈1,900) · tracks 1,869 (≈1,950) · track_points 541,913 (≈1,000,000, D-030)
  flights flown 1,869 · flights not detected 0
  live first contact 21:39:51 (21:39:30-21:40:30) · live orbit established T+94 s (T+65-100 s)
  elapsed 23.6 s
  53 passed, 128 deselected in 18.32s
  ```
  `reports/data_card.md`: incidents −1.6% and tracks −4.2% against §8.11 (within ±15%);
  `reports/figures/pattern_{orbit,lawnmower,figure8,perimeter,hover,transit_dips,random_walk}.png`.
  `make check`: ruff clean, 181 passed (3 slow deselected), web lint, typecheck and Vitest pass.
  `make test-all` slow tests: 3 passed in 46 s (full volumes; two full runs give identical hashes).
- Figures reviewed by eye. Fixed: captions collided with tick labels, radar dots hid the true path,
  and the legend overlapped the axis label. Palette: dataviz reference blue and orange, validator passes.
- Open issues:
  - **D-033 (needs a decision):** BRAVO's seeded fuel-farm jitter puts the live orbit at T+94 s, not
    ≈T+80 s. That passes the 65–100 s window, but the T+90 top-3 beat would match on transit only.
    (Resolved in phase 2: option (b), orbit at T+79 s.)
  - D-024: phase 3 must read §9.4's `loiter_dir` as `ccw` when the bearing rate is *negative*.
  - D-028: phase 2 must recompute incident `start_ts`/`end_ts` across radar, RF and Remote ID.
  - D-030: track points ≈0.54 M against ≈1 M in §8.11 (by design; incident and track counts are on target).
  - Phase 0's commit lived on branch `claude/charming-einstein-iyqxsd`, not `main`. This branch
    fast-forwarded onto it, so merging this branch brings phase 0 along.
- Next: phase 2 (swarms, RF, Remote ID, reports and assessments).

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
