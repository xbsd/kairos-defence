# Phase 9: exit-check evidence

Run in the Claude Code cloud container (4 vCPU Intel Xeon @ 2.80 GHz, 15 GB, Ubuntu 24.04, no GPU:
Chromium renders WebGL with SwiftShader), 2026-10-29. Servers ran in the background with a time
limit and were stopped; no server was left running. `make check` ran with the default temp folder:
the CLI no longer hard-wraps messages, so no test depends on the temp path's length (D-156).

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Rebuild from scratch | `make clean && make data index models eval` | pass: 1,878 incidents (9 swarms); 1,898 history tracks and 8 history swarms indexed (8 detected, 4,636 `swarm_features` rows); models trained; eval written; 7 min 18 s |
| Serve offline | `make demo` (background, 300 s limit) + curl | pass: health ok, both live incidents, matching on; `/api/swarm/DEMO-SWARM-ECHO-0614` ranks S1-GOLF-260503 first; chat disabled by default; every page route 200; server stopped, port free |
| `make e2e` | `make e2e` | pass: 31 passed in 11.9 min (29 phase 7–8 tests + 2 Swarm view tests; the Director spec now reaches the encore); axe clean on every route, `/swarm` included |
| All §19 targets met (or approved gaps) | `python3 scripts/check_targets.py 9` | pass: exit 0; every §19.3 target PASS (swarm top-1 1.000, time to match 96%); WARN only for the accepted `live_top3_incidents` row and the report-only prefilter latency |
| The encore works | `director.spec.ts` encore step, `swarm.spec.ts` | pass: Director at 5× reaches beat 9 at 1440 × 900 and 1920 × 1080 with `swarm-ghost` visible and the computed caption "Same choreography, six weeks apart, in another region: Golf on May 3 and Echo on Jun 14."; the ledger head does not move; `swarm.spec.ts` (top match S1-GOLF-260503, ghost, curves, Play advances) passes at both sizes |
| An MCP client lists the tools (`make mcp`) | `timeout 120 uv run python -m kairos_defense.agent.probe -- make mcp`; `--allow-proposals` variant; `uv run pytest tests -q -k mcp` | pass: six read-only tools from `make mcp`, eight with `--allow-proposals`; MCP tests pass |
| `docs/DEMO.md` complete | headings and every command resolves via `--help` | pass: every Appendix B section present; every `kairos-defense` command and `make` target in it resolves |
| Definition of done (§21) | `make check`; `make test-all` | pass: `make check` 795 fast Python tests (731 at the start), Vitest 168 (153); slow tests 17 passed (`make test-all` equivalent), `test_full_mcp.py` 1 passed |

Note: `make clean && make data index models eval && make demo` as one line stops at `make eval`,
which exits 1 on the accepted `live_top3_incidents` row (the §19.4 gate fails on any failed demo
row; D-081, phase 4 `GAPS.md`). `make demo` therefore ran as its own step, and
`check_targets.py 9` judged the targets (PLAN_REVIEW-1 suggestion).

