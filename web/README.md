# web (Command Center)

The React Command Center (SPEC §17). From phase 7: the app shell, the replay stream client, the
Zustand stores, the live 3D theater, the instrument rail (Stream, Signals, Recorder, Ledger chain)
and the memory rail's match list with Approve and Reject wired to the API. From phase 8: the
time-warp lens, afterglow ghosts and core beams, the region constellation, the forecast with its
road highlight, the report recall overlay and its beam, the Match explainer, Case board,
Evidence, Shift delta and Eval pages, and Director mode. From phase 9: the Swarm view (the 3D
swarm with formation edges, the matched past swarm as a DTW-aligned afterglow ghost, descriptor
curves), Director's ninth beat (the swarm encore) and the optional chat slide-over.

## Responsibilities

- Provide the only front end (§2): React 19.3, strict TypeScript, Vite 8, Tailwind 4,
  three.js through @react-three/fiber 9, drei 10 and postprocessing (D-114).
- Draw only real stream events and computed results (rule 10): every moving element is driven by a
  `/ws/replay/{incident}` message or the replay clock (§17.3, D-012).
- Keep the §17.1 tokens the only styling vocabulary (D-021): Tailwind classes from `tokens.css`;
  canvases and the 3D scene read the same CSS variables at runtime (`theme/colors.ts`).
- Ship everything from our origin (rule 5): fonts from `@fontsource`, including the `.woff` files
  the 3D labels need (troika does not read woff2 and would otherwise fetch a CDN font).
- Keep high-frequency data out of React re-renders (§17.11): stores are written outside React,
  the theater reads them in `useFrame`, DOM panels redraw at most 10 times a second.

## Public API

- Routes (`src/app/routes.ts`, `Link.tsx`, D-112, D-141): `/` opens Live watch for the first
  live single-track incident; `/live/:incidentId`; `/explainer?incident=&at=&track=`; `/cases`;
  `/cases/:caseId?focus=`; `/evidence?case=`; `/delta?since=`; `/eval`; `/swarm` says phase 9
  builds it. Every page is `React.lazy` (only Live watch loads the `vendor-3d` chunk).
- `src/app/CommandBar.tsx`: breadcrumb, replay clock (`T+mm:ss`, local time in
  `data-local-time`), status chip (Live, Paused, Connecting, Reconnecting, No replay loaded;
  `app/status.ts`), speed 1× 2× 5×, Play, Pause, Restart (seek 0), Reduce motion, Performance
  mode, the Pages menu, Director (`aria-pressed`).
- `src/app/Shortcuts.tsx`, `keys.ts`, `fullscreen.ts`: D Director, Space play or pause (Live
  watch), → and ← beats (Director), R reset, M reduce motion, F full screen, ? the list, Esc.
  Keys are ignored while typing; Space is left to a focused button (D drops focus).
- `src/director/` (D-122 to D-125, D-142, D-143): `beats.ts` (eight beats as data: shot, focus
  panels, reveal, key element), `engine.ts` (`beatAt`, `currentBeat`, `nextBeat`, `prevBeat`,
  `revealOf`, `dimmedIn`), `captions.ts` (one computed sentence per beat), `context.ts`,
  `actions.ts` (`toggleDirector`, `directorNext`, `directorPrev`, `resetDemo`), `useDirector.ts`
  (the driver: pending seeks, beat activation, camera, lens choice and morph, the beat log),
  `DirectorOverlay.tsx` (the 24 px caption in the theater or at the page bottom, the progress
  rail with `data-beat`).
- `src/lens/` (D-126, D-127): `lensMath.ts` (`decodeCost`, `lensScale`, `sameTimeConnectors`,
  `warpedConnectors`, `morphConnectors`, `connectorAt`, `paceWords`, `pathCells`), `ramp.ts`
  (OKLab scope → afterglow), `LensCurves.tsx` (curves, connectors, 1.2 s morph), `CostMatrix.tsx`
  (band, path drawn on), `TimeWarpLens.tsx` (compact and full variants, selectors, readouts).
- `src/overlay/` (D-131): `clues.ts` (report choice, spans, zone note), `scramble.ts`,
  `RecallOverlay.tsx`, `RecallBeam.tsx`.
