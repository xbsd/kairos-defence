# Progress

| Phase | Title | Status | Exit check evidence | Date |
|---|---|---|---|---|
| 0 | Scaffold | done | Exit check exit 0 in 12 s: ruff clean; pytest 89 passed; web lint, typecheck, Vitest 5 passed; help lists 14 commands; web build 223 kB JS | 2026-10-28 |
| 1 | World, flights and radar | done | Exit check exit 0 in 46 s from `make clean`: 1,869 incidents and 1,869 tracks (≈1,900 / ≈1,950, within ±15%); figures for all 7 patterns; 53 selected tests pass; live first contact 21:39:51, orbit T+94 s | 2026-10-28 |
| 2 | Swarms, RF, Remote ID, reports and assessments | done | Exit check exit 0 in 31 s from `make clean`: 1,878 incidents (9 swarms), 956 reports, 1,876 assessments; planted DELTA report, wrong label and both swarm events present; 109 selected tests pass; live orbit T+79 s (D-033 b) | 2026-10-28 |
| 3 | Features, windows, Euclidean baseline and eval skeleton | done | Exit check exit 0 in 87 s after `make clean data`: 1,898 history tracks indexed (6 live skipped), 136,266 windows; baseline Recall@5 0.435, MRR 0.302, time to match 26%, copycat-first 57%, prefilter p95 83 ms; demo first contact and orbit pass | 2026-10-28 |
| 4 | DTW matcher and fusion model | done with gaps (2026-10-28, see docs/phases/phase-04/GAPS.md) | `make index`, `make models` (62 queries, 123,404 pairs, τ 1.645, 44 s), `make eval`: Recall@5 1.000, DTW lift +0.522, copycat-first 0%, time to match 96%, p95 prefilter 30 / DTW (500) 81 / end to end 149 ms; first contact and orbit pass; live top 3 misses by one place (DELTA 1, ALPHA-0303 2, CHARLIE 3, ALPHA-0502 4; soft gap, D-078); `eval --baseline` written; `check_targets.py 4` 8 PASS, 1 GAP; 431 fast, 441 in all | 2026-10-28 |
| 5 | Report recall and analog forecast | done (2026-10-28, autopilot gate passed) | `make index`: 956 reports with FTS, 82 `report_clues`; `make eval`: report linkage 1.000 (65/65), forecast median 340 m / P80 495 m at T = 90 s; demo DELTA report rank 1 and forecast 139 m at T+105 pass; `forecast --at 105` exit 0 (2,164 m northwest, County Rd 12 in the zone); `check_targets.py 5` 12 PASS, 1 WARN (accepted top 3); 497 fast, 509 in all | 2026-10-28 |
| 6 | Case memory (Kairos-lite) | done (2026-10-29, autopilot gate passed) | `memory reseed && memory verify && pytest -k memory` exit 0 in 7.8 s: 4,681 rows seeded in 0.14 s, chain intact, 92 passed; DELTA at 10:00 local hobbyist, closed, no links; `memory demo --approve` known then 1 member → known now 3 (real top 3: DELTA, ALPHA-0303, CHARLIE; D-081); evidence verify PASS, then FAIL after one edited byte; 586 fast, 601 in all | 2026-10-28 |
| 7 | Streaming API and Command Center foundation | done (2026-10-29, autopilot gate passed) | `make demo` serves API, stream and web app offline (T+90 match cached; all stream types by T+50 at 5×; D-010 resets through the API); `make e2e` 19/19 with axe clean on 7 routes; 8 screenshots reviewed, 9 fixes; median 59.9 fps (P5 59.9) at 1920 × 1080 with bloom, ANGLE Metal on an Apple M4 Max, macOS 26.5.2; 710 fast, 726 in all; Vitest 73 | 2026-10-29 |
| 8 | Command Center: the memorable moments | done (2026-10-29, autopilot gate passed) | Director at 1× through every §1.2 row: T+0 21:40:06, T+15, T+45, loiter marker T+87 (T+80 row), T+90, T+105, T+120 21:42:06, then Case board and Evidence on →; median 59.9 fps (P5 59.9) on every Live watch beat at 1920 × 1080 with bloom, ANGLE Metal, Apple M4 Max, macOS 26.5.2; 18 beat + 12 page screenshots at both sizes reviewed, 17 fixes (D-146); `make e2e` 29/29 with axe clean on 9 routes and on Live watch at T+120; `make eval` + `check_targets.py 8` exit 0 (accepted `live_top3_incidents` WARN, D-081); 731 fast, 747 in all; Vitest 153 | 2026-10-29 |
| 9 | Swarms, agent, MCP, hardening and runbook | not started | | |
| 10 | User guide, one-pager and rollback guide (docs/phases/PHASE_10.md) | not started | | |

Status values: `not started` · `in progress` · `done` · `blocked (<reason>)`

## Session log

<!-- Newest first. One entry per session:
### YYYY-MM-DD · Phase N
- Built: …
- Exit check: <command> → <key output / metrics>
- Open issues: …
- Next: …
-->

### 2026-10-29 · Phase 8 (autopilot build)
- Built: the Command Center's memorable moments (SPEC §17.3, §17.7–§17.13).
  - Backend:
    - `GET /api/explain/{incident}/{track}` (`api/routes_explain.py`,
      `match/explain.contribution_table`, D-135);
    - `GET /api/cases` (`memory/asof.case_summaries`), `POST /api/cases/{id}/decisions`,
      `GET /api/evidence`, `POST /api/evidence/verify` with a path guard
      (`api/schemas_pages.py`, D-136);
    - `api --exports` for e2e scratch exports (D-137);
    - `eval/targets.py`, written into the eval JSON as `targets` and kept equal to
      `scripts/check_targets.py` by a test (D-139).
  - Web:
    - the time-warp lens with the 1.2 s connector morph onto the DTW path, the cost matrix and its
      drawn-on path (D-126, D-127);
    - afterglow ghosts, core beams, the region constellation (D-128 to D-130);
    - the forecast path, pulsing zone, computed label and County Rd 12's in-zone dots
      (D-132, D-133);
    - computed memory and forecast camera shots (D-134);
    - the report recall overlay with clue spans, glyph resolve, zone note and its beam to the road
      (D-131);
    - the Match explainer, Case board (as-of scrubber, d3-force graph, diff, approvals, decisions),
      Evidence, Shift delta and Eval pages, all lazy (D-135, D-138, D-140, D-141);
    - Director mode (eight beats, computed captions, keys D, Space, →, ←, R, M, F, ?, progress
      rail, panel dimming, progressive reveal; never commits) (D-122 to D-125, D-142, D-143);
    - Performance mode and static grain (D-144).
