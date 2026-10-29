# Phase 8: exit-check evidence

Run on the dev laptop (Apple M4 Max, 16 cores, 128 GB, macOS 26.5.2), 2026-10-29. Servers ran in
the background and were stopped; no server was left running.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| `make eval` demo assertions pass | `make eval; python3 scripts/check_targets.py 8` | pass: every demo row except `swarm_top1` passes, apart from `live_top3_incidents` (accepted gap D-081, listed in `docs/phases/accepted_gaps.json`, printed as WARN); phase 4 and 5 metrics PASS; exit 0 |
| Director mode at 1× through every §1.2 row with times recorded | `make e2e` (`director-1x.spec.ts`) → `reports/figures/ui/director_1x.json` | pass: the table below |
| Screenshots of every beat at both sizes reviewed, fixes logged | `make e2e` (`director.spec.ts`, `pages8.spec.ts`) → `reports/figures/ui/phase08-*` | pass: 18 beat and 12 page screenshots, three review rounds, findings and fixes below and in D-146 |
| Median frame rate ≥ 50 fps on the dev machine | `director_1x.json` | pass: 59.9 fps median (P5 59.9) over the 1× Live watch beats, 1920 × 1080, bloom on, ANGLE Metal |
| Playwright Director at 5×: every beat's key element; axe on every page | `make e2e` | pass: 29 passed in 8.3 min (19 phase 7 + 10 new); axe clean on 9 routes and on Live watch at T+120 |
| Fast and slow tests | `make check`; `make test-all` | pass: 731 fast (710 at the start), 747 in all; Vitest 153 (73 at the start) |
| Contract current | `api --dump-openapi` + `gen:types`, twice | pass: byte-identical |
| `make demo` serves the new pages offline | block below | pass |
| Ledger untouched by the exit check | `uv run kairos-defense memory verify` | pass: chain intact, 4,681 rows (e2e and the demo use scratch ledgers) |

## make eval; python3 scripts/check_targets.py 8
```text
$ make eval
wrote reports/eval_2026-10-29.md and reports/eval_2026-10-29.json
demo assertion failed: live_top3_incidents (2/3 in top 3; P1-DELTA-260419 #1 (1.00, 'Same time
of night'); P1-ALPHA-260303 #2 (1.00, 'Same time of night'); P1-ALPHA-260502 #5 (0.99, 'Same time
of night'))
make: *** [eval] Error 1        <- the gate runs `make eval || echo …`; check_targets judges
$ python3 scripts/check_targets.py 8; echo exit=$?
PASS  Recall@5 at T=120 s (§19.3): 1 (target >= 0.8)
PASS  DTW lift over the Euclidean baseline (§19.3): 0.5217 (target >= 0.1)
PASS  Copycat-first rate (§19.3): 0 (target <= 0.05)
PASS  Prefilter p95 ms (§10.9): 30.3 (target <= 50)
PASS  DTW re-rank of 50 candidates p95 ms (§10.9): 56.51 (target <= 800)
PASS  End-to-end live update p95 ms (§10.9): 124 (target <= 1500)
PASS  Report linkage (§19.3): 1 (target >= 0.7)
PASS  Forecast median error at T=90 s, m (§19.3): 340.4 (target <= 400)
PASS  demo forecast_error_max_m: pass
PASS  demo live_first_contact_local: pass
PASS  demo live_orbit_established_s: pass
PASS  demo live_rank1_report_for: pass
WARN  demo live_top3_incidents: fail      <- accepted gap (accepted_gaps.json; D-081, phase 4 GAPS.md)

All targets met (accepted gaps shown as WARN).
exit=0
$ python3 -c "import json; d=json.load(open('reports/eval_2026-10-29.json')); print(len(d['targets']), [t['key'] for t in d['targets']][:3])"
10 ['recall_at_5_t120', 'dtw_lift', 'copycat_first_t120']
```

"Demo assertions pass" holds apart from `live_top3_incidents`, the accepted phase 4 gap: the live
top 3 at T+90 is DELTA, ALPHA-260303, CHARLIE-260710, and ALPHA-260502 is fifth. Phase 8 changes
no matcher, recall, forecast or metric code, so every number equals phase 7's.

## Director at 1× (director-1x.spec.ts → director_1x.json)