- `src/explainer/` (`Contributions.tsx`, `FlightPair.tsx`), `src/case/` (`graphModel.ts`,
  `CaseGraph.tsx`, `Scrubber.tsx`, `DiffList.tsx`, `CaseControls.tsx`, `GraphText.tsx`,
  `time.ts`), `src/eval/` (`evalView.ts`, `Charts.tsx`).
- `src/pages/`: `LiveWatch.tsx`, `MatchExplainer.tsx`, `CaseBoard.tsx` (`CaseList` and
  `CaseBoard`), `Evidence.tsx`, `ShiftDelta.tsx`, `Eval.tsx`, `Home.tsx`, `Planned.tsx`.
- `src/pages/LiveWatch.tsx`: the §17.2 grid (theater hero; memory rail on the right; instrument
  rail at the bottom; below 1280 px the rails stack under the theater), with an error boundary so
  a WebGL failure keeps the panels.
- `src/api/`:
  - `types.gen.ts`: generated from `web/openapi.json` (never edit); `messages.ts` names them
    (`StreamMessage`, `MatchItem`, `Scene`, `LedgerBlock` …).
  - `stream.ts`: `ReplayStream` (dispatch by `type`, drop malformed, reconnect after 0.5, 1, 2, 4,
    8 s, then restore speed, position and play), `replayUrl`, `parseMessage`.
  - `client.ts`: `api.health`, `scene`, `installations`, `history`, `dtw`, `match`, `explain`,
    `liveIncidents`, `cases`, `caseSnapshot`, `caseGraph`, `caseDiff`, `recordDecision`,
    `ledgerTail`, `ledgerRecord`, `ledgerVerify`, `decideLink(case, seq, decision, clock)`
    (analyst `demo`), `exportEvidence` (NDJSON), `evidenceList`, `verifyEvidence`, `delta`,
    `evalLatest`, `adminReset`, `adminReseed`; `ApiError` carries the server's message.
  - `pages.ts`: hand-written shapes of the routes that return plain JSON (history, case graph,
    snapshot and diff, shift delta, eval report).
- `src/state/` (vanilla Zustand):
  - `replayStore`: hello, clock (+ `clockNow()` interpolation), tracks, RF, Remote ID, 120 s of
    features, 200 stream rows, detections for packets, the distinct total, recorder writes;
    helpers `detectionRate`, `recordedTotal`.
  - `matchStore`: match (+ its arrival time for the core beams), forecast, recall, dtw and every
    lens payload by match and channel (`lensDtw`), the hovered match, the lens selection and
    mode, `farthestWarp`; `entrance` bumps only for a new top-3 set; session decisions.
  - `directorStore` (active, page beat, last beat, the beat log, page facts, pending seek),
    `ghostStore` (fetched history paths), `overlayStore` (the projected road point),
    `sceneStore` (the scene and the installations).
  - `caseStore`: ledger blocks by seq (with live arrival times), verify result, open record.
  - `uiStore`: reduce motion (OS or M), camera preset (+ `forecast`), performance level,
    Performance mode; `effectsOn`, `beamsOn`, `packetBudget`.
  - `dispatch.ts` routes stream messages; `useReplay.ts` opens the stream, loads the ledger tail,
    re-verifies the chain when the head moves and fetches the scene; `controls.ts`.
- `src/lib/format.ts` (`tPlus`, `meters`, `shortHash`, `localDate`, `baseName`, `rate`, `ms`),
  `src/lib/useThrottledStore.ts`.
- `src/three/`: the live theater (ground grid, installation and labels, radar shadow, roads, radar
  ring and sweep, RF bearings and rings, drone glyph with trail and "No Remote ID" tag, data
  packets, the Kairos core, camera presets, bloom, vignette and static grain, auto-degrade). Phase
  8: `Ghosts.tsx` (+ `ghostLayer.ts`, `ghostMath.ts`), `CoreBeams.tsx` (+ `beams.ts`),
  `Forecast.tsx` (+ `forecastLayer.ts`, `forecastMath.ts`: path, pulsing zone, label, in-zone
  road), `Projector.tsx`, `camera.ts` (`frameBox`, `forecastShot`). `data-perf` on the theater
  shows the effects level; visually hidden text describes the drone, the ghosts and the zone
  (`theater-summary`, `forecast-label`, `ghost-count`).
