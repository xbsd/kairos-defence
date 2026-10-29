# Phase 7: Streaming API and Command Center foundation, plan

Autopilot plan step, 2026-10-29. Written without a human in the loop (CLAUDE.md rule 5, `phase-auto`):
every assumption below is recorded in `docs/DECISIONS.md` during the build (D-103 to D-118).

## Goal

Real data flowing from the replay into a living 3D theater and instrument rail (SPEC §20, phase 7):

- `kairos_defense.live`: the §16.1 `ReplayEngine` and `LiveLoop` (matcher, forecast and report recall
  rerun on the replay clock, cached by replay second), `kairos-defense replay --precompute | --reset`
  (D-013), recording to `live_*` scratch tables (§16.2).
- `kairos_defense.api`: the FastAPI app with every §16.4 REST endpoint, the `/ws/replay/{incident_id}`
  stream with all thirteen §16.3 message types (including `ingest` and `ledger`), the two admin
  endpoints (D-010), static hosting of `web/dist`, and `kairos-defense api --dump-openapi`.
- `api/schemas.py` with the `StreamMessage` discriminated union, `npm --prefix web run gen:types`
  (openapi-typescript → `web/src/api/types.gen.ts`) and a contract test.
- `web/`: app shell, command bar wired to the stream, routing, tokens and fonts (§17.1), WebSocket client
  with reconnect, Zustand stores.
- Live theater (react-three-fiber): ground, installation (fence, assets, labels, radar shadow), roads,
  radar ring and sweep, RF rings and bearings, drone glyph with phosphor trail and "No Remote ID" tag,
  data packets, Kairos core, camera presets; bloom and vignette (off in reduce-motion).
- Instrument rail: Stream, Signals, Recorder, Ledger chain. Memory rail: the match list wired to
  `match` messages, with Approve and Reject wired to `POST /api/cases/{case_id}/links`.
- `make dev`, `make demo`, `make e2e` (Playwright with screenshots, axe and a frame-rate probe).

Exit check (SPEC §20 phase 7): `make demo`, then `make e2e`; screenshots reviewed per §17.13; median frame
rate and the machine it was measured on recorded in PROGRESS.md. The autopilot gate for phase 7
(`docs/phases/gates.json`) runs `make check`, `npm --prefix web run build` and `make e2e`. Phase 7 has
no `check_targets.py` step and no §19 metric.

## Inputs read

- `CLAUDE.md`, `docs/PROGRESS.md` (phases 0 to 6), `docs/phases/TEMPLATES.md`,
  `docs/phases/phase-06/REPORT.md` and `PLAN_REVIEW-1.json` (what reviewers check),
  `docs/phases/gates.json`, `docs/phases/accepted_gaps.json`, `docs/phases/INDEX.md`.
- SPEC §1.2 (demo script and beat times), §16 (all), §17.1–§17.6, §17.11–§17.13, Appendix B (the
  phase 7 "Read first" list), plus §3 (stack), §4.1 (ports), §5 (layout and Makefile targets), §6.1,
  §6.5 (`live.min_track_s` 45, `rerun_every_s` 5), §7.1–§7.6, §10.8 (`Match`), §13, §15.6, §15.7,
  §17.2 layout, §17.7 (lens data, which the `dtw` message carries), §17.8 (match list), §20 phases 7–9,
  §21, §22.
- `docs/DECISIONS.md`, in particular D-003 and D-039 (T+0 is first radar contact), D-010 (one writing
  process per DuckDB file; admin endpoints; `recorded_at = max(replay clock, head)`), D-012 (no
  decorative motion: the core turns only per `ingest`, grain is static), D-013 (precomputed live
  results in `data/cache/live/`), D-019 (web pins: React 19.3.1, TypeScript ~6.0.3), D-021 (tokens are
  the only styling vocabulary), D-022 (CLI stubs), D-053 and D-092 (adapters in `store/`, ports for
  logic), D-060 (latency does not block), D-063, D-072 and D-093 (how to add port methods), D-081 (the
  accepted live top-3 gap), D-094 to D-102 (ledger rules, proposal dedup, evidence, CLI shapes). Next
  free number: **D-103**.
- Code: `cli.py` (`STUBS` holds `replay`, `api`, `mcp`), `cli_memory.py` (`reseed_cmd`, `_open`,
  `_seed_into`), `ports.py`, `config/app.py`, `config/world.py` (`TerrainMask`), `store/duck.py`
  (`DuckTrackStore`, read-only by default), `store/ledger_duck.py` (`DuckCaseMemory`, `copy_from`),
  `store/lance.py`, `store/guard.py`, `match/matcher.py` (`DtwMatcher.match` → `MatchResult` with
  `signature`, `signatures`), `match/query.py` (`query_at`, `load_query`), `match/types.py`
  (`Match.to_dict`), `match/dtw_rerank.py` (`anchor_bounds`, `warp_path`, `warp_ratio`, `warp_text`),
  `forecast/analog.py` (`forecast`, `Forecast.to_dict`), `recall/search.py` (`ReportRecall.for_matches`,
  `RecallResult.to_dict`), `recall/clues.py` (`Clue` spans), `features/signatures.py` (`loiter_mask`),
  `features/channels.py` (`choose_target`, `load_site`), `memory/actions.py`, `memory/asof.py`,
  `memory/diff.py`, `memory/delta.py`, `memory/views.py`, `memory/evidence.py`, `memory/seed.py`,
  `tests/conftest.py` (`p1_index`, `toy_models`, `seeded_p1`, `ledger_copy`), `tests/unit/test_cli.py`,
  `Makefile`, `pyproject.toml`, `.gitignore`, `web/package.json`, `web/vite.config.ts`,
  `web/eslint.config.js`, `web/src/**`, `web/tests/**`, `web/README.md`, root `README.md`.

### Facts checked during planning

Read-only checks (queries on `data/kairos_defense.duckdb`, `npm view`, a timing script in `/tmp`). Nothing
in the repo or `data/` was written.

1. **No `api/` or `live/` package exists.** `replay` and `api` are stubs in `cli.py` `STUBS` (phase 7);
   `mcp` stays a stub (phase 9). `make e2e` prints "not built yet" until `web/package.json` has an
   `e2e` script. `make demo` already runs `npm run build`, `replay --precompute`, `api --static web/dist`.
2. **Live incidents.** `DEMO-BRAVO-0828`: BRAVO, 2026-08-29 02:40:06 → 02:48:41 UTC (515 s), 1 track,
   438 radar points at 1 Hz, 258 RF detections at BRAVO in the window, 0 Remote ID messages.
   `DEMO-SWARM-ECHO-0614`: ECHO, 2026-06-15 03:50:02 → 04:03:52 (830 s), 5 tracks, 3,235 points,
   2,076 RF detections.
3. **Rerun schedule.** With `min_track_s` 45 and `rerun_every_s` 5, BRAVO has 95 rerun seconds
   (45, 50, …, 515).
4. **Cost of one rerun on the real data** (dev laptop, read-only script): query 4–5 ms, `DtwMatcher.match`
   97–247 ms, `forecast` 8–11 ms, `ReportRecall.for_matches` 14–51 ms. A full precompute of BRAVO is
   therefore about 20–40 s. The top 3 changes along the replay: T+45 BRAVO-251114, DELTA-260419,
   ALPHA-260303; T+90 DELTA-260419, ALPHA-260303, CHARLIE-260710 (the accepted gap, D-081).
