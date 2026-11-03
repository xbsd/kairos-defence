# Phase 12: DTW workbench and live-mode documentation, report

Status: done (the gate decides: `scripts/cloud_gate.py gate 12`) · Date: 2026-11-03 · Commits:
`a2074d5` (plan), `07bba8d` (review 1, revision and the matcher trace), `b4104e8` (review 2,
approved), `9b0578c` and `6514c88` (checkpoints), and `phase 12: DTW workbench …`

## Summary

People can now watch the matcher work (`docs/phases/PHASE_12.md`):

- `DtwMatcher.match(q, trace=True)` records what one call computed (the prefilter's shortlist, every
  candidate's DTW distance, similarity, band and time, warping paths and cost thumbnails for the
  first 50 plus any final top-10 track computed later, the fusion inputs and scores, the final
  ranking) without changing any result, and measures its own overhead.
- A `matcher_trace` message follows each `match` on the replay stream and on the live stream
  (fresh reruns only); `GET /api/trace/{incident}?at=` and `GET /api/live/trace` serve them.
- The **DTW workbench** replays one run in slow motion from that record: the shortlist, each
  alignment (two curves joined along the warping path, the cost matrix with the path, a readout),
  the ranking re-sorting as each lands, then the fused top 5 with reasons. Its header says what is
  shown ("Slow-motion replay of rerun T+01:20: 500 alignments computed in 202 ms; the first 50
  and 6 more of the final top 10 replayed at 6 per second"). It pins the run it opened with, has
  Pause, Step, Replay and three speeds, and opens on the final state with reduced motion. Open it
  from "DTW workbench" under the Matches panel (Live page, Live watch) or "Watch the matcher work"
  on the Match explainer.
- The user guide has a new section 13, Live mode (launching each scenario from the UI and the
  CLI, the expectations, the reveal, the workbench, `live check`, `live reset`, the ingest
  contract for real adapters) with four screenshots that `make e2e` takes from a real 20× flight;
  README, one-pager, DEMO and the package READMEs describe live mode and the workbench.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Matcher trace | The record of one match call, identical results, measured overhead | `match/trace.py`, `match/matcher.py`, `match/candidates.py`, `match/dtw_rerank.py` (`alignment`) |
| Streams and routes | `matcher_trace` after each `match` (replay cache `CACHE_FORMAT` 2; live fresh reruns), the two GET routes, schemas and OpenAPI types | `api/schemas_trace.py`, `api/schemas.py`, `api/schemas_live.py`, `api/routes.py`, `api/routes_live.py`, `live/loop.py`, `live/session.py`, `live/runner.py`, `live/feed.py` |
| Workbench | Replay machine, store and rAF clock, panel, dialog, button; Match explainer button | `web/src/workbench/*`, `web/src/state/matchStore.ts`, `dispatch.ts`, `web/src/api/messages.ts`, `client.ts`, `panels/MatchList.tsx`, `pages/MatchExplainer.tsx`, `app/App.tsx` |
| Stream panel | Rows skip the fade when they arrive faster than 10 a second (D-191) | `web/src/panels/Stream.tsx` |
| Docs | Guide section 13 with four screenshots; README, one-pager, DEMO, READMEs | `docs/USER_GUIDE.md`, `docs/guide/img/live-mode-*.png`, `web/e2e/guide.spec.ts`, `README.md`, `docs/ONE_PAGER.md`, `docs/DEMO.md` |

## Decisions and deviations from SPEC

D-187 to D-191 in `docs/DECISIONS.md`: the matcher trace (D-187), the trace on the streams and
routes (D-188), the workbench (D-189), live mode in the guide (D-190), and stream rows that skip
the fade when they arrive fast (D-191, found in the guide's first live-mode screenshot).

Deviations from the block and the plan:

- Paths are down-sampled to at most 48 points (the block says about 64): 48 keeps the trace near
  170 kB per rerun with 50 paths.
- 500 candidates (D-068), not 50: the workbench replays the first 50 in the order computed plus
  any final top-10 track computed later, and its header says so.
- `TraceCurves` and `CostThumb` live in one file, `workbench/TraceViews.tsx`, not two.
- Once fused, the alignment shown is the fused #1's (the last computed candidate was a poor match
  and said little), found while reviewing the screenshots.

## Tests

- New Python tests (fast): `test_matcher_trace.py` (identical results with and without the
  trace at T = 60, 120, 180 on two queries; order, counts and fields; the 50-path cutoff plus the
  top 10; down-sampling and thumbnails; the overhead printed), `test_api_trace.py` (a
  `matcher_trace` after each replay `match` with the same top 3; `GET /api/trace` at the latest
  rerun at or before `at`, 404 and 422; `GET /api/live/trace` 404 before a rerun). Extended:
  `test_live_hub.py` (fresh reruns stream a trace; a backfilled rerun is computed untraced and
  streams nothing), `test_api_live.py` (after a flight, `GET /api/live/trace` equals the last
  streamed trace and its top 3 the last `match`), the contract tests' type sets (`matcher_trace`
  added; one test renamed to say so).