- `src/panels/`: `Stream`, `Signals`, `Recorder`, `LedgerChain` (+ `LedgerRecord` dialog),
  `MatchList` (+ `ScoreRing`, an Explain link), `RegionConstellation` (+ `constellation.ts`),
  `LensPanel`, all in the shared `Panel` frame (dimmed by Director, `data-dimmed`). On a live
  swarm `MatchList` links to the Swarm view (phase 9).
- Phase 9, Swarm view (`/swarm?incident=&match=`, `pages/SwarmView.tsx`, lazy; no incident opens
  the live swarm): `swarm/SwarmScene.tsx` (+ `swarmLayer.ts`: drones as discs, the ghost as
  rings, nearest-neighbor edges, a 60 s centroid trail, the target ring, a follow camera),
  `swarm/swarmMath.ts` (positions between recorded seconds, `nearestEdges`, `matchSecond` and
  `ghostAt` from `aligned`, `swarmFacts` for the encore caption), `DescriptorCurves.tsx` (spread,
  pair-distance quartiles, rotation rate; the match dashed on tonight's seconds; crosshair; click
  to seek), `SwarmMatches.tsx`, `PlaybackBar.tsx` (+ `usePlayback.ts`: rAF), `SwarmTable.tsx`
  (the text equivalent). State in `state/swarmStore.ts` (the result and the playhead: read in
  `useFrame`, ≤ 10 Hz in the DOM). `REST`: `api.swarms()`, `api.swarm(incident, match, at)`.
- Phase 9, Director: beat 9 `encore` (page beat, route `swarm`, key `swarm-ghost`); its caption
  (`encoreCaption`) is computed from the swarm result's dates, bases and regions; the encore
  reads only.
- Phase 9, chat (`chat/ChatPanel.tsx`, `chat/chatStore.ts`): an Ask button and a slide-over,
  present only when `GET /api/chat/status` says enabled (`llm.provider: none` hides them);
  `POST /api/chat` returns the reply and the tool calls behind it, which the panel lists.

## Data in and out

- In: `GET /api/…` and `WS /ws/replay/{incident}` on the same origin (Vite proxies `/api` and
  `/ws` to `:8000` in dev; FastAPI serves `dist/` in the demo).
- Out: link decisions (`POST /api/cases/{case}/links`), case decisions
  (`POST /api/cases/{case}/decisions`), evidence exports and verifies, admin reset and reseed
  (R). `dist/` from `npm run build` (ignored).
- Generated: `src/api/types.gen.ts` from `openapi.json` (both committed).

## How it works

