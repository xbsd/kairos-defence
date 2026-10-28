# Decisions

<!-- One entry per decision, newest last:
## D-001 · <short title> · YYYY-MM-DD
- Context: what forced a choice
- Decision: what we chose
- Why: the reason, including alternatives rejected
- Consequences: what this changes later (tests, swap to KDB-X, demo)
-->

D-001 to D-014 come from the pre-build review of SPEC v1.1 and are already folded into SPEC v1.2.
Where this file and the SPEC ever disagree, this file wins.

## D-001 · Kit flattened into the repo root · 2026-10-28
- Context: the kit arrived nested in `kairos-defense-kit/`, with identical copies of CLAUDE.md and SPEC.md
  one level up and no git repo, so Claude Code started in the wrong folder and could not find `/phase`.
- Decision: moved CLAUDE.md, README.md, `docs/` and `.claude/` to the repo root, removed the duplicates,
  ran `git init`.
- Why: SPEC §0 and the README expect the kit at the root of a git repo.
- Consequences: start `claude` from the repo root. Nothing is committed yet; phase 0's commit is the first.

## D-002 · Toolchain: Node 22 LTS and Python 3.12 · 2026-10-28
- Context: the machine had Node 26.12.1 (Current line, not LTS) and no Python 3.11; Python 3.12 (uv),
  3.13 (miniconda, first on PATH) and 3.14 (Homebrew) are installed.
- Decision: installed Homebrew `node@22` (22.23.4 LTS "Jod", npm 10.9.9), keg-only at
  `/opt/homebrew/opt/node@22/bin`, alongside Node 26. Phase 0 pins Python 3.12 (`.python-version`) and
  Node 22 (`.nvmrc`, `engines`), and the Makefile puts Node 22 first on PATH when that folder exists.
- Why: matches the README prerequisites. Python 3.12 has the widest wheel coverage for compiled
  dependencies (dtaidistance, lancedb) and keeps uv from picking conda's interpreter.
- Consequences: to use Node 22 in your own shell, put `/opt/homebrew/opt/node@22/bin` first on PATH.

## D-003 · Demo timing follows the flight physics · 2026-10-28
- Context: §1.2 had the drone orbiting at T+45 after appearing at the fence. Under the §8.3 kinematics,
  P1 at 12 m/s needs about 160 s from launch to orbit, BRAVO's radar (3.5 km) sees the launch site, and
  BRAVO's fence lies about 1.37 km from the fuel farm along the approach, so no realistic speed covers
  fence to orbit in 45 s. Matching at T+60 would also have used a window of straight transit, where all
  five P1 flights look alike and the planted top 3 would come down to luck.
- Decision:
  - BRAVO gets a terrain mask (a wooded ridge to the northwest): its radar, RF and Remote ID sensors
    cannot see a target below 200 m that is more than 50 m outside the fence with a bearing between 285°
    and 20° from the installation origin.
  - P1 cruise speed 12 → 15 m/s.
  - The live flight launches at 21:38:45 with no per-flight jitter (`jitter: none`); first contact is
    about 21:40:00, about 50 m outside the north fence.
  - T+0 is first radar contact. Beats: first matcher run T+45, orbit about T+80, top 3 at T+90,
    forecast at T+105, report at T+120.
  - An incident starts at its first detection; `start_local` in the scenario is the launch time, kept
    in truth as `track_truth.launch_ts`. A flight nobody detects produces no incident.
  - Launch and recovery points are unknown when the first or last point is above 30 m (not seen at
    takeoff or landing); the forecast uses only matches with a known recovery point.