5. **BRAVO geometry.** Origin (22000, −6000) region meters, rotation 12°, 5 assets. Radar
   `BRAVO-RADAR-1` at the origin, range 3.5 km, `rate_hz` 1; `BRAVO-RF-1` at (22226.8, −5894.9), 4 km,
   0.5 Hz; `BRAVO-RID-1` 3 km. The terrain mask (bearing 285°→20°, 50 m beyond the fence, below 200 m)
   lives only in `config/world.yaml` (`TerrainMask`), not in the `sensors` table. County Rd 12's WKT is
   23 kB (a long road), so the scene must clip roads.
6. **No `live_*` tables exist** in `data/kairos_defense.duckdb` (18 tables, all generator or index output).
7. **Python libraries.** fastapi 0.162.0, uvicorn 0.54.0, starlette 1.10.0, pydantic 2.14.1,
   websockets 17.3 are installed. `httpx` is **not** installed; FastAPI's `TestClient` needs it.
8. **npm (registry, 2026-10-29).** three 0.186.1, @react-three/fiber 9.8.2 (peer react `>=19 <19.4`),
   @react-three/drei 10.7.9, @react-three/postprocessing 3.2.2 (peer postprocessing ^6.36; 6.39.5),
   motion 14.7.1, d3 7.9.0, zustand 5.0.16, @playwright/test 1.64.1, @axe-core/playwright 4.14.0,
   openapi-typescript 7.13.0, @types/three 0.186.0, troika-three-text 0.52.5 (drei `Text`).
   React stays exactly 19.3.1 (D-019).
9. **Playwright browsers** cached on the laptop: chromium-1217, -1223, -1243 and the matching headless
   shells. 1.64.1 may want a newer revision; `npx playwright install chromium` is a build step.
10. **Fixtures to reuse.** `p1_index` generates and indexes the six P1 nights *including the live
    incident*; `toy_models` adds a hand-set model; `seeded_p1` and `ledger_copy` give a seeded ledger.
11. **`export_evidence`** writes the files, then hashes them in one dict comprehension: there is no
    progress hook yet. **`memory reseed`** refuses a locked file and keeps its logic inside
    `cli_memory.reseed_cmd`.
12. **Fast test count at the start: 586** (`pytest -m "not slow" --co`: 586/601). Turning `replay` and
    `api` into real commands removes two cases of `test_stub_names_its_phase`; the new tests more
    than replace them.
13. `web/vite.config.ts` proxies `/api` (with `ws: true`) but not `/ws`.

## Assumptions and decisions

Each becomes a `docs/DECISIONS.md` entry during the build.

- **A1 (D-103) Live scratch tables live in their own file.** `paths.live: data/live.duckdb` (new key in
  `config/app.yaml` and `PathsConfig`; the distinct-files validator covers it). Tables `live_points`,
  `live_rf`, `live_rid` with exactly the §7.1 columns of `track_points`, `rf_detections` and
  `remote_id` (§16.2 names two tables; Remote ID detections are detections too, so the third keeps the
  Recorder honest for incidents that broadcast). The API opens `data/kairos_defense.duckdb`
  **read-only**, so `match`, `forecast`, `recall` and `eval` keep working while `make demo` runs. Each
  WebSocket session records its own replay: it keeps a high-water mark of replay time already written;
  a tick writes the detections in (mark, clock]; seeking forward writes the skipped detections in one
  batch; seeking back writes nothing. `replay --reset` and `POST /api/admin/reset` empty only the
  `live_*` tables, never the ledger.
- **A2 (D-104) Two ports and three adapters.** `ports.py` gains `LiveSink` (`append(table, rows) ->
  IngestStat`, `count(table)`, `reset() -> dict[str, int]`) and `ResultCache` (`get(incident, t_s)`,
  `put(…)`, `manifest(incident)`, `is_fresh(incident, fingerprint)`), as D-072/D-093 did. Adapters:
  `store/live_duck.py` (`DuckLiveSink`, through `connect_app_db`, so the truth path is refused),
  `store/live_cache.py` (`FileResultCache`, JSON under `data/cache/live/<incident>/`). The reseed core
  moves from `cli_memory.reseed_cmd` to `store/ledger_duck.reseed_ledger(path, app, store, scenario)`,
  shared by the CLI and the admin endpoint (behavior unchanged: temp file, verify, close, remove stale
  WAL files, `os.replace`). `live/` and `api/` logic use ports; only `api/services.py` (the composition
  root) and the CLI construct adapters (rule 6).
- **A3 (D-105) The live loop, its schedule and its cache.**
  - Rerun seconds: `min_track_s, min_track_s + rerun_every_s, … ≤ duration_s`. At a replay second
    between reruns the latest rerun ≤ it is current; `GET /api/match/{id}?at=` snaps the same way and
    reports the rerun second it used (`t_s`). Before `min_track_s` there is no result (REST answers 200
    with `matches: []` and `waiting_for_s`).
  - A `LiveResult` per rerun second: `t_s`, `model_version`, the top 10 matches (§10.8 fields, NaN →
    null), `forecast` (§13, or null), `recall` (top 3 distinct incidents, clues linked to the forecast's
    zone roads), the lens payload for the top match on `dist_target_m` (A15), `target_asset_id`, and
    `elapsed_ms` = the time the computation took when it ran. A cache hit sets `cached: true` and keeps
    the original `elapsed_ms` (rule 10: no invented timings).
  - Features at every whole second s come from `query_at(points, site, s)` (points up to s only, rule 3);
    the last row feeds the `features` message with the flight phase (A13).
  - `kairos-defense replay --precompute` computes every rerun second and every feature second of each
    live **single-track** incident into `data/cache/live/<incident>/` (`manifest.json`, `features.json`,
    `t0045.json` …). The manifest fingerprint is the SHA-256 of: the fusion model and DTW calibration
    file bytes, the scoring config dump, the embeddings config, the incident's track-point count and
    last timestamp, the `track_signatures`, `flight_windows` and `reports` row counts, and a
    `CACHE_FORMAT` integer. A mismatch is stale and is recomputed; `--force` recomputes anyway. A cache
    miss at run time computes on demand in the compute executor, then stores the result.
  - The swarm incident (`DEMO-SWARM-ECHO-0614`) streams its detections in phase 7 but gets no single-track
    match, forecast, recall or features: swarm matching is phase 9 (§14, §20). Its `hello` carries
    `matching: false`, and the memory rail says that swarm matching is not built yet.
- **A4 (D-106) Which case receives live proposals** (left open by D-097). Before the first proposal of
  a replay, the loop records tonight's incident (`record_incident`, actor `system`, valid from its
  start) and registers the model (`register_model`, SHA-256 of the model file); both dedupe. The target
  case is the case, as of the replay clock, whose founder or member is the **best-ranked top-3 incident
  that belongs to any case** (ties: the earliest `case_opened`). For BRAVO that is
  `CASE-P1-DELTA-260419` at every rerun. With no such case nothing is proposed and the `match` message
  carries `case_id: null`. Proposals use `propose_matches` (its §15.6 dedup), actor `matcher@<version>`,
  clock = incident start + t_s, stamped `max(clock, head)` by the writer (D-010). Opening a case from the
  UI is phase 8.
