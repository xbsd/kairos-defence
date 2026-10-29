# Phase 8: Command Center: the memorable moments, plan

Autopilot plan step, 2026-10-29. Written without a human in the loop (CLAUDE.md rule 5, `phase-auto`).
Every assumption below (A1 to A24) is recorded in `docs/DECISIONS.md` during the build, numbered from
**D-122** (D-121 is the last entry).

## Goal

The demo's memorable moments, on top of the phase 7 foundation (SPEC §20, phase 8):

- **Time-warp lens** in the memory rail: tonight's window over the matched segment, "Same time"
  connectors that miss and "Warped" connectors on the real DTW path, a 1.2 s morph between them, the
  cost matrix with the Sakoe-Chiba band and the path drawn on, readouts in words (§17.7). The
  **Match explainer** page shows the lens full screen, both flights side by side in target-relative
  frames, and the fusion contributions as horizontal bars (§17.9, §10.4 step 6, §10.7).
- **Afterglow**: ghost trails of the matched past flights mapped into tonight's target frame, three
  core beams per `match`, the region constellation with arcs to Bravo (§17.3, §17.8).
- **Forecast**: the dotted exit path, the pulsing recovery zone with its computed label, and the County
  Rd 12 segment inside the zone turned bone (§13, §17.3).
- **Report recall overlay**: the top report resolving from glyphs, clue spans highlighted, a bone beam
  from the "County Rd 12" span to the road in the theater (§17.8).
- **Case board** (as-of scrubber with event ticks, Known then / Known now, d3-force graph, diff,
  approvals and decisions), **Evidence** (real per-file hashing progress, signature and chain checks,
  Verify package), **Shift delta** and **Eval** pages (§15.4–§15.8, §17.9).
- **Director mode**: one beat per §1.2 row with a camera shot, panel dimming and a computed one-line
  caption; keys Space, →, ←, R, M, F, ?, D; a progress rail; reduce-motion and performance modes
  (§17.10, §17.11).

Exit check (SPEC §20, phase 8): Director mode at 1× through every §1.2 row with times recorded;
screenshots of every beat at both sizes reviewed and fixes logged; median frame rate ≥ 50 fps on the
dev machine; `make eval` demo assertions pass.

The autopilot gate for phase 8 (`docs/phases/gates.json`) runs `make check`, `make eval`,
`soft: python3 scripts/check_targets.py 8`, `npm --prefix web run build` and `make e2e`.
`check_targets.py 8` checks the phase 4 and 5 metrics cumulatively and every demo row except
`swarm_top1`; `live_top3_incidents` is an accepted gap (`accepted_gaps.json`, D-081) and prints WARN.
Phase 8 changes no matcher, recall, forecast or metric code, so those numbers must not move.

## Inputs read

- `CLAUDE.md`; `docs/PROGRESS.md` (phases 0 to 7); `docs/phases/TEMPLATES.md`;
  `docs/phases/phase-07/REPORT.md`, `PLAN.md` and `PLAN_REVIEW-1.json` (what reviewers check);
  `docs/phases/gates.json`; `docs/phases/accepted_gaps.json`; `scripts/check_targets.py` (phase 8 = every
  demo row except `swarm_top1`, plus the phase 4 and 5 metrics).
- SPEC "Read first" for phase 8: §1.2, §13, §15 (all), §17.3, §17.7–§17.13, Appendix B. Also §6.4
  (`scenario_demo.yaml` expectations), §10.4 step 6 and §10.7–§10.8 (explanations, `Match`), §14
  (swarm, for what stays in phase 9), §16.3–§16.4 (messages and routes), §17.1–§17.2 (tokens, layout),
  §19.3–§19.4 (metrics, targets, eval JSON), §20 phases 7–9, §21, §23.
- `docs/DECISIONS.md`, in particular D-010 (admin reset and reseed, Director's R), D-011 (planted DELTA
  timing: known then 2026-04-20 09:10 local), D-012 (no decorative motion; static grain), D-013
  (precomputed live results), D-060 (latency does not block), D-063 (soft gaps), D-074 (reasons),
  D-081 (accepted live top-3 gap: DELTA, ALPHA-260303, CHARLIE-260710 at T+90), D-087 and D-090
  (forecast), D-094 to D-101 (ledger rules, evidence, delta and diff groups), D-103 to D-121 (phase 7:
  live file, ports, loop and cache, case for proposals, stream and REST details, coordinates,
  concurrency, CLI, web foundation, e2e plumbing, pins, flight phase, memory status, lens payload,
  replay clock, theater and panel choices). D-113 asks phase 8 to restore the per-beat screenshot set.
- Code: `api/routes.py` (`/api/dtw`, `/api/history`, `/api/eval/latest` already exist),
  `api/routes_memory.py` (cases, diff, graph, links, evidence NDJSON, delta, admin), `api/schemas.py`
  (505 lines: new models go in a new module), `api/services.py`, `api/app.py`, `cli_live.py`
  (`api_cmd`), `live/loop.py` (`result_at`, `lens`, `query`), `match/explain.py`, `match/fusion.py`
  (`FusionModel.contributions`), `match/dtw_rerank.py` (`warp_text`, `explain_alignment`),
  `match/lens.py`, `memory/actions.py` (`record_decision`, `decide_link`), `memory/asof.py`,
  `memory/graph.py`, `memory/diff.py`, `memory/delta.py`, `memory/evidence.py` (`verify_evidence`),
  `eval/report.py`, `eval/report_md.py` (targets are hard-coded strings today), `sim/lexicon.py`
  (`compass8`). Web: every file under `web/src/`, `web/tests/`, `web/e2e/`, `playwright.config.ts`,
  `web/README.md`.