- Vitest: `workbenchMachine.test.ts`, `WorkbenchPanel.test.tsx` (including the pinned trace
  against a newer one, reduced motion and at most 10 renders a second), `Stream.test.tsx` (D-191).
- Playwright: `e2e/workbench.spec.ts` (live at 20×: aligning under the pinned rerun, settling,
  then after the close the Matches panel's rerun second and top 3; from the Match explainer with
  Pause and Step; axe on the open dialog; screenshots at 1440 × 900 and 1920 × 1080) and a
  `guide.spec.ts` test for the guide's four live-mode screenshots. No skip or xfail marker was
  added and no test was weakened.
{{TEST_COUNTS}}

## Exit check

{{EXIT_TABLE}}

## Metrics

Measured on the demo replay (`DEMO-BRAVO-0828`, 95 reruns) after `replay --precompute`:

| Measure | Value |
|---|---|
| Trace per rerun (compact JSON) | median 167 kB (161 to 171 kB) |
| Recording the trace (`trace_ms`) | median 120 ms, at most 340 ms; the matcher's own run median 440 ms |
| Replay cache | 97 files, 25.2 MB (about 270 kB per rerun with the trace) |
| `replay --precompute` from an empty cache | 88 s (94 reruns computed) |
| Unit test (`test_matcher_trace.py`, toy models) | 40 to 93 ms of trace overhead per call |

The §19 history metrics are unchanged: with the trace off the matcher runs the same code, and
with it on its results are identical (tested). Live reruns are traced only when fresh.

## Known issues and follow-ups

- The trace costs about 120 ms per traced rerun in this container (paths, curves and thumbnails
  for 50 candidates); at 50× in `live check` only fresh reruns pay it.
- The workbench replays the first 50 candidates in the order computed, not all 500; the other
  450 keep their distance, similarity and time in the trace but no path.
- In this container the browser draws about 8 frames a second with the 3D theater on software
  WebGL; D-191 keeps fast stream rows visible, and other panel animations may look stepped there.

## How to debug this phase

- `uv run python -c "…DtwMatcher(...).match(q, trace=True).trace"` or
  `GET /api/trace/DEMO-BRAVO-0828?at=90` on a running API shows a trace; its `trace_ms` is the
  overhead and `dtw.detail` the replayed candidates.
- After changing the trace's fields: update `api/schemas_trace.py`, then
  `uv run kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types`,
  and run `uv run kairos-defense replay --precompute --force` (or bump `CACHE_FORMAT`).
- The workbench's state is on `data-stage`, `data-step`, `data-t` and `data-track` of
  `[data-testid=workbench]`; `workbenchStore.getState()` in the console shows the pinned trace.

## Fix attempts

None: the gate is run once the exit check has passed.
