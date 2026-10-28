# web (Command Center)

The React Command Center (SPEC §17). Today it is the phase 0 scaffold: design tokens, self-hosted
fonts, the shared command bar and a truthful placeholder Live watch screen.

## Responsibilities

- Provide the only front end (§2): React 19.3, strict TypeScript, Vite 8 and Tailwind 4 via
  `@tailwindcss/vite`.
- Make the §17.1 tokens the only styling vocabulary for colors, type, radii, blur and durations
  (D-021).
- Ship fonts from `@fontsource` (B612, B612 Mono) and nothing from a CDN (rule 5).
- Show only real stream events or computed results (rule 10). With no replay connected, the screen
  says so and shows no numbers.

## Public API

- `src/app/App.tsx`: `App`, the placeholder Live watch: the command bar, then a "Live theater" region
  that reads "No replay loaded".
- `src/app/CommandBar.tsx`: `CommandBar({ trail, replayClock, speed, live })`.
  - Shows a breadcrumb, the replay clock (`T+--:--` when `replayClock` is null), a status chip ("No
    replay loaded" or "Live"), the speed (`1×`, `2×`, `5×`), Play, Pause, Restart and Director.
  - The controls are disabled unless `live` is true.
- `src/theme/tokens.css`: the §17.1 `:root` block verbatim, plus Tailwind `@theme` blocks that remove
  the defaults and define:
  - type sizes `text-12` to `text-32`;
  - radii `rounded-panel`, `rounded-button` and `rounded-chip`;
  - `backdrop-blur-glass`;
  - token colors (`bg-scope`, `text-ink-mid`, `text-flash`, …);
  - `font-sans` (B612) and `font-mono` (B612 Mono, tabular figures).
- `src/theme/motion.ts`:
  - `parseCssTimeMs("240ms" | "1.2s") -> number` (NaN if it is not a time);
  - `durationMs(token)`, which reads `--dur-*` from the computed style;
  - `prefersReducedMotion()`.
- `src/theme/fonts.ts`: imports B612 400/700 and B612 Mono 400.

## Data in and out

- In: nothing yet. Phase 7 adds `src/api/` (REST client, the `/ws/replay/{incident_id}` stream and
  generated types, §16.5) and Zustand stores in `src/state/`.
- Out: `web/dist/` from `npm --prefix web run build`. It is git-ignored, and FastAPI serves it in
  `make demo` from phase 7.
- The dev server proxies `/api` (including WebSockets) to `http://127.0.0.1:8000`.

## How it works

- `vite.config.ts` runs the React plugin and `@tailwindcss/vite`. The dev server is on `:5173` with
  `strictPort`. Vitest runs in jsdom with `tests/setup.ts` (jest-dom matchers).
- `tokens.css` resets Tailwind's palette, shadows, easings, text sizes, radii and blurs, so an
  off-token class produces no CSS. The built CSS contains only the 11 token colors (D-021).
- `eslint.config.js` (typescript-eslint strict, react-hooks, react-refresh) rejects `any` and any hex
  color literal in TS/TSX. Use durations as `duration-(--dur-panel)` and easings as `ease-(--ease-out)`.
- Reduced motion is honored globally in `tokens.css` (§17.11), and `prefersReducedMotion()` is there
  for JS-driven motion.

## Configuration

- `package.json` `engines.node` is `>=22 <23`. The Makefile puts `/opt/homebrew/opt/node@22/bin`
  first on PATH when it exists (D-002).
- Pins (D-019): React and React DOM exactly `19.3.1` (R3F 9 needs React below 19.4), TypeScript
  `~6.0.3` (typescript-eslint support), jsdom `^29.1.1` (Node 22.22.0 in the cloud).
- Scripts:
  - `dev`;
  - `build` (`tsc --noEmit` and `vite build`);
  - `lint` (eslint with `--max-warnings 0`, then `prettier --check`);
  - `typecheck`, `test` (`vitest run`), `format`;
  - `check` (lint, typecheck and test), which `make check` runs.

## Tests

- `tests/CommandBar.test.tsx`: the idle and live command bar; the placeholder App shows no numbers.
- `tests/motion.test.ts`: CSS time parsing.
- Run: `npm --prefix web run check`. The build: `npm --prefix web run build`.
- Playwright (`make e2e`), screenshots and axe checks arrive in phase 7. Until then, `make e2e`
  prints that it is not built yet.

## Gotchas

- `npm --prefix web …` run outside `make` uses the `node` on PATH. On the dev laptop that is Node 26,
  so npm prints an EBADENGINE warning. It is harmless; put Node 22 first on PATH to silence it.
- A new color, size or duration needs a token in `tokens.css` first. A Tailwind default class such as
  `text-sm` or `bg-blue-500` silently produces nothing.
- `index.html` declares no favicon, so browsers log a 404 for `/favicon.ico` (phase 7 follow-up).
- three.js, R3F, drei, postprocessing, Motion, D3, Zustand and Playwright are not installed yet; phase
  7 adds them (D-019).

## Changelog

- Phase 0: scaffold, tokens, fonts, motion helpers, command bar and placeholder Live watch (D-019,
  D-021).