- Data checked (the precomputed BRAVO results in `data/cache/live/DEMO-BRAVO-0828/`):
  - T+45: first result; top match BRAVO-251114; tonight's target is still `BRAVO-fence`.
  - T+90: top 3 DELTA (warp 0.84, "flown 19% faster"), ALPHA-260303 (1.03, no pace text),
    CHARLIE-260710 (0.90, "flown 12% faster"); target `BRAVO-fuel_farm`.
  - T+105: forecast center (21 253, −4 178) m, radius 370 m, roads ["County Rd 12"], 3 analogs (the
    phase 5 CLI reports it as 2,164 m northwest of the fuel farm).
  - T+120: the recall's first match is DELTA, whose rank-1 report `R-P1-DELTA-260419-1` has the
    clues "white pickup" and "County Rd 12"; `zone_roads` = ["County Rd 12"].
  - Newest `reports/eval_2026-10-29.json`: every demo row passes except `live_top3_incidents`
    (accepted); `swarm_top1` is pending (phase 9).

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md` during the build (D-122 onward).

- **A1 · Director beats (one per §1.2 row; the encore is phase 9).** Eight beats in phase 8:

  | # | Beat (§17.10) | Kind | Starts | Route | Camera | Key element (e2e) |
  |---|---|---|---|---|---|---|
  | 1 | Detection | clock | T+0 | Live watch | overview (fence, radar shadow) | first stream row; theater summary names the first radar point |
  | 2 | Recording | clock | T+15 | Live watch | overview | recorder total > 0; ledger chain |
  | 3 | Recognition | clock | T+45 | Live watch | follow | first `match-entry` (the matcher has run) |
  | 4 | Time warp | clock | T+90 | Live watch | memory (frames the ghosts) | three entries; lens in Warped mode; 3 ghosts in the summary |
  | 5 | Forecast | clock | T+105 | Live watch | forecast (orbit, zone, road) | forecast sentence in the summary |
  | 6 | Recall | clock | T+120 | Live watch | forecast | recall overlay with clue highlights and the road beam |
  | 7 | Known then and now | page | → | `/cases/<case>` | – | graph and diff; Known then shows "hobbyist" and no links |
  | 8 | Evidence | page | → | `/evidence?case=<case>` | – | export button; after the human click, 5 file rows and passing checks |

  §1.2's T+80 row (orbit established) has no beat of its own. It is observed during beat 3: the
  Signals loiter marker appears (T+87 by the D-115 phase rule; the eval's §1.2 orbit check is T+79),
  and the 1× run records when. The recording beat at T+15 comes after the first write batches; §17.10
  names it, §1.2 has no row for it. The encore beat and the Swarm view are phase 9 (§20 phase 9 lists
  "the Director encore beat"). Beats are data in `web/src/director/beats.ts`, so phase 9 appends one
  entry.
- **A2 · How beats advance.** Clock beats start when the replay clock crosses their time. Page beats
  start only on → (the presenter). Appendix B already says "press → to advance". → on a clock beat
  seeks to the next beat's time (instant, results are cached per second, D-013) and keeps the play
  state. ← goes back the same way; from a page beat it returns to Live watch and seeks to the recall
  beat. **Director never approves, rejects, decides or exports** (rule 8). Beat 7's caption asks the
  presenter to approve; beat 8's export needs the button and its confirm dialog. An e2e test checks
  that a Director run with no clicks appends no `link_approved`, `link_rejected`, `decision_recorded`
  or `evidence_exported`.
- **A3 · Progressive reveal in Director.** One hero moment per beat (§17.11). In Director, layers
  appear cumulatively: ghosts, core beams, lens and constellation from beat 4; forecast and road
  highlight from beat 5; the recall overlay from beat 6. With Director off, every layer shows as soon
  as its data exists. Hiding computed data until its beat changes no number (rule 10).
- **A4 · Captions are computed.** `director/captions.ts` holds pure functions from store state to one
  plain sentence, with values from the results, never hard-coded:
  - Detection: "First radar contact at {Bravo}'s {north} fence, {21:40} local." The side comes from
    `compass8` of the first point's bearing from the installation origin.
  - Recording: "Every detection is written as it arrives: {n} rows so far, {x} ms per write."
  - Recognition: "After {45} seconds of track, Kairos Defense searches every past flight at every
    base."
  - Time warp: "{Delta, Apr 19}: the same shape, {flown 19% faster}. Warping time lines the two
    flights up."
  - Forecast: "Those flights ended about {2.2 km} {northwest}{, in Bravo's radar shadow}." The
    radar-shadow clause appears only when the zone center is inside `scene.radar_shadow.polygons`.
  - Recall: "A {Delta} report from {Apr 19} mentions a {white pickup} on {County Rd 12}{, which runs
    through tonight's predicted zone}."
  - Known then and now: "{Delta} closed this as {hobbyist} on {Apr 20}. Here is what was known then,
    and what is known now."
  - Evidence: "Approve the links you agree with, then export: every step is signed and replayable."

  A missing value gives a shorter sentence without that clause; a caption never shows "undefined",
  "NaN" or a placeholder. The distance and bearing are measured from tonight's target-asset centroid,
  the same as the phase 5 `forecast` CLI. A Vitest checks the T+105 fixture against the CLI's
  2,164 m northwest. `compass8` mirrors `sim/lexicon.compass8`, and a Vitest checks its boundaries.
- **A5 · Lens connectors.**
  - **Same time**: pairs `(i, i)` for `i < overlap`. This is exactly what the payload's
    `euclid_distance` compares (D-117: the first `min(n, m)` samples).
  - **Warped**: the DTW `path` pairs, subsampled evenly along the path to at most 48 connectors,
    always keeping the first and last pairs.
  - Each connector keeps its query index `i`; the morph moves only the candidate end, from `i` to its
    path partner `j`. One shared x-scale (`L = max(n, m)` samples) puts equal timestamps on a vertical,
    so a slower or faster flight visibly overhangs.
  - The morph runs 1.2 s (`--dur-cinema`, `--ease-inout`). In reduce motion it is a cross-fade
    (`--dur-panel`).
  - The pace readout is the payload's `warp_text` with a capital first letter ("Flown 19% faster"),
    or "Same pace (within 10%)" when it is null. The wording stays in one place, Python's
    `warp_text`.
- **A6 · Which match the lens shows.** By default, the stream's `dtw` (the top match). The match and
  channel selectors send the existing `{"type":"dtw"}` request (§16.3). In the time-warp beat,
  Director selects the top-3 match whose `warp_ratio` is farthest from 1 in log terms (T+90: DELTA,
  0.84). If none has pace text, it keeps the top match and the caption omits the pace clause.
  §1.2's "ALPHA 2026-03-03 (flown ~18% slower)" is not what the 60 s window computes at T+90
  (ALPHA-260303: 1.03). The UI shows the computed ratio, and REPORT.md records this.
- **A7 · Ghost mapping.** `GET /api/history/{track_id}?frame=target` points are placed at tonight's
  target-asset centroid plus the relative vector (`x_rel_m`, `y_rel_m`, altitude as recorded),
  translation only. This is "mapped into tonight's target frame" (§17.3). No bearing rotation is
  applied: the P1 approaches agree within 5°, and the forecast keeps its own §13 rotation.
  - Ghosts are drawn only once tonight's target is a named asset in the scene. Before T+87 it is the
    fence pseudo-target (D-081, D-115), and ghosts mapped there would mislead.
  - Ghosts are re-mapped when the target changes, and exist only for the current top 3.
  - The label ("Delta, Apr 19") sits at the ghost's last point, its recovery point in tonight's
    frame, which ties the ghosts to the forecast zone.
  - They dissolve in over 1.2 s, staggered 150 ms: a per-segment alpha threshold from a fixed hash of
    the segment index. In reduce motion they fade in instead.
  - Hovering or focusing a match entry brightens its ghost (`matchStore.hovered`).
- **A8 · Core beams.** On each `match` message, three afterglow beams leave the core for 1.2 s, one
  toward each top-3 ghost's aligned point. That is the ghost point at `window_offset_s +
  features.window_s`, clamped to the track: where that flight was at the matched moment. Before the
  ghosts exist, beams go toward tonight's target. No beams in reduce motion (they count as particles,
  §17.11).
- **A9 · Region constellation.** Positions are the live region's installation origins from
  `GET /api/installations`, scaled to fit the panel with padding (stylized: no map). On a new top-3
  set (the `entrance` counter), arcs draw from each matched base to Bravo with a travelling light over
  1.2 s, labeled with the match dates. A matched base in another region sits at an "Other regions"
  node on the panel edge. In reduce motion the arcs appear without the light.
- **A10 · Recall overlay.**
  - Which report: the rank-1 report of the first recall match that has a report with a linked clue;
    otherwise the rank-1 report of the first recall match.
  - Clue spans are cut from `text[start:end]`: vehicles in afterglow, roads in bone.
  - The zone note ("County Rd 12 runs through tonight's predicted zone.") appears when a road clue's
    value is in `recall.zone_roads`.
  - The text resolves over 600 ms by deterministic glyph substitution: a fixed glyph set, the order
    from the character index. In reduce motion it is a plain fade.
  - The overlay can be collapsed.
- **A11 · Road highlight and beam.**
  - The in-zone part of a zone road is the polyline clipped to the zone circle (`forecastMath.ts`,
    computed client-side from the scene's road lines and the forecast's center and radius).
  - The beam joins the overlay's road span to that segment's midpoint, projected to the screen in
    `useFrame` and written to `overlayStore`. The beam is hidden when the point is behind the camera
    or outside the theater.
- **A12 · Forecast and road motion.** The forecast path's flowing dash, the road's moving dots and the
  zone's 1.6 s pulse advance in wall time only while the replay plays, and freeze when it pauses (they
  belong to a live, computed forecast, D-012, D-120). In reduce motion they are static.
  - Zone label: "Predicted recovery zone, {2.2 km} {northwest}, from {3} matches". The count is
    `forecast.analogs.length`.
  - Forecasts are dotted bone, always (§17.1).
- **A13 · Camera shots.**
  - `memory` becomes a computed shot framing the ghosts' bounding box (it was a fixed far shot).
  - A new `forecast` preset frames the orbit, the zone and the in-zone road segment (§17.3 lists five
    presets; this one serves beats 5 and 6).
  - Both come from `frameBox(points, fov, aspect)` in `three/camera.ts`.
  - Transitions stay 1.2 s damped, instant in reduce motion.
- **A14 · Explainer data: a new route.**
  `GET /api/explain/{incident_id}/{match_track_id}?at=90` returns:
  - the decorated match;
  - the contribution table: per model feature its value, coefficient and contribution
    (`FusionModel.contributions`, §10.7), plus the intercept, logit and score;
  - tonight's target-relative 1 Hz path up to the rerun second only (rule 3);
  - the past flight's whole target-relative path, with the matcher's anchored segment
    (`window_offset_s` to `window_offset_s + window_s`) and the §10.4 step 6 `explain_alignment` of
    tonight's `dist_target_m` window inside the whole past flight.

  Pure helper `match/explain.contribution_table(features, model)`. The route lives in a new
  `api/routes_explain.py`. Errors: unknown incident, a track not among the matches, or no result yet
  (before T+45) → 404, the same as `/api/dtw`.
- **A15 · Four more routes for the pages.** New response models go in a new `api/schemas_pages.py`,
  because `schemas.py` is already 505 lines.
  - `GET /api/cases` → case summaries (case id, founder, base, status, opened at, members, pending
    proposals, contradictions), as of the ledger head. Pure `memory/asof.case_summaries`.
  - `POST /api/cases/{case_id}/decisions` → `decision_recorded` through `record_decision`. Decision
    must be one of close, reopen, escalate, notify_law_enforcement; analyst handle; clock defaults to
    the head. Errors: 422 unknown decision, 404 unknown case.
  - `GET /api/evidence` → exported packages under `paths.exports` (dir name, case, created, manifest
    SHA-256).
  - `POST /api/evidence/verify` with `{"dir": …}` → `verify_evidence(dir, memory)` checks and
    `passed`. The directory must resolve inside `paths.exports`, otherwise 400 (no path traversal).
- **A16 · e2e exports go to scratch.** `kairos-defense api` gains `--exports PATH` (passed through
  `KD_EXPORTS` under `--reload`, like `--memory`, D-111). Playwright's server uses
  `data/cache/e2e/exports`, so e2e never writes into `exports/`.
- **A17 · Case board mechanics.**
  - The scrubber runs from the case's first event to the ledger head. Its ticks are the
    `recorded_at` of the case's diff items, from `GET /api/cases/{id}/diff?t1=2025-01-01T00:00:00Z`.
  - Known then = the case node's `recorded_at` (its `case_opened`, 09:10 local on 2026-04-20,
    D-011). Known now = the ledger head: the replay clock as of the last append, §15.6, D-010.
  - The graph is refetched for each scrub position (debounced 150 ms), so superseded and pending
    states are the server's as-of (§15.4), not a client filter.
  - The d3-force layout is deterministic: initial positions seeded by node kind and index,
    `randomSource` from a fixed LCG, 300 synchronous ticks. Nodes keep their positions across
    refetches; new nodes fade in over 600 ms.
  - Incidents are colored by base. Contradictions are outlined in `--alert`; approved members are
    `--verified`.
  - The diff panel shows `case_diff(then, scrub)` grouped (D-101).
  - Approve and Reject per pending proposal use the existing links route. Decision buttons (Close,
    Reopen, Escalate, Notify law enforcement) each need a confirm dialog (rule 8).
  - A visually hidden list of nodes and edges is the text equivalent (§17.12).
- **A18 · Eval targets live in Python.** New `eval/targets.py` holds the §19.3 and §10.9 targets
  (key, operator, value, label, SPEC section, report-only for latency per D-060, pending for
  `swarm_top1`).
  - `eval/report.py` writes them into the eval JSON as `targets`; `report_md.py` uses them instead of
    its hard-coded strings.
  - A test loads `scripts/check_targets.py` (read, never edited) and asserts every key, operator and
    value there matches `TARGETS`.
  - No metric definition, query set or protocol changes.
  - The Eval page shows a stale report without `targets` as "this report has no targets; rerun
    `make eval`".
- **A19 · Eval page charts.**
  - Tiles: value against target, with pass, gap or report-only.
  - Recall vs seconds of flight: `recall_by_t`, Recall@5 and top 3 for probers.
  - DTW vs Euclidean: the two numbers the eval wrote, `recall_at_5_t120` and
    `recall_at_5_t120_baseline`, plus `dtw_lift`.
  - Forecast error distribution: a histogram of `outcomes[].forecast_error_m` for prober queries at
    `at_s = 90`, with the median and P80 from `metrics`.
  - Demo assertions table: every `demo` row with its status as written, including the failing
    accepted gap. Nothing is recomputed in the browser beyond binning.
  - Charts follow the dataviz skill's method inside the §17.1 tokens. Each has a data-table text
    equivalent.
- **A20 · Routes and code splitting.**
  - New routes: `/explainer?incident=&at=&track=`, `/cases` (list), `/cases/:caseId`,
    `/evidence?case=`, `/delta?since=`, `/eval`. `/swarm` stays a phase 9 placeholder.
  - Pages are `React.lazy`, so the Case board, Eval and the other pages do not load the `vendor-3d`
    chunk.
  - Each match entry gets an "Explain" link to the explainer at the current rerun second.
- **A21 · Director across pages.**
  - `directorStore` lives outside React, and `DirectorOverlay` (caption and progress rail) is
    rendered by `App`, so it survives navigation.
  - Leaving Live watch closes the stream as today. Returning reconnects, and Director seeks to the
    beat's time.
  - D toggles Director from any page: it opens Live watch for the live single-track incident, seeks
    to T+0 and plays at the selected speed.
  - Space (play/pause) and R work on Live watch with or without Director; → and ← act only in
    Director. F toggles full screen anywhere.
  - Keys are ignored while typing in inputs; Space is left to a focused button.
- **A22 · R reset.** R calls `POST /api/admin/reset` and `POST /api/admin/reseed` (D-010), reloads
  the ledger tail, seeks to T+0 and, in Director, returns to beat 1.
- **A23 · Performance mode and grain.**
  - A command-bar toggle "Performance mode" (`uiStore.perfMode`) turns off bloom, grain and the core
    beams and halves packets. Auto-degrade (D-120) still applies on top. §17.10 assigns no key to it,
    so it gets none.
  - Film grain (deferred by D-112) is a custom static postprocessing effect: a hash of the pixel
    coordinate, no time uniform (D-012), about 3% opacity. It is off in reduce motion and performance
    mode.
- **A24 · Frame-rate criterion.**
  - `e2e/director-1x.spec.ts` samples requestAnimationFrame through the Live watch beats of the 1×
    run (1920 × 1080, bloom on), and writes the median overall and per beat, the renderer string and
    the machine to `reports/figures/ui/director_1x.json`.
  - It asserts a median of at least 50 fps when the WebGL renderer is a hardware one.
  - If Chromium falls back to SwiftShader, the run records the number and adds a test annotation
    saying the GPU was not used, instead of failing on the environment. The exit check is then not
    met, and REPORT.md says so.
  - Phase 7's `perf.spec.ts` stays unchanged.

How the plan keeps the CLAUDE.md non-negotiable rules:

- **Rule 1, synthetic only:** every page shows generated data.
- **Rule 2, truth isolation:** no new module reads truth. `eval/targets.py` holds constants only, and
  the existing truth scan covers the new `api/` modules.
- **Rule 3, no look-ahead:** the explainer's tonight path stops at the rerun second (tested), and
  ghosts are matched history flights.
- **Rule 4, determinism:** the UI adds no data. The scramble, dissolve and graph layout are seeded,
  not random.
- **Rule 5, offline:** no new dependency; d3 is already bundled; fonts are local.
- **Rule 6, ports and adapters:** the routes use the `TrackStore` and `CaseMemory` ports through
  `Services`; the new helpers are pure.
- **Rule 7, append-only:** decisions append `decision_recorded` through `memory.actions`.
- **Rule 8, humans approve:** approvals, decisions and exports need a click, and a dialog where
  specified. Director never commits (A2, tested).
- **Rule 9, flights not people:** the overlay shows report text as written (synthetic,
  guardrail-scanned, D-045), and clue highlights cover only vehicles and roads.
- **Rule 10, truthful animation:** every new motion is tied to a message, a computed result or a
  presenter's beat change (A3, A8, A12). Captions are computed (A4).

## Work breakdown

Run `make check` after each step. Keep every module under ~400 lines, with docstrings stating units.

1. **Backend for the pages** (A14–A16, A18).
   - `src/kairos_defense/match/explain.py`: `contribution_table(features, model) -> dict` (rows sorted
     by |contribution|, intercept, logit, score).
   - `src/kairos_defense/memory/asof.py`: `case_summaries(rows, t, offsets) -> list[dict]`.
   - `src/kairos_defense/eval/targets.py` (new): `Target` dataclass and `TARGETS`.
     `eval/report.py` adds `targets` to the JSON; `eval/report_md.py` renders the target column from
     `TARGETS`.
   - `src/kairos_defense/api/schemas_pages.py` (new): `ContributionRow`, `ExplainPath`,
     `ExplainResponse`, `CaseSummary`, `DecisionRequest`, `DecisionResponse`, `EvidencePackage`,
     `EvidenceVerifyRequest`, `EvidenceVerifyResponse`.
   - `src/kairos_defense/api/routes_explain.py` (new): `GET /api/explain/{incident_id}/{track_id}`.
     It reads under `Services.lock`, uses `loop.result_at`, `loop.query`,
     `store.features(track_id)` and `explain_alignment`.
   - `src/kairos_defense/api/routes_memory.py`: `GET /api/cases`,
     `POST /api/cases/{id}/decisions`, `GET /api/evidence`, `POST /api/evidence/verify` (about 300
     lines after this).
   - `src/kairos_defense/api/app.py`: include the explain router. `api/services.py`: optional
     `exports_path` override. `cli_live.py`: `--exports`, plus `KD_EXPORTS` for `--reload`.
   - Regenerate `web/openapi.json` and `web/src/api/types.gen.ts`.
2. **Web data layer** (A20–A22).
   - `web/src/api/client.ts`: `installations`, `history`, `dtw`, `match`, `explain`, `cases`,
     `caseSnapshot`, `caseGraph`, `caseDiff`, `recordDecision`, `evidenceList`, `verifyEvidence`,
     `delta`, `evalLatest`. `messages.ts` names the new generated types.
   - `web/src/state/`:
     - `matchStore.ts`: `hovered`, `lensSel` (track and channel), `lensMode`.
     - `ghostStore.ts` (new): fetched ghost paths by track id, with load state.
     - `overlayStore.ts` (new): the road span and screen point for the beam.
     - `directorStore.ts` (new): active, beat index, reveal flags, the log of beat activations with
       replay `t_s`, local time and wall time.
     - `uiStore.ts`: `perfMode`, and `forecast` in `CameraPreset`.
   - `web/src/app/routes.ts`, `App.tsx` (lazy pages, `DirectorOverlay`), `keys.ts` (Space, →, ←, R,
     F, D, M, ?), `Shortcuts.tsx` (the full key list; drop the "arrives in phase 8" note),
     `CommandBar.tsx` (Director enabled with `aria-pressed`, a Performance mode toggle, the local time
     as `data-local-time` for the 1× record).
3. **Time-warp lens** (A5, A6).
   - `web/src/lens/lensMath.ts`: `decodeCost`, `lensScale`, `sameTimeConnectors`,
     `warpedConnectors`, `connectorAt(t)`, `paceWords`.
   - `web/src/lens/ramp.ts`: OKLab ramp from `--scope` to `--afterglow`.
   - `web/src/lens/LensCurves.tsx`: SVG curves and connectors, morph through requestAnimationFrame.
   - `web/src/lens/CostMatrix.tsx`: canvas heatmap, band corridor, path drawn on over 1 s with a
     glowing head.
   - `web/src/lens/TimeWarpLens.tsx`: Same time / Warped segmented control, match and channel
     selectors, readouts, compact and full variants.
   - `web/src/panels/LensPanel.tsx`: the memory-rail panel, waiting until T+45.
4. **Theater afterglow and forecast** (A7, A8, A11–A13, A23).
   - `web/src/three/ghostMath.ts`, `Ghosts.tsx`, `CoreBeams.tsx`, `forecastMath.ts`
     (`clipPolylineToCircle`, `distanceBearing`, `compass8`, `pointInPolygons`), `Forecast.tsx`
     (dotted path, pulsing disc, label), `RoadHighlight.tsx`, `Projector.tsx` (road point to screen,
     into `overlayStore`).
   - `Effects.tsx`: static grain. `camera.ts`: `frameBox`, `forecastShot`. `CameraRig.tsx`: the
     computed memory and forecast shots.
   - `summary.ts`: ghost and forecast sentences in the text equivalent. `Theater.tsx`: mount the new
     layers behind the reveal flags.
5. **Memory rail and recall overlay** (A9, A10).
   - `web/src/panels/RegionConstellation.tsx` and `constellation.ts`.
   - `web/src/overlay/RecallOverlay.tsx`, `clues.ts` (span segmentation, report choice, zone note),
     `scramble.ts`, `RecallBeam.tsx` (SVG line from the span rect to the projected point).
   - `pages/LiveWatch.tsx`: the memory rail holds Matches, Region constellation and the Time-warp lens
     (§17.2); the overlay sits inside the theater.
   - `panels/MatchList.tsx`: hover and focus set `hovered`; an "Explain" link.
6. **Match explainer** (A14). `web/src/pages/MatchExplainer.tsx`:
   - the full-size lens, with selectors bound to the URL;
   - `explainer/FlightPair.tsx`: two SVG plots of target-relative meters, the segment and alignment
     marked;
   - `explainer/Contributions.tsx`: signed horizontal bars by |contribution|, with intercept, logit and
     score in words;
   - the match's reasons and memory status.
7. **Case board** (A17).
   - `web/src/pages/CaseBoard.tsx` (list at `/cases`, board at `/cases/:caseId`).
   - `web/src/case/graphModel.ts`: API graph to nodes and links, colors, deterministic layout.
   - `case/CaseGraph.tsx`: SVG, d3-force, fade-ins.
   - `case/Scrubber.tsx`: range, ticks, Known then and Known now.
   - `case/DiffList.tsx`.
   - `case/CaseControls.tsx`: approve and reject per pending proposal; decisions with confirm.
   - `case/GraphText.tsx`: the hidden text equivalent.
8. **Evidence, Shift delta, Eval** (A15, A18, A19).
   - `web/src/pages/Evidence.tsx`: case picker; members and pending counts; "Export evidence package"
     with a confirm dialog, then per-file NDJSON rows (name, bytes, SHA-256 as each file is hashed),
     then the signature, chain and ledger checks; "Verify package" calls the verify route; earlier
     packages from `GET /api/evidence`.
   - `web/src/pages/ShiftDelta.tsx`: a since picker (local time of the live installation; default 24 h
     before the head), groups (D-101), each item linking to `/cases/<case>?focus=<subject>` when it
     belongs to a case.
   - `web/src/pages/Eval.tsx` and `eval/evalView.ts` (tiles, histogram binning, demo rows),
     `eval/Charts.tsx`.
9. **Director mode** (A1–A4, A21, A22).
   - `web/src/director/beats.ts`: beat data (id, kind, start, route, camera, focus panels, reveal,
     caption function, key-element test id).
   - `director/engine.ts`: `beatAt`, `nextBeat`, `prevBeat`, `shouldAdvance`, as pure functions.
   - `director/captions.ts`.
   - `director/useDirector.ts`: reads the clock at ≤ 10 Hz, activates beats, sets camera, dimming,
     reveal and lens selection, and logs activations.
   - `director/DirectorOverlay.tsx`: caption (24 px, bottom center, glass strip, `aria-live="polite"`)
     and progress rail ("Beat 4 of 8: Time warp").
   - `panels/Panel.tsx`: `data-dimmed` when out of focus.
   - `app/fullscreen.ts`.
10. **End to end and visual QA.**
    - New specs: `web/e2e/director.spec.ts`, `director-1x.spec.ts`, `lens.spec.ts`,
      `pages8.spec.ts`.
    - Changed: `pages.spec.ts` (routes `/cases/CASE-P1-DELTA-260419` and
      `/explainer?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1` added to the axe list);
      `helpers.ts` (`director`, `beat`, `approveAllPending` helpers); `playwright.config.ts`
      (`--exports data/cache/e2e/exports`).
    - Run `make e2e` and review every screenshot against §17 (alignment, overlap, contrast, glow
      restraint, numbers legible from three meters). Fix, rerun, and log findings and fixes.
11. **Exit check and documents.** Run the blocks below. Write EXIT_CHECK.md, REPORT.md, the READMEs,
    PROGRESS.md and DECISIONS.md. Run `make test-all`, then commit.

Coverage of the §20 checkboxes:

| Phase 8 checkbox | Steps |
|---|---|
| Time-warp lens with the morph, cost matrix and path reveal; Match explainer page | 1 (explain route), 3, 6 |
| Ghost trails, core beams and region constellation; forecast path, pulsing zone and road highlight | 4, 5 |
| Report recall overlay with clue highlights and the beam to the road | 4 (projector), 5 |
| Case board (scrubber, graph, diff, approvals); Evidence; Shift delta; Eval | 1, 7, 8 |
| Director mode: beats, captions, camera shots and keys; reduce-motion and performance modes | 2, 4, 9 |

## Tests

Named tests, with what each asserts. SPEC §20 phase 8 test bullets are marked **(SPEC)**.

Python (fast, `tests/unit/`):

- `test_explain.py::test_contribution_table_sums_to_logit`: with a toy `FusionModel`, the rows are
  `coef × x` for model features only (not `d_norm`, `euclidean_d2`, `window_s`), sorted by |value|,
  and intercept + Σ contributions = logit, with sigmoid(logit) = `predict`.
- `test_api_explain.py` (new):
  - `test_explain_contributions_reproduce_the_score`: for P1-DELTA-260419-T1 at T+90, sigmoid(intercept
    + Σ) equals the match's score within 1e-9; seven rows.
  - `test_explain_tonight_path_stops_at_the_rerun_second`: max tonight `t_s` ≤ the rerun second
    (rule 3), and `at=93` uses 90.
  - `test_explain_past_segment_and_alignment_inside_the_track`.
  - `test_explain_unknown_track_404`, `test_explain_before_first_rerun_404`.
- `test_memory_cases.py::test_case_summaries_known_then_and_now` (new): at 2026-04-20 10:00 local the
  planted case is closed with one member and no pending proposals; after hand-written proposals and an
  approval it has two members.
- `test_api_cases.py` (new):
  - `test_cases_list_has_the_planted_delta_case`.
  - **(SPEC)** `test_case_graph_known_then_10_local_has_hobbyist_and_no_links`:
    `as_of=2026-04-20T10:00:00-05:00` gives an assessment node labeled "hobbyist", one `member_of`
    edge (the founder's) and no `proposed` edge.
  - `test_decision_appends_decision_recorded_by_the_analyst`,
    `test_decision_unknown_value_422`, `test_decision_unknown_case_404`.
- `test_api_evidence.py` (new): `test_evidence_list_after_export`,
  `test_evidence_verify_passes_then_fails_after_one_byte`,
  `test_evidence_verify_refuses_a_path_outside_exports` (400 for `../`, absolute paths and symlinks
  out).
- `test_eval_targets.py` (new):
  - `test_targets_match_check_targets_script`: every `METRICS` key, operator and value in
    `scripts/check_targets.py` (loaded with `importlib.util.spec_from_file_location`) equals
    `TARGETS`, and the latency keys are report-only in both.
  - `test_eval_json_writes_targets`, `test_report_md_target_column_from_targets`.
- `test_live_cli.py::test_api_exports_option_reaches_services_and_reload_env`.
- Existing `test_openapi_json_is_current` and `check:types` keep the contract current. The append-only
  and truth-isolation scans already cover the new modules: no truth paths; ledger writes only through
  `memory.actions`.

Vitest (`web/tests/`, jsdom):

- **(SPEC lens math)** `lensMath.test.ts`:
  - `decodeCost` round-trips a float32 base64 fixture encoded by `match/lens.encode_f32`.
  - `sameTimeConnectors(4, 6, 4)` → (0,0)…(3,3).
  - `warpedConnectors(path)` ⊂ path, includes the first and last pairs, ≤ 48.
  - `connectorAt(1)` endpoints equal the DTW path pairs; `connectorAt(0)` equals same time.
  - `paceWords("flown 19% faster")` = "Flown 19% faster"; `paceWords(null)` = "Same pace (within
    10%)".
  - On the real T+90 `dtw` fixture, the warped connector ends sit at `lensScale(path[k])`.
- `TimeWarpLens.test.tsx`: mode buttons toggle `aria-pressed`; connectors carry `data-i` / `data-j`
  equal to the path in Warped mode; the readouts show DTW, Euclidean and pace; reduce motion
  cross-fades; the match selector sends a `dtw` request.
- `ramp.test.ts`: ramp ends equal `--scope` and `--afterglow`; NaN cells are transparent.
- `ghostMath.test.ts`: a known-answer translation; no ghosts while the target is `BRAVO-fence`; the
  aligned point index is clamped.
- `forecastMath.test.ts`: `clipPolylineToCircle` (chord through, a tangent miss, a polyline partly
  inside); `distanceBearing` on the T+105 fixture gives 2,164 m ± 1 at 320° ± 1 (the CLI's value);
  `compass8` at 0, 22.4, 22.5, 315, 337.5 matches Python's; `pointInPolygons`.
- `camera.test.ts` (extended): `frameBox` keeps every point inside the frustum; `forecastShot`
  frames the zone and road.
- `constellation.test.ts`: normalization into the box with padding; out-of-region matches go to
  "Other regions".
- `clues.test.ts`, `scramble.test.ts`, `RecallOverlay.test.tsx`:
  - span segmentation yields exact substrings with vehicle and road classes;
  - the report choice follows A10 on the T+120 fixture (`R-P1-DELTA-260419-1`);
  - the zone note appears only when the road is in `zone_roads`;
  - the scramble's final frame equals the text, is deterministic and keeps the length;
  - reduce motion shows plain text immediately.
- `engine.test.ts`: `beatAt` at 0, 14.9, 15, 44.9, 45, 89.9, 90, 104.9, 105, 130 → the A1 beats; page
  beats never auto-advance; `nextBeat` / `prevBeat` across the clock and page boundary; reset → beat 1.
- `captions.test.ts`:
  - on fixtures trimmed from the real precomputed results, the time-warp caption names DELTA and
    "flown 19% faster";
  - the forecast caption says "about 2.2 km northwest" and includes the radar-shadow clause only
    inside the polygon;
  - the recall caption names "white pickup" and "County Rd 12";
  - with values removed, no caption contains "undefined", "NaN" or "{".
- `directorStore.test.ts`, `useDirector.test.tsx`: crossing a beat time activates it once, logs it,
  sets the camera preset, dimming and reveal; the time-warp beat selects the farthest-warp match.
- `keys.test.ts`: Space, →, ←, R, F, D, M, ? map to their actions; keys are ignored in inputs; F calls
  `requestFullscreen` (mocked).
- `graphModel.test.ts`:
  - **(SPEC)** the known-then fixture (from the API at 2026-04-20 10:00 local) yields an assessment
    node labeled "hobbyist" and no link edges beyond the founder;
  - the layout is identical for identical input;
  - contradiction nodes are flagged;
  - colors come from the base palette.
- `CaseBoard.test.tsx`: Known then and Known now set the scrubber; the diff groups render; Approve
  calls `decideLink`; Close opens a confirm and calls `recordDecision` only after confirmation.
- `Evidence.test.tsx`: NDJSON lines render five file rows, then the checks; Export needs the confirm;
  Verify calls the verify route.
- `ShiftDelta.test.tsx`: groups render; items link to `/cases/…?focus=…`.
- `evalView.test.ts`, `Eval.test.tsx`: tiles read pass, gap or report-only from `targets`; histogram
  bins on a fixture; demo rows show status as written; a report without `targets` shows the rerun
  message.
- `MatchExplainer.test.tsx`: bars sorted by |contribution|; the logit line equals intercept + Σ; both
  flight plots render with the segment marked.
- Extended: `router.test.ts` (new routes, `/swarm` still planned), `uiStore.test.ts` (perfMode turns
  effects off), `matchStore.test.ts` (hovered, lens selection), `CommandBar.test.tsx` (Director and
  Performance mode buttons), `LiveWatch.test.tsx` (the memory rail has Matches, Region constellation,
  Time-warp lens).

Playwright (`web/e2e/`, one worker, scratch server):

- **(SPEC)** `director.spec.ts`:
  - `Director at 5x shows every beat's key element at 1440x900` and the same at 1920x1080. Reseed,
    open Live watch, 5×, press D. For each beat, wait for `director-beat[data-beat=<id>]`, a non-empty
    caption and the A1 key element.
  - At beat 7: click Known then (assert the "hobbyist" node and no link edges), click Known now
    (assert the diff lists proposals), approve every pending proposal.
  - Press →; at beat 8: Export, confirm, five file rows, checks pass, Verify package passes.
  - Save `reports/figures/ui/phase08-beat-<nn>-<id>-<w>x<h>.png` at every beat (§17.13, restoring
    D-113's per-beat set).
- `director.spec.ts::Director never commits by itself`: run beats 1 to 8 at 5× without clicking. The
  ledger tail since the seed head has only `incident_recorded`, `model_registered` and
  `match_proposed` rows (rule 8).
- `director.spec.ts::keys and modes`:
  - ← from beat 7 returns to Live watch at the recall beat;
  - Space pauses and resumes;
  - R resets to T+0 and beat 1 with the ledger at the seed head;
  - M (reduce motion) keeps the captions, the forecast sentence and the overlay text, and sets the
    theater's `data-perf` to effects off;
  - Performance mode does the same for bloom.
- `director-1x.spec.ts::Director at 1x through every §1.2 row` (timeout 8 min, 1920 × 1080):
  - writes `reports/figures/ui/director_1x.json` with, per beat, its activation replay T, local time,
    wall seconds and when its key element became visible;
  - also records the loiter-marker time for §1.2's T+80 row;
  - records the A24 frame-rate fields, and asserts ≥ 50 fps median on a hardware renderer.
- `lens.spec.ts::lens connectors follow the DTW path`: at T+90 (paused), fetch
  `/api/dtw/DEMO-BRAVO-0828/<top track>?at=90`. In Warped mode every connector's `(data-i, data-j)` is
  a path pair and the first and last pairs are present. In Same time mode every connector has
  `i == j < overlap`. The readouts match the payload's distances to 1 decimal.
- `pages8.spec.ts`:
  - Case board known then and known now;
  - Explainer bars (7) and both flights;
  - Shift delta groups and a link that opens the Case board;
  - Eval tiles and demo table (6 rows);
  - Evidence list after an export;
  - a screenshot of each page at both sizes (`phase08-page-<name>-<w>x<h>.png`).
- `pages.spec.ts`: axe (no serious or critical violation) on every route, now including the Case
  board for the planted case and the explainer (**SPEC**: axe check on every page). Existing phase 7
  specs stay as they are.

No skip or xfail marker is added anywhere.

## Exit-check mapping

Each block's command and trimmed output go into `EXIT_CHECK.md`. Servers run in the background with a
time limit and are stopped (no server left running).

| Criterion (SPEC §20 phase 8) | Command | Evidence it will produce |
|---|---|---|
| `make eval` demo assertions pass | `make eval && python3 scripts/check_targets.py 8; echo exit=$?` | Every demo row except `swarm_top1` passes; `live_top3_incidents` prints WARN (accepted D-081); the phase 4 and 5 metrics PASS (latency WARN, report-only); `exit=0`; the JSON now has `targets` |
| Director mode at 1× through every §1.2 row with times recorded | `make e2e` (runs `director-1x.spec.ts`), then `python3 -m json.tool reports/figures/ui/director_1x.json` | A table per §1.2 row: beat, activation T, local time, wall seconds, key-element time; T+80 loiter-marker time; the encore row marked "phase 9". Pasted into EXIT_CHECK.md and PROGRESS.md |
| Screenshots of every beat at both sizes reviewed, fixes logged | `ls reports/figures/ui/phase08-*` after `make e2e`; each image opened and reviewed | 16 beat screenshots (8 beats × 2 sizes) and 10 page screenshots; a findings → fix list in EXIT_CHECK.md, PROGRESS.md and a DECISIONS entry; a second `make e2e` after the fixes |
| Median frame rate ≥ 50 fps on the dev machine | from `director_1x.json` (and the phase 7 `perf.json`) | Median and P5 fps overall and per Live watch beat, renderer string, CPU, cores, macOS version; the ≥ 50 assertion passed |
| Playwright Director at 5×, every beat's key element; axe on every page | `make e2e` | All specs pass (phase 7's 19 plus the new ones); counts in REPORT.md |
| Fast and slow tests | `make check`; `make test-all` | Fast count ≥ 710 (phase 7 end) plus the new tests; all pass; Vitest count |
| Web build | `npm --prefix web run build` | Chunk list: lazy pages split out; `vendor-3d` not loaded by `/cases` or `/eval` |
| `make demo` serves the new pages offline | see block below | Health ok; `/api/cases`, `/api/explain/…`, `/api/eval/latest` `.targets`; SPA routes 200; port 8000 free afterwards |
| Contract current | `uv run kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types && git diff --exit-code web/openapi.json web/src/api/types.gen.ts` | Empty diff |
| Ledger untouched by the exit check | `uv run kairos-defense memory verify` | Chain intact |

