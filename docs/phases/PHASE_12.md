# Phase 12 — DTW workbench and live-mode documentation

Added 2026-11-02 at the user's request (D-169). It plays the role of a SPEC §20 phase block: the
`phase-auto` skill and the plan reviewer read this file for N = 12. Edited by humans only.

**Goal.** Let people watch the matcher work, live: at each rerun, the shortlist the vector search
returned, each candidate being aligned by DTW with its warping path, the ranking re-sorting as the
scores land, and the fusion step that produces the final order. Then document live mode so a new
user can run it from the guide.

**Read first.** CLAUDE.md, `docs/phases/PHASE_11.md` and `docs/phases/phase-11/REPORT.md`, SPEC §10,
§16.3, §17.1, §17.7, §17.11 to §17.13, `match/README.md`, `live/README.md`, `web/README.md`,
`docs/USER_GUIDE.md`, `README.md`.

## Tasks

- [ ] **Matcher trace.** `DtwMatcher.match` optionally returns a trace of the real computation,
  without changing its result: the prefilter's hits (track id, vector distance, rank) and timing;
  for every DTW candidate, in the order computed: track id, DTW distance, calibrated shape similarity,
  band width, warping-path length, a down-sampled warping path (at most ~64 points) and its time in
  ms; the fusion features and score of each; the final ranking. Off by default; a unit test proves
  results are identical with and without it, and the overhead is measured.
- [ ] **Stream it.** A `matcher_trace` stream message per rerun, on the live stream (phase 11) and on
  the replay stream, plus `GET` access for the latest trace. Regenerate the OpenAPI types.
- [ ] **The workbench panel** (on the Live page, and reachable from Live watch and the Match
  explainer): the shortlist as a list with vector distances; then each candidate in turn with its
  query and candidate curves, a small cost-matrix thumbnail with its warping path, and its distance
  and similarity; a ranking list that re-sorts as each score lands; then the fused top 5 with their
  reasons. All 50 alignments take tens of milliseconds, so the panel replays the recorded trace in
  slow motion (a speed control; default about 6 candidates per second) and says so on screen, for
  example "Slow-motion replay of rerun T+90: 50 alignments computed in 56 ms". Every value shown is
  from the trace (rule 10). Reduced motion shows the final state without animation. Tokens only.
- [ ] **Docs.** A "Live mode" section in `docs/USER_GUIDE.md` (launching each scenario from the UI
  and the CLI, what to expect, the ingest contract for real sensor adapters, the workbench, `live
  check`, `live reset`) with new screenshots captured by a Playwright spec into `docs/guide/img/`
  (at least: the Live page with a live incident and matches, the scenario launcher, the workbench
  mid-replay). Update `README.md` (a "Live mode" quick start: `make live`, then the Live page),
  `docs/ONE_PAGER.md` (one sentence), `docs/DEMO.md` (a live segment for presenters), the package
  READMEs, PROGRESS.md and DECISIONS.md.

## Tests

Trace on/off gives identical matches; the trace's order, counts and fields; the `matcher_trace`
message validates against the schema; Vitest for the workbench's replay state machine (step,
re-sort, reduced motion); a Playwright test that opens the workbench during a live scenario and sees
candidates aligned and the ranking settle; screenshots reviewed per §17.13; the documentation tests
and `scripts/check_docs.py` still pass.

## Exit check

```bash
make check && npm --prefix web run build && make e2e && python3 scripts/check_docs.py
```

All pass; the guide's new screenshots were produced by this run's `make e2e`.