- **A5 (D-107) Stream protocol details** beyond the §16.3 table (the table's fields are all present):
  - `hello` adds `region_id`, `tracks`, `is_swarm`, `matching` (bool, A3), `min_track_s`,
    `rerun_every_s`, `playing` (always false: the server starts paused at T+0).
  - `clock` adds `seeked: bool`. After a seek, play/pause or reset the server sends one `clock` with
    `seeked: true`, then a catch-up: the detections in (t − 120 s, t], the `features` of the last 120 s,
    and the latest `match`/`dtw`/`forecast`/`recall` at or before t (cached, so instant).
  - `point` adds `incident_id`; `features` adds `track_id` and `target_asset_id`; `match` adds `cached`,
    `case_id`, and per match `proposal_seq`, `decision` (`approved`, `rejected` or null),
    `memory_status` (A14) and `local_start` (the match's local start time, `YYYY-MM-DDTHH:MM`).
  - Speed accepts 1, 2 or 5 (§6.1); anything else is an `error` with `recoverable: true`. The replay
    pauses itself at `duration_s`.
  - `dtw` and `recall` are sent only when their content hash changes; `dtw` on request
    (`{"type":"dtw","match_track_id":…,"channel":…}`) is always answered.
  - Every ledger append (live proposals, incident and model records, REST approvals and rejections,
    evidence exports) is broadcast as a `ledger` message to every open session. A reseed replaces the
    file and is not broadcast row by row; clients refetch `GET /api/ledger/tail` after it.
  - `t_s` is float seconds since `incidents.start_ts` (T+0, D-039); `ts` is ISO 8601 UTC with `Z`.
- **A6 (D-108) REST details.**
  - Extra routes: `GET /api/health` (readiness for the CLI fallback and Playwright), `GET
    /api/ledger/tail?n=12` (the chain panel's first blocks) and `GET /api/ledger/{seq}` (the full
    record behind a clicked block, §17.6).
  - Times in query strings and bodies must carry `Z` or an offset; a naive time is a 422 that says so
    (as the CLI does, D-100). Defaults: `as_of`, `t2` and `until` = the ledger head; the link POST's
    optional `clock` defaults to the head (the UI sends its replay time).
  - Errors: `ProposalNotFound` and unknown case or incident 404; `WrongCase` and
    `ProposalAlreadyDecided` 409; `ApprovalRequired` 400 (nothing written); `ActionError` 422.
  - `POST /api/cases/{id}/evidence` (`{"approve": true, "analyst": "demo"}`) streams NDJSON:
    one `{"type":"file","name","bytes","sha256","i","n"}` line per file as it is hashed (the real
    hashing: `export_evidence` gains an optional `progress` callback, called after each file is
    written and hashed), then `{"type":"done","dir","manifest_sha256","seq","checks":[…]}` from
    `verify_evidence`.
  - `POST /api/admin/reseed` closes the ledger connection under the memory lock, runs
    `reseed_ledger`, reopens, and returns the head; `POST /api/admin/reset` returns the emptied row
    counts. No authentication (§2: not in v1); the server binds 127.0.0.1 by default.
  - `GET /api/cases/{id}/graph` returns nodes (incidents colored by base, reports, assessments,
    pending proposals) and edges (`member_of` links, `proposed`, `report_of`, `assessed`) from the
    snapshot; contradictions are flagged on their nodes. Phase 8 draws it.
- **A7 (D-109) Coordinates.** The API sends region-frame meters everywhere (the database convention,
  CLAUDE.md); `GET /api/installations/{id}/scene` adds the installation origin. The web maps
  `x = x_m − origin_x`, `z = −(y_m − origin_y)`, `y = alt_m` (§17.3: scene origin = installation
  origin, north-up, no rotation). The scene clips roads and parks to 6 km of the origin (shapely) to
  match the grid's fade; the radar shadow wedge comes from the world config (`TerrainMask`, config, not
  truth). Asset heights (6–20 m by kind) are presentation constants in the web app.
- **A8 (D-110) Concurrency.** One single-thread "compute" executor owns the read-only
  `DuckTrackStore`, LanceDB, the `DtwMatcher`, `ReportRecall` and every REST read of the main
  database; a second single-thread executor owns the `DuckLiveSink`. `DuckCaseMemory` keeps its own
  lock. No DuckDB connection is used from two threads. The WebSocket tick loop is async and never
  blocks on these executors for longer than a write batch.
- **A9 (D-111) CLI shapes.**
  - `kairos-defense api [--host 127.0.0.1] [--port 8000] [--static DIR] [--reload]
    [--dump-openapi PATH] [--memory PATH] [--live-db PATH] [--reseed] [--config config]`.
    `--dump-openapi` writes the schema and exits without serving; `--reseed` reseeds the given memory
    file before serving (used by the e2e server on scratch files); `--reload` runs uvicorn with an app
    factory (config passed through `KD_CONFIG`).
  - `kairos-defense replay [--incident ID] [--precompute] [--force] [--reset] [--api URL]
    [--config config]`. With no flag it prints each live incident's duration, detections, rerun
    seconds and cache state.
  - `replay --reset` and `memory reseed` try the file first; when DuckDB reports the file locked they
    call `POST {--api}/api/admin/reset` or `/reseed` (default `http://127.0.0.1:8000`, stdlib `urllib`,
    loopback only) and print that they did (D-010). Both exit 1 with the old message if the API does
    not answer.
  - The new commands live in `cli_live.py` (`cli.py` is 370 lines).
- **A10 (D-112) Web foundation choices.**
  - A small in-house router (`app/routes.tsx`, history API, about 60 lines) instead of a new
    dependency. Routes: `/` → the first live single-track incident, `/live/:incidentId`, and
    `/explainer`, `/cases`, `/swarm`, `/evidence`, `/delta`, `/eval`, which in phase 7 render one
    plain sentence naming the phase that builds them (no fake data). FastAPI serves `index.html` for
    any non-`/api`, non-`/ws`, non-asset path.
  - Stores: `replayStore` (connection, `hello`, clock, ring buffers of points, RF, Remote ID,
    features, stream rows, ingest stats), `matchStore` (match, forecast, recall, dtw, decisions),
    `caseStore` (ledger blocks, verify state, selected record), `uiStore` (reduce motion, camera
    preset, performance level). High-frequency data is read in `useFrame` or requestAnimationFrame;
    DOM panels re-render through a `useThrottledStore` hook capped at 10 Hz (§17.11).
  - The analyst handle the UI sends is `demo` (as `memory demo`, D-098).
  - The memory rail holds only the match list in phase 7; the region constellation and time-warp lens
    arrive in phase 8 (their slots are not drawn as empty decoration).
  - Effects: bloom (mipmap blur, threshold 0.2) and a light vignette; film grain waits for phase 8
    (static, with the performance modes). All effects are off in reduce motion (OS setting or M).
    Auto-degrade (§17.11): frame time above 25 ms for 2 s drops bloom; another 2 s halves the packet
    budget (300 → 150). The level shows as `data-perf` on the theater.
  - The Kairos core sits 2.4 km southeast of the origin at 120 m altitude, inside the grid and in
    the overview shot. drei `Text` gets the B612 `.woff` from `@fontsource` (troika does not read
    woff2); it never falls back to troika's default CDN font (rule 5).
  - ESLint bans `setInterval` in `src/` (§17.11: no interval animation); reconnect backoff uses
    `setTimeout`.
- **A11 (D-113) Test and evidence plumbing.**
  - Playwright's `webServer` starts `kairos-defense api --static web/dist --port 8765 --memory
    data/cache/e2e/memory.duckdb --live-db data/cache/e2e/live.duckdb --reseed` from the repo root
    (timeout 240 s, `reuseExistingServer: false`), so e2e never touches `data/memory.duckdb` and never
    collides with `make demo` on :8000. Tests that need fresh ledger blocks call
    `POST /api/admin/reseed` first.
  - `make e2e` = `npm run build`, `kairos-defense replay --precompute`, `npm run e2e`.
  - Screenshots and `perf.json` go to `reports/figures/ui/`, which is git-ignored (they change every
    run and would dirty the tree after each gate); EXIT_CHECK.md and PROGRESS.md record the list, the
    review findings and the numbers.
  - The frame rate is measured in Playwright's Chromium (headless, launched with
    `--ignore-gpu-blocklist --use-angle=metal` on macOS) by sampling requestAnimationFrame for 10 s of
    1× playback; the WebGL renderer string is recorded with it, so a software renderer is visible.
    Phase 7 records the number and does not assert it (phase 8 owns ≥ 50 fps).
  - `httpx` joins the dev dependency group (TestClient).
  - `web/openapi.json` is committed. A Python test fails if it differs from `create_app().openapi()`,
    and `npm run check:types` (part of `npm run check`) regenerates the types to a temp file and fails
    if `src/api/types.gen.ts` differs.
- **A12 (D-114) Web dependency pins.** Exact or tilde pins from fact 8: three `~0.186.1`,
  @react-three/fiber `~9.8.2`, drei `~10.7.9`, @react-three/postprocessing `~3.2.2`, postprocessing
  `~6.39.5`, motion `~14.7.1`, d3 `^7.9.0` (scales and lines for the signal lanes), zustand `^5.0.16`;
  dev: @playwright/test `1.64.1`, @axe-core/playwright `^4.14.0`, openapi-typescript `^7.13.0`,
  @types/three `~0.186.0`, @types/d3 `^7.4.3`. Vite `manualChunks` puts three, R3F, drei and
  postprocessing in a `vendor-3d` chunk.
- **A13 (D-115) Flight phase for the `features` message.** On the features up to second s:
  `loiter` when at least 7 of the last 10 seconds pass `signatures.loiter_mask`; `egress` once a loiter
  run of 10 s or more has happened and `dist_target_m` is above 600 m and has risen over the last 5 s;
  otherwise `approach`. The Signals panel's bone marker sits at the first `loiter` second.
- **A14 (D-116) Memory status per match** (§17.8), `memory.views.incident_status(rows, incident_id,
  at, utc_offset_hours)`: in a closed case → "Closed as <label> on <Mon D>" (label: the case's
  active assessment of that incident, else the close rationale; date: the close decision's local
  date); in an open case → "Open case, <n> linked"; in no case → "Open, unattributed".
- **A15 (D-117) Lens payload** (`match/lens.py`, the `dtw` message and `GET /api/dtw/…`): query =
  tonight's last `rows_used` seconds of the channel; candidate = the matched track's anchor segment
  (`dtw_rerank.anchor_bounds`, the segment the shape distance used), raw channel units. Series longer
  than 128 are averaged down to 128 (PAA). Band `w = max(|n − m| + 1, ceil(band_fraction × max(n, m)))`
  so the corner is reachable. `cost` = `dtw.warping_paths(a, b, window=w)` without its padding row and
  column, float32 little-endian, row-major, base64, with `shape`; `path` = `dtw.best_path(paths)`;
  `dtw_distance` = `paths[n, m]`; `euclid_distance` = same-time distance over the first `min(n, m)`
  samples (reported with `overlap`); `warp_ratio` and its wording from the match (`warp_text`).
- **A16 (D-118) Replay clock semantics.** The clock is server-side per session: `t_s` advances by
  `speed × wall seconds` while playing; `seek` clamps to `[0, duration_s]`; `reset` = seek 0 and
  pause; a detection is sent when its `t_s ≤ clock`. The engine takes an injectable monotonic time
  source so tests drive it without waiting.

### How the non-negotiable rules hold

1. Synthetic only: no new data; the UI shows the generator's ids and synthetic names.
2. Truth isolation: `api/` and `live/` never name the truth path; `DuckLiveSink` opens through
   `connect_app_db` (refuses it, `test_live_sink_refuses_truth_path`); the existing scan covers the new
   modules. `GET /api/eval/latest` reads the eval harness's output JSON in `reports/`, not
   `data/truth.duckdb`.
3. No look-ahead: the matcher keeps its started-before filter (`test_matches_started_before_live_start`);
   features at second s use points up to s (`test_features_at_ignores_later_points`); the stream and
   the catch-up send only detections with `t_s ≤ clock`; `GET /api/history` refuses live tracks.
4. Determinism: no random draws are added; replay messages and loop results are identical for the same
   second, and cached results equal computed ones.
5. Offline: FastAPI serves `web/dist`; fonts come from `@fontsource`; drei `Text` uses the local font;
   `no request leaves the origin` asserts it in e2e. npm and Playwright downloads happen only at install.
6. Ports and adapters: A2; only `api/services.py` and the CLI construct adapters.
7. Append-only memory: ledger writes go through `memory.actions` (append only); the reseed replaces the
   whole file as phase 6 does; `live_*` resets use `DELETE FROM live_points` etc. on scratch tables in
   their own file, which the append-only scan (it targets `ledger`) allows by design.
8. Humans approve: the loop only writes `match_proposed` (plus `system` records); links change only on
   an Approve or Reject click (`POST …/links`); evidence needs `approve: true`.
9. Link flights, never people: the UI shows incidents, bases and dates only; analyst handles pass the
   phase 6 validation.
10. Truthful animation: every moving element is driven by a stream event or the replay clock (sweep,
    trail, packets, rings, core turns per `ingest`); grain is deferred; `setInterval` is banned in
    `src/`; timings shown are measured (`write_ms`, original `elapsed_ms` with `cached`).

## Work breakdown

Run `make check` after every step. Keep every Python module under about 400 lines.

Coverage of the SPEC §20 phase 7 checklist:

| Checklist item | Steps |
|---|---|
| `api/`: FastAPI app, REST endpoints, WebSocket replay stream, recording to `live_*` tables, `ingest` and `ledger` messages, `api --dump-openapi` | 1, 2, 3, 4 |
| `schemas.py` with the `StreamMessage` union; `gen:types`; contract test | 3, 5 |
| `web/`: app shell, command bar, routing, tokens and fonts, WebSocket client with reconnect, Zustand stores | 6, 7 |
| Live theater: ground, installation, roads, radar ring and sweep, RF rings and bearings, drone glyph and phosphor trail, data packets, Kairos core, camera presets | 9 |
| Instrument rail (stream, signals, recorder, ledger chain); memory rail match list with approve and reject wired to the API | 8 |
| `make dev`, `make demo`, `make e2e` | 4, 10, 11 |

1. **Python plumbing.**
   - `pyproject.toml`: `httpx>=0.28` in the dev group; `uv sync`.
   - `config/app.yaml` + `config/app.py`: `paths.live`; validator lists four distinct files.
   - `ports.py`: `IngestStat`, `LiveSink`, `ResultCache` (A2).
   - `store/ddl.py`: `LIVE_DDL` (three tables, §7.1 columns). `store/live_duck.py`: `DuckLiveSink`
     (`append` times the insert and returns rows, total, `write_ms` and the statement shape
     `INSERT INTO live_points … 3 rows`; `reset`; `count`). `store/live_cache.py`: `FileResultCache`.
   - `store/ledger_duck.py`: `reseed_ledger` (moved from `cli_memory.reseed_cmd`, which now calls it).
   - Tests: `test_live_recorder.py`, `test_live_cache.py`, `test_config.py` (paths.live),
     `test_memory_cli.py` (reseed still works).
2. **Pure live logic.**
   - `live/replay.py`: `LiveIncident` (loaded once through `TrackStore.sql`: incident row, tracks,
     points, RF and Remote ID of the installation in [start, end], site), `ReplayEngine` (A16;
     `play`, `pause`, `reset`, `seek`, `set_speed`, `elapsed_s`, `visible_points()`), and
     `detection_messages(incident, t0, t1)` → ordered `point`/`rf`/`rid` dicts in (t0, t1].
   - `live/phase.py`: `flight_phase(features)` (A13).
   - `live/loop.py`: `rerun_seconds`, `LiveResult` (`to_dict`/`from_dict`), `LiveLoop(store, vstore,
     recall, matcher, scoring, cache)` with `result_at(t_s)`, `compute(t_s)`, `features_at(t_s)`.
   - `live/precompute.py`: `fingerprint(...)`, `precompute(incident, force)` → summary.
   - `match/lens.py`: `lens_payload(live, segment, channel, band_fraction, warp_ratio)` (A15).
   - `memory/views.py`: `incident_status` (A14). `memory/graph.py`: `case_graph(rows, case_id, t)`.
     `memory/evidence.py`: optional `progress` callback.
   - `live/session.py`: `Session` — per-client state machine with no FastAPI import:
     `hello()`, `handle(client_msg)`, `step(now) -> list[dict]` (clock at 10 Hz, detections, 1 Hz
     features, ingest after each sink write, results at rerun seconds, proposals and their ledger
     rows), the high-water mark (A1), catch-up after seeks (A5), case targeting (A4).
   - Tests: `test_live_replay.py`, `test_live_phase.py`, `test_live_loop.py`, `test_lens.py`,
     `test_live_session.py`, `test_memory_status.py`, `test_memory_graph.py`, the new evidence test.
3. **API.**
   - `api/schemas.py`: one pydantic model per §16.3 type (`type: Literal[...]`), `StreamMessage =
     Annotated[Union[...], Field(discriminator="type")]`, client message models, REST response models.
     Written first, with `test_api_contract.py`.
   - `api/services.py`: `Services` (config, adapters, executors, `DtwMatcher`, `ReportRecall`, loops
     per incident, `PublishingMemory` wrapping `DuckCaseMemory` to publish appended rows,
     `Broadcaster` of ledger rows to sessions, `reseed()` under the memory lock).
   - `api/routes.py` (health, installations, scene, incidents, match, dtw, history, eval, schema) and
     `api/routes_memory.py` (cases, diff, graph, links, evidence, ledger verify/tail/seq, delta,
     admin). `live/scene.py`: `installation_scene(store, world_cfg, installation_id, radius_m=6000)`.
   - `api/stream.py`: the WebSocket endpoint: accepts, sends `hello`, runs `Session.step` every 100 ms,
     forwards client messages and broadcast ledger rows; validates every outgoing message against
     `StreamMessage` in tests (`KD_VALIDATE_STREAM=1`), not in production.
   - `api/static.py`: mount `web/dist` with the SPA fallback; `/api/*` and `/ws/*` never fall back.
   - `api/app.py`: `create_app(cfg, *, static_dir=None, memory_path=None, live_path=None,
     reseed=False)` with a lifespan that builds and closes `Services`; `factory()` for `--reload`.
   - Tests: `test_api_rest.py`, `test_api_ws.py`, `test_api_static.py`.
4. **CLI and Makefile.**
   - `cli_live.py`: `api` and `replay` (A9); `cli.py` registers them and drops them from `STUBS`.
     `cli_memory.reseed_cmd`: API fallback when locked.
   - `Makefile`: `e2e` = build + precompute + `npm run e2e`; `demo` unchanged; `dev` unchanged
     (it already starts both servers; `concurrently` is not needed); help text without "(phase 7)".
   - `.gitignore`: `reports/figures/ui/`, `web/e2e-results/`.
   - Tests: `test_cli.py` (`BUILT` gains `replay`, `api`).
5. **Contract and types.** `uv run kairos-defense api --dump-openapi web/openapi.json`; web scripts
   `gen:types` (`openapi-typescript openapi.json -o src/api/types.gen.ts`) and `check:types`;
   `types.gen.ts` in `.prettierignore` and ESLint ignores.
6. **Web dependencies and data layer.** `npm install` the A12 pins; `npx playwright install chromium`.
   `src/api/client.ts` (typed REST: scene, incidents, ledger tail, record, verify, links, evidence
   NDJSON reader), `src/api/stream.ts` (`ReplayStream`: connect, dispatch by `type`, drop malformed,
   reconnect with backoff 0.5, 1, 2, 4, 8 s, then resend speed, seek to the last `t_s` and play if it was
   playing), `src/api/messages.ts` (aliases from `types.gen.ts`). Stores in `src/state/`
   (`replayStore.ts`, `matchStore.ts`, `caseStore.ts`, `uiStore.ts`), `src/lib/format.ts`,
   `src/lib/useThrottledStore.ts`. `vite.config.ts`: proxy `/ws` (ws) and `/api`; `manualChunks`.
   Tests: `stream.test.ts`, `client.test.ts`, the store tests, `format.test.ts`.
7. **Shell and pages.** `app/routes.tsx`, `app/App.tsx` (shell + routes), `app/CommandBar.tsx` (wired:
   breadcrumb with the installation name, T+mm:ss, status chip Live / Paused / Reconnecting / No replay
   loaded, speed buttons 1× 2× 5×, Play, Pause, Restart (seek 0), Director disabled with "Director mode
   arrives in phase 8", a Pages menu, a reduce-motion toggle), `pages/LiveWatch.tsx` (§17.2 grid:
   theater hero, memory rail right, instrument rail bottom; stacks below 1280 px),
   `pages/Planned.tsx`. Tests: `router.test.ts`, `CommandBar.test.tsx`, `LiveWatch.test.tsx`.
8. **Instrument and memory rails.** `panels/Stream.tsx` (§17.4), `panels/Signals.tsx` (§17.5, four
   canvases redrawn in one requestAnimationFrame loop from the store), `panels/Recorder.tsx` (§17.6,
   statement, rows, last write ms, write-time history, row glyphs dropping into a table glyph per
   `ingest`), `panels/LedgerChain.tsx` (§17.6, blocks slide in, 400 ms connector, verified badge from
   `GET /api/ledger/verify`, click → `LedgerRecord` dialog with `GET /api/ledger/{seq}`),
   `panels/MatchList.tsx` (§17.8: three entries once, staggered 120 ms, 600 ms score ring, reason chips,
   memory status, Approve link / Reject; approving turns the ring `--verified`). Tests: one Vitest file
   per panel.
9. **Live theater.** `three/Theater.tsx` (Canvas, scene frame, `data-perf`, an `aria-live` text
   summary updated at most once a second), `Ground.tsx` (drei `Grid`), `Installation.tsx` (fence,
   extruded assets with `Edges`, labels, target edges flash blue once `target_asset_id` is known, radar
   shadow wedge), `Roads.tsx`, `Radar.tsx` (range ring; sweep angle = bearing of the last detection +
   360° × rate × (clock − its time), so the beam crosses the drone at each real detection and stops when
   the replay pauses), `Rf.tsx` (measured bearing lines and 0 → 300 m rings over 1.2 s), `Drone.tsx`
   (constant-screen-size quatrefoil glyph with heading tick, drop line, ground ring, 60 s phosphor trail,
   "No Remote ID" tag when no `rid` was heard for the track in the last 10 replay seconds),
   `Packets.tsx` (instanced, ≤ 300 in flight, drone → sensor → core, 0.9 s + 0.6 s), `Core.tsx`
   (ringed octahedron, a few degrees per `ingest`, pulse on `ingest`, label), `CameraRig.tsx`
   (overview, follow, target; memory and swarm presets defined for phases 8–9; drei `CameraControls`,
   1.2 s damped, free orbit), `Effects.tsx`, `sceneMath.ts` (pure helpers), `perf.ts` (degrade
   policy). Tests: `sceneMath.test.ts`, `perf.test.ts`.
10. **End to end.** `web/playwright.config.ts` (A11), `web/e2e/helpers.ts`, `live.spec.ts`,
    `pages.spec.ts`, `screens.spec.ts`, `perf.spec.ts`. Run `make e2e`; open every screenshot (Read
    tool), fix what §17.13 asks about (alignment, overlap, contrast, glow restraint, legibility from
    three meters), rerun, and log findings and fixes.
11. **Exit check, docs, commit.** Run the exit-check commands below; write EXIT_CHECK.md, REPORT.md, the
    READMEs, PROGRESS.md (session log, evidence line, UI review, frame rate and machine), DECISIONS.md
    D-103 to D-118; `make test-all`; `git add -A && git commit -m "phase 7: streaming API and Command
    Center foundation"`.

## Tests

Python, fast (`tests/unit/`), unless marked slow. Datasets come from `p1_index` + `toy_models` (the
six P1 nights including `DEMO-BRAVO-0828`) and `ledger_copy` (seeded ledger), so no test needs `make data`.

Coverage of the SPEC §20 phase 7 test bullets:

| SPEC test bullet | Tests |
|---|---|
| API tests with FastAPI `TestClient`, WebSocket included | `test_api_rest.py`, `test_api_ws.py`, `test_api_static.py` |
| Replay determinism (same second ⇒ same messages) | `test_same_second_same_messages`, `test_same_second_identical_results`, `test_cached_result_equals_computed`, slow `test_precompute_every_rerun_second_matches_recompute` |
| Contract test | `test_api_contract.py`, `test_every_message_validates_against_stream_message`, `npm run check:types` |
| Vitest for stores and formatting | `replayStore`, `matchStore`, `caseStore`, `format`, plus stream, client, router, scene math, perf and panel tests |
| Playwright: open Live watch, play at 5×, stream rows and recorder totals rise, matches by T+90, ledger gains a block | `live.spec.ts`: `streams real data at 5x`, `matches appear by T+90 and the ledger gains a block` |
| Axe check | `pages.spec.ts` (every route) |

`test_live_replay.py`
- `test_t0_is_incident_start_ts`: `t_s` 0 maps to `incidents.start_ts`; the first point has `t_s` 0.
- `test_clock_advances_by_speed_times_wall`: fake time source, speed 5, 2 wall s → 10 s.
- `test_pause_freezes_clock`, `test_seek_clamps_to_duration`, `test_reset_returns_to_zero_paused`.
- `test_speed_accepts_only_1_2_5`: 3 raises `ValueError`.
- `test_visible_points_only_up_to_clock`.
- `test_detection_messages_half_open_interval`: (t0, t1] boundaries; order by `t_s`, then kind, sensor.
- `test_same_second_same_messages`: two engines, same incident, same second → identical JSON.
- `test_rf_and_rid_limited_to_installation_and_window`.
- `test_replay_pauses_at_duration`.

`test_live_phase.py`
- `test_short_track_is_approach`, `test_inbound_is_approach`, `test_orbit_is_loiter`,
  `test_leaving_after_loiter_is_egress` (synthetic 1 Hz features with known answers).

`test_live_loop.py`
- `test_rerun_seconds_schedule`: 45, 50, …, last ≤ duration.
- `test_result_snaps_to_latest_rerun_second`: at 93 → 90.
- `test_no_result_before_min_track_s`.
- `test_same_second_identical_results`: two computes of t = 90 equal except `elapsed_ms`.
- `test_matches_started_before_live_start` (rule 3).
- `test_features_at_ignores_later_points`: appending a point after s leaves `features_at(s)` unchanged.
- `test_result_has_forecast_recall_and_lens_for_top_match`.
- `test_swarm_incident_has_no_single_track_result` (A3).

`test_live_cache.py`
- `test_round_trip`: `put` then `get` equals the `LiveResult` dict.
- `test_cached_result_equals_computed`: precompute, then `result_at(90)` from the cache equals a fresh
  compute except `elapsed_ms` and `cached` (D-013).
- `test_precompute_writes_every_rerun_second_and_features`.
- `test_second_precompute_is_noop_when_fresh`, `test_model_change_makes_cache_stale`,
  `test_force_recomputes`.

`test_live_recorder.py`
- `test_live_tables_have_source_columns`: `DESCRIBE live_points` equals `track_points`, and so on.
- `test_append_returns_rows_total_write_ms_statement`.
- `test_empty_batch_writes_nothing`.
- `test_reset_empties_only_live_tables`.
- `test_live_sink_refuses_truth_path`.

`test_live_session.py` (the `Session` with a fake clock, a fake sink and `ledger_copy`)
- `test_hello_first_and_paused`.
- `test_clock_at_10_hz_while_playing_and_none_while_paused`.
- `test_points_in_order_then_ingest_with_real_counts`.
- `test_seek_forward_writes_skipped_detections_in_one_batch`.
- `test_seek_back_writes_nothing_and_catches_up_last_120_s`.
- `test_rerun_second_sends_match_forecast_recall_dtw`.
- `test_dtw_and_recall_sent_only_when_changed`.
- `test_dtw_request_is_answered`.
- `test_first_rerun_records_incident_registers_model_and_proposes`: three kinds of `ledger` messages.
- `test_rerun_again_appends_no_duplicate_proposal` (§15.6 dedup through the stream).
- `test_proposals_target_case_of_best_ranked_member` (A4, with hand-written match lists so it does not
  depend on the matcher: rank-1 incident in no case, rank-2 DELTA → `CASE-P1-DELTA-260419`).
- `test_no_case_means_no_proposal_and_null_case_id` (hand-written matches, none in a case).
- `test_bad_client_message_is_recoverable_error`.
- `test_stream_rate_under_20_per_second_at_1x`: 60 s of 1× → fewer than 1,200 messages.
- `test_every_message_validates_against_stream_message`.

`test_lens.py`
- `test_path_equals_dtaidistance_best_path`: small known arrays.
- `test_cost_is_base64_float32_with_shape`.
- `test_long_series_averaged_to_128`.
- `test_band_reaches_corner_for_unequal_lengths`.
- `test_dtw_not_above_euclid_for_equal_lengths`.
- `test_unknown_channel_raises`.

Memory additions (named `test_memory_*` so `-k memory` still selects them)
- `test_memory_status.py`: `test_closed_as_hobbyist_on_apr_20` (DELTA after 2026-04-20 09:10 local),
  `test_open_unattributed_without_case`, `test_open_case_counts_links`.
- `test_memory_graph.py`: `test_graph_known_then_has_founder_report_assessment_no_links`,
  `test_graph_after_approvals_has_three_member_edges`, `test_graph_flags_contradictions`.
- `test_memory_evidence.py`: `test_progress_callback_reports_every_file_with_its_hash`.
- `test_memory_cli.py`: `test_reseed_calls_api_when_locked` (lock simulated, `urlopen` patched),
  `test_reseed_exits_1_when_locked_and_no_api`.

`test_api_rest.py` (TestClient on `create_app` over `toy_models` and a ledger copy)
- `test_health`.
- `test_installations_lists_every_base_with_region_and_offset`.
- `test_scene_has_origin_fence_assets_roads_parks_sensors_and_shadow`.
- `test_scene_clips_roads_to_6_km`.
- `test_incidents_filter_by_status`.
- `test_match_at_90_snaps_and_returns_10_8_fields`.
- `test_match_before_min_track_is_empty_with_wait`.
- `test_dtw_endpoint_equals_stream_payload`, `test_dtw_unknown_track_404`.
- `test_history_in_target_frame`, `test_history_refuses_live_track`.
- `test_case_snapshot_known_then_hobbyist_closed_no_links`.
- `test_case_diff_lists_added_members`, `test_case_graph_shape`.
- `test_naive_time_is_422`.
- `test_link_approve_appends_link_approved`, `test_link_reject_supersedes_proposal`,
  `test_link_twice_is_409`, `test_link_wrong_case_is_409`, `test_unknown_proposal_is_404`.
- `test_evidence_without_approve_is_400_and_writes_nothing`.
- `test_evidence_streams_file_progress_then_verified_done`.
- `test_ledger_verify_intact`, `test_ledger_tail_and_record`.
- `test_admin_reset_empties_live_tables`, `test_admin_reseed_restores_seed_head`.
- `test_delta_since`.
- `test_eval_latest_404_then_newest_file`.
- `test_schema_stream_returns_a_stream_message`.

`test_api_ws.py`
- `test_ws_hello_then_clock_after_play`.
- `test_ws_seek_44_play_5x_reaches_match_with_valid_messages`: within 5 wall s, `match`, `forecast`,
  `recall`, `dtw`, `ingest` and `ledger` arrive and all validate.
- `test_ws_unknown_incident_sends_error_and_closes`.
- `test_ws_rest_approval_is_broadcast_as_ledger`.

`test_api_contract.py`
- `test_every_message_type_has_a_valid_example`.
- `test_union_covers_exactly_the_16_3_types` (thirteen, no extra).
- `test_messages_serialize_without_nan`.
- `test_openapi_json_is_current`.

`test_api_static.py`
- `test_root_serves_index`, `test_spa_route_serves_index`, `test_api_404_is_json_not_index`,
  `test_assets_served_with_type`, `test_no_static_dir_is_api_only`.

`test_cli.py` (changed and new)
- `BUILT` gains `replay`, `api`; `test_stub_names_its_phase` now runs for `mcp` only.
- `test_api_dump_openapi_writes_schema`, `test_replay_lists_live_incidents`,
  `test_replay_precompute_then_fresh`, `test_replay_reset_empties_live_tables`,
  `test_replay_reset_calls_api_when_locked`.

Existing guards that now cover the new code without changes: `test_truth_isolation.py` (scans
`src/`), `test_memory_append_only.py` (no `UPDATE`/`DELETE` on `ledger`), `test_no_lookahead.py`.

Slow (`tests/slow/test_full_live.py`, `@pytest.mark.slow`)
- `test_precompute_every_rerun_second_matches_recompute`: full precompute of the P1 live incident; for
  every rerun second the cached result equals a fresh compute (except `elapsed_ms`, `cached`).

Web, Vitest (`web/tests/`)
- `stream.test.ts`: dispatch by type; malformed JSON dropped; reconnect backoff 0.5 → 8 s; on reconnect
  resends speed, seek to last `t_s`, play if playing; `close()` stops reconnecting.
- `client.test.ts`: link POST body (`proposal_seq`, `decision`, `analyst: "demo"`, `clock`); evidence
  NDJSON parsed line by line; errors carry the server's message.
- `replayStore.test.ts`: buffers fill; stream rows capped at 200, newest first; detection rate over
  the last 5 replay seconds; recorder totals from `ingest`; `seeked` clears buffers; features keep 120 s.
- `matchStore.test.ts`: a `match` replaces the list; entrance flag only for a new top-3 set; decision
  after approve; `memory_status` passed through.
- `caseStore.test.ts`: blocks sorted and deduped by seq; verify state; selected record.
- `format.test.ts`: `tPlus(62)` = "T+01:02"; meters; short hash; local date "Apr 19"; rates.
- `router.test.ts`: path matching, navigation, popstate.
- `sceneMath.test.ts`: `toScene` with the origin and `y → −z`; sweep angle equals the detection bearing
  at the detection time; packet arc endpoints; trail alpha 1 → 0 over 60 s; RF ring radius 0 → 300 m
  over 1.2 s; quatrefoil symmetry.
- `perf.test.ts`: 2 s above 25 ms drops bloom, 2 more s halves packets, short spikes do not.
- `CommandBar.test.tsx` (updated), `LiveWatch.test.tsx` (Canvas mocked), `Stream.test.tsx`,
  `Signals.test.tsx`, `Recorder.test.tsx`, `LedgerChain.test.tsx`, `MatchList.test.tsx` (three entries,
  ring, chips, status; Approve calls the client; disabled without a proposal seq).

Web, Playwright (`web/e2e/`, Chromium; `make e2e`)
- `live.spec.ts`
  - `streams real data at 5x`: reseed, open `/live/DEMO-BRAVO-0828`, Play, 5×; stream rows and the
    recorder total rise over two samples; the drone summary reports points.
  - `matches appear by T+90 and the ledger gains a block`: when the command bar reads ≥ T+01:30 the
    match list has three entries, each with a score and at least one reason; the ledger chain shows a
    seq above the seed head.
  - `approve link adds a block and turns the ring verified`.
  - `reduce motion keeps the data`: `reducedMotion: "reduce"` → `data-perf` shows effects off and the
    stream still updates.
  - `no request leaves the origin`: every request URL during the run is same-origin (rule 5).
- `pages.spec.ts`: every route renders the command bar; `@axe-core/playwright` on each route reports no
  serious or critical violation; at 1440 × 900 no horizontal scroll and both rails visible; at
  1200 × 900 the rails stack under the theater.
- `screens.spec.ts`: at 1920 × 1080 and 1440 × 900, screenshots at first contact, T+45 (matcher has
  run), T+90 (matches), and after an approval → `reports/figures/ui/phase07-<moment>-<w>x<h>.png`.
- `perf.spec.ts`: 10 s of 1× playback from T+5; median and 5th-percentile fps, frame count, WebGL
  renderer, user agent, CPU model and viewport → `reports/figures/ui/perf.json`.

## Exit-check mapping

| Criterion (SPEC §20 phase 7) | Command | Evidence it produces |
|---|---|---|
| Fast tests, lint, typecheck, Vitest (gate `always`) | `make check` | ruff clean; pytest count ≥ 586 (expected about 700); web lint, typecheck, `check:types`, Vitest counts |
| Web build (gate) | `npm --prefix web run build` | `tsc` clean; `dist/` asset list and sizes (`vendor-3d` chunk) |
| `make demo` serves everything offline from FastAPI | see block 1 | `/api/health` answers; `/` returns the built `index.html`; live incidents listed; `match?at=90` returns three matches with `cached: true`; a WebSocket client at 5× receives every message type by T+50; the server is stopped and :8000 is free |
| D-010 resets while the API runs | inside block 1 | `memory reseed` and `replay --reset` print that they went through the API; `data/memory.duckdb` back at seed head `a361b4bf…` |
| `make dev` (phase checklist) | see block 2 | Vite :5173 serves the app and proxies `/api/health`; both stopped |
| `make e2e` (gate) | `make e2e` | Playwright list: every spec passed; axe: 0 serious or critical; screenshot files listed |
| Screenshots reviewed per §17.13 | review of `reports/figures/ui/phase07-*.png` | per screenshot: findings and fixes, in EXIT_CHECK.md and PROGRESS.md |
| Median frame rate and machine in PROGRESS.md | `cat reports/figures/ui/perf.json`; `sysctl -n machdep.cpu.brand_string`; `sw_vers -productVersion` | fps median and P5, renderer string, CPU, macOS version |
| Contract and generated types are current | `uv run kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types && git diff --exit-code web/openapi.json web/src/api/types.gen.ts` | exit 0 |
| Phase test bullets (API, WebSocket, determinism, contract) | `uv run pytest tests/unit -q -k "api or live or lens"` | pass count |
| Slow tests still pass | `make test-all` | total pass count (601 + new) |

Block 1, `make demo` (background, time-limited, everything inside the repo):

```bash
mkdir -p data/cache/exit7
make demo > data/cache/exit7/demo.log 2>&1 &
curl -sf --retry 240 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/ | grep -o '<title>[^<]*</title>'
curl -s 'http://127.0.0.1:8000/api/incidents?status=live' | python3 -m json.tool | head -20
curl -s 'http://127.0.0.1:8000/api/match/DEMO-BRAVO-0828?at=90' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["t_s"], d["cached"], d["elapsed_ms"], [(m["incident_id"], round(m["score"], 3)) for m in d["matches"][:3]])'
uv run python -I - <<'EOF'
import collections, json, time
from websockets.sync.client import connect
seen = collections.Counter()
with connect("ws://127.0.0.1:8000/ws/replay/DEMO-BRAVO-0828") as ws:
    for m in ({"type": "speed", "value": 5}, {"type": "seek", "t_s": 40}, {"type": "play"}):
        ws.send(json.dumps(m))
    end = time.monotonic() + 6
    while time.monotonic() < end:
        seen[json.loads(ws.recv(timeout=2))["type"]] += 1
print(dict(sorted(seen.items())))
EOF
uv run kairos-defense replay --reset
uv run kairos-defense memory reseed
pkill -f "kairos-defense api --static web/dist"; wait
curl -s -o /dev/null http://127.0.0.1:8000/api/health || echo "port 8000 free"
uv run kairos-defense memory verify
tail -5 data/cache/exit7/demo.log
```

Block 2, `make dev` (background, time-limited):

```bash
make dev > data/cache/exit7/dev.log 2>&1 &
curl -sf --retry 120 --retry-delay 1 --retry-connrefused http://127.0.0.1:5173/api/health
curl -s http://127.0.0.1:5173/ | grep -o '<title>[^<]*</title>'
pkill -f "kairos-defense api --reload"; pkill -f "vite"; wait
curl -s -o /dev/null http://127.0.0.1:5173/ || echo "port 5173 free"
```

## Documentation to write or update

- New: `src/kairos_defense/api/README.md`, `src/kairos_defense/live/README.md` (package template).
- Update: `src/kairos_defense/store/README.md` (`DuckLiveSink`, `FileResultCache`, `reseed_ledger`,
  `LIVE_DDL`), `match/README.md` (`lens.py`), `memory/README.md` (`incident_status`, `case_graph`,
  evidence `progress`, reseed moved), `config/README.md` (`paths.live`), `src/kairos_defense/README.md`
  (CLI: `api`, `replay`, reseed fallback; module map), `web/README.md` (rewritten for the phase 7 app:
  structure, stores, stream client, theater, panels, scripts, e2e, gotchas), root `README.md` (Status
  row for phase 7, run instructions for `make dev`, `make demo`, `make e2e`).
- `docs/PROGRESS.md`: session log entry; the phase 7 evidence line (Status cell left to the
  autopilot); the §17.13 review log (findings and fixes per screenshot); median frame rate, renderer and
  machine.
- `docs/DECISIONS.md`: D-103 to D-118 (A1–A16), plus any deviation found while building.
- `docs/phases/phase-07/EXIT_CHECK.md` and `REPORT.md` (templates).
- `web/openapi.json` and `web/src/api/types.gen.ts` (generated, committed).

## Risks and mitigations

- **Playwright's Chromium revision is not cached.** Run `npx playwright install chromium` (network is
  allowed for installs, not at run time). If it cannot download, write BLOCKED.md.
- **Headless WebGL may be a software renderer** (SwiftShader): low fps, auto-degrade drops bloom in
  screenshots. Launch flags try the GPU; the renderer string is recorded; phase 7 does not assert fps.
  Screenshots are reviewed for layout, contrast and legibility, which do not depend on the renderer.
- **WebSocket tests are timing-sensitive.** The `Session` is tested with a fake clock (no waiting); only
  four TestClient WebSocket tests use real time, with seek 44 at 5× and 5 s ceilings.
- **DuckDB locks.** The API opens the main database read-only and keeps live and memory files apart, so
  `make demo` and the e2e server (port 8765, scratch files) can run together and CLI reads keep
  working. A process holding the main file read-write (`make index`) still blocks the API: the startup
  error says so.
- **Precompute cost.** Measured 20–40 s for BRAVO. If it exceeds 3 minutes, the lens moves to on-demand
  (it is the cheapest part) and the reason is logged.
- **React re-renders per message** would stall the theater. Stores are written outside React; panels
  use the 10 Hz throttled hook; Vitest asserts the throttle; the perf spec shows the result.
- **troika fonts.** drei `Text` falls back to a CDN font when none is given; every `Text` gets the local
  `.woff`, and `no request leaves the origin` catches a miss.
- **openapi-typescript output for the union.** If it emits a shape `tsc` rejects, keep the generated
  file untouched and narrow in `src/api/messages.ts`.
- **Ledger growth in the real file.** `make demo` appends live proposals to `data/memory.duckdb` (that
  is the product). The exit check reseeds through the API afterwards; e2e uses scratch files.
- **Gate test count.** Two stub cases disappear; about 120 new fast Python tests are added.
- **Scope.** This is the largest phase so far. Order of work follows the exit check: API and stream
  first (testable alone), then data layer, shell, rails, theater, e2e. Module size limits are kept by
  splitting (`routes.py` / `routes_memory.py`, `cli_live.py`, `live/session.py`).

## Out of scope

- Phase 8: time-warp lens UI and Match explainer, ghost trails, core beams, region constellation,
  forecast path and zone in the theater, report recall overlay, Case board, Evidence, Shift delta and
  Eval pages, Director mode and its keys (except M), film grain and manual performance modes, the
  ≥ 50 fps target. The stream already carries `dtw`, `forecast` and `recall`, and the REST routes they
  need exist.
- Phase 9: swarm matching and descriptors, Swarm view, the encore beat, agent tools, MCP server,
  `docs/DEMO.md`.
- Opening cases from the UI, analyst identities beyond the `demo` handle, authentication (§2).
- The live top-3 gap (D-081): accepted in phase 4; the e2e asserts three matches, not their ids.

## Review changes

<!-- filled in when a reviewer's blocking issues are resolved -->