`make demo` block (no foreground sleep; curl retries until the server answers):

```bash
make demo > /tmp/kd-demo-p8.log 2>&1 &
curl -sf --retry 120 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/cases | python3 -m json.tool | head -20
curl -s "http://127.0.0.1:8000/api/explain/DEMO-BRAVO-0828/P1-DELTA-260419-T1?at=90" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['score'], d['logit'], len(d['contributions']))"
curl -s http://127.0.0.1:8000/api/eval/latest | python3 -c "import json,sys; print(len(json.load(sys.stdin)['targets']))"
for p in /cases/CASE-P1-DELTA-260419 /evidence /delta /eval "/explainer?incident=DEMO-BRAVO-0828&at=90"; do
  curl -s -o /dev/null -w "%{http_code} $p\n" "http://127.0.0.1:8000$p"; done
pkill -f "kairos-defense api --static web/dist"; lsof -nP -iTCP:8000 -sTCP:LISTEN || echo "port 8000 free"
```

The 1× table will look like this (values from the run):

| §1.2 row | Beat | Activated at | Key element visible at | Note |
|---|---|---|---|---|
| T+0 | Detection | T+0 (21:40:06 local) | … | first point 71 m from the fence (eval) |
| T+45 | Recognition | T+45 | … | first `match` |
| T+80 | (during Recognition) | – | loiter marker at T+… | eval orbit check T+79 |
| T+90 | Time warp | T+90 | … | top 3 as computed (D-081) |
| T+105 | Forecast | T+105 | … | zone label text |
| T+120 | Recall | T+120 | … | DELTA report rank 1 |
| Case Board | Known then and now | → | … | hobbyist then, members now |
| Evidence | Evidence | → | … | 5 files, checks pass |
| Encore | – | – | – | phase 9 |

