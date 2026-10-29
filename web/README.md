# web (Command Center)

The React Command Center (SPEC §17). From phase 7: the app shell, the replay stream client, the
Zustand stores, the live 3D theater, the instrument rail (Stream, Signals, Recorder, Ledger chain)
and the memory rail's match list with Approve and Reject wired to the API.

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

- Routes (`src/app/routes.ts`, `Link.tsx`, D-112): `/` opens Live watch for the first live
  single-track incident; `/live/:incidentId`; `/explainer`, `/cases`, `/swarm`, `/evidence`,
  `/delta`, `/eval` say which phase builds them.
- `src/app/CommandBar.tsx`: breadcrumb, replay clock (`T+mm:ss`), status chip (Live, Paused,
  Connecting, Reconnecting, No replay loaded; `app/status.ts`), speed 1× 2× 5×, Play, Pause,
  Restart (seek 0), Reduce motion, the Pages menu, Director (disabled until phase 8).
- `src/app/Shortcuts.tsx` and `keys.ts`: M toggles reduce motion, ? opens the shortcuts dialog.
- `src/pages/LiveWatch.tsx`: the §17.2 grid (theater hero; memory rail on the right; instrument
  rail at the bottom; below 1280 px the rails stack under the theater), with an error boundary so
  a WebGL failure keeps the panels.
- `src/api/`:
  - `types.gen.ts`: generated from `web/openapi.json` (never edit); `messages.ts` names them
    (`StreamMessage`, `MatchItem`, `Scene`, `LedgerBlock` …).
  - `stream.ts`: `ReplayStream` (dispatch by `type`, drop malformed, reconnect after 0.5, 1, 2, 4,
    8 s, then restore speed, position and play), `replayUrl`, `parseMessage`.
  - `client.ts`: `api.health`, `scene`, `liveIncidents`, `ledgerTail`, `ledgerRecord`,
    `ledgerVerify`, `decideLink(case, seq, decision, clock)` (analyst `demo`), `exportEvidence`
    (NDJSON); `ApiError` carries the server's message.
- `src/state/` (vanilla Zustand):
  - `replayStore`: hello, clock (+ `clockNow()` interpolation), tracks, RF, Remote ID, 120 s of
    features, 200 stream rows, detections for packets, the distinct total, recorder writes;
    helpers `detectionRate`, `recordedTotal`.
  - `matchStore`: match, forecast, recall, dtw; `entrance` bumps only for a new top-3 set;
    session decisions (`decisionOf`).
  - `caseStore`: ledger blocks by seq (with live arrival times), verify result, open record.
  - `uiStore`: reduce motion (OS or M), camera preset, performance level; `effectsOn`,
    `packetBudget`.
  - `dispatch.ts` routes stream messages; `useReplay.ts` opens the stream, loads the ledger tail,
    re-verifies the chain when the head moves and fetches the scene; `controls.ts`.
- `src/lib/format.ts` (`tPlus`, `meters`, `shortHash`, `localDate`, `baseName`, `rate`, `ms`),
  `src/lib/useThrottledStore.ts`.
- `src/three/`: the live theater (ground grid, installation and labels, radar shadow, roads, radar
  ring and sweep, RF bearings and rings, drone glyph with trail and "No Remote ID" tag, data
  packets, the Kairos core, camera presets, bloom and vignette, auto-degrade). `data-perf` on the
  theater shows the effects level; a visually hidden summary describes the drone.
- `src/panels/`: `Stream`, `Signals`, `Recorder`, `LedgerChain` (+ `LedgerRecord` dialog),
  `MatchList` (+ `ScoreRing`), all in the shared `Panel` frame.

## Data in and out

- In: `GET /api/…` and `WS /ws/replay/{incident}` on the same origin (Vite proxies `/api` and
  `/ws` to `:8000` in dev; FastAPI serves `dist/` in the demo).
- Out: link decisions (`POST /api/cases/{case}/links`). `dist/` from `npm run build` (ignored).
- Generated: `src/api/types.gen.ts` from `openapi.json` (both committed).

## How it works

`useReplay` opens one `ReplayStream`; `dispatch` writes each message into its store (a `clock`
with `seeked` drops the buffers before the server's catch-up). The theater's `useFrame` reads
`getState()` and interpolates the clock between 10 Hz `clock` messages; panels re-render through
`useThrottledStore`. Approve calls the API, then records the decision and the new ledger block;
the server also broadcasts the block to every open stream. Reduce motion turns off bloom,
packets, camera flights and the stream's slide-ins; every number stays.

## Configuration

- Node 22 (`engines`; the Makefile puts Homebrew's node@22 first, D-002). React and React DOM
  exactly 19.3.1, TypeScript ~6.0.3 (D-019); the 3D, motion and test pins in D-114.
  `overrides` points openapi-typescript's TypeScript 5 peer at the project's TypeScript.
- Scripts: `dev`, `build`, `lint`, `typecheck`, `gen:types`, `check:types`, `test`, `check`
  (lint, typecheck, check:types, test; run by `make check`), `e2e` (Playwright).

## Tests

- Vitest (`tests/`, jsdom): stream client (dispatch, malformed, backoff, restore), REST client,
  stores, formatting, router, command bar, Live watch layout, each panel, scene math and the
  auto-degrade policy. `npm --prefix web run check`.
- Playwright (`e2e/`, `make e2e`): `live.spec.ts` (5× stream and recorder rise, three matches by
  T+90 and a new ledger block, approve turns the ring verified, reduce motion keeps the data, no
  request leaves the origin), `pages.spec.ts` (axe on every route, layout at 1440 × 900 and
  1200 × 900, shortcuts), `screens.spec.ts` (screenshots to `reports/figures/ui/`),
  `perf.spec.ts` (frame rate, renderer and machine to `reports/figures/ui/perf.json`).
  Playwright starts its own API on :8765 with scratch files under `data/cache/e2e` (D-113).
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

## Changelog

- Phase 0: scaffold, tokens, fonts, motion helpers, command bar and placeholder Live watch (D-019,
  D-021).
- Phase 7: routing, stream client, stores, live theater, instrument and memory rails, generated
  types, Playwright e2e with screenshots, axe and a frame-rate probe (D-107, D-112 to D-114).