- Why: a scratch simulation of the §8.3 model (10 Hz, τ = 1.5 s, 45°/s turn cap, 4 m/s climb cap,
  ground velocity + 0.3 × wind, BRAVO's real rotated layout) over 300 seeded wind and altitude draws gave:
  first contact 41–50 m outside the fence, 65–94 s after launch (p5–p95, median 77 s); orbit established
  67–94 s after contact (median 78 s); on the orbit at T+90 in at least 95% of draws. The mask keeps
  "appears at the fence" and "45 seconds of track" literally true, and puts the forecast zone in the radar
  shadow, which is how real terrain masking plays out. 15 m/s is ordinary for a small multirotor (P4 flies
  15, P6 18). The T+90 top-3 beat lines up with the §19 time-to-match metric (top 3 by T = 90 s).
  Rejected: an unexplained one-off radar outage on the live flight (contrived); keeping full coverage and
  re-timing the script to about T+165 for the orbit (slow demo, transit-only matching windows).
- Consequences: phase 1 tests assert `expectations.live_first_contact_local` and
  `live_orbit_established_s`; if that night's seeded wind pushes the orbit past T+100, cap the live night's
  wind with a scenario override and log it. Phase 4 and 5 exit checks use `--at 90` and `--at 105`.
  BRAVO-251114 is masked too, so its launch and recovery are unknown and it never feeds the forecast.
  The 3D theater draws the radar shadow (§17.3).

## D-004 · P1 orbits slower than it cruises · 2026-10-28
- Context: 6°/s on a 180 m radius is 18.8 m/s, faster than P1's cruise. §9.2 picks the target from the
  slowest 50% of seconds and §9.4 defines loiter as speed below 1.2 × median, so the orbit would be
  skipped and the fence picked as the target.
- Decision: P1 `angular_speed_dps` 6 → 3 (9.4 m/s, 2-minute laps); C1 inherits it.
- Why: keeps the §9 definitions as written and makes loiter clearly slower than transit (9.4 vs 15 m/s).
- Consequences: P1 flights last about 9–12 min. The phase 3 signature test (radius 180 ± 25 m, ccw) stays.

## D-005 · Launch points and parks fit the sensor geometry · 2026-10-28
- Context: P5 (1,800 m at 135° from HQ) and C2 (700 m at 270° from munitions) launched inside the fence.
  Every park was 5.7–8 km from its nearest base, beyond radar range, and six bases had none, so hobbyists
  launching from parks would never be detected and the §8.11 volumes could not be reached.
- Decision: a launch point inside the fence, or less than 300 m outside it, is pushed out along its bearing
  to 300 m outside. Added one 300 m park per installation, 2.2 km from its origin, clear of the launch
  sectors of the actors that visit it and at least 2.2 km from County Rd 12. Copycat `from: parks` only
  labels the launch site in reports. "2× rate near public events" means the rate doubles.
- Why: the smallest change that keeps every actor observable and the volumes reachable.
- Consequences: world.yaml lists 12 more parks; the original parks stay for public events.

## D-006 · County Rd 12 shape and snapping · 2026-10-28
- Context: the road runs through the ALPHA, BRAVO and DELTA launch points only, but P1's CHARLIE flight
  also snaps to it, about 15 km away. Corner-cutting smoothing would also pull the road off DELTA's launch
  point (the ALPHA → DELTA → BRAVO bend is sharp) and fail the 250 m test.
- Decision: straight segments through the three points, densified to 50 m; P1 snaps to the road only when
  the road is within 500 m of its nominal launch point.
- Why: keeps every planted P1 launch where the story needs it.
- Consequences: CHARLIE's P1 flight keeps its nominal launch point.

## D-007 · Frames and rotation sense · 2026-10-28
- Context: the spec did not say whether bearings are true or base-relative, or which way `rotation_deg` turns.
- Decision: every bearing is a true bearing in the region frame, clockwise from north; `rotation_deg`
  turns the installation template clockwise.
- Why: matches the bearing convention in CLAUDE.md, keeps County Rd 12 about 2.1 km northwest of every
  fuel farm, and lets the shift-only target frame (§9.2) line up flights across bases.
- Consequences: `geo.py` tests cover clockwise rotation.

## D-008 · Truth-isolation scan allows the guard · 2026-10-28
- Context: `store/guard.py` must refuse `paths.truth`, but the §7.6 scan failed on that string anywhere
  outside `eval/` and `sim/writers.py`.
- Decision: the scan also allows `kairos_defense/store/guard.py`.
- Why: the guard has to name the path it refuses.
- Consequences: none for the rule itself; only `eval/` reads truth.

## D-009 · Swarm schedule and unanswerable queries · 2026-10-28
- Context: an S1 random event before 2026-06-14 would be an equally valid match for the encore and could
  outrank GOLF 05-03.
- Decision: S1's random events fall after 2026-06-14. Eval excludes queries with no earlier track by the
  same actor (or team) from rank metrics and reports how many there were.
- Why: keeps the encore line ("six weeks earlier, in another region") exact; unanswerable queries only add noise.
- Consequences: GOLF 05-03 is itself an unanswerable swarm query.

## D-010 · Ledger time and single-writer files · 2026-10-28
- Context: ledger times come from the replay clock, so re-runs, seeking back, or the June swarm after the
  August replay would write rows whose time goes backwards. DuckDB lets only one process write a file, so
  the runbook's CLI resets would fail while `make demo` runs.
- Decision: `recorded_at = max(replay clock, chain head recorded_at)`; a proposal already present for the
  same query incident and top-3 set is not appended again; the swarm encore does not write to the ledger.
  `replay --reset` and `memory reseed` call `POST /api/admin/reset` and `POST /api/admin/reseed` when the
  API is running.
- Why: transaction time must never go backwards along the chain, and the reset must work mid-demo.
- Consequences: two admin endpoints; Director's R key uses them.

## D-011 · Planted DELTA case timing · 2026-10-28
- Context: §15.5 did not time `case_opened` or the close decision, yet "known then" is 09:10 and the
  phase 6 test expects "hobbyist, closed" at 10:00.
- Decision: all three events recorded at 2026-04-20 09:10 local, in that seq order. P1-DELTA-260419 gets
  only its planted report; the other P1 flights get normal generated reports and assessments.
- Why: "known then" shows the whole mistake, and a lone report protects its rank 1.
- Consequences: none beyond §15.5.

## D-012 · No decorative motion · 2026-10-28
- Context: §17.3's "slowly rotating" Kairos core and film grain moved without data (CLAUDE.md rule 10).
- Decision: the core turns a few degrees per `ingest` batch and is otherwise still; the grain is static.
- Why: rule 10 is non-negotiable.
- Consequences: none.

## D-013 · DTW speed and precomputed live results · 2026-10-28
- Context: in dtaidistance 2.x, `dtw_ndim.distance` appears to default to pure Python (`use_c=False`);
  to verify on 2.5.1. At 5× the matcher reruns every wall-clock second against a 1.5 s p95 budget.
- Decision: use the C implementations and fail loudly without them. `kairos-defense replay --precompute`
  computes every rerun second of both demo incidents into `data/cache/live/`; `make demo` runs it when stale.
- Why: keeps Director at 5× and seeking instant, with the same computed results.
- Consequences: one more CLI flag.

## D-014 · Small consistency fixes · 2026-10-28
- Context: minor contradictions between CLAUDE.md, the SPEC and PROGRESS.md.
- Decision: `make check` includes `npm --prefix web run check`; `CaseMemory.verify_chain()` returns the first
  broken seq or None (as §15.3 says); LanceDB calls live in `store/lance.py`, never in `prefilter.py`;
  PROGRESS.md phase titles follow §20; phase sessions read DECISIONS.md (CLAUDE.md and the `/phase` skill).
- Why: one source of truth per rule.
- Consequences: none.

## D-015 · Kit committed before phase 0 to run in the cloud · 2026-10-28
- Context: the user wants to build in Claude Code on the web (claude.ai/code) so sessions keep running with
  the laptop off. Cloud sessions start from a GitHub repo, and D-001 left nothing committed.
- Decision: one commit of the kit as-is (`kit: …`) before phase 0, pushed to a private GitHub repo. Phase 0
  stays the first code commit. A minimal `.gitignore` (`.DS_Store`) comes with it; phase 0 extends it.
- Why: the smallest change that lets a cloud session see CLAUDE.md, the spec and the `/phase` skill.
- Consequences: supersedes D-001's "phase 0's commit is the first". On the cloud machine
  `/opt/homebrew/opt/node@22/bin` does not exist, so the Makefile falls back to the `node` on PATH;
  phase 0 must check it is Node 22 there (add an environment setup step if not).