## Documentation to write or update

- `docs/phases/phase-08/EXIT_CHECK.md` and `REPORT.md` (templates), including the screenshot findings,
  the 1× table, the frame rate and machine, and the A6 note on ALPHA-260303's pace.
- `web/README.md`: new routes and pages, stores, the lens, theater layers, overlay, Director (beats,
  keys, reveal), performance mode, the new e2e specs and artifacts, changelog entry for phase 8.
- `src/kairos_defense/api/README.md`: the explain, cases, decisions, evidence list and verify routes;
  `schemas_pages.py`; `--exports`.
- `src/kairos_defense/match/README.md`: `contribution_table`; `explain_alignment` now used by the
  explainer.
- `src/kairos_defense/memory/README.md`: `case_summaries`.
- `src/kairos_defense/eval/README.md`: `targets.py` and the JSON `targets` key.
- `src/kairos_defense/README.md`: CLI `api --exports`.
- Root `README.md` "Status": phase 8 built (awaiting gate), with what the demo now shows.
- `docs/PROGRESS.md`: a session-log entry and the one-line exit-check evidence (Status cell
  unchanged; the autopilot marks it).
- `docs/DECISIONS.md`: D-122 onward for A1–A24, deviations found while building, and the screenshot
  review fixes.

## Risks and mitigations

