# Phase 11: Live mode MVP (simulated sensor feed, live matching, scenarios), report

Status: done (the gate decides: `scripts/cloud_gate.py gate 11`) · Date: 2026-11-02 · Commits:
`ea8e98d` (plan), `688d757` (review 1 and revision), `6c90192` (review 2, approved), `553e495`
and `f08e9fc` (checkpoints), and `phase 11: live mode MVP …`

## Summary

Kairos Defense now runs live, not only as a replay (`docs/phases/PHASE_11.md`, D-169, D-170):

- `kairos-defense simulate` is a separate process that flies new flights with the generator's own
  code on a live calendar after the 18-month history and streams **only sensor detections** into
  the app through a versioned ingest contract (`/ws/ingest`, `POST /api/ingest`): the seam a real
  radar, RF or Remote ID adapter would implement.
- The app forms incidents itself, reruns the existing matcher, forecast and report recall every
  5 s of feed time on what it has received (the swarm matcher for swarms), learns every closed
  incident so the next live flight can match it, and records incidents and proposals in the case
  memory, with the models already trained.
- A Live page launches the five scenarios, shows the theater and rails fed by the live stream, and
  after an incident closes, **Reveal who flew** names the operator and the matcher's verdict,
  computed by `kairos_defense.eval` and never stored.
- `kairos-defense live check` flies all five scenarios headless at 50× and scores them with the
  same function: all five pass at 50× (returning prober, copycat, hobbyist, swarm repeat, new operator twice), 335 s in all.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Simulator | Five scenarios from the generator's functions; the persisted live clock and deterministic seeds; the feed client (scaled clock, heartbeats to the close, reconnects); truth rows through the sim writer | `sim/live_scenarios.py`, `sim/live_clock.py`, `sim/live_feed.py`, `sim/writers.py`, `cli_live_mode.py` (`simulate`) |
| Ingest contract | `point`, `rf`, `rid`, `heartbeat` v1; schema checks, then the app's own checks (installation, sensor, after the history, lateness) | `api/schemas_ingest.py`, `api/routes_live.py`, `live/feed.py` |
| Live incidents | Join within 10 s and 300 m; swarm at three tracks; close after 30 s of feed time without a detection (radar, RF or Remote ID) | `live/incidents.py` |
| Live hub and worker | Writes, stream fan-out and catch-up per installation, rerun and close queue; reruns fresh first then backfilled, every one recorded; proposals as in the replay | `live/feed.py`, `live/runner.py`, `live/loop.py` (`compute_result`), `live/session.py` (`propose`, `result_messages`) |
| Learning | Closed incidents become history through the ports with the index build's own per-track code | `live/learn.py`, `features/build.py` (`track_rows`) |
| Stores | The live-mode folder (feed database, vectors, clock, logs); history plus learned live history behind the same ports | `store/live_feed.py`, `store/composite.py`, `ports.py` (`LiveFeed`) |
| API | Ingest, the live stream, status, scenarios, reset, launch (a separate process, one at a time), the reveal, the live schema route | `api/routes_live.py`, `api/schemas_live.py`, `api/launcher.py`, `api/live_services.py` |
| Evaluation | The reveal (the only reader of live truth) and `live check` | `eval/reveal.py`, `eval/live_check.py` |
| Web | The Live page: launcher, matches or swarm matches, incidents with Reveal and Reset, the reveal card, the command bar's live mode; the theater's own Suspense boundary | `web/src/pages/LiveMode.tsx`, `web/src/live/*`, `web/src/state/liveStore.ts`, `liveDispatch.ts`, `useLive.ts`, `web/src/api/liveStream.ts`, `web/src/three/TheaterFrame.tsx` |
| Make | `make live`, `make live-check` | `Makefile` |

## Decisions and deviations from SPEC

