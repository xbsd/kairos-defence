# Phase 8: Command Center: the memorable moments, report

Status: done (awaiting the autopilot gate) · Date: 2026-10-29 · Commits: the single
`phase 8: Command Center memorable moments and Director mode` commit

## Summary

Phase 8 adds the demo's memorable moments to the phase 7 Command Center:

- the time-warp lens, whose connectors morph from "Same time" onto the real DTW path, with the
  cost matrix and its path drawn on;
- afterglow ghosts of the matched past flights in tonight's frame, and core beams;
- the region constellation;
- the forecast's dotted exit path and pulsing recovery zone, with County Rd 12 lit inside it;
- the DELTA report resolving at the lower left with a beam to that road;
- five pages: the Match explainer, the Case board (Known then and Known now), Evidence, Shift
  delta and Eval;
- Director mode: one beat per §1.2 row, computed captions, camera shots, keys, and reduce-motion
  and performance modes.

At 1× every §1.2 row lands at its replay second, at a 59.9 fps median on the dev laptop.
Director never commits anything by itself. `make e2e` passes with axe clean on every route.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Explainer route | One match taken apart: decorated match, fusion contributions, tonight's path to the rerun second, the past flight, its window and §10.4 step 6 alignment (D-135) | `api/routes_explain.py`, `match/explain.contribution_table` |
| Page routes | Case list, decisions, evidence list, evidence verify with a path guard; page response models; `--exports` (D-136, D-137) | `api/routes_memory.py`, `api/schemas_pages.py`, `memory/asof.case_summaries`, `cli_live.py`, `api/services.py` |
| Eval targets | §19.3 and §10.9 targets as data, written into the eval JSON, the Markdown's target column (D-139) | `eval/targets.py`, `eval/report.py`, `eval/report_md.py` |
| Web data layer | REST client for every new route, page types, stores for ghosts, overlay, scene and Director, lens selection and hover in `matchStore`, Performance mode in `uiStore` | `web/src/api/`, `web/src/state/` |
| Time-warp lens | Math, OKLab ramp, curves with the 1.2 s morph, cost matrix, compact and full variants, the memory-rail panel (D-126, D-127) | `web/src/lens/`, `web/src/panels/LensPanel.tsx` |
| Theater afterglow | Ghosts, core beams, forecast path, zone and label, in-zone road, the road's screen projection, computed memory and forecast shots, static grain (D-128 to D-134, D-144) | `web/src/three/Ghosts.tsx`, `ghostLayer.ts`, `ghostMath.ts`, `CoreBeams.tsx`, `beams.ts`, `Forecast.tsx`, `forecastLayer.ts`, `forecastMath.ts`, `Projector.tsx`, `camera.ts`, `CameraRig.tsx`, `Effects.tsx` |
| Memory rail and overlay | Region constellation; report recall with clue spans, glyph resolve, zone note and the beam (D-130, D-131) | `web/src/panels/RegionConstellation.tsx`, `constellation.ts`, `web/src/overlay/` |
| Pages | Match explainer, Case board (scrubber, d3-force graph, diff, approvals, decisions), Evidence, Shift delta, Eval (D-135 to D-140) | `web/src/pages/`, `web/src/explainer/`, `web/src/case/`, `web/src/eval/` |
| Director mode | Beats, engine, captions, driver, actions, caption and progress rail, keys, reset, full screen (D-122 to D-125, D-142, D-143) | `web/src/director/`, `web/src/app/keys.ts`, `fullscreen.ts`, `App.tsx`, `CommandBar.tsx` |
| End to end | Director at 5× and 1×, lens, pages, axe on every route and on Live watch at T+120 (D-145) | `web/e2e/director.spec.ts`, `director-1x.spec.ts`, `lens.spec.ts`, `pages8.spec.ts`, `pages.spec.ts`, `helpers.ts` |

## Decisions and deviations from SPEC

