# Phase 12: DTW workbench and live-mode documentation, plan

## Goal

Let people watch the matcher work (`docs/phases/PHASE_12.md`, D-169): at each rerun, the
shortlist the vector search returned, each candidate aligned by DTW with its warping path, the
ranking re-sorting as the scores land, and the fusion step that produces the final order, replayed
in labelled slow motion from a trace of the real computation. Then document live mode so a new
user can run it from the guide.

## Inputs read

- `CLAUDE.md` (rules 1 to 10), `docs/phases/PHASE_12.md`, `docs/phases/PHASE_11.md`,
  `docs/phases/phase-11/REPORT.md`, `docs/CLOUD_HANDOFF.md`, `docs/phases/TEMPLATES.md`,
  `.claude/skills/phase-auto/SKILL.md`.
- SPEC §10 (pipeline, prefilter, DTW, fusion, explanations), §16.3 (stream protocol), §17.1
  (tokens), §17.7 (the time-warp lens), §17.11 (motion), §17.12 (accessibility), §17.13 (visual QA).
- `match/README.md`, `live/README.md`, `web/README.md`, `docs/USER_GUIDE.md`, `README.md`,
  `docs/ONE_PAGER.md`, `docs/DEMO.md`; code: `match/matcher.py`, `candidates.py`,
  `dtw_rerank.py`, `lens.py`; `live/loop.py`, `session.py`, `runner.py`, `precompute.py`;
  `api/schemas.py`, `stream.py`, `routes.py`, `routes_live.py`; `tests/unit/test_api_contract.py`,
  `test_docs.py`; `web/src/state/dispatch.ts`, `matchStore.ts`, `panels/MatchList.tsx`,
  `pages/MatchExplainer.tsx`, `lens/*`, `e2e/guide.spec.ts`, `e2e/livemode.spec.ts`.
- PROGRESS.md and DECISIONS.md through D-186; phase 11 closed by `cloud_gate.py` (gate 1 PASS:
  914 fast Python tests, `live check` 5 of 5, `make e2e` 35 passed).

## Assumptions and decisions

Recorded in `docs/DECISIONS.md` during the build (numbers provisional).

