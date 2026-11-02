# Phase 11 — Live mode MVP: a simulated sensor feed, live matching, scenarios

Added 2026-11-02 at the user's request (D-169). It plays the role of a SPEC §20 phase block: the
`phase-auto` skill and the plan reviewer read this file for N = 11. Edited by humans only.

**Goal.** Turn the replay demo into a live system, MVP style. A simulated sensor network flies new,
never-seen flights in real time (optionally sped up) and pushes detections into the app through an
ingest interface that a real sensor adapter could use later; the app incidents, matches, forecasts,
recalls and remembers them live, with the models already trained (no retraining). A presenter
launches scenarios from the UI and watches the system recognize them. Simplicity wins over
completeness: no user accounts, no auth, one installation watched at a time is enough.

**Read first.** CLAUDE.md (all rules still hold), SPEC §1, §4, §7, §8 (the generator you will reuse),
§9, §10, §11.3, §14, §15.6, §16, §17.2 to §17.4, `docs/phases/phase-07/REPORT.md`,
`docs/phases/phase-09/REPORT.md`, `src/kairos_defense/live/README.md`, `src/kairos_defense/sim/README.md`,
`src/kairos_defense/match/README.md`, `src/kairos_defense/api/README.md`, `web/README.md`, D-063.

## Design constraints

- **Two processes, like real life.** The simulator (`kairos-defense simulate`) is a separate process:
  it plans and flies flights with the existing `sim` functions (`actors.make_flight`, `kinematics.fly`,
  `sensors.radar_track`, `rf_track`, `rid_track`, the swarm choreography) and streams **only sensor
  detections** (the columns of `track_points`, `rf_detections`, `remote_id`, plus a sensor track id)
  to the app. It never sends the actor. The app never learns who flew (rule 2). The simulator writes
  ground truth for its flights only through the sim writer path into `data/truth.duckdb` (a
  `live_truth` table), and prints the actor in its own terminal so a presenter can reveal it.
- **Ingest interface (the sensor adapter contract).** A documented, versioned message schema
  (pydantic, in `api/schemas*.py`): `point`, `rf`, `rid` and `heartbeat`, accepted on a WebSocket
  `/ws/ingest` (and a REST `POST /api/ingest` batch for simple adapters). Validate and reject bad
  messages with a reason. This is the seam a real radar, RF or Remote ID adapter would implement.
- **Live incidents.** The app forms incidents from incoming tracks itself: an incident opens at a
  track's first detection at an installation and closes after `live.idle_close_s` (add to
  `config/scoring.yaml`, default 30 s) without detections. Tracks that overlap in time and space at
  one installation (the swarm rules in `scoring.yaml`) form one swarm incident.
- **Live matching on unseen data.** Every `live.rerun_every_s` of feed time (5 s) from
  `live.min_track_s` (45 s), build the query from the points received so far (`match.query.query_at`)
  and run the existing `DtwMatcher`, forecast and report recall; swarms use the phase 9 swarm
  matcher. Nothing is precomputed. Use the existing models in `models/`; no retraining.
- **The live clock and no look-ahead.** Live flights are stamped on a live calendar that starts
  after the last history night (default the first night after `calendar.end_local`, 21:00 local)
  and only moves forward across scenarios (persist it). So every history flight started before
  every live flight (rule 3). `--speed` (1 to 50, default 1) scales the simulator's clock; the app
  runs on the timestamps it receives.
- **Live memory.** When a live incident closes, it becomes history: its features, signature and
  window vectors are computed with the existing feature code and added through the ports
  (`TrackStore`, `VectorStore`) so the next live flight can match it, and its incident and the
  matcher's proposals are recorded in the case memory as for the demo (humans approve, rule 8).
  Keep live-generated rows separable (a `source = 'live'` marker or separate tables/stores) so
  `kairos-defense live reset` removes all of them, and the 18-month history, the evaluation and the
  demo replay are never changed by live use.
- **The replay demo keeps working** exactly as before (Director mode, `DEMO-BRAVO-0828`, the encore).

## Scenarios