- [D-122](../../DECISIONS.md) to [D-145](../../DECISIONS.md): the plan's A1–A24, as built.
- Deviations from the plan, recorded in those entries:
  - D-132: the separate `RoadHighlight.tsx` was folded into `Forecast.tsx`.
  - D-136: `case_summaries` takes no offsets.
  - D-134: the forecast shot shifts its content right and up, so the recall overlay never covers
    the zone.
  - D-127: §1.2's "ALPHA … flown ~18% slower" is not what the 60 s window computes. The UI shows
    ALPHA-260303 at 1.03 (no pace text) and DELTA at "flown 19% faster".
- [D-146](../../DECISIONS.md): the screenshot review's findings and fixes (three rounds plus pages).
- [D-147](../../DECISIONS.md): structure forced by the React compiler lint rules, and the
  `sceneStore`.

Plan-review suggestions (`PLAN_REVIEW-1.json`), applied:
- EXIT_CHECK.md explains the accepted `live_top3_incidents` WARN next to its line (D-081).
- The `make demo` curl waits up to 300 s.
- The cost matrix draws one pixel per cell with no downsampling, and `pathCells` is tested.
- The 1× spec presses → only on the page beats.
- Each Director run reseeds and empties `data/cache/e2e/exports`.
- The targets test tells you to update `eval/targets.py`, never the script.
- The 1440 × 900 rail budget was set before the review (D-145).

Not applied, with the reason:
- Failing the frame-rate spec on darwin when the renderer is SwiftShader. The spec asserts ≥ 50
  fps only on a hardware renderer and annotates software WebGL (D-145), so a gate machine
  without a GPU does not fail on its environment. This machine used ANGLE Metal, and the
  assertion ran and passed at 59.9 fps.
- A Vitest that the T+105 ghosts end inside or near the zone. Ghost mapping stays translation
  only (A7, D-128): the P1 approaches agree within 5°, and the forecast keeps its own §13
  rotation. The round-2 forecast screenshot shows the three ghosts ending at the zone.

## Tests

- New fast Python tests (21):
  - `test_api_explain.py` (5);
  - `test_api_cases.py` (5);
  - `test_api_evidence.py` (3);
  - `test_memory_cases.py` (1);
  - `test_eval_targets.py` (4);
  - `test_explain.py` (+2);
  - `test_live_cli.py` (+1, `--exports`);
- Counts:
  - `make check`: 731 fast Python tests (710 at the start + 21).
  - `make test-all`: 747 passed.
- Vitest: 153 tests in 35 files (73 at the start):
  - `lensMath`, `ramp`, `ghostMath`, `forecastMath`, `camera`, `constellation`, `clues`;
  - `engine`, `captions`, `director` (the driver), `keys`, `graphModel`, `evalView`;
  - `TimeWarpLens`, `RecallOverlay`, `pages` (explainer, Case board, Evidence, Shift delta, Eval);
  - extended `router`, `CommandBar`, `uiStore`, `matchStore`, `LiveWatch`.
  - Real payloads: `web/tests/fixtures/*.json`, written by `dump_fixtures.py`.
- Playwright: 29 tests in `web/e2e/`, 8.3 min. New: `director.spec.ts` (4), `director-1x.spec.ts`
  (1), `lens.spec.ts` (1, with an axe check on Live watch at T+120), `pages8.spec.ts` (2), and
  `pages.spec.ts` with two more axe routes.
- Changed tests, all for intended behavior changes:
  - `router.test.ts`: the phase 8 routes replace the "planned" placeholders, and query
    parameters are tested.
  - `CommandBar.test.tsx`: Director is now enabled. Tests for local time and Performance mode
    were added.
  - `LiveWatch.test.tsx`: the memory rail now has three panels in order.