D-171 to D-186 in `docs/DECISIONS.md`: how this session runs (D-171), the live-mode stores
(D-172), the ingest contract (D-173), incident formation and closing, including RF and Remote ID as
activity after a radar dropout split a flight in the first browser run (D-174), the fresh-first
worker after a plain queue left the Matches panel empty at 20× (D-175), learning (D-176), the live
clock and deterministic seeds (D-177), the scenarios and the invented operator (`FAM-24`, not the
plan's `FAM-40`, which the RF band model does not know) (D-178), live ground truth (D-179),
expectations (D-180), the case memory (D-181), the launcher keeping who flew out of every app log
(D-182), `live check` (D-183), the live stream and page (D-184), the theater's own Suspense
boundary, which fixed a baseline e2e failure in this container (D-185), and fast live tests
(D-186).

Deviation from the block: the command bar has no separate Replay or Live switch; the Live page is
reached from the Pages menu and puts the command bar in its live mode (D-184).

## Tests

- New Python tests (fast): `test_sim_live.py`, `test_live_clock.py`, `test_feed_client.py`,
  `test_ingest_schema.py`, `test_live_incidents.py`, `test_live_stores.py`, `test_live_hub.py`,
  `test_live_learning.py`, `test_live_reset.py`, `test_api_live.py`, `test_api_live_contract.py`,
  `test_eval_reveal.py`, `test_cli_live_mode.py`; `test_truth_isolation.py` now also forbids
  `live_truth` outside `eval/` and `sim/writers.py`. Slow: `tests/slow/test_full_live_mode.py`.
- Fast Python tests: 913 pass (803 at the start of the phase); 19 slow.
- Vitest: 184 (169): `liveStore.test.ts`, `LiveMode.test.tsx`, `router.test.ts`.
- Playwright: `e2e/livemode.spec.ts` (launch at 20×, incident, matches, close, reveal; axe); 35 e2e tests pass (34 before). No skip or xfail marker was added.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| `make check` | pass | ruff clean; 913 fast Python tests; web lint, typecheck, types current, Vitest 184 |
| `live check --scenarios all --speed 50` | pass | 5 of 5 PASS in 335 s; per-scenario ranks in EXIT_CHECK.md |
| `make e2e` | pass | 35 passed in 15.5 min; axe clean on the Live page with an incident open |

## Metrics

| Scenario | Expectation | Observed (seed) |
|---|---|---|
| returning-prober | P1 history flight in the top 3 by T+120 s | rank 1 from T+45 s (1101) |
| copycat | C1 flight in the top 5 above every P1 flight by T+120 s | C1 rank 1, no P1 in the top 10 (1102) |
| hobbyist | none (calibration) | top score 1.0 at T+475 s (1103) |
| swarm-repeat | the team's past event first | S1's `ECHO-260806-2049` first (1104) |
| new-operator-twice | flight 2 ranks flight 1, learned live, first | yes; flight 1 had no N1 history (1105) |

Timing in this container: a rerun (matcher over history plus learned live history, forecast,
recall, lens) takes about 0.7 s; a 50× scenario takes 26 to 108 s including every rerun and the
close.

The §19 history metrics are unchanged: no matcher, model, index or evaluation code changed its
results (the extracted `compute_result`, `track_rows` and `match_flight` give identical output).

## Known issues and follow-ups

- Any RF or Remote ID heard at an installation keeps every open incident there alive (RF is not
  tied to a track at ingest, D-174); with concurrent flights at one installation an incident may
  close later than its own drone left.
- Live swarms are matched but their choreography is not learned (D-176); a second live swarm
  cannot match the first.
- The fusion model scores near 1.0 for many live matches (its coefficients are large); the
  ranking is what the expectations score.
- A rerun takes about 0.7 s in this container; at 20× and 50× the screen shows the newest rerun
  and the skipped ones are filled in after the flight (D-175).
- Phase 12 adds the DTW workbench and the full live-mode guide with screenshots.

## How to debug this phase

- Run the API with a scratch folder: `uv run kairos-defense api --static web/dist --port 8001
  --live-mode-dir data/cache/try/live_mode`, open `/live`, launch, and watch
  `GET /api/live/status` (`pending` is the worker queue).
- A launched simulator's output is in `<live_mode>/sim/<n>.log` (seed, times, counts; never the
  actor). Run `uv run kairos-defense simulate --scenario … --dry-run --show-actor` in a terminal
  to see what a seed flies.
- `uv run kairos-defense live check --scenarios returning-prober --speed 50` reproduces one
  scenario (scratch stores under `data/cache/live_check/`).
- The live-mode database is a plain DuckDB file: `live_incidents`, `live_tracks`, `live_results`
  (the matches each rerun showed) and the learned `track_signatures`.
- Likely failure points: a locked truth file (the simulator and the reveal retry for 10 s), a
  stale web build (`npm --prefix web run build`), and the regenerated OpenAPI types after a schema
  change (`kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types`).

## Fix attempts