- Exit check (`docs/phases/phase-08/EXIT_CHECK.md`), dev laptop:
  - Director at 1× (`director_1x.json`): every §1.2 row landed at its replay second. T+0 21:40:06,
    T+15, T+45, T+90 (lens Warped at T+91), T+105, T+120 21:42:06. The T+80 row is the loiter
    marker at T+87; the eval's orbit check is T+79. → opened the Case board and Evidence. The
    encore is phase 9.
  - Frame rate: median 59.9 fps (P5 59.9) overall and on each Live watch beat. Recall P5 59.5.
    1920 × 1080, bloom on, ANGLE Metal on an Apple M4 Max (16 cores, 128 GB), macOS 26.5.2.
  - `make e2e`: 29 passed in 8.3 min. This includes Director at 5× at both sizes with each beat's
    key element, "never commits by itself", the keys and modes, the lens connectors on the DTW
    path, the five pages, and axe clean on 9 routes and on Live watch at T+120.
  - `make eval` then `check_targets.py 8`: exit 0. The phase 4 and 5 metrics PASS. Every demo row
    except `swarm_top1` passes, apart from the accepted `live_top3_incidents` (WARN, D-081). The
    eval JSON has 10 targets.
  - `make demo` (background, stopped): health ok; `/api/cases`, `/api/explain/…` (score 0.9996,
    logit 7.89, 7 rows) and the eval `targets` answer; every page route returns 200; port 8000
    free afterwards.
  - Contract regenerated byte-identical. `memory verify`: chain intact at 4,681 rows.
  - `make check`: 731 fast (710 at the start). `make test-all`: 747 passed. Vitest 153 (73 at
    the start).
- UI review (§17.13): 18 beat screenshots and 12 page screenshots, at 1920 × 1080 and
  1440 × 900, in three rounds. 17 findings were fixed:
  - grain too strong;
  - Space taken by a focused button;
  - three match entries not fitting at 1440 × 900;
  - lens controls wrapping and the matrix cut off;
  - the overlay covering the zone (the forecast shot shifted);
  - ghost labels overprinting;
  - a cramped case graph;
  - duplicate proposals with no way to tell them apart;
  - the page caption over the controls;
  - the self-match arc with no label;
  - ghosts going dark after a top-3 change (spec cache);
  - the zone label colliding with a ghost label;
  - constellation labels colliding;
  - a faint beam drawn under the overlay;
  - the explainer's faint tonight path;
  - Eval chart labels clipped and colliding;
  - the Stream list not keyboard-reachable (axe `scrollable-region-focusable`).

  Left as is: at 1440 × 900 the third match entry's buttons sit just below the fold of its
  scrolling list. Details are in D-146 and EXIT_CHECK.md.
- Decisions D-122 to D-147. No skip or xfail marker was added.

### 2026-10-29 · Phase 7 (autopilot build)
- Built: the streaming API and the Command Center foundation (SPEC §16, §17.1–§17.6, §17.11–§17.13).
  - `kairos_defense.live`: replay engine and clock (D-118), the live loop with reruns every 5 s
    from T+45, result cache with a fingerprint and `replay --precompute` (D-105), flight phase
    (D-115), per-client sessions with recording into `live_*` (D-103), proposals into the case
    of the best-ranked member (D-106), ledger fan-out, the theater scene (D-109).
  - `kairos_defense.api`: schemas with the 13-type `StreamMessage` union, every §16.4 route plus
    health and ledger tail/record, the WebSocket, static hosting, `api --dump-openapi` (D-107,
    D-108, D-110, D-112). Ports `LiveSink`, `ResultCache`; adapters `DuckLiveSink`,
    `FileResultCache`; `reseed_ledger` shared by the CLI and the admin endpoint (D-104).
    `match/lens.py` (D-117); memory status, case graph, evidence progress (D-116, D-108).
  - CLI `api` and `replay`; `replay --reset` and `memory reseed` go through the API while it runs
    (D-010, D-111).
  - `web/`: generated types (`gen:types`, `check:types`), stream client with reconnect, REST
    client, Zustand stores, router, wired command bar, shortcuts dialog, Live watch layout; the 3D
    theater (D-120); Stream, Signals, Recorder, Ledger chain, Match list with Approve and Reject
    (D-121); Playwright e2e with screenshots, axe and a frame-rate probe (D-113, D-114).
- Exit check (`docs/phases/phase-07/EXIT_CHECK.md`), dev laptop:
  - `make demo` (background, stopped): health ok; `/` and `/live/…` serve the app; T+90 match
    from the cache (DELTA, ALPHA-260303, CHARLIE-260710, D-081); a WebSocket at 5× from T+40 got
    every type except `rid` (P1 broadcasts none) within 6 s; `replay --reset` and
    `memory reseed` went through the API; port 8000 free; ledger at seed head `a361b4bf…`.
  - `make dev`: Vite proxies `/api/health` and the WebSocket; both stopped, ports free.
  - `make e2e`: 19 passed in 2.0 min (axe: no serious or critical violation on 7 routes).
  - Frame rate (Playwright Chromium 156, 10 s of 1× playback, 1920 × 1080, bloom on): median
    59.9 fps, P5 59.9 fps, renderer ANGLE Metal, Apple M4 Max (16 cores, 128 GB), macOS 26.5.2.
  - Contract: regenerated `web/openapi.json` and `types.gen.ts` byte-identical.
  - `make check` 710 passed (586 at the start); `make test-all` 726 passed; Vitest 73.
- UI review (§17.13; 8 screenshots, first contact, T+45, T+90, approved × 1920 × 1080 and
  1440 × 900):
  - labels cut by grid lines: fixed with a depth-test-free base material;
  - dashed fence and ground lines: the grid no longer writes depth;
  - the "No Remote ID" tag over the "Fuel farm" label: asset labels below their footprints, the
    tag above the drone;
  - the base small in the overview: camera about 25% closer;
  - Signals "Loiter since loiter at": now "Loiter since T+01:27";
  - Recorder stats wrapping and "1 rows": label and value rows, singular;
  - Ledger chain title wrapping and badge truncated: titles never wrap, badge "Chain verified";
  - Stream tight at 1440 px: wider column;
  - axe `label-content-name-mismatch` on ledger blocks: the visible text starts the name.
  The second set shows no overlaps and numbers legible at 13–15 px mono.
- Deviations: D-105 (fingerprint counts), D-107 (play and pause without catch-up), D-110 (locks),
  D-111 (startup seeding), D-114 (openapi-typescript override), D-115 (phase rule), D-119
  (`make dev` recipe), D-113 (screenshot moments instead of Director beats).