| §1.2 row | Beat | Activated at | Local time | Wall s | Key element visible | Note |
|---|---|---|---|---|---|---|
| T+0 | 1 Detection | T+0 | 21:40:06 | 0.0 | first stream row at T+0 | eval: first point 71 m from the fence, 21:40:06 |
| (T+15) | 2 Recording | T+15 | 21:40:21 | 15.1 | recorder total at T+15 | §17.10 beat, no §1.2 row |
| T+45 | 3 Recognition | T+45 | 21:40:51 | 45.2 | first match entry at T+45 | the matcher ran on 45 s of track |
| T+80 | (during Recognition) | – | – | – | Signals loiter marker at T+87 | eval's §1.2 orbit check: T+79 (D-115 phase rule needs an asset target) |
| T+90 | 4 Time warp | T+90 | 21:41:36 | 90.2 | lens in Warped mode at T+91 (1.5 s hold, then the 1.2 s morph) | top 3 as computed: DELTA, ALPHA-260303, CHARLIE-260710 (D-081) |
| T+105 | 5 Forecast | T+105 | 21:41:51 | 105.0 | zone label at T+105 | "Predicted recovery zone, 2.2 km northwest, from 3 matches" |
| T+120 | 6 Recall | T+120 | 21:42:06 | 120.1 | recall overlay at T+120 | `R-P1-DELTA-260419-1`, white pickup, County Rd 12 in the zone |
| Case Board | 7 Known then and now | → | – | 126.3 | case graph at 126.9 s | → pressed 6 s into the recall beat |
| Evidence | 8 Evidence | → | – | 127.1 | export button at 127.3 s | the export itself needs the human click and confirm (rule 8) |
| Encore | – | – | – | – | – | phase 9 |

Frame rate (requestAnimationFrame over the Live watch beats, 1920 × 1080, bloom on):

```text
overall      frames 7564  median 59.9 fps  P5 59.9 fps
detection    frames  907  median 59.9      P5 59.9
recording    frames 1806  median 59.9      P5 59.9
recognition  frames 2698  median 59.9      P5 59.9
time-warp    frames  891  median 59.9      P5 59.9
forecast     frames  902  median 59.9      P5 59.9
recall       frames  361  median 59.9      P5 59.5
renderer     ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Max, Unspecified Version)  hardware: true
browser      chromium 156.0.8078.4; cpu Apple M4 Max, 16 cores, 128 GB; darwin 25.5.0 (macOS 26.5.2)
```

The full `make e2e` run sampled frames only until the recall overlay appeared. The spec now
samples 6 s more, and the table above is from that rerun: `npx playwright test
e2e/director-1x.spec.ts`, 1 passed in 2.2 min. Both runs gave the same beat times and 59.9 fps.

## Screenshot review (§17.13)

18 beat screenshots (`phase08-beat-NN-<beat>-<w>x<h>.png`, beat 7 twice: known then and known
now) and 12 page screenshots (`phase08-page-<page>-<w>x<h>.png`), at 1920 × 1080 and 1440 × 900.
Each was opened and checked for alignment, overlap, contrast, glow restraint, and legibility at
three meters.

Round 1 (all beats at 1440 × 900), found and fixed:
1. Film grain visibly speckled the theater (3%): now ±0.3%.
2. Space did not pause: a clicked speed button kept focus and took Space. D now drops focus, and
   the e2e key presses blur first.
3. Only one and a half match entries were visible: the incident id moved to the tooltip and
   screen-reader text, and the chips and buttons were tightened.
4. The lens controls wrapped and the cost matrix was cut: shorter channel names, narrower
   selects and a measured height budget.
5. The recall overlay covered the zone and its road: the forecast shot now shifts the content
   right and up (D-134).
6. Ghost labels overprinted at the recovery points: stacked 16 px apart.
7. The case graph was cramped and its labels overlapped: longer links, stronger repulsion and a
   58 px collide radius.
8. Two proposals for the same incident were indistinguishable: rank and rerun second shown.
9. The page caption covered the Case board's decisions and the Evidence results: pages pad
   their bottom while a page beat's caption shows.
10. The self-match arc (Bravo, Nov 14) had no date: one label per base, name and dates.

Round 2 (both sizes), found and fixed:

11. The ghosts went dark after the top-3 set changed at T+105. Every 4 Hz re-render rebuilt each
    `Line2` after its dissolve had finished; mapped specs are now cached (D-128).
12. The zone label collided with a ghost label: it now sits east of the zone.
13. Constellation names and dates collided: one line per base, and the panel stretches up to
    2.5 times east-west.
14. The recall beam was faint and drawn under the overlay: it is now above it, at 1.6 px.

Pages, found and fixed:

15. The explainer drew tonight's path at 45% opacity: now full.
16. The Eval recall chart clipped its direct label, and the histogram's rule labels collided: a
    wider margin and a key above the chart.

Accessibility, found by the new axe run on Live watch at T+120:

17. The Stream's scrolling list was not keyboard-reachable (`scrollable-region-focusable`): it
    is now a focusable, named region that pauses while focused.

Round 3 shows the time-warp beat with three amber ghosts and labels stacked at the zone. The
forecast beat shows the dotted path and zone with its label clear. The recall beat shows the
report at the lower left with the bone beam from "County Rd 12" to the road inside the zone. The
Case board graph is readable; Known then shows only "hobbyist" and no links. Known now shows
dashed proposals. The page beats keep their controls clear of the caption.

Left as is (recorded in REPORT.md):
- At 1440 × 900 the third match entry's buttons are just below the fold of the scrolling list.
- "No Remote ID" can overlap the "Fuel farm" label in the close forecast shot (phase 7 element).
- The zone label can reach the theater's right edge at 1440 × 900.