Each scenario is a named recipe the simulator flies (CLI `kairos-defense simulate --scenario <name>
--base <ID> [--actor <id>] [--speed N] [--seed N]`, and the UI launcher). The seed is printed and
recorded; the same seed flies the same flight.

| Scenario | What flies | Expected outcome (scored by `live check`) |
|---|---|---|
| `returning-prober` | A known prober (`--actor`, default P1; P1 to P6) flies its pattern again at `--base` | A same-actor history flight in the top 3 by T+120 s |
| `copycat` | C1 (mimics P1's orbit, different RF and launch) | A same-actor (C1) history flight in the top 5 by T+120 s, ranked above every P1 flight |
| `hobbyist` | A random hobbyist flight | No expectation on identity; report the top score (a calibration view) |
| `swarm-repeat` | A swarm team (`--actor`, default S1; S1 or S2) flies its choreography at `--base` | The same team's past swarm event ranked first |
| `new-operator-twice` | An invented operator (a fixed, seeded pattern, RF family and launch offset not used by any actor) flies at `--base`, then at a second base | First flight: no same-actor history exists (report it). Second flight: the first flight, learned live minutes earlier, is ranked first |

## Tasks

- [ ] `sim/live.py` (or similar): build one scenario's flights from the existing generator functions
  with an explicit seed; turn them into time-ordered detections; a feed client that sends them to
  `/ws/ingest` on the live clock × speed, with reconnect and a clean stop. CLI `simulate`.
- [ ] `live/` ingest and live sessions: incident formation and closing, the per-installation live
  loop (rerun schedule on feed time, matcher, forecast, recall, swarm), learning closed incidents into
  history, recording into the `live_*` tables and the case memory. Keep modules under ~400 lines.
- [ ] API: `/ws/ingest`, `POST /api/ingest`, a live stream `/ws/live/{installation_id}` that sends the
  §16.3 message types the Live watch components already understand (plus `incident_opened` and
  `incident_closed`), `GET /api/live/status`, `POST /api/live/reset`, and `POST /api/sim/launch`,
  which starts the simulator **as a separate process** for a scenario (the API never imports truth).
  Regenerate the OpenAPI types (§16.5).
- [ ] Web: a **Live** page (in the Pages menu and the command bar's mode): pick the installation,
  a scenario launcher (scenario, actor or team where it applies, base, speed, Launch), the theater and
  instrument rail fed by the live stream, the match list, forecast and recall as on Live watch, a
  "Live incidents this session" list, and Reset live data (with a confirm). When nothing is flying it
  says so. Everything shown comes from the live stream (rule 10).
- [ ] `kairos-defense live check [--scenarios all] [--speed 50]`: starts the API in-process (or a
  test server), runs each scenario headless at speed, waits for each incident to close, then scores
  the outcomes in `kairos_defense.eval` (the only code that may read `live_truth`). Prints one line
  per scenario (`PASS`, or `GAP <scenario>: <what was expected and observed>`), exits 0 when all
  pass, 1 when only expectations were missed, 2 on a crash or timeout. Then it resets live data.
- [ ] `make live` (API plus the web app, ready for the Live page) and `make live-check`.
- [ ] Docs: `live/README.md`, `sim/README.md`, `api/README.md`, `web/README.md` (the ingest contract
  goes in `api/README.md`), DECISIONS entries, and a short "Live mode" section in `docs/DEMO.md`.

## Tests

Simulator determinism (same seed, same detections; different seeds differ); ingest validation;
incident formation and closing (single track, swarm, idle close); no look-ahead (a live query never
sees history that started after it, and live history only enters once closed); learning a closed
incident makes it searchable; `live reset` removes every live row and leaves history and the ledger
chain intact (`memory verify`); the truth-isolation scan still passes; a Playwright test that
launches `returning-prober` at speed 20 on the Live page and sees an incident open and matches
appear; existing replay and Director tests unchanged.

## Exit check

```bash
make check && uv run kairos-defense live check --scenarios all --speed 50 && make e2e
```

All pass; `live check` prints PASS for every scenario (a missed expectation is a target gap, D-063);
the replay demo still passes its e2e tests. Record the per-scenario results and timings in
EXIT_CHECK.md and PROGRESS.md.