- Open issues: the D-081 top-3 gap shows in the UI as computed; scores read 1.00; the `vendor-3d`
  chunk is 1.18 MB; `make dev`'s `trap 'kill 0'` also stops a script that started it.
- Next: phase 8 (the memorable moments: time-warp lens, ghosts, forecast, recall overlay, Case
  board, Evidence, Director mode).

### 2026-10-28 · Phase 6 (autopilot build)
- Built: case memory, Kairos-lite (SPEC §15).
  - `memory/canonical.py` and `memory/ledger.py`: canonical JSON, validation (rule 8 actor
    permissions, rule 9 ids), sealing with `recorded_at = max(clock, head)`, `verify_rows`
    (D-094, D-095). DuckDB adapter `store/ledger_duck.py` with the verbatim §15.1 DDL and macro,
    one locked connection, atomic batches (D-092, D-093); `CaseMemory.append_many` and `events`,
    typed `CaseSnapshot`.
  - `memory/asof.py`, `diff.py`, `views.py`: snapshots, contradictions (never auto-resolved),
    valid time, grouped diffs (D-094, D-101).
  - `memory/seed.py`: every history event before the live first contact plus the planted DELTA
    case and close decision at 09:10 local (D-096). `memory/actions.py`: deduplicated proposals,
    analyst-only approvals (D-097). `memory/delta.py`: the shift delta (D-101).
  - `memory/evidence.py`, `evidence_html.py`: approved export, Ed25519-signed manifest, static map,
    verification (D-099). `guard.refuse_truth` (D-102).
  - CLI: `memory seed|reseed|verify|show|delta|demo`, `export`, `verify-evidence` (D-098, D-100).
