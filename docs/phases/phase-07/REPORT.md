# Phase 7: Streaming API and Command Center foundation, report

Status: done (awaiting the autopilot gate) · Date: 2026-10-29 · Commits: the single
`phase 7: streaming API and Command Center foundation` commit

## Summary

Phase 7 turns the replay into a live product:

- a FastAPI backend with every §16.4 route and the `/ws/replay/{incident}` stream carrying all
  thirteen §16.3 message types;
- recording into the `live_*` scratch tables, with the real write timings;
- a live loop that reruns the matcher, forecast, report recall and the lens every 5 replay
  seconds, precomputed and cached by second;
- proposals into the case memory, broadcast as ledger blocks;
- the React Command Center: a 3D theater (radar sweep, RF bearings, the drone and its phosphor
  trail, data packets into the Kairos core), four instruments, and a match list whose Approve
  writes a real `link_approved`.

`make demo` serves it all offline from one process. `make e2e` passes 19 Playwright tests with
axe, screenshots and a 59.9 fps median on the dev laptop.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Live replay | `LiveIncident` and the `ReplayEngine` clock (D-118); flight phase (D-115) | `live/replay.py`, `live/phase.py` |
| Live loop | reruns at 45, 50, … s; results with matches, forecast, recall, lens; cache with a fingerprint; precompute (D-105) | `live/loop.py`, `live/precompute.py` |
| Session | one client's §16.3 protocol: clock, detections, ingest, features, results, proposals, ledger fan-out, seek catch-up (D-106, D-107) | `live/session.py`, `live/broadcast.py` |
| Scene | fence, assets, clipped roads, parks, sensors, radar-shadow wedge (D-109) | `live/scene.py` |
| Lens | the `dtw` message: PAA, band, accumulated cost matrix, best path (D-117) | `match/lens.py` |
| Ports and adapters | `IngestStat`, `LiveSink`, `ResultCache`; `DuckLiveSink`, `FileResultCache`; `reseed_ledger` (D-103, D-104) | `ports.py`, `store/live_duck.py`, `store/live_cache.py`, `store/ledger_duck.py`, `store/ddl.py` |
| Memory additions | memory status per match (D-116), case graph, evidence hashing progress (D-108) | `memory/views.py`, `memory/graph.py`, `memory/evidence.py` |
| API | schemas and the `StreamMessage` union, services (composition root), REST, WebSocket, static hosting (D-107 to D-110, D-112) | `api/schemas.py`, `api/services.py`, `api/routes.py`, `api/routes_memory.py`, `api/stream.py`, `api/static.py`, `api/app.py` |
| CLI | `api`, `replay`; reseed and reset through the API when the file is held (D-111) | `cli_live.py`, `cli_memory.py`, `cli_tables.py` |
| Web data layer | generated types, stream client with reconnect, REST client, four Zustand stores, dispatch, throttled hook | `web/src/api/`, `web/src/state/`, `web/src/lib/` |
| Web shell | router, command bar, shortcuts dialog, Live watch layout, planned pages | `web/src/app/`, `web/src/pages/` |
| Live theater | ground, installation, roads, radar, RF, drone, packets, core, camera presets, effects, auto-degrade (D-120) | `web/src/three/` |
| Panels | Stream, Signals, Recorder, Ledger chain with record dialog, Match list with score ring (D-121) | `web/src/panels/` |
| End to end | Playwright config, live, pages, screens and perf specs (D-113) | `web/playwright.config.ts`, `web/e2e/` |

## Decisions and deviations from SPEC

- [D-103](../../DECISIONS.md) to [D-118](../../DECISIONS.md): the plan's A1–A16, as built.
- Deviations from the plan, recorded in those entries:
  - D-105: the cache fingerprint counts `track_features` instead of LanceDB `flight_windows`.
  - D-107: play and pause answer with a plain `clock` (no catch-up).
  - D-110: locks instead of two single-thread executors (same guarantee).
  - D-111: the API seeds an empty or missing ledger at startup.
  - D-114: an npm `overrides` entry lets openapi-typescript (TS 5 peer) use TypeScript 6.0.
  - D-115: the flight phase needs an asset target and does not flicker back to approach
    mid-orbit (the plain rule called the inbound T+45 a loiter).
- [D-119](../../DECISIONS.md): `make dev` keeps its `trap 'kill 0'` recipe instead of
  `concurrently` (§16.6).
- [D-120](../../DECISIONS.md), [D-121](../../DECISIONS.md): theater and panel choices, and the
  screenshot-review fixes.
- [D-113](../../DECISIONS.md): screenshot moments (first contact, T+45, T+90, after an approval)
  stand in for §17.13's Director beats until phase 8.

Plan-review suggestions applied (`PLAN_REVIEW-1.json`):
- Playwright runs with `workers: 1`, not fully parallel.
- The Canvas sits in an error boundary; `--enable-unsafe-swiftshader` is the fallback flag, and
  the renderer string is recorded.
- D-119 records the `make dev` choice; D-113 records the screenshot substitute.
- The exit check stops Vite with a narrow `pkill` pattern.
- Fast tests run two reruns; the full sweep is one slow test.
- The rate test covers a five-track incident.
- §17.12:
  - focus rings come from the base `:focus-visible` rule;
  - the `?` dialog lists the phase 7 keys;
  - Signals has hidden current values;
  - ledger blocks are a list of named buttons.