1. **D-187 The matcher trace.** `DtwMatcher.match(q, trace=False)`; with `trace=True`
   `MatchResult.trace` holds a JSON-ready record of that call, and nothing else changes (the same
   arrays, the same order, the same floating-point path). Contents, in computation order:
   - `query`: track, incident, `at_s`, `window_s`, `rows_used`, channel `dist_target_m` and the
     query's curve on it (PAA to at most 48 points, raw meters).
   - `prefilter`: `ms`, `k_windows`, the number of windows returned, and every candidate track in
     prefilter order: rank, track and incident, installation, start, vector distance (squared L2)
     and the best window's size and offset.
   - `dtw`: `ms`, band fraction, normalization, and for **every** candidate in the order computed
     (columns that line up with the prefilter's, so ids are sent once): DTW distance `d`,
     `d_norm`, the calibrated `shape_sim`, band width (cells), `m` (and the shared `n`), and its
     time in ms. For the **first 50** in that order (`TRACE_PATHS`) **plus every final top-10
     track beyond them** (a few extra alignments, so the fused top 5 is always shown aligned) also
     the warping path (the matcher's own full-matrix alignment with the segment's ends relaxed,
     `dtw_rerank.warp_path`'s recipe, down-sampled to at most 48 points), its full length, the
     candidate's curve on the same channel (≤ 48 points) and a 12 × 12 thumbnail of the
     accumulated cost matrix (block minimum, 3 significant digits). The config's 500 candidates
     (D-068) make 500 paths too heavy for every rerun's stream message (about 185 kB with this
     layout, measured; the size is recorded in REPORT.md); every scalar field stays for all.
   - `fusion`: `ms`, the feature names, intercept, and every candidate's feature values and score.
   - `ranking`: the final top 10 (rank, track, incident, score, shape_sim, reasons for the top 5).
   - `total_ms` (the matcher's own time, unchanged by tracing) and `trace_ms` (the extra time spent
     recording paths and thumbnails): the overhead is measured, not guessed.
2. **D-188 Streaming and access.** A `matcher_trace` message (`MatcherTraceMsg`) per rerun: on
   the replay stream (the trace is stored with each cached result; `CACHE_FORMAT` 2, so
   `replay --precompute`, run by `make e2e` and `make demo`, refreshes the cache) and on the live
   stream (fresh reruns only: backfilled reruns are not shown). It is sent with each `match`, and
   only when it changed. `GET /api/trace/{incident}?at=` serves a replay incident's trace at a
   rerun second; `GET /api/live/trace?installation=` the latest live trace. The replay union
   `StreamMessage` gains `matcher_trace` (the contract test's type set and its examples are
   extended to it: a new type, not a weakened check); the live union too. OpenAPI types
   regenerated.
3. **D-189 The workbench.** `web/src/workbench/`: a pure replay state machine
   (`workbenchMachine.ts`: stage `shortlist` → `align` (candidate i lands at i / rate) →
   `fusion` → `done`; the ranking of the landed candidates by shape similarity; reduced motion
   goes straight to `done`), driven by `requestAnimationFrame` with React updates at most 10 per
   second (§17.11); `WorkbenchPanel.tsx`: a header that says what is shown ("Slow-motion replay of
   rerun T+90: 500 alignments computed in 223 ms; the first 50 replayed at 6 per second"), a speed
   control (3, 6, 10 per second: at most one candidate per 10 Hz update, §17.11), Pause, Step and
   Replay (WCAG 2.2.2: moving content that lasts more than 5 s can be paused); the shortlist with
   vector distances; the current candidate's two curves, its cost-matrix thumbnail with the
   warping path (labelled "alignment: full matrix, ends relaxed"; the band is not drawn, because
   that path is the unbanded alignment while the distance is banded, D-069), its distance,
   similarity and time, with a text equivalent; the ranking re-sorting as each score lands; then
   the fused top 5 with their reasons. Every value shown comes from the trace (rule 10); tokens
   only (§17.1). `data-stage`, `data-step` and `data-track` expose the state to Playwright.
   **The workbench pins the trace it opened with**: the dialog snapshots it on open and names its
   rerun in the header; a newer trace from the stream only enables "Newer rerun available:
   replay it", which switches to it; nothing restarts on its own. It opens in a native dialog
   (`WorkbenchDialog`, `aria-labelledby`; the SVG curves and thumbnail are `role="img"` with an
   `aria-label`) from a "DTW workbench" button on the Live page and on Live watch (the stream's
   latest trace at that moment) and from the Match explainer ("Watch the matcher work", the
   trace fetched for that incident and second).
4. **D-190 Documentation.** A "Live mode" section in `docs/USER_GUIDE.md` (launching each
   scenario from the UI and the CLI, what to expect, the ingest contract for real adapters, the
   workbench, `live check`, `live reset`) with new screenshots taken by `web/e2e/guide.spec.ts`
   (a new test: the scenario launcher set for `new-operator-twice`, the Live page with a live
   incident and its matches, the workbench paused mid-replay, the reveal card) into
   `docs/guide/img/`: each a literal `snap(page, "live-mode-…")` call (the docs test reads only
   literals), whole-page PNGs at 1920 × 1080, distinct and over 20 kB, so `test_docs.py` keeps
   checking that every guide image is written by that spec. The guide's section is a new
   `## 13. Live mode` after the glossary (no section is renumbered, so no anchor breaks); the CLI
   reference's `### Live mode` subsection becomes `### Live-mode commands` and links to it.
   The trace's models live in a new `api/schemas_trace.py` (`schemas.py` is past 400 lines). README (a
   "Live mode" quick start), `docs/ONE_PAGER.md` (one sentence), `docs/DEMO.md` (the workbench in
   the live segment), the package READMEs, PROGRESS.md and DECISIONS.md.

## Work breakdown

Each step ends with `make check` and a checkpoint commit.

1. **Trace (Python).** `match/trace.py` (`TraceRecorder`: down-sampling, thumbnails, the record
   layout), `dtw_rerank.alignment(live, seg, weights, mode, scales) -> (path, cost)` (the
   full-matrix alignment `warp_path` already computes, now also returning the accumulated cost),
   `CandidateBuilder.build(q, recorder=None)` (per-candidate time and fields; paths for the first
   `TRACE_PATHS`), `DtwMatcher.match(q, trace=False)` (prefilter, fusion and ranking sections,
   and the paths of final top-10 tracks beyond the first 50).
2. **Stream and routes.** `live/loop.compute_result(..., trace=False)` puts the trace in the
   result; `LiveLoop` stores it (`CACHE_FORMAT` 2); `session.result_messages` emits
   `matcher_trace`; `runner` traces fresh reruns; `api/schemas_trace.py` `MatcherTraceMsg` and
   its parts (in both unions); `GET /api/trace/{incident}`, `GET /api/live/trace`; regenerate
   `web/openapi.json` and `types.gen.ts`.
3. **Workbench (web).** `state/matchStore.ts` keeps the latest trace; `dispatch.ts`;
   `workbench/workbenchMachine.ts`, `WorkbenchPanel.tsx`, `WorkbenchDialog.tsx`,
   `TraceCurves.tsx`, `CostThumb.tsx`; buttons on `MatchList` (Live page, Live watch) and the
   Match explainer; `api.trace`, `api.liveTrace`.
4. **Tests** (below) and the Playwright workbench test; review its screenshots (§17.13).
5. **Docs** (guide section and screenshots, README, one-pager, DEMO, READMEs), exit check,
   EXIT_CHECK.md, REPORT.md, PROGRESS.md, DECISIONS.md, commit, push, gate.

## Tests

- `tests/unit/test_matcher_trace.py` (on `toy_models`):
  - `test_trace_on_and_off_give_identical_matches`: same tracks, scores, shape_sim, features,
    reasons, warp ratios and baseline order at T = 60, 120 and 180 for two P1 queries.
  - `test_trace_order_counts_and_fields`: the prefilter list is in prefilter order and as long as
    the candidates; `dtw.candidates` in the order computed, one per candidate, `d_norm =
    d / sqrt(n)`, `shape_sim = exp(-d_norm / tau)`, band = `band_window(n, m)`; paths only for the
    first 50, each ≤ 48 points, monotone, from (0, ·) to (n−1, ·) after scaling; thumbnails
    12 × 12; `fusion` scores equal the matches' scores; `ranking` equals the top 10.
  - `test_trace_overhead_is_measured`: `trace_ms` > 0 and `total_ms` is the untraced matcher's
    own stages; the overhead is printed into the test log and recorded in REPORT.md.
  - `test_the_path_cutoff_and_the_top10_paths`: with a recorder of `paths=3`, details exist for
    orders 0 to 2 and for every final top-10 track, and for no other candidate.
- `tests/unit/test_api_contract.py`: `matcher_trace` joins the type set with a real example
  (`TYPES_16_3` stays the §16.3 set; `TYPES` adds the extension);
  `tests/unit/test_api_live_contract.py` likewise; `tests/unit/test_api_trace.py`: the replay
  stream sends `matcher_trace` with each `match` (validated with `KD_VALIDATE_STREAM=1`),
  `GET /api/trace/{incident}?at=` (200, 404 unknown, 422 before `min_track_s`),
  `GET /api/live/trace` (404 before any rerun, then the latest).
- `tests/unit/test_live_hub.py`: fresh live reruns stream a `matcher_trace`; backfilled ones do not.
- Vitest `workbenchMachine.test.ts`: stages over time, one candidate landing per 1 / rate s, the
  ranking re-sorting as each lands (and ties), speed changes, pause and step, reduced motion jumps
  to `done`, the final state equals the trace's fused top 5; `WorkbenchPanel.test.tsx`: the header
  text from the trace's numbers, the candidate view and its text equivalent at a given step, the
  ranking, the reduced-motion final state, the controls, and that a newer trace only offers
  "replay it" (the pinned trace keeps playing).
- Playwright `e2e/workbench.spec.ts`: launch `returning-prober` at 20× on the Live page, open the
  DTW workbench once matches appear and see candidates aligned (`data-step` advances, the path is
  drawn) while the pinned rerun stays the one named in the header; then, after the incident has
  closed (no fresh rerun follows, so the Matches panel and the latest trace are the same rerun),
  open it again, let the ranking settle and check that its rerun second equals the Matches
  panel's "At T+…" and its fused top 3 equal the panel's entries; axe on the open dialog;
  screenshots to `reports/figures/ui/phase12-*`; also opened from the Match explainer on the
  replay incident. Live data reset before and after, the ledger reseeded after.
- `guide.spec.ts` (new test) writes the guide's live-mode screenshots; `test_docs.py` and
  `scripts/check_docs.py` still pass.

## Exit-check mapping

| Criterion (PHASE_12.md) | Command | Evidence |
|---|---|---|
| All checks pass | `make check` | ruff, fast pytest count, web lint, typecheck, types current, Vitest count |
| The web app builds | `npm --prefix web run build` | build output |
| e2e passes, the guide's new screenshots produced by this run | `make e2e` | pass count; `ls -l --time-style` of `docs/guide/img/live-mode-*.png` after the chain's start |
| Push after the phase | `git push origin HEAD` | allowed for this session by the handoff (D-171); the remote's answer |
| Documentation complete | `python3 scripts/check_docs.py` | "Documentation complete." and the guide's word and image counts |

One chain: `make check && npm --prefix web run build && make e2e && python3 scripts/check_docs.py`,
recorded in EXIT_CHECK.md; then `python3 scripts/cloud_gate.py gate 12`.

## Documentation to write or update

`docs/phases/phase-12/PLAN.md`, `PLAN_REVIEW-k.json`, `REPORT.md`, `EXIT_CHECK.md`;
`docs/USER_GUIDE.md` (Live mode), `README.md` (Live mode quick start, Status), `docs/ONE_PAGER.md`,
`docs/DEMO.md`; package READMEs `match/`, `live/`, `api/`, `web/`; `docs/PROGRESS.md` (session
log, and the closing summary of phases 11 and 12); `docs/DECISIONS.md` (D-187 to D-19x).

## Risks and mitigations

- **Message size and Director at 5×**: the trace carries paths for 50 candidates only and is sent
  only when it changed; measured in the e2e run (Director and guide specs keep passing).
- **Trace changing results**: the recorder only reads what the matcher computed and adds separate
  calls for paths; `test_trace_on_and_off_give_identical_matches` guards it.
- **Live rerun time**: tracing adds the 50 paths (measured) to fresh reruns only.
- **Cache staleness**: `CACHE_FORMAT` 2 makes old caches stale; `make e2e` and `make demo`
  precompute again.
- **Screenshots in a slow container**: each guide shot waits for the element that proves its state
  (D-163); the workbench shot pauses the replay at a fixed candidate.

## Out of scope

Tracing the swarm matcher; recomputing or editing a trace in the browser; new matching logic.

## Review changes

Review 1 (`PLAN_REVIEW-1.json`) found one blocking issue, resolved: the workbench now pins the
trace it opened with (a newer trace only offers "replay it"), and the e2e compares the settled
ranking with the Matches panel for the same rerun, opening the workbench after the incident has
closed (D-189, Tests). Suggestions applied: details for final top-10 tracks beyond the first 50;
Pause and Step, `data-*` attributes and speeds capped at 10 per second; literal `snap()` names,
1920 × 1080 shots; the guide's section 13 and the renamed CLI subsection; resets in the live specs;
the path labelled as the full-matrix alignment and no band drawn; `api/schemas_trace.py`; the
contract tests' type sets; the cutoff test with `paths=3`; dialog and SVG accessible names and a
text equivalent; the message size in REPORT.md; D-171 for the push. The uncommitted trace code
written during the review matches the revised plan and is committed with this revision.

Review 2 (`PLAN_REVIEW-2.json`) approved the plan with no blocking issues. Suggestions applied:
the path and thumbnail sizes above now match the code (48 points, 12 × 12); the guide's
`#live-mode` link moves to `#13-live-mode` with the rename; the live-mode guide images are
written and committed before the exit-check chain; tests for `GET /api/live/trace` after a rerun
and for backfilled reruns streaming no trace; the workbench's React reads stay at or under 10 per
second (a Vitest checks it); the workbench screenshots at 1920 × 1080 and 1440 × 900; the cache
size and the `make e2e` duration in REPORT.md; the renamed union test; links to section 13 from
the guide's introduction, running-the-demo section and Live watch tour.
