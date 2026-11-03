# Phase 11: exit-check evidence

Run in the Claude Code cloud container (4 vCPU, Ubuntu, no GPU: Chromium renders WebGL with
SwiftShader), 2026-11-02 to 2026-11-03, as one command chain, exactly the block's exit check:

```bash
make check && uv run kairos-defense live check --scenarios all --speed 50 && make e2e
```

It took 26 min 5 s and exited 0. `live check` started and stopped its own API (a thread on a free
loopback port) and five simulator processes; Playwright started and stopped its own server and,
in `livemode.spec.ts`, one simulator. No server or child was left running.

| Criterion (PHASE_11.md) | Command | Result |
|---|---|---|
| All checks pass | `make check` | pass: ruff clean, 269 files formatted; 914 fast Python tests (803 at the start of the phase), 19 slow deselected; web lint, typecheck, generated types current, Vitest 184 (169) |
| `live check` prints PASS for every scenario | `uv run kairos-defense live check --scenarios all --speed 50` | pass: 5 of 5 PASS in 335 s, exit 0 (below) |
| The Live page works and the replay demo still passes its e2e tests | `make e2e` | pass: 35 passed in 15.5 min (34 before this phase plus `livemode.spec.ts`), axe clean on every route and on the Live page with a live incident |

## `make check`

```text
uv run ruff check .                 → All checks passed!
uv run ruff format --check .        → 269 files already formatted
uv run pytest -m "not slow" -q      → 914 passed, 19 deselected in 242.14s (0:04:02)
npm --prefix web run check          → eslint and prettier clean; tsc clean; src/api/types.gen.ts is current;
                                      Test Files 40 passed (40), Tests 184 passed (184)
```

## `live check --scenarios all --speed 50`

```text
PASS returning-prober: P1 at BRAVO (LIVE-BRAVO-260901-210136, 111 reruns): rank 1 at T+45 s; seed 1101, 83 s
PASS copycat: C1 at BRAVO (LIVE-BRAVO-260902-190008, 91 reruns): at T+120 s: C1 rank 1, P1 rank none; seed 1102, 61 s
PASS hobbyist: H-LIVE-1103 at BRAVO (LIVE-BRAVO-260902-191013, 79 reruns): top match BRAVO-250721-2030 at score 1.0 at T+475 s; seed 1103, 55 s
PASS swarm-repeat: S1 at GOLF (LIVE-GOLF-260902-200005, 97 reruns): final rerun T+525 s: first ECHO-260806-2049 (S1); seed 1104, 26 s
PASS new-operator-twice: flight 1: N1 at BRAVO (LIVE-BRAVO-260902-221029, 99 reruns): 0 earlier flight(s) of N1; top match INDIA-260413-2206 at T+605 s; flight 2: N1 at CHARLIE (LIVE-CHARLIE-260902-222217, 64 reruns): final rerun T+385 s: first LIVE-BRAVO-260902-221029-T1; seed 1105, 108 s
live check: 5 of 5 scenario(s) pass at speed 50 in 335 s
```

Per scenario (wall time includes the feed at 50×, every rerun computed and the close):

| Scenario | Who flew (revealed) | Incident | Reruns | Outcome | Time |
|---|---|---|---|---|---|
| returning-prober | P1 at Bravo, seed 1101 | `LIVE-BRAVO-260901-210136` | 111 | a P1 history flight ranked 1 from the first rerun, T+45 s | 83 s |
| copycat | C1 at Bravo, seed 1102 | `LIVE-BRAVO-260902-190008` | 91 | at T+120 s a C1 flight ranks 1, no P1 flight in the top 10 | 61 s |
| hobbyist | a hobbyist at Bravo, seed 1103 | `LIVE-BRAVO-260902-191013` | 79 | calibration view: top match `BRAVO-250721-2030`, score 1.0 | 55 s |
| swarm-repeat | S1 at Golf, seed 1104 | `LIVE-GOLF-260902-200005` | 97 | the final swarm rerun ranks an S1 event (`ECHO-260806-2049`) first | 26 s |
| new-operator-twice | N1 at Bravo, then Charlie, seed 1105 | `LIVE-BRAVO-260902-221029`, `LIVE-CHARLIE-260902-222217` | 99, 64 | flight 1: no N1 history; flight 2: flight 1's learned track ranked first | 108 s |

An earlier full run (before the scheduler fix in D-175) printed `GAP new-operator-twice`: flight
2's reruns had run before flight 1 was learned. Running a closing incident's work first fixed it;
the run above is after the fix.

## `make e2e`

```text
npm --prefix web run build          → ✓ built in 1.52s
uv run kairos-defense replay --precompute
  DEMO-BRAVO-0828: 95/95 fresh, 0 computed, 95 cached
npm --prefix web run e2e
Running 35 tests using 1 worker
  ✓   1 e2e/director-1x.spec.ts › Director at 1x through every §1.2 row (2.2m)
  ✓   2 e2e/director.spec.ts › Director at 5x shows every beat's key element at 1440x900 (57.4s)
  ✓   3 e2e/director.spec.ts › Director at 5x shows every beat's key element at 1920x1080 (55.3s)
  ✓   6 e2e/guide.spec.ts › guide: Live watch at T+90 (both sizes) and T+120 (2.1m)
  ✓  10 e2e/live.spec.ts › streams real data at 5x (5.6s)
  ✓  11 e2e/live.spec.ts › matches appear by T+90 and the ledger gains a block (22.4s)
  ✓  14 e2e/live.spec.ts › no request leaves the origin (14.9s)
  ✓  15 e2e/livemode.spec.ts › a returning prober flown live is recognized and revealed (1.0m)
  ✓  27 e2e/pages.spec.ts › rails stack under the theater below 1280 px (4.4s)
  ✓  34 e2e/swarm.spec.ts › Swarm view at 1440x900 (6.3s)
  … (35 tests; the full list is in the gate log)
  35 passed (15.5m)
```

`livemode.spec.ts` launched `returning-prober` at 20× at Bravo from the Live page, saw the
incident open, "Live feed, 20×", matches by T+01:20, ran axe with the incident open (no serious or
critical violation), waited for the close, pressed Reveal who flew and read "P1, County Rd
operator" and "Expectation met: rank 1 at T+45 s". The test `rails stack under the theater below
1280 px`, which failed in this container's baseline run before the phase, passes since D-185.

## Screenshot review (§17.13)

`reports/figures/ui/phase11-live-incident-1440.png` and `phase11-live-reveal-1440.png`, and the
same page driven by hand at 20×, were reviewed against §17.2 to §17.4. Found and fixed during the
build: a P1 flight split in two incidents by a radar dropout (D-174), the Matches panel empty at
T+02:28 at 20× (D-175), the "Nothing is flying" banner over the camera buttons (moved below them),
and axe's `scrollable-region-focusable` on the Matches list once the Explain link is hidden (the
three scroll lists are keyboard regions now).