- 3D colors are read from `tokens.css` at runtime (`theme/colors.ts`, `three/palette.ts`).
- Playwright output goes to the ignored `web/test-results/`.

## Tests

- New fast Python tests (125, plus one new `test_config.py` case):
  - Live: `test_live_replay.py` (12), `test_live_phase.py` (6), `test_live_loop.py` (9),
    `test_live_cache.py` (8), `test_live_recorder.py` (5), `test_live_session.py` (17).
  - Lens: `test_lens.py` (7).
  - API: `test_api_rest.py` (29), `test_api_ws.py` (5), `test_api_static.py` (6),
    `test_api_contract.py` (5).
  - Memory: `test_memory_status.py` (3), `test_memory_graph.py` (3), plus 1 in
    `test_memory_evidence.py`.
  - CLI: `test_live_cli.py` (7), plus 2 in `test_cli.py`.
- Changed:
  - `test_config.py`: `paths.live` and the four-file check.
  - `test_cli.py`: `replay` and `api` are built; the stub test now covers only `mcp`.
  - `tests/conftest.py`: `paths.live`; fixtures `live_kit`, `live_loop`, `make_loop`,
    `api_config` and `api`.
- Slow: `tests/slow/test_full_live.py`, the full precompute equals a recompute at all 95 rerun
  seconds (15 s).
- Counts:
  - `make check`: 710 fast Python tests (586 at the start − 2 stub cases + 126 new).
  - `make test-all`: 726 passed.
- Web:
  - Vitest: 73 tests in 19 files (stream client, REST client, four stores, format, router,
    command bar, Live watch layout, five panels, scene math, the auto-degrade policy, Theater).
  - Playwright: 19 tests in `web/e2e/`.
- No skip or xfail markers were added.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| `make demo`, offline from FastAPI | pass | health ok; app and SPA routes; T+90 match cached (123 ms original); every stream type by T+50 |
| `make e2e` | pass | 19 of 19; axe clean on 7 routes |
| Screenshots reviewed per §17.13 | pass | 8 screenshots; 9 findings fixed (EXIT_CHECK.md) |
| Median frame rate and machine in PROGRESS.md | pass | 59.9 fps median, P5 59.9, ANGLE Metal, Apple M4 Max, macOS 26.5.2, 1920 × 1080 |
| `make dev` | pass | Vite proxies `/api` and `/ws`; both stopped |
| D-010 resets while the API runs | pass | `replay --reset` and `memory reseed` through the API; ledger at seed head |
| Contract current | pass | regenerated `openapi.json` and `types.gen.ts` byte-identical |

Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Phase 7 has no §19 metric and no `check_targets.py` step. For the record (dev laptop):

- One live rerun takes 120–300 ms; `replay --precompute` fills BRAVO (95 reruns and 515 feature
  seconds, 9.1 MB) in 20 s, and a fresh cache makes it a no-op.
- At 5× the first `match` arrives 1.3 s after seeking to T+40.
- A batch insert into `live_points` takes 0.4–1.9 ms.
- Stream rate at 1×: under 20 messages per second (tested on one and on five tracks).
- Frame rate: 59.9 fps median at 1920 × 1080 with bloom on.
- `make eval` was not run: no matcher, recall or forecast code changed.

## Known issues and follow-ups

- The live top 3 at T+90 is DELTA, ALPHA-260303, CHARLIE-260710 (the accepted phase 4 gap,
  D-081). The UI shows what the real matcher returns; the e2e asserts three matches, not their
  ids.
- Scores show 1.00 / 1.00 / 1.00 (the fusion model's confidence on P1, known since phase 6).
- The `vendor-3d` chunk is 1.18 MB (323 kB gzip); acceptable offline, a candidate for lazy
  loading in phase 8.
- R3F logs a "THREE.Clock deprecated" warning from inside the library.
- "No Remote ID" tags every drone of a multi-drone incident (Remote ID is not tied to a track).
- The radar sweep spins five times a second at 5× (truthful but busy); it is hidden in reduce
  motion.
- Phase 8 restores the per-Director-beat screenshot set and owns ≥ 50 fps as a target.

## How to debug this phase

- **Server.**
  - `uv run kairos-defense api --port 8766 --memory data/cache/probe/memory.duckdb --live-db
    data/cache/probe/live.duckdb --reseed` runs a scratch server; `curl :8766/api/health` lists
    problems (missing models or indexes).
  - With `KD_VALIDATE_STREAM=1` every outgoing message is checked against `StreamMessage`.
- **Stream.** A Python client (see EXIT_CHECK.md block 1) counts message types. Each `seek` must
  be followed by `clock` with `seeked: true`.
- **Cache.** `uv run kairos-defense replay` shows its state; `--precompute --force` rebuilds it.
  A changed model or config clears it on first use.
- **"database is locked".** `replay --reset` and `memory reseed` go through the API when it
  holds the file. A process holding `data/kairos_defense.duckdb` read-write (`make index`) stops
  the API.
- **Web.**
  - `make dev`, then http://localhost:5173.
  - Store state: `replayStore.getState()` (import it in the console from Vite's module graph).
  - Playwright traces: rerun one spec with `npx --prefix web playwright test e2e/live.spec.ts
    --trace on`; artifacts in `web/test-results/`.
- **Contract.** After editing `api/schemas.py`: `uv run kairos-defense api --dump-openapi
  web/openapi.json && npm --prefix web run gen:types`.

## Fix attempts

<!-- appended by fix steps: cause, change, evidence -->