## make clean && make data index models eval (then check_targets.py 9)
```text
$ make clean && make data index models
│ incidents              │    1,878 │            ≈1,900 │
│ swarm incidents        │        9 │                   │
│ live first contact     │ 21:40:06 │ 21:39:30-21:40:30 │
│ live orbit established │   T+79 s │        T+65-100 s │
│ elapsed                │   26.0 s │                   │
│ elapsed                            │                                         39.0 s + reports 0.4 s │
│ history tracks indexed             │                                                          1,898 │
│ flight_windows 60 s                │                                                         57,462 │
│ flight_windows 120 s               │                                                         51,297 │
│ flight_windows 300 s               │                                                         27,507 │
│ swarm incidents indexed (detected) │                               8 (8); swarm_features rows 4,636 │
wrote track_features, track_signatures and report_clues to /home/user/kairos-defence/data/kairos_defense.duckdb, flight_windows and reports to /home/user/kairos-defence/data/lancedb
rebuild exit 0
$ make eval
│ Recall@5 at T=120 s                             │                                                              1.000 │
│ DTW lift                                        │                                                              0.522 │
│ time to match (top 3 by T=90 s)                 │                                                                96% │
│ copycat-first at T=120 s                        │                                                                 0% │
│ report linkage (T=120 s, top 3, k=5)            │                                                   1.000 (65 of 65) │
│ forecast error T=90 s median / P80              │                                                        341 / 495 m │
│ swarm top-1, whole flight (4 answerable)        │                                                              1.000 │
│ latency prefilter p50 / p95                     │                                                       128 / 164 ms │
│ latency dtw p50 / p95                           │                                                       141 / 249 ms │
│ latency end to end p50 / p95                    │                                                       472 / 649 ms │
│ latency swarm p50 / p95                         │                                                       217 / 252 ms │
│ demo live_first_contact_local                   │                                               pass: 21:40:06, 71 m │
│ demo live_orbit_established_s                   │                                                       pass: T+79 s │
│ demo live_top3_incidents                        │        fail: 2/3 in top 3; P1-DELTA-260419 #1 (1.00, 'Same time of │
│ demo live_rank1_report_for                      │   pass: R-P1-DELTA-260419-1 rank 1 of 1 for P1-DELTA-260419 (match │
│ demo forecast_error_max_m                       │                pass: 139 m (radius 370 m; analogs P1-ALPHA-260303, │
│ demo swarm_top1                                 │  pass: #1 S1-GOLF-260503 (0.476, pace 0.75); #2 JULIET-260511-0024 │
demo assertion failed: live_top3_incidents (2/3 in top 3; …)   <- the accepted gap (D-081)
latency_end_to_end_p95_ms: 649 vs baseline 122.3              <- this machine is slower; report only (D-060)
make: *** [Makefile:40: eval] Error 1
$ python3 scripts/check_targets.py 9
PASS  Recall@5 at T=120 s (§19.3): 1 (target >= 0.8)
PASS  DTW lift over the Euclidean baseline (§19.3): 0.5217 (target >= 0.1)
PASS  Copycat-first rate (§19.3): 0 (target <= 0.05)
WARN  Prefilter p95 ms (§10.9): 164.1 (target <= 50)
PASS  DTW re-rank of 50 candidates p95 ms (§10.9): 248.9 (target <= 800)
PASS  End-to-end live update p95 ms (§10.9): 649 (target <= 1500)
PASS  Report linkage (§19.3): 1 (target >= 0.7)
PASS  Forecast median error at T=90 s, m (§19.3): 340.5 (target <= 400)
PASS  Time to match: top 3 by T=90 s (§19.3): 0.9565 (target >= 0.7)
PASS  Swarm top-1 (§19.3): 1 (target >= 0.8)
PASS  demo forecast_error_max_m: pass
PASS  demo live_first_contact_local: pass
PASS  demo live_orbit_established_s: pass
PASS  demo live_rank1_report_for: pass
WARN  demo live_top3_incidents: fail
PASS  demo swarm_top1: pass

All targets met (accepted gaps shown as WARN).
targets exit 0
```

The latency WARN is this container (LanceDB prefilter p95 164 ms here, 30 ms on the laptop); §10.9 latency is report only (D-060). `make eval` exits 1 on the accepted demo row, as in phases 4 to 8.

## make demo (background, stopped)
```text
== GET /api/health
{
    "status": "ok",
    "version": "0.0.1",
    "live_incidents": [
        "DEMO-BRAVO-0828",
        "DEMO-SWARM-ECHO-0614"
    ],
    "matching": true,
    "problems": [],
    "ledger_rows": 4681,
    "ledger_head_seq": 4681
}
== GET /api/swarm/DEMO-SWARM-ECHO-0614 (top 3)
observed_s 820 detected True drones 5
1 S1-GOLF-260503 GOLF similarity 0.475884 pace 0.75
2 JULIET-260511-0024 JULIET similarity 0.426491 pace 0.6342
3 KILO-250603-0041 KILO similarity 0.424576 pace 0.7574
aligned rows 812 elapsed_ms 386.6
== GET /api/swarms
[('HOTEL-260829-0036', 'history'), ('ECHO-260806-2049', 'history'), ('DEMO-SWARM-ECHO-0614', 'live')]
== GET /api/chat/status
{"enabled":false,"provider":"none","model":"","tools":["find_similar_flights","recall_reports","forecast_recovery","as_of_view","diff_case","shift_delta"],"problem":null}
== page routes
200 /
200 /live/DEMO-BRAVO-0828
200 /swarm
200 /swarm?incident=DEMO-SWARM-ECHO-0614
200 /cases
200 /evidence
200 /delta
200 /eval
200 /explainer
== GET /api/eval/latest swarm_top1
1.0 ['pass']
server stopped; port 8000 free
```

## An MCP client lists the tools (`make mcp`)
```text
$ timeout 120 uv run python -m kairos_defense.agent.probe -- make mcp
find_similar_flights
recall_reports
forecast_recovery
as_of_view
diff_case
shift_delta
6 tools from `make mcp`
(exit 0)
$ timeout 120 uv run python -m kairos_defense.agent.probe --expect 8 -- uv run kairos-defense mcp --allow-proposals
find_similar_flights
recall_reports
forecast_recovery
as_of_view
diff_case
shift_delta
propose_link
propose_evidence_export
8 tools from `uv run kairos-defense mcp --allow-proposals`
(exit 0)
```
`uv run pytest tests -q -k mcp` selects `test_mcp.py` (8), `tests/slow/test_full_mcp.py` (1, drives `make mcp` itself through the probe) and the `mcp` CLI test in `test_cli.py`: `10 passed, 803 deselected in 20.15s`.