- **Frame rate under 50 fps with the new layers and bloom.**
  - Ghosts are three `Line2` objects; beams are one instanced mesh; the forecast and road are one
    dashed line each; the grain is one fullscreen pass.
  - Measure with `director-1x.spec.ts` as soon as step 4 lands, not at the end.
  - Auto-degrade (D-120) stays. If the median still misses, profile with Chrome tracing before cutting
    anything specified.
- **Director timing flakiness at 5× and across pages.**
  - e2e waits on key elements, not on time.
  - Beat activation reads the server clock (`clock` messages), not wall timers.
  - Remount on return to Live watch is tested (← from beat 7).
  - One worker; every spec reseeds first.
- **The stream closes when Director leaves Live watch.** On return, Director reconnects and seeks.
  "Known now" uses the ledger head, which holds the proposals written at replay-clock times (D-010,
  §15.6).
- **Captions that overclaim (rule 10).** Captions are computed with fallbacks; a Vitest checks for
  missing values. The T+90 caption names what the matcher returned (DELTA, CHARLIE in the top 3;
  D-081), not the scenario's list.
- **Path traversal in `POST /api/evidence/verify`.** Resolve the path and require it to be inside
  `paths.exports`. Tested with `../`, an absolute path and a symlink.
- **Memory rail crowding at 1440 × 900** (matches, constellation and lens in ~840 px). The lens has a
  compact variant (curves and connectors above a smaller matrix). Constellation height is fixed at
  about 150 px. Screenshot review at both sizes decides.