## make e2e
```text
$ make e2e
npm --prefix web run build      ✓ built (lazy pages: LiveWatch 72 kB + vendor-3d 1.2 MB, CaseBoard
                                  66 kB, Eval 13 kB, MatchExplainer 10 kB, Evidence 7 kB, …)
kairos-defense replay --precompute
npm --prefix web run e2e
  ✓   1 director-1x.spec.ts › Director at 1x through every §1.2 row (2.0m)
  ✓   2 director.spec.ts › Director at 5x shows every beat's key element at 1440x900 (45.7s)
  ✓   3 director.spec.ts › Director at 5x shows every beat's key element at 1920x1080 (45.7s)
  ✓   4 director.spec.ts › Director never commits by itself (27.8s)
  ✓   5 director.spec.ts › Director keys and modes: ←, Space, M, Performance mode, R (27.9s)
  ✓   6 lens.spec.ts › lens connectors follow the DTW path (27.1s)   (+ axe at T+120)
  ✓   7-11 live.spec.ts (5 tests, phase 7)
  ✓  12-20 pages.spec.ts › axe and the command bar on /live/…, /explainer, /explainer?incident=…
                          &at=90&track=P1-DELTA-260419-T1, /cases, /cases/CASE-P1-DELTA-260419,
                          /swarm, /evidence, /delta, /eval
  ✓  21-24 pages.spec.ts › root, layout at 1440 x 900, stacking below 1280 px, shortcuts
  ✓  25 pages8.spec.ts › phase 8 pages at 1920x1080 (31.7s)
  ✓  26 pages8.spec.ts › phase 8 pages at 1440x900 (31.6s)
  ✓  27 perf.spec.ts › frame rate over 10 s of 1x playback (12.6s)
  ✓  28-29 screens.spec.ts › screenshots at 1920x1080 and 1440x900 (phase 7 moments)
  29 passed (8.3m)
exit=0
```

## make check; make test-all
```text
$ make check
uv run ruff check .                    All checks passed!
uv run ruff format --check .           206 files already formatted
uv run pytest -m "not slow" -q         731 passed, 16 deselected in 37.12s
npm --prefix web run check             eslint, prettier, tsc clean; types.gen.ts is current;
                                       Test Files 35 passed (35), Tests 153 passed (153)
$ make test-all
747 passed in 231.60s (0:03:51)
```

## make demo (background, stopped)
```text
$ make demo > /tmp/kd-p8/demo.log 2>&1 &
$ curl -sf --retry 300 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/api/health
{"status":"ok","version":"0.0.1","live_incidents":["DEMO-BRAVO-0828","DEMO-SWARM-ECHO-0614"],
 "matching":true,"problems":[],"ledger_rows":4681,"ledger_head_seq":4681}
$ curl -s http://127.0.0.1:8000/api/cases
[{"case_id":"CASE-P1-DELTA-260419","founder":"P1-DELTA-260419","base":"DELTA","status":"closed",
  "opened_at":"2026-04-20T14:10:00.000000Z","members":["P1-DELTA-260419"],"pending":0,
  "contradictions":0,"claims":["hobbyist"],"last_decision":"close","exports":0}]
$ curl -s ".../api/explain/DEMO-BRAVO-0828/P1-DELTA-260419-T1?at=90"   (t_s, score, logit, rows, …)
explain 90 0.999625 7.8894 7 91 {'start_s': 90, 'end_s': 150}
        {'start_s': 116, 'end_s': 184, 'value': 0.6655781119889205}
$ curl -s http://127.0.0.1:8000/api/eval/latest            (file, number of targets)
eval eval_2026-10-29.json targets 10
$ for p in /live/DEMO-BRAVO-0828 /cases /cases/CASE-P1-DELTA-260419 /evidence /delta /eval \
           "/explainer?incident=DEMO-BRAVO-0828&at=90"; do curl -s -o /dev/null -w "%{http_code} $p\n" …; done
200 /live/DEMO-BRAVO-0828
200 /cases
200 /cases/CASE-P1-DELTA-260419
200 /evidence
200 /delta
200 /eval
200 /explainer?incident=DEMO-BRAVO-0828&at=90
$ pkill -f "kairos-defense api --static web/dist"; lsof -nP -iTCP:8000 -sTCP:LISTEN || echo "port 8000 free"
port 8000 free
```

`GET /api/evidence` on the real `exports/` listed the package an earlier phase's exit check left
there (`CASE-P1-DELTA-260419_20260829T024136`). Phase 8's e2e exports go to
`data/cache/e2e/exports` (D-137).

## Contract and ledger
```text
$ uv run kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types
wrote web/openapi.json (25 paths)
$ (again, then) cmp web/openapi.json <first> && cmp web/src/api/types.gen.ts <first>
regenerated contract byte-identical
$ uv run kairos-defense memory verify
chain intact: 4,681 rows in data/memory.duckdb, head seq 4,681 hash a361b4bfe3b2…
```