## docs/DEMO.md complete
```text
sections: Before the audience arrives; Director keys; Script (about four minutes); Fallbacks; Optional: the agent tools (MCP); Likely questions; Checklist
Appendix B sections present: True
kairos-defense memory reseed --help -> exit 0
kairos-defense memory verify --help -> exit 0
kairos-defense replay --help -> exit 0
kairos-defense api --help -> exit 0
kairos-defense mcp --help -> exit 0
replay --reset documented in --help: True
replay --precompute documented in --help: True
mcp --allow-proposals documented in --help: True
make clean: target exists
make data: target exists
make demo: target exists
make eval: target exists
make mcp: target exists
python -m kairos_defense.agent.probe --help -> exit 0
```

## make e2e
```text
$ make e2e
  ✓   1 [chromium] › e2e/director-1x.spec.ts:48:1 › Director at 1x through every §1.2 row (2.3m)
  ✓   2 [chromium] › e2e/director.spec.ts:40:3 › Director at 5x shows every beat's key element at 1440x900 (1.1m)
  ✓   3 [chromium] › e2e/director.spec.ts:40:3 › Director at 5x shows every beat's key element at 1920x1080 (1.1m)
  ✓   4 [chromium] › e2e/director.spec.ts:144:1 › Director never commits by itself (33.6s)
  ✓   5 [chromium] › e2e/director.spec.ts:162:1 › Director keys and modes: ←, Space, M, Performance mode, R (44.4s)
  ✓   6 [chromium] › e2e/lens.spec.ts:8:1 › lens connectors follow the DTW path (44.9s)
  ✓   7 [chromium] › e2e/live.spec.ts:8:1 › streams real data at 5x (9.7s)
  ✓   8 [chromium] › e2e/live.spec.ts:25:1 › matches appear by T+90 and the ledger gains a block (27.2s)
  ✓   9 [chromium] › e2e/live.spec.ts:49:1 › approve link adds a block and turns the ring verified (18.5s)
  ✓  10 [chromium] › e2e/live.spec.ts:71:3 › reduce motion › reduce motion keeps the data (7.0s)
  ✓  11 [chromium] › e2e/live.spec.ts:83:1 › no request leaves the origin (16.6s)
  ✓  12 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /live/DEMO-BRAVO-0828 (6.9s)
  ✓  13 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /explainer (2.2s)
  ✓  14 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /explainer?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1 (2.3s)
  ✓  15 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /cases (1.5s)
  ✓  16 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /cases/CASE-P1-DELTA-260419 (1.9s)
  ✓  17 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /swarm (1.6s)
  ✓  18 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /evidence (1.3s)
  ✓  19 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /delta (1.9s)
  ✓  20 [chromium] › e2e/pages.spec.ts:31:3 › axe and the command bar on /eval (1.8s)
  ✓  21 [chromium] › e2e/pages.spec.ts:52:1 › the root opens Live watch for the live incident (213ms)
  ✓  22 [chromium] › e2e/pages.spec.ts:57:1 › layout holds at 1440 x 900 (5.0s)
  ✓  23 [chromium] › e2e/pages.spec.ts:70:1 › rails stack under the theater below 1280 px (6.2s)
  ✓  24 [chromium] › e2e/pages.spec.ts:86:1 › shortcuts dialog lists M and closes with Escape (601ms)
  ✓  25 [chromium] › e2e/pages8.spec.ts:29:3 › phase 8 pages at 1920x1080 (41.0s)
  ✓  26 [chromium] › e2e/pages8.spec.ts:29:3 › phase 8 pages at 1440x900 (40.0s)
  ✓  27 [chromium] › e2e/perf.spec.ts:10:1 › frame rate over 10 s of 1x playback (19.5s)
  ✓  28 [chromium] › e2e/screens.spec.ts:20:3 › screenshots at 1920x1080 (44.2s)
  ✓  29 [chromium] › e2e/screens.spec.ts:20:3 › screenshots at 1440x900 (41.7s)
  ✓  30 [chromium] › e2e/swarm.spec.ts:23:3 › Swarm view at 1440x900 (8.3s)
  ✓  31 [chromium] › e2e/swarm.spec.ts:23:3 › Swarm view at 1920x1080 (9.0s)
  31 passed (11.9m)
```

Screenshots reviewed (§17.13): `reports/figures/ui/phase09-swarm-1920x1080.png`,
`phase09-swarm-1440x900.png`, `phase08-beat-09-encore-1920x1080.png` and `-1440x900.png`. The web
helper's review found and fixed seven issues (D-160); the main session's review of the final images
found the formations, ghost, edges, curves, labels and caption legible at both sizes, with one
note left as is: the ghost's "Golf · May 3" label can touch the centroid trail.

Frame rate: not re-measured here (SwiftShader, no GPU; `director_1x.json` records the software
renderer). The laptop's 59.9 fps median at phase 8 stands until re-measured there (D-148).