- **Bundle growth.** Pages are lazy and d3-force loads only with the Case board; the build output is
  checked in the exit check.
- **Module size over ~400 lines.** Split as listed (`schemas_pages.py`, `routes_explain.py`, lens and
  case subfolders).
- **Fullscreen and keyboard in headless Chromium.** F is unit-tested with a mocked
  `requestFullscreen`. e2e covers Space, →, ←, R and M.
- **d3-force nondeterminism.** A seeded `randomSource`, seeded initial positions and synchronous ticks
  make the layout testable.
- **A stale eval JSON without `targets` on a machine that skipped `make eval`.** The Eval page says so
  instead of failing. The gate runs `make eval` before `make e2e`.
- **e2e duration** (about 8 min with the 1× run). Per-test timeouts are set explicitly. The webServer
  timeout stays 240 s.

## Out of scope

- The swarm encore beat, swarm matching and the Swarm view (phase 9; `/swarm` stays a placeholder).
- Agent tools, the MCP server, the optional LLM chat (phase 9).
- Any matcher, recall, forecast or metric change, including D-081's follow-up (target-aware partial
  signatures). The accepted top-3 gap stays as computed.
- Latency work (D-060) and `docs/DEMO.md` (phase 9).
- Authentication (§2).

## Review changes

None yet.