`useReplay` opens one `ReplayStream`; `dispatch` writes each message into its store (a `clock`
with `seeked` drops the buffers before the server's catch-up). The theater's `useFrame` reads
`getState()` and interpolates the clock between 10 Hz `clock` messages; panels re-render through
`useThrottledStore`. Approve calls the API, then records the decision and the new ledger block;
the server also broadcasts the block to every open stream. Reduce motion turns off bloom,
packets, beams, grain, camera flights, the text scramble and the morph (a cross-fade instead);
every number stays.

Director (D to start) is driven by the replay clock: `useDirector` activates the beat the clock
is on, sets its camera, dims the panels it does not feature, reveals layers cumulatively and logs
when each beat began; → and ← seek (or open the Case board and Evidence pages). Captions are
computed from the same stores. The lens shows the stream's `dtw` or a chosen match and channel
(re-asked each rerun); ghosts are fetched once per past flight and mapped to tonight's target.

## Configuration

- Node 22 (`engines`; the Makefile puts Homebrew's node@22 first, D-002). React and React DOM
  exactly 19.3.1, TypeScript ~6.0.3 (D-019); the 3D, motion and test pins in D-114.
  `overrides` points openapi-typescript's TypeScript 5 peer at the project's TypeScript.
- Scripts: `dev`, `build`, `lint`, `typecheck`, `gen:types`, `check:types`, `test`, `check`
  (lint, typecheck, check:types, test; run by `make check`), `e2e` (Playwright).

## Tests

- Vitest (`tests/`, jsdom): stream client (dispatch, malformed, backoff, restore), REST client,
  stores, formatting, router, command bar, Live watch layout, each panel, scene math and the
  auto-degrade policy; phase 8: lens math and ramp, ghost and forecast geometry, camera shots,
  constellation, clues and scramble, the Director engine, captions, driver and keys, the case
  graph model, the eval view, and the lens, overlay and page components; phase 9:
  `swarmMath.test.ts`, `SwarmView.test.tsx` (real `swarm.json`), `ChatPanel.test.tsx`, the encore
  in `engine` and `captions`, the swarm route. Real payloads are in `tests/fixtures/`
  (`dump_fixtures.py` rewrites them; `swarm.json` keeps positions for its first 180 s).
  `npm --prefix web run check`.
- Playwright (`e2e/`, `make e2e`): `live.spec.ts` (5× stream and recorder rise, three matches by
  T+90 and a new ledger block, approve turns the ring verified, reduce motion keeps the data, no
  request leaves the origin), `pages.spec.ts` (axe on every route, layout at 1440 × 900 and
  1200 × 900, shortcuts), `screens.spec.ts` (screenshots to `reports/figures/ui/`),
  `perf.spec.ts` (frame rate, renderer and machine to `reports/figures/ui/perf.json`); phase 8:
  `director.spec.ts` (Director at 5× at both sizes, every beat's key element and a screenshot
  `phase08-beat-*`; never commits by itself; keys and modes), `director-1x.spec.ts` (the 1× run
  and frame rate to `director_1x.json`), `lens.spec.ts` (connectors on the DTW path; axe on Live
  watch at T+120), `pages8.spec.ts` (each page and its screenshots `phase08-page-*`); phase 9:
  `swarm.spec.ts` (Swarm view at both sizes: top match S1-GOLF-260503, ghost, curves, Play
  advances the playhead, `phase09-swarm-*` screenshots, axe) and the encore step in
  `director.spec.ts` (`phase08-beat-09-encore-*`, ledger head unchanged).
  Playwright starts its own API on :8765 with scratch ledger, live and export folders under
  `data/cache/e2e` (D-113, D-137).
  First time on a machine: `npx --prefix web playwright install chromium`.

## Gotchas

- Change `src/kairos_defense/api/schemas.py`, then `uv run kairos-defense api --dump-openapi
web/openapi.json && npm --prefix web run gen:types`; `check:types` fails on stale types.
- Store buffers are mutated in place: copy before keeping a reference in React state.
- A Tailwind default class (`text-sm`, `bg-blue-500`) silently produces nothing: use tokens.
- ESLint bans hex literals and `setInterval` in `src/`.
- Headless Chromium may render WebGL in software (SwiftShader): `perf.json` records the renderer.
- On a case-insensitive disk, `Shortcuts.tsx` and a `shortcuts.ts` would collide: the hook lives
  in `keys.ts`.
- The React compiler lint rules: mutate three.js objects in module functions called from
  `useFrame`, never in the component body; component files export only components (D-147).
- A clicked button keeps Space: e2e key presses blur first (`press` in `e2e/helpers.ts`).

## Changelog

- Phase 0: scaffold, tokens, fonts, motion helpers, command bar and placeholder Live watch (D-019,
  D-021).
- Phase 7: routing, stream client, stores, live theater, instrument and memory rails, generated
  types, Playwright e2e with screenshots, axe and a frame-rate probe (D-107, D-112 to D-114).
- Phase 8: time-warp lens, ghosts, core beams, constellation, forecast and road highlight, recall
  overlay and beam, Match explainer, Case board, Evidence, Shift delta and Eval pages, Director
  mode, Performance mode, static grain, lazy pages (D-122 to D-147).
- Phase 9: Swarm view, Director's swarm encore, chat slide-over (hidden by default), MatchList's
  swarm link; the planned-page placeholder removed (D-160 to D-162).