- No skip or xfail markers were added.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| Director at 1× through every §1.2 row, times recorded | pass | T+0 21:40:06, T+15, T+45, (T+80: loiter marker at T+87), T+90, T+105, T+120 21:42:06; Case board and Evidence on →; encore is phase 9 |
| Screenshots of every beat at both sizes reviewed, fixes logged | pass | 18 beat screenshots + 12 page screenshots; 3 review rounds, 17 fixes (D-146) |
| Median frame rate ≥ 50 fps on the dev machine | pass | 59.9 fps median and P5, ANGLE Metal on Apple M4 Max, macOS 26.5.2, 1920 × 1080, bloom on |
| `make eval` demo assertions pass | pass (one accepted gap) | every demo row except `swarm_top1` passes, apart from `live_top3_incidents` (accepted, D-081, WARN); `check_targets.py 8` exit 0 |
| Playwright Director at 5×, each beat's key element; axe on every page | pass | `make e2e` 29 passed in 8.3 min; axe clean on 9 routes and on Live watch at T+120 |
| Contract current | pass | regenerated `openapi.json` and `types.gen.ts` byte-identical |
| `make demo` serves the new pages | pass | health ok, `/api/cases`, `/api/explain/…`, eval `targets`, SPA routes 200, port freed |

Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Phase 8 changes no matcher, recall, forecast or metric code. `make eval` gives the same numbers as
phase 7:
- Recall@5 at T = 120 s: 1.000.
- DTW lift: +0.522.
- Copycat-first rate: 0%.
- Report linkage: 1.000.
- Forecast median error at T = 90 s: 340 m.
- Time to match: 96%.
- Latency p95: prefilter 30 ms, DTW 57 ms, end to end 124 ms (timing noise; report only, D-060).

The JSON now also carries `targets`.

UI performance on the dev laptop:
- 59.9 fps through every Live watch beat at 1×.
- Bundle: only `LiveWatch` loads `vendor-3d` (1.2 MB). The Case board chunk is 66 kB (d3-force);
  the other pages are 4–13 kB.

## Known issues and follow-ups

- The live top 3 at T+90 is still DELTA, ALPHA-260303, CHARLIE-260710 (D-081). At T+105 it is
  BRAVO-251114, DELTA, ALPHA-260303. Captions and the lens show what the matcher computes.
- At 1440 × 900 the third match entry's buttons sit just below the fold of the match list, which
  scrolls. At 1920 × 1080 all three entries show in full.
- The "No Remote ID" tag can overlap the "Fuel farm" label when the forecast camera is close
  (phase 7 element).
- Scores show 1.00 (the fusion model's confidence on P1). The explainer shows why: a logit of
  +7.89.
- The forecast zone label can reach the theater's right edge at 1440 × 900.
- Swarm view, the encore beat, agent tools, MCP and `docs/DEMO.md` belong to phase 9.

## How to debug this phase

- **Director.**
  - `directorStore.getState()` holds the active flag, page, beat and the beat log.
  - `[data-testid="director-beat"]` carries `data-beat`, `data-n` and `data-t`.
  - A beat that never activates usually means the stream is not open, or a pending seek has not
    landed. The driver waits until the clock is within 2 s of the target.
- **Lens.** `matchStore.getState().dtwBy` holds every payload. The selection is re-requested on
  each new rerun. Connectors carry `data-i`, `data-j` and `data-shown`.
- **Ghosts.**
  - `ghostStore.getState().paths` shows what was fetched.
  - There are no ghosts while the target is `BRAVO-fence`, before T+87.
  - `ghost-count` (visually hidden) says how many ghosts are drawn.
- **Recall beam.** `overlayStore.getState().road` holds the projected point. `recall-beam` has
  `data-on`.
- **Routes.**
  - `curl ':8765/api/explain/DEMO-BRAVO-0828/P1-DELTA-260419-T1?at=90'`.
  - `curl :8765/api/cases`.
  - `curl -XPOST :8765/api/evidence/verify -d '{"dir":"…"}' -H 'content-type: application/json'`.
- **e2e.**
  - Rerun one spec with `npx --prefix web playwright test e2e/director.spec.ts -g 1440`.
  - Artifacts go to `web/test-results/`. Screenshots go to `reports/figures/ui/phase08-*` and
    the 1× record to `director_1x.json`.
  - Key presses in e2e blur first (`press`). A clicked button keeps Space.

## Fix attempts

<!-- appended by fix steps: cause, change, evidence -->