- Exit check (`docs/phases/phase-06/EXIT_CHECK.md`), dev laptop:
  - `memory reseed && memory verify && pytest tests/unit -q -k memory`: exit 0 in 7.8 s; 4,681
    rows (1,866 / 949 / 1,864 / 1 / 1), head `a361b4bf…`, chain intact; 92 passed.
  - DELTA as of 2026-04-20 10:00 local: hobbyist, closed, no links. Unknown at 09:00.
  - `memory demo --approve`: "known then" 1 member, closed → "known now" 3 members (DELTA,
    ALPHA-260303, CHARLIE-260710: the real matcher's top 3, accepted phase 4 gap D-081); the diff
    lists 3 `members_added`. `data/memory.duckdb` unchanged.
  - `export` without `--approve` exit 1; with it, a signed package; `verify-evidence` all PASS,
    then `files` FAIL after one byte of `case.html` changed.
  - `make check` 586 passed (497 at the start − 3 stub cases + 92 new); `make test-all` 601
    passed in 3 min 25 s.
- Deviations: three CLI modules (D-100); extra delta groups (D-101); `guard.refuse_truth` (D-102).
- Open issues: the terminal demo links CHARLIE rather than ALPHA-260502 (D-081); DuckDB's process
  lock means reseed and verify exit 1 while `make demo` runs (phase 7 adds the admin endpoints).
- Next: phase 7 (streaming API and Command Center foundation).

### 2026-10-28 · Phase 5 (autopilot build)
- Built: report recall and the analog forecast (SPEC §12, §13).
  - `recall/embed.py`: the hashing embedder (offline default, D-083), a FastEmbed adapter that
    refuses to start unless the model is cached, and `kairos-defense fetch-models`, the only
    downloader (D-084, new key `paths.cache`).
  - `make index` also builds LanceDB `reports` (FTS on `text` with positions) and DuckDB
    `report_clues` (D-085, D-089).
  - `recall/search.py`: the §12.3 filter plus no look-ahead (D-082), LanceDB native hybrid with an
    RRF tie-break by `report_id`, and the §12.5 fallback, identical row for row (D-085).
  - `recall/clues.py`: vehicles and gazetteer roads with spans, linked across matches and to the
    forecast zone (D-086; the color is optional because the paperwork writes "a motorcycle").
  - `forecast/analog.py`: §13 steps 1 to 7 (D-087; j* uses the shape distance's scaling).
    `forecast.anchor: match_kind`, adopted by the rule registered first in D-090 (training split:
    median 311 m against 502 m, P80 492 m against 1,000 m).
  - `eval/downstream.py`: forecast error and report linkage (D-088); two demo assertions;
    `eval/forecast_choice.py`; real `recall`, `forecast` and `fetch-models` commands (D-091).
- Exit check (`docs/phases/phase-05/EXIT_CHECK.md`), dev laptop:
  - `make index` 7.2 s: 956 reports indexed, `report_clues` 82 rows (equal to the generator's
    vehicle and gazetteer-road clues), `hashing-v1-384`.
  - `make eval` 36 s: report linkage 1.000 (65 of 65), forecast median 340 m / P80 495 m at
    T = 90 s; demo `live_rank1_report_for` pass (DELTA report rank 1, County Rd 12 linked to the
    zone) and `forecast_error_max_m` pass (139 m at T+105). Phase 4 metrics unchanged; no
    regression. Exit 1 only for the accepted `live_top3_incidents` row.
  - `forecast --incident DEMO-BRAVO-0828 --at 105` exit 0: 2,164 m at 320° (northwest) of BRAVO's
    fuel farm, radius 370 m, County Rd 12 crosses the zone. `recall --at 120` exit 0.
  - `check_targets.py 5`: 12 PASS, 1 WARN (accepted), exit 0. `eval --baseline` refreshed.
  - `make check` 497 passed (443 at the start); `make test-all` 509 passed in 3 min 12 s.
- Deviations: CLAUDE.md's `create_fts_index` note (deprecated), §12.4 vehicle form, §13 step 4
  while tonight reads the fence; the plan's colored-only vehicles and j* alignment. D-082 to D-091.
- Open issues:
  - Report linkage is near-trivial on this data (at most 4 reports per incident in a filter
    window, k = 5); the DELTA rank-1 beat is structural (one report in its window).
  - The forecast median's margin is 60 m; the demo forecast uses two rotated P3 analogs, since
    only 2 of 5 earlier P1 flights have a known recovery.
  - FastEmbed tested with a fake module only; the phase 4 top-3 gap carries over.
- Next: phase 6 (case memory).

### 2026-10-28 · Phase 4 (gate fix attempt 3, autopilot)
- Gate 3: the same single GAP, `demo:live_top3_incidents`.
- Root cause recorded (D-081): CHARLIE's "weaker" trait is its target, and partial tracks' targets
  and loiter radii are unreliable at T+90. All 48 same-actor target mismatches come from unsettled
  partial targets, and the partial radius is off by a median of 1.1 km at T = 90 s. No honest
  method change flips the beat, so there is no code change. The gap goes to GAPS.md.
- Gate list rerun: `make check` 443 passed; `make models` hash unchanged; `make eval` unchanged;
  `match` exit 0; `check_targets.py 4` 8 PASS, 1 GAP; `make test-all` 453 passed.
- Follow-up (phase 7 or 8): mark partial-signature target, radius and radius reasons unknown until
  the loiter is established.

### 2026-10-28 · Phase 4 (gate fix attempt 2, autopilot)
- Gate 2: every command passed; the same single GAP, `demo:live_top3_incidents` (ALPHA-0502 #5).
- Tried (D-080, criterion registered first): a `target_match` fusion feature. On the held-out
  training nights MAP fell from 0.9603 to 0.9568 with a coefficient of −0.91, because partial
  tracks often read the fence or a wrong target. Not adopted; no code change.
- Full gate list rerun: `make check` 443 passed; `make models` hash `418c5edf` (unchanged);
  `make eval` unchanged, no regression; `match` exit 0; `check_targets.py 4` 8 PASS, 1 GAP.
- Open: the soft gap. Recommendation: accept it in GAPS.md, since the top 4 are all P1 and CHARLIE
  is genuinely closer to tonight's flight on the measured features.

### 2026-10-28 · Phase 4 (gate fix attempt 1, autopilot)
- Gate 1: every command passed; one GAP, `demo:live_top3_incidents`.
- Change (D-079, criterion registered before evaluation): `dtw.normalize: fixed`. The DTW shape
  distance now uses the prefilter's fixed units instead of §9.3's per-series z, which turned
  orbit noise into shape.
  - Held-out training nights, pair AUC of −`d_norm`: `series` 0.558, `floored` 0.565, `fixed`
    0.786.
  - Fused held-out metrics are unchanged.
- Full gate list rerun:
  - `make check` 443 passed.
  - `make models`: τ 2.227, hash `418c5edf`.
  - `make eval`: Recall@5 1.000, lift +0.522, copycat-first 0%; p95 DTW 57 ms, end to end
    124 ms.
  - `match` exit 0.
  - `check_targets.py 4`: 8 PASS, 1 GAP. The demo row is still 2/3: ALPHA-0502 is #5 behind a
    P3 flight, because of its 118 m altitude against tonight's 90 m.
  - `reports/baseline.json` refreshed.
- Open: the same soft gap; two attempts remain.

### 2026-10-28 · Phase 4 (autopilot build)
- Built: the DTW matcher and fusion model (SPEC §10.4 to §10.8).
  - Fixed-unit window vectors and 500 candidates (D-068, resolving D-058).
  - An anchored, end-relaxed banded DTW and a speed-ratio warp (D-069).
  - Partial live signatures bounded to T, through two new read-only port methods (D-071, D-072).
  - §10.5 fusion features, a logistic model trained in `eval/training.py` on prober and copycat
    queries of months 1 to 12 (D-073, D-078), and §10.7 reasons (D-074).
  - Stale-index and missing-model guards (D-075).
  - `make models`; `match` and `eval` default to `--method dtw`; DTW lift measured in the same run
    (D-076); the eval figure font pinned (D-077).
  - Committed: `models/fusion_v1.json`, `models/dtw_calibration.json`, `reports/baseline.json`.
- Exit check (`docs/phases/phase-04/EXIT_CHECK.md`), dev laptop:
  - `make index` 7 s, unchanged counts. `make models` 44 s: 123,404 pairs, τ 1.645, validation
    AUC 0.998.
  - `make eval` 39 s: Recall@5 1.000, DTW lift +0.522 (the same candidates in prefilter order
    give 0.478), MRR 1.000, time to match 96%, copycat-first 0%, copycat Recall@5 1.000.
    p95: prefilter 30 ms, DTW of 500 candidates 81 ms, end to end 149 ms.
  - Demo: first contact and orbit pass. `live_top3_incidents` fails by one place: DELTA #1,
    ALPHA-0303 #2, CHARLIE-0710 #3, ALPHA-0502 #4, all P1, each with three reasons. `make eval`
    therefore exits 1 and the SPEC chain stops there; `match --method dtw` alone exits 0.
  - `eval --baseline` writes `reports/baseline.json`. `check_targets.py 4`: 8 PASS and 1 GAP
    (the demo row), exit 1, a soft gap under D-063.
  - `make check` 431 passed (367 at the start); `make test-all` 441 passed in 3 min 31 s.
- Deviations: §9.3 for the prefilter vectors, §6.5 prefilter sizes, §10.4 steps 3 and 5, §4.1
  ports, §10.6 query kinds. Each is in D-068 to D-078.
- Open issues:
  - The live top-3 gap: CHARLIE (planted as weaker) leads ALPHA-0502 by 0.80 logit, mostly on
    altitude.
  - The §1.2 "flown ~18% slower" caption does not appear (ALPHA-0303 warp reads 1.03).
  - D-046 and D-065 carried over.
- Next: phase 5 (report recall and analog forecast).

### 2026-10-28 · Phase 3 (documentation backfill, autopilot)
- Built: no code. `docs/phases/phase-03/PLAN.md` (as built, from `e494995`), `REPORT.md` and
  `EXIT_CHECK.md`, plus `src/kairos_defense/features/README.md` and `match/README.md`. Every
  subpackage now has a README (D-061). The eval README gained two gotchas (UTC report dates,
  figure fonts). The root README's Status links the report. D-067.
- Exit check rerun at `53134b8` on the dev laptop, after `make clean && make data`:
  `make index && make eval` → exit 0 in 13.8 s.
  - Index: identical to phase 3. 1,898 history tracks indexed, 6 live skipped; 800,148 feature
    rows; windows 57,462 / 51,297 / 27,507; targets, loiter directions, RF and Remote ID counts
    unchanged. 7.2 s (55.0 s on the cloud sandbox).
  - Eval: Recall@5 0.435, MRR 0.302, time to match 26%, copycat-first 57%, copycat Recall@5
    0.500. All 198 outcomes, per-actor rows and demo rows are identical to the committed
    `eval_2026-10-28.json`; only latencies differ. Prefilter p50/p95 13/15 ms (83 ms p95 at phase
    3), end to end 17/19 ms. The report is `reports/eval_2026-10-29.*`, because file names use
    the UTC date.
  - `match --method euclidean --incident DEMO-BRAVO-0828 --at 90`: window 60 s, target fuel farm,
    50 candidates, 28 ms.
  - D-058 rechecked with the same ranks: at T+90 the three expected P1 flights rank 1,149 to
    1,194 of 1,882.
  - Phase 3's own tests: 81 + 3 fast and 3 slow passed. `make check`: 367 passed.
    `make test-all`: 374 passed in 42.8 s.
  - The web build restored `web/dist`. The recall figure was re-rendered in the laptop's font
    (same data) and committed.
- Open issues: D-058 (phase 4 must start here). D-057 does not apply on the laptop (prefilter p95
  15 ms against the 50 ms budget). D-046 (P6, C2, swarm targets). D-056 (`baseline.json` from phase
  4). Pin the figure fonts in `sim/figures.py` (D-065) and `eval/report.py` when they next change.
- Next: phase 4 (DTW matcher and fusion model), starting with D-058.

### 2026-10-28 · Phase 2 (documentation backfill, autopilot)
- Built: no code. `docs/phases/phase-02/PLAN.md` (as built, from `06cc826`), `REPORT.md` and
  `EXIT_CHECK.md`. `src/kairos_defense/sim/README.md` gained the `nights=` option and the phase 2
  fixtures (`swarms`, `planted`, `world_names`). The root README's Status links the report. D-066.
- Exit check rerun at `ba703ec` on the dev laptop, from `make clean`:
  `make data && uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"`
  → exit 0 in 10.9 s.
  - Data: identical to phase 2's run, because `sim/` and `config/` have not changed since
    `06cc826`. Incidents 1,878 (9 swarms), tracks 1,904, RF 414,999, Remote ID 686,263, reports
    956, assessments 1,876. Live first contact 21:40:06 and orbit T+79 s.
  - `reports/data_card.md` and all nine figures are byte-identical to the committed ones.
  - Planted items read back from both DuckDB files: the DELTA report with "white pickup",
    "County Rd 12", "21:20" and "22:05" and four true clues; the `hobbyist` label with truth
    `probing`; `S1-GOLF-260503` and `DEMO-SWARM-ECHO-0614` with 5 tracks each.
  - 116 passed, against 109 at phase 2. The filter now also matches 7 phase 3 tests (2 in
    `test_duck_store.py`, 5 in `test_index.py`); collecting it at `06cc826` gives 109 of 286.
  - Phase 2's own files: 103 fast passed, plus 3 in phase 1 files and 4 slow. `make check`: 367
    passed. `make test-all`: 374 passed in 44 s.
  - `make index` and the web build then restored phase 3's working state, and the index counts
    are identical to phase 3's exit check.
  - Swarm figures reviewed by eye; they match the S1 and S2 choreographies.
- Open issues: none new. Carried over: D-065 (pin the figure font in the next phase that touches
  `sim/`), D-040 (case-insensitive clue extraction, phase 5), D-043 (paraphrase, phase 9).
- Next: the phase 3 backfill (the `features/` and `match/` READMEs), then phase 4.

### 2026-10-28 · Phase 1 (documentation backfill, autopilot)
- Built: no code. `docs/phases/phase-01/PLAN.md` (as built, from `1a13664`), `REPORT.md` and
  `EXIT_CHECK.md`, plus `src/kairos_defense/sim/README.md` (phases 1 and 2). The root README's Status
  links the report. D-065.
- Exit check rerun at `3b0f06c` on the dev laptop, from `make clean`:
  `make data && uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"`
  → exit 0 in 12.2 s.
  - Results: incidents 1,878 (−1.2%) and tracks 1,904 (−2.4%), within ±15% of §8.11. All seven
    pattern figures written. 62 passed.
  - Live first contact 21:40:06 and orbit T+79 s.
  - `reports/data_card.md` came out byte-identical to the committed card.
  - Differences from phase 1's 1,869 / 1,869, 53 tests, 21:39:51 and T+94 s: phase 2 added 9 swarm
    incidents and 35 drone tracks, and D-033 (b) moved BRAVO's fuel farm. The `-k` filter now also
    matches 9 phase 2 tests.
  - `make check`: 367 passed. `make test-all`: 374 passed in 44 s. Phase 1's own files: 93 fast and
    4 slow passed.
  - `make index` and the web build then restored phase 3's working state. Index counts are identical
    to phase 3's exit check.
- Open issues:
  - **D-065:** the figures set no font, so `make data` on the laptop re-renders all nine PNGs in
    DejaVu Sans. The data is identical. The laptop renders are committed (D-034). The next phase
    that touches `sim/` should pin a font.
  - The web CSS bundle is 10.77 kB against 10.45 kB in phase 0's backfill. The likely cause is
    Tailwind scanning `web/README.md`; this is harmless, and phase 7 may exclude docs with
    `@source not`.
- Next: backfills for phases 2 and 3 (the `features/` and `match/` READMEs), then phase 4.

### 2026-10-28 · Phase 0 (documentation backfill, autopilot)
- Built: no code. `docs/phases/phase-00/PLAN.md` (as built, from `f9258de`), `REPORT.md` and
  `EXIT_CHECK.md`, plus READMEs for `src/kairos_defense/`, `config/`, `store/`, `eval/` and `web/`,
  and a Status section in the root README (D-061).
- Exit check rerun at `911aba1` on the dev laptop:
  `uv sync && npm --prefix web install && make check && uv run kairos-defense --help && npm --prefix web run build`
  → exit 0 in 18.7 s. Ruff clean; 367 passed, 7 slow deselected; web lint, typecheck and Vitest 5/5;
  14 commands in help; JS 222.56 kB and CSS 10.45 kB, identical to phase 0's build.
  `make test-all`: 374 passed in 51 s. The built placeholder in Playwright at 1920×1080 loads the
  B612 fonts, makes only same-origin requests and does not overflow.
- Open issues:
  - **D-062 (phase 4 must start here, with D-058):** dtaidistance's C library does not load on this
    laptop because `libomp` is missing. `dtw_ndim.distance(use_c=True)` silently runs pure Python, and
    D-020's fail-loudly rule would stop the matcher. Options are in D-062.
  - `npm --prefix web install` outside `make` runs under Node 26 and prints EBADENGINE (harmless,
    D-002). The built app logs a favicon 404 (phase 7).
- Next: backfills for phases 1 to 3, then phase 4.

### 2026-10-28 · Phase 3
- Built: this branch fast-forwarded onto phase 2's commit (it started at the kit). `features/`:
  `resample.py` (§9.1), `channels.py` (§9.2-§9.3, target choice D-046), `signatures.py` (§9.4,
  D-047), `windows.py` (§9.5 PAA, query vector, D-050, D-051), `build.py` (`kairos-defense index`,
  history tracks only, D-049, D-053). `store/duck.py` (`TrackStore`, §11.1 as-of weather and base
  events, §11.2 RF and §9.4 Remote ID association with time-bucketed joins, §11.3, D-048),
  `store/lance.py` (`VectorStore`, D-052), derived DDL in `store/ddl.py`. `match/`: `query.py`
  (rebuilt from points up to T), `prefilter.py` (§10.3, `LookAheadError`), `baseline.py` (§10.2,
  D-054), `types.py` (§10.8 `Match`). `eval/`: `truth.py` (the only truth reader), `harness.py`
  (§19.1-§19.2, D-055), `metrics.py`, `demo.py`, `report.py` (md, json, figure, `--baseline` gate,
  D-056). CLI: `index`, `match --method euclidean --incident --at [--track --top]`, `eval
  [--baseline]` are real.
- Tests: `test_resample` (straight line and circle known answers, ccw turn negative, gaps,
  duplicates, smoothing inside runs), `test_channels` (target choice incl. far takeoff, distances,
  normalization), `test_signatures` (cw/ccw/none, radius, approach, tod wrap, launch and recovery
  rules, Remote ID operator), `test_duck_store` (RF bearing gate on concurrent tracks, Remote ID
  ±5 s/100 m, as-of weather, events, strict `tracks_before`, truth refused), `test_windows` (PAA
  known answers, channel-major order, gap skipping, query = indexed vector), `test_index` (six P1
  nights generated and indexed: planted P1 signatures approach 315° ± 15°, radius 180 ± 25 m,
  `ccw` on all six flights incl. the live one from its points; live incidents absent from every
  derived table and LanceDB; filters return only the requested window size; metadata; rebuild
  gives identical hashes), `test_no_lookahead` (written before the matcher: filter text, every
  result started before the query for every track at T = 45/90/180, later P1 flights never
  returned, tampering with points after T leaves the query unchanged, a leaky store raises),
  `test_eval_metrics`, `test_eval_harness` (query sets, protocol, outputs, gate, CLI), slow
  `test_full_index` (full volumes, two builds give identical hashes, full eval passes the gate).
- Exit check (after `make clean && make data`; data card unchanged):
  ```bash
  make index && make eval
  ```
  → exit 0, 87.1 s wall. Key lines:
  ```text
  kairos-defense index
  tracks 1,904 · history tracks indexed 1,898 · live tracks skipped 6
  track_features rows 800,148 · gap seconds 62,850 (7.9%) · track_signatures rows 1,898
  flight_windows 60 s 57,462 · 120 s 51,297 · 300 s 27,507
  targets fence 1,800, flight_line 35, fuel_farm 19, hq 16, munitions 28
  loiter direction ccw 20, cw 1, none 1,877 · RF family unknown 0 · Remote ID present 1,634
  elapsed 55.0 s
  kairos-defense eval · euclidean
  prober queries 23 (0 unanswerable) · copycat queries 10 (0 unanswerable) · swarm incidents 5
  Recall@5 at T=120 s 0.435 · MRR at T=120 s 0.302 · time to match (top 3 by T=90 s) 26%
  copycat-first at T=120 s 57% · Recall@5 at T=120 s, copycats 0.500
  latency query build p50/p95 25/38 ms · prefilter 64/83 ms · end to end 93/117 ms
  demo live_first_contact_local pass: 21:40:06, 71 m · live_orbit_established_s pass: T+79 s
  demo live_top3_incidents info (target from phase 4): 0/3 in top 3
  demo live_rank1_report_for, forecast_error_max_m: pending (phase 5) · swarm_top1: pending (phase 9)
  elapsed 23.1 s
  ```
  **Euclidean baseline (phase 3, no targets):** Recall@5 0.435 · MRR 0.302 · time to match 26% ·
  copycat-first 57% · prefilter p50/p95 64/83 ms · end to end 93/117 ms. Recall@5 by T (probers):
  T=45 0.087, 60 0.304, 90 0.130, 120 0.435, 180 0.261. Per actor at T=120: P4 1.00, P3 0.60,
  C2 0.60, P5 0.50, C1 0.40, P6 0.33, P2 0.25, P1 0.00. Full report: `reports/eval_2026-10-28.md`,
  figure `reports/figures/eval_recall_by_t.png` (reviewed by eye: no collisions, legend and end
  labels, T = 30 omitted because the matcher does not run).
  `match --method euclidean --incident DEMO-BRAVO-0828 --at 90` runs in 164 ms (window 60 s,
  target BRAVO-fuel_farm, 50 candidates).
  `make check`: ruff clean, 367 passed (7 slow deselected), web lint, typecheck and Vitest pass.
  `pytest tests/slow`: 7 passed in 246 s.
- Open issues:
  - **D-058 (phase 4 must start here):** at T+90 the three planted P1 flights rank 1,149-1,194 of
    1,882 earlier tracks in the Euclidean prefilter, outside its 50 candidates, so DTW cannot
    re-rank them into the top 3 as the pipeline stands. Dropping noisy channels or smoothing more
    does not fix it; per-window z-normalization is the likely cause. Options are in D-058.
  - D-057: prefilter p95 83 ms against the 50 ms budget (§10.9) on this sandbox.
  - D-046: target choice is still wrong for P6 (consistently the flight line), C2 and swarm drones.
  - D-056: `reports/baseline.json` is first written by phase 4's exit check; with 23 prober
    queries the 5% gate moves on a single query.
  - Copycat-first (57%) counts queries whose own actor is not in the candidates at all (D-055).
- Next: phase 4 (DTW matcher and fusion model), starting with D-058.

### 2026-10-28 · Phase 2
- Built: D-033 resolved with option (b): BRAVO's fuel farm (the live target) keeps its template
  place (`world.unjittered_assets`). `sim/`: `formations.py` (formations, actions, timeline, swarm
  center path, D-035), `swarm.py` (schedule, center plans, drone paths), RF and Remote ID in
  `sensors.py` (D-036, D-037), `incidents.py` (sensing, incidents across all sensors, ids, D-038),
  `tables.py` (raw and truth tables), `facts.py` (what the paperwork knows, actor clue profiles,
  D-040), `lexicon.py` (clue vocabulary, clue scanner, guardrail scan, D-045), `reports.py`
  (sources, delays, grades, base styles, Appendix A templates, clue model, D-040, D-041),
  `assessments.py` (rules, 20% mislabel, truth labels, D-042), `paperwork.py` (planted report and
  assessment, D-011, D-043), `figures.py` and `datacard_paper.py` (data card split to stay under
  400 lines). `generate.py` flies single flights and swarm centers in one batch; `gen` prints the
  new counts. Kinematics gained one hook (the `choreography` pattern); existing flights are unchanged.
- Tests: `test_swarm_formations` (layouts, spacing, rotate direction, expand, split, blend and hold,
  center path), `test_swarm` (schedule incl. D-009, jitter ±10%, spacing ±20% on every event, rotation
  sense, orbit radius, plausible speeds, adding a team changes no other event), `test_rf` (family
  per actor, bands, rate, airborne only, range, mask, bearing noise, SNR), `test_rid` (on / off /
  spoofed, stable serials, operator positions, range, mask), `test_reports` (every clue in the text
  has a `clue_truth` row and back, delays and grades per source, counts per actor type, hobbyist
  rate and template, clue rates on 3,000 synthetic incidents, styles, swarm wording, paraphrase
  flag), `test_reports_lexicon` (forbidden-content scan over >1,000 texts; the scanner catches
  made-up plates, names, titles, addresses, phones and e-mail and allows world vocabulary; name
  lexicon shares no world word), `test_assessments` (one per history incident, 2–36 h, rules,
  mislabel rate, truth labels), `test_planted` (DELTA report and wrong label, other P1 paperwork,
  swarm events, no paperwork for live incidents, RF families, live T+0 = first radar contact),
  `test_generate` (incident span over all sensors, swarm tracks, no-radar flights make no incident),
  `test_world` (D-033), slow test (report and assessment volumes, swarm count, paperwork coverage).
- Exit check (after `make clean`):
  ```bash
  make data && uv run pytest tests/unit -q -k "swarm or rf or rid or reports or assessments or planted"
  ```
  → exit 0, 31.0 s wall. Key lines:
  ```text
  kairos-defense gen --seed 42
  incidents 1,878 (≈1,900) · tracks 1,904 (≈1,950) · track_points 560,884 (≈1,000,000, D-030)
  rf_detections 414,999 (≈500,000, D-044) · reports 956 (≈1,000) · assessments 1,876 (≈1,900)
  remote_id 686,263 · swarm incidents 9 · drones flown 1,904 · drones not tracked 0
  live first contact 21:40:06 (21:39:30-21:40:30) · live orbit established T+79 s (T+65-100 s)
  elapsed 19.5 s
  109 passed, 177 deselected in 9.07s
  ```
  Planted items, read back from the written DuckDB files:
  ```text
  reports  R-P1-DELTA-260419-1 security_forces B2 2026-04-20 03:40 UTC (22:40 local):
    "Security forces patrol observed a small drone near the fuel farm at about 21:35, est. 300 ft,
     a flashing white light. A white pickup was parked on County Rd 12 from 21:20 to 22:05 and left
     shortly after the drone flew northwest. The drone departed to the northwest at about 21:46.
     No contact with the operator."
  clue_truth  vehicle white pickup True · road County Rd 12 True · lights True · departure True
  assessments  P1-DELTA-260419 hobbyist, DELTA BDOC, 2026-04-20 14:10 UTC (09:10 local)
  assessment_truth  P1-DELTA-260419 probing
  incidents  S1-GOLF-260503 GOLF 5 tracks swarm history · DEMO-SWARM-ECHO-0614 ECHO 5 tracks swarm live
  ```
  `reports/data_card.md` now has swarm incidents, sensors, reports (sources, counts per actor type,
  delay histogram, styles), clue rates, an assessment confusion table, planted items and live
  timing; figures `reports/figures/swarm_S1.png` and `swarm_S2.png` are new.
  `make check`: ruff clean, 286 passed (4 slow deselected), web lint, typecheck and Vitest pass.
  `pytest tests/slow`: 4 passed in 39 s (full volumes, swarms and paperwork; two full runs give
  identical hashes).
- Figures reviewed by eye: swarm snapshots show line abreast across the heading, the cw quarter turn
  carrying drone 0 to the front, the split, the V apex leading; S2's triangle, expand, ccw half
  turn and trail. Fixed: the pattern-figure legend overlapped the middle panel's axis label (also in
  phase 1's figures).
- Open issues:
  - D-024 (still open): phase 3 must read §9.4's `loiter_dir` as `ccw` when the bearing rate is negative.
  - D-044: RF detections ≈415 k against ≈0.5 M (83%), the same cause as D-030.
  - D-038: RF hears takeoff, so most incidents now start at launch, before the first track point;
    phase 3's no-look-ahead filter compares `start_ts`, which is consistent across flights.
  - D-040: blotter reports are upper case; phase 5's clue extraction must be case-insensitive.
  - D-037: a copycat's Remote ID flights share one serial (same drone); fine for eval, worth knowing.
- Next: phase 3 (features, windows, Euclidean baseline and eval skeleton).

### 2026-10-28 · Phase 1
- Built: `store/ddl.py` (§7.1 and §7.3 DDL, column lists). `sim/`: `world.py` (sites, jittered
  assets, sensors, launch parks, County Rd 12 per D-006/D-031, push-out rule, terrain mask, world
  tables), `calendar.py` (549 nights, hourly weather, base and public events, D-023), `patterns.py`
  (all seven patterns, D-024), `kinematics.py` (timed reference, warp, pauses, batched 10 Hz model,
  D-025), `plan.py`, `actors.py` (hobbyists, P2–P6, C1, C2, D-026), `scenario.py` (six P1 flights,
  live timing helpers), `sensors.py` (radar, D-027), `generate.py` (pipeline, incident ids D-028),
  `writers.py` (the only truth writer, table hashes, D-029), `datacard.py` (data card and figures).
  `kairos-defense gen --seed --config --figures/--no-figures` is real, with a rich summary.
- Tests: `test_world`, `test_calendar`, `test_patterns`, `test_kinematics` (speed, climb and turn
  caps; band ± 15 m; orbit ±10%; warp scales time not shape; no pauses in patterns; batch
  independence; wind drift), `test_actors`, `test_sensors`, `test_scenario` (planted flights, road
  within 250 m, outage, live first contact and orbit windows), `test_generate`, `test_determinism`
  (three-week window twice ⇒ identical SHA-256 per table; extra actor changes no other flight;
  other seed differs), `tests/slow/test_full_generation.py` (full volumes and full determinism).
- Exit check (after `make clean`):
  ```bash
  make data && uv run pytest tests/unit -q -k "world or kinematics or patterns or scenario or determinism"
  ```
  → exit 0, 45.6 s wall. Key lines:
  ```text
  kairos-defense gen --seed 42
  incidents 1,869 (≈1,900) · tracks 1,869 (≈1,950) · track_points 541,913 (≈1,000,000, D-030)
  flights flown 1,869 · flights not detected 0
  live first contact 21:39:51 (21:39:30-21:40:30) · live orbit established T+94 s (T+65-100 s)
  elapsed 23.6 s
  53 passed, 128 deselected in 18.32s
  ```
  `reports/data_card.md`: incidents −1.6% and tracks −4.2% against §8.11 (within ±15%);
  `reports/figures/pattern_{orbit,lawnmower,figure8,perimeter,hover,transit_dips,random_walk}.png`.
  `make check`: ruff clean, 181 passed (3 slow deselected), web lint, typecheck and Vitest pass.
  `make test-all` slow tests: 3 passed in 46 s (full volumes; two full runs give identical hashes).
- Figures reviewed by eye. Fixed: captions collided with tick labels, radar dots hid the true path,
  and the legend overlapped the axis label. Palette: dataviz reference blue and orange, validator passes.
- Open issues:
  - **D-033 (needs a decision):** BRAVO's seeded fuel-farm jitter puts the live orbit at T+94 s, not
    ≈T+80 s. That passes the 65–100 s window, but the T+90 top-3 beat would match on transit only.
    (Resolved in phase 2: option (b), orbit at T+79 s.)
  - D-024: phase 3 must read §9.4's `loiter_dir` as `ccw` when the bearing rate is *negative*.
  - D-028: phase 2 must recompute incident `start_ts`/`end_ts` across radar, RF and Remote ID.
  - D-030: track points ≈0.54 M against ≈1 M in §8.11 (by design; incident and track counts are on target).
  - Phase 0's commit lived on branch `claude/charming-einstein-iyqxsd`, not `main`. This branch
    fast-forwarded onto it, so merging this branch brings phase 0 along.
- Next: phase 2 (swarms, RF, Remote ID, reports and assessments).

### 2026-10-28 · Phase 0
- Built: `pyproject.toml` (uv, src layout, §3 dependencies, script `kairos-defense`), `uv.lock`,
  `.python-version` (3.12), `.nvmrc` (22), `Makefile` (all §5 targets plus `help`), `.gitignore`;
  `config/*.yaml` copied byte-for-byte from §6; `kairos_defense.config` (one pydantic model per file,
  cross-file reference checks, `load_config()`, D-016 to D-018); `ports.py` (§4.1); `rng.py` (§8.9);
  `geo.py` (bearing, wrap180, wrap360, clockwise rotate, rectangle polygon, installation ↔ region ↔
  target frames); `store/guard.py` (`connect_app_db` refuses truth, however spelled); empty `eval/`;
  Typer CLI with 14 stubs that name their phase (D-022). `web/`: Vite 8, React 19.3.1, strict
  TypeScript 6.0, Tailwind 4.3 via `@tailwindcss/vite`, ESLint 10, Prettier 3, Vitest 5, self-hosted
  B612 and B612 Mono; §17.1 tokens in `theme/tokens.css` with Tailwind defaults removed (D-021);
  placeholder Live watch screen with the command bar, idle and truthful ("No replay loaded").
- Tests: `test_config.py` (shipped configs load; 29 invalid variants rejected; YAML 1.2 booleans;
  root-relative paths), `test_geo.py` (cardinals, wrap edge cases incl. −0.0 and 360, clockwise rotation,
  frame round trips), `test_rng.py` (pinned values; same names ⇒ same draws; different names, order or
  seed ⇒ different; adding a component changes nothing else), `test_truth_isolation.py` (§7.6 scan plus
  guard against relative, `..`, symlink and hard-link spellings), `test_cli.py` (help lists all 14
  commands; every stub exits 0 and names its phase). Web: command bar idle/live states, placeholder has
  no numbers, CSS time parsing.
- Exit check:
  ```bash
  uv sync && npm --prefix web install && make check && uv run kairos-defense --help && npm --prefix web run build
  ```
  → exit 0, 12.0 s wall (warm caches). Key lines:
  ```text
  Resolved 101 packages in 2ms
  up to date, audited 254 packages in 607ms · found 0 vulnerabilities
  ruff check: All checks passed! · ruff format --check: 25 files already formatted
  pytest -m "not slow": 89 passed in 2.59s
  web lint: eslint 0 warnings · All matched files use Prettier code style!
  web typecheck: tsc --noEmit clean · Vitest: Test Files 2 passed (2), Tests 5 passed (5)
  kairos-defense --help: gen index models eval match recall forecast replay memory export
                         verify-evidence fetch-models api mcp
  vite build: dist/assets/index-*.css 10.45 kB, index-*.js 222.56 kB (gzip 69.63 kB), built in 422ms
  ```
- Toolchain (cloud, D-015 check): Python 3.12.3, uv 0.11.32, Node 22.22.0, npm 10.9.4. Installed:
  duckdb 2.0.0, lancedb 0.40.0, dtaidistance 2.5.1 (C extension and OpenMP present), numpy 2.5.4,
  pandas 3.1.0, pydantic 2.14.1, typer 0.27.3 (D-019, D-020).
- UI review (pre-installed Playwright, built app, 1920×1080, 1440×900, 1100×800): B612 400/700 and
  B612 Mono load from the bundle; zero external requests; no console errors; no horizontal scroll.
  Fixed: the theater caption left "yet." alone on its own line, so the text is now balanced
  (`text-balance`). Screenshots were not committed; phase 7 sets up `reports/figures/ui/`.
- Open issues: the cloud sandbox prints a `UV_NATIVE_TLS` deprecation warning on every `uv` call. It
  comes from the environment, not the repo, and does no harm. Phase 4 must call `dtw_ndim.distance(...,
  use_c=True)`, because the default is pure Python (D-020).
- Next: phase 1 (world, flights and radar).

### 2026-10-28 · Pre-phase 0 (kit review)
- Built: no code. Kit flattened into the repo root and `git init` (D-001); Node 22 LTS installed (D-002);
  SPEC v1.1 → v1.2 with review fixes D-003 to D-014.
- Exit check: none for this session. Timing simulation of the live P1 flight (§8.3 model, 300 seeded
  wind and altitude draws): first contact 41–50 m outside BRAVO's fence; orbit established 67–94 s after
  contact (p5–p95); on the orbit at T+90 in at least 95% of draws.
- Open issues: confirm the dtaidistance C path on 2.5.1 (D-013); check every pinned library version and API
  against what actually installs (phase 0).
- Next: phase 0.
