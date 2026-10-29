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

## D-016 · `kairos_defense.config` is a package · 2026-10-28
- Context: one pydantic model per YAML file in a single `config.py` came to about 600 lines, over the
  ~400-line module limit in CLAUDE.md.
- Decision: `config/` package with `app.py`, `world.py`, `actors.py`, `scenario.py`, `scoring.py`, a
  shared `_types.py` and `_yaml.py`; `__init__.py` holds the root `Config` model, cross-file checks and
  `load_config()`. The import path is unchanged: `from kairos_defense.config import load_config`.
- Why: one module per file mirrors the "one model per YAML file" rule.
- Consequences: §5's `config.py` is `config/__init__.py`.

## D-017 · YAML 1.2 booleans in the config loader · 2026-10-28
- Context: PyYAML follows YAML 1.1, so `rid: off` loads as `False` and the clue key `true:` as the
  boolean `True`. `Road.construct` would also shadow pydantic's `BaseModel.construct`.
- Decision: the loader resolves only `true`/`false` as booleans and turns boolean mapping keys into the
  strings `"true"`/`"false"`. The clue field is `is_true` (alias `true`) and the road field is `build`
  (alias `construct`). The YAML stays exactly as in §6.
- Why: keeps the spec's YAML verbatim and the values what they mean (`rid` is `"off"`, not `False`).
- Consequences: always load config through `kairos_defense.config.load_yaml`, never `yaml.safe_load`.

## D-018 · Config validation rules · 2026-10-28
- Context: §6 gives the values but not how strictly to check them.
- Decision: every model forbids unknown keys and is frozen. Ranges `[lo, hi]` must be ordered; times
  are `HH:MM` and may wrap past midnight; bearings are in [0, 360). Cross-file checks: actor bases
  exist, targets are template assets or `fence`, `snap_to_road` names a road, the road's actor is a
  prober, P1 flights use P1's bases, swarm events use a known team on one of its bases, and expectations
  name real incidents. `app.paths.*` and `signing.key_path` are resolved against the project root (the
  config folder's parent), so commands work from any directory.
- Why: CLAUDE.md asks for config errors to fail loudly; the cross-file checks catch typos that would
  otherwise surface phases later.
- Consequences: `Config.root` is the project root; paths in `cfg.app.paths` are absolute.

## D-019 · Web toolchain pins · 2026-10-28
- Context: the newest TypeScript is 7.0, but typescript-eslint 8.72 supports TypeScript only below 6.1.
  jsdom 30 needs Node ≥ 22.22.2, and the cloud machine has 22.22.0. @react-three/fiber 9 needs React
  below 19.4.
- Decision: TypeScript `~6.0.3`, jsdom `^29.1.1`, React and React DOM exactly `19.3.1`, `@types/react`
  `~19.3.0`. Phase 0 installs only what the placeholder needs: Vite 8.3, @vitejs/plugin-react 6.1,
  Tailwind 4.3, ESLint 10 with typescript-eslint, Prettier 3.9, Vitest 5.0, Testing Library and
  @fontsource B612. three, R3F, drei, postprocessing, Motion, D3, Zustand and Playwright arrive in
  phase 7. `package-lock.json` is committed.
- Why: a clean install with no peer or engine warnings on both the laptop and the cloud machine.
- Consequences: move to TypeScript 7 once typescript-eslint supports it, and log that change.

## D-020 · Python library versions verified; dtaidistance C path · 2026-10-28
- Context: CLAUDE.md asked phase 0 to check the pinned versions against what installs. D-013 asked
  about `dtw_ndim`.
- Decision: the pins are lower bounds from §3. The lockfile resolves duckdb 2.0.0, lancedb 0.40.0 and
  dtaidistance 2.5.1, the verified versions. On 2.5.1, `dtw.try_import_c()` succeeds (OpenMP found) and
  `dtw_ndim.distance` defaults to `use_c=False`; with `use_c=True` it returns the same value as pure Python.
- Why: D-013 asked us to confirm before phase 4.
- Consequences: phase 4 calls `dtw_ndim.distance(..., use_c=True)` and, as D-013 requires, fails loudly
  when `dtw.try_import_c()` is false.

## D-021 · Tokens are the only styling vocabulary · 2026-10-28
- Context: §17.1 and §21 allow only token colors, type, radii and durations. Tailwind ships its own
  palette, shadows and easings. The spec's `:root` block names no radius, type-size or blur variables.
- Decision: `tokens.css` keeps the spec's `:root` block verbatim. A Tailwind `@theme` block resets the
  default colors, shadows, easings, text sizes, radii and blurs, then defines the §17.1 type scale
  (`text-12` to `text-32`), radii (`rounded-panel` 6, `rounded-button` 4, `rounded-chip`) and
  `backdrop-blur-glass` (14 px). `@theme inline` maps the colors (`bg-scope`, `text-ink-mid`, …) and the
  fonts (`font-sans` is B612, `font-mono` is B612 Mono with tabular figures). Durations and easings are
  used as `duration-(--dur-panel)` and `ease-(--ease-out)`. ESLint rejects hex color literals in TS/TSX.
- Why: an off-token class or hex value fails the build or the lint, instead of slipping past review.
- Consequences: a new token needs an edit to `tokens.css`. The built CSS contains only the 11 token colors.

## D-022 · CLI stubs and Makefile-only targets · 2026-10-28
- Context: the phase block lists 14 CLI commands. §5 also names `test-all`, `clean`, `api`, `web` and
  `dev` as Makefile targets.
- Decision: the 14 commands are Typer stubs. Each accepts and ignores any options, prints which phase
  implements it, and exits 0, so `make data` (`gen --seed 42`) already runs end to end. `test-all`,
  `clean`, `web` and `dev` exist only as Makefile targets; `make e2e` says Playwright comes in phase 7
  until `web/package.json` has an `e2e` script. Ruff excludes `*.md`, because ruff 0.17 also reformats
  Python code blocks inside Markdown and would rewrite the spec.
- Why: the simplest option that satisfies the exit check without inventing behavior.
- Consequences: each later phase replaces its stubs with real commands and keeps `test_cli.py` green.

## D-023 · Calendar and weather model · 2026-10-28
- Context: §8.2 gives the weather marginals and event rates but not how hours relate, which way the
  wind direction points, or when exercises and visits happen.
- Decision: hourly weather at 19:00 … 03:00 local (9 rows per region-night) from a per-night stream.
  Wind speed has a Weibull(k = 2) marginal with mean 5 m/s through a Gaussian AR(1) copula (ρ = 0.7 per
  hour). Direction is the direction the wind blows *from*, as a random walk (σ 10° per hour). Visibility
  is a random walk clipped to 2–15 km. Values are rounded like a METAR (0.1 m/s, 1°, 0.1 km), and the
  flight model uses the rounded table values as of the current hour. Exercises: Bernoulli(1/7) per base-night,
  start 17:00–23:00, 2–6 h. VIP visits: Bernoulli(1/30), start 16:00–21:00, 4–8 h, so a visit always
  overlaps its night. Shift change: 22:00–22:30 every night. Public events: Friday and Saturday nights,
  p = 0.3 per public park, start 17:00–20:00, 3–5 h, uniform in the park.
- Why: correlated hours avoid unphysical jumps while keeping the specified marginal; "blows from"
  is the meteorological convention; using the rounded values means the flight model sees exactly what
  the `weather` table shows.
- Consequences: phase 3's as-of join (§11.1) returns the same wind the drone flew in.

## D-024 · Pattern geometry conventions · 2026-10-28
- Context: §8.4 names the patterns but not their orientation, start point or size.
- Decision: `ccw` means counter-clockwise seen from above on a north-up map, so the bearing from the
  target to the drone *decreases*. Perimeter runs go clockwise. Lawnmower and figure-eight axes follow
  the target's long axis; for a square target (munitions) that is the installation's local x axis. The
  figure-eight is a lemniscate of Gerono with half-length a = 2 × lobe radius, so its "size" for the
  entry point is 2 × lobe radius. Size per pattern: orbit = radius; lawnmower = half the footprint
  diagonal; hover = 0. For perimeter and transit with dips, size is the distance along the approach ray
  to the buffered fence and to the fence respectively. The entry point is skipped when the launch is
  already nearer the target than the entry point (P4's pushed-out launch). Transit with dips crosses
  the base on the approach line and dips over the target and the next nearest assets. A dip's duration
  comes from the 2.8 m/s nominal vertical rate, so the drone slows horizontally to make it.
- Why: the simplest geometry that matches the spec text.
- Consequences: **§9.4 says `loiter_dir` is `ccw` "if positive" (bearing rate). With bearings
  clockwise from north, a positive rate is clockwise. Phase 3 must read it as `ccw` when the rate is
  negative, or P1 (ccw) will be labeled `cw`.**
- **Resolved in phase 3 (D-047):** `loiter_dir` is `ccw` when the net bearing change around the
  target is negative; all six P1 flights and every C1 flight read `ccw` (tested).

## D-025 · Flight model details · 2026-10-28
- Context: §8.3 fixes the physics (10 Hz, τ = 1.5 s, 45°/s, 4 m/s, 0.3 × wind) but not the guidance.
- Decision: each flight is a timed reference in nominal seconds: takeoff → transit → pattern →
  egress → landing. The time warp then scales time (durations × w, speeds ÷ w, shapes identical). A
  smooth altitude wander is added (OU, σ 3 m, 30 s, clipped ±10 m). The reference is smoothed with a
  2 s Gaussian on a 2 Hz grid and interpolated to 10 Hz. Guidance: desired velocity = reference
  velocity + 0.3/s × horizontal error (0.4/s vertical). Caps: air speed ≤ 1.3 × cruise ÷ w + 2 m/s;
  first-order lag; the turn cap rotates the velocity at most 4.5° per step above 0.5 m/s; climb
  ≤ 4 m/s. Wind drift applies only when airborne. Nominal climb and descent is 2.8 m/s, so the reference
  stays under 4 m/s after any allowed warp (≥ 0.7). Hover jitter, N(0, 1 m) per second, enters the
  reference, not the output, so true paths obey the caps. Pauses (Poisson, 0.08 per minute, 5–20 s)
  happen on transit and egress legs only. A `jitter: none` flight also gets no pauses.
- Why: a timed reference makes time warp exact and keeps planted timing independent of wind. Smoothing
  removes corners the dynamics cannot fly. 3.5 m/s climbs left warped flights still climbing into transit
  (up to 22 m below the band). Pauses on the live flight could move its first contact past the window.
- Consequences: all 1,869 flights simulate in about 13 s, batched 256 at a time; each row is independent of
  its batch (tested).

## D-026 · Actor plan details · 2026-10-28
- Context: §8.2 and §8.5 leave several draws open.
- Decision: launch jitter and recovery offsets are uniform in a disc. Radius ±8% applies to the orbit
  radius and the figure-eight lobe radius. C1's radius comes from its override range instead. Copycats
  fly the mimicked actor's pattern, altitude and cruise speed, but approach along their own launch
  bearing. "Uniformly by month" is stratified: flight k falls in month ⌊(k + u)·M/n⌋. With
  `target_override`, P1's launch is measured from the override target (CHARLIE: the flight line).
  Each hobbyist flight is its own actor (`H-<BASE>-<YYMMDD>-<n>`, truth only), launches uniformly in
  its base's park, recovers within 300 m, and lasts its drawn duration. With p = 0.3 it first flies to
  a point 150 m inside the fence, skipped when that round trip takes over 80% of the flight. Hobbyist
  counts per base-night use one uniform per night from a per-base stream, inverted through the Poisson CDF.
- Why: the simplest reading of the spec. Unique hobbyist actors keep eval from treating unrelated
  hobbyists as "the same actor" (D-009). The per-base count stream is about 6,600 fewer random-stream setups.
- Consequences: 1,773 hobbyist flights (expected ≈1,779).

## D-027 · Radar details · 2026-10-28
- Context: §8.6 leaves range geometry, `quality` and outage timing open.
- Decision: range is the slant range from the radar. `quality` is the detection probability at that
  range. Planted `sensor_outage_s` is measured from launch. Dropouts run per second as alternating
  geometric up (mean 33 s) and down (mean 6 s) spells, starting up. Each scan draws a fixed number of
  variates, so what is visible never shifts the stream.
- Why: stable streams and a quality value that means something.
- Consequences: about 15% of in-range seconds are lost to dropouts (tested).

## D-028 · Incident ids and boundaries · 2026-10-28
- Context: §7.1 defines incident ids only for planted flights.
- Decision: generated ids are `<BASE>-<YYMMDD>-<HHMM>` of the first detection in local time, with
  `-2`, `-3` … on a clash, so they never reveal the actor. In phase 1 the radar is the only sensor, so
  `start_ts`/`end_ts` are the first and last radar points.
- Why: an operator names an incident by when it was first seen; the launch time is truth only (D-003).
- Consequences: phase 2 must recompute `start_ts`/`end_ts` across radar, RF and Remote ID. That can
  move a generated id's minute; ids are reassigned on every `gen`.

## D-029 · Writers, truth paths and `memory.duckdb` · 2026-10-28
- Context: §8.11 says `gen` recreates three DuckDB files, but phase 6 defines `memory.duckdb`.
- Decision: `gen` deletes `memory.duckdb` and does not create it until phase 6. `sim/writers.py` is
  the only module that opens the truth file for writing. Noiseless paths go to `true_paths` once per
  second from launch (`t_s` = 0, 1, 2, …). `table_hashes` hashes each table's rows ordered by all columns.
- Why: rule 2, and the smallest truth table that still lets eval check recovery and timing.
- Consequences: none for app code.

## D-030 · Track-point volume below §8.11 · 2026-10-28
- Context: §8.11 expects ≈1 M track points at 1 Hz; the generator produces about 0.55 M.
- Decision: keep the specified flight durations and radar model and report the real number.
- Why: hobbyists are ≈95% of flights and last 180–720 s (mean ≈450 s). At a launch park's range
  (2.2 km) the radar detects about 80% of scans, dropouts remove ≈15%, and nothing below 15 m is seen.
  Reaching 1 M would mean stretching flights or inventing detections. The phase 1 exit check covers
  incident and track counts, which are within ±15%.
- Consequences: raise radar `rate_hz` (§8.11) to stress-test larger volumes.

## D-031 · County Rd 12 bases come from the scenario · 2026-10-28
- Context: D-006 says the road runs through P1's ALPHA, BRAVO and DELTA launch points, but P1 also
  flies CHARLIE.
- Decision: the road joins P1's nominal launch points at the bases where its planted flights target
  its own target (no `target_override`). An actor with no planted flights would use all its bases in
  the region.
- Why: derives D-006's three bases from config instead of hard-coding them.
- Consequences: changing CHARLIE's override would reroute the road.

## D-032 · Public events never change hobbyist rates · 2026-10-28
- Context: D-005 keeps public events in the six original parks, 5.7–8 km from the nearest base.
- Decision: keep D-005 as written. The doubling rule (event within 5 km) and launching from an event
  within 3 km are implemented but never trigger with the shipped world.
- Why: changing it would move parks or redefine "near"; neither is needed for the demo.
- Consequences: hobbyist volume is the plain Poisson rate.

## D-033 · BRAVO's seeded layout puts the live orbit at T+94 · 2026-10-28
- Context: D-003 expected the orbit about 78 s after first contact, assuming the template layout
  (fence about 1.37 km from the fuel farm along the approach). At seed 42 the BRAVO fuel farm's asset
  jitter (§8.1) is (+57, −121) m in the installation frame. The inbound leg from the 50 m mask edge to the
  orbit is therefore 1.42 km instead of 1.20 km.
- Decision: keep §8.1 as written. The live flight still meets both acceptance windows: first contact
  21:39:51, about 47 m outside the fence, and orbit established T+94 s (allowed 65–100).
- Why: the timing comes from geometry, not wind (the reference is timed), so capping wind would not
  help. Changing the jitter rule or the seed would change the world to fit one beat.
- Consequences: **open for phase 4 and the demo story (§1.2):** at T+90 the drone is still on its
  final approach, so the top-3 beat would match on transit only. Options: (a) keep it and let phase 4
  test T+90; (b) leave the P1 target assets at BRAVO un-jittered; (c) cap asset jitter at 1σ. Needs a
  decision from the product owner.
- **Resolved in phase 2 (product owner chose (b)):** the live P1 flight's target at its base
  (BRAVO's fuel farm) keeps its template position; its jitter is still drawn, so no other stream
  moves (`world.unjittered_assets`, derived from the scenario like D-031). Measured before choosing:
  (a) first contact 21:39:51, 47 m out, orbit T+94, 251 m from the farm at T+90; (b) 21:40:06, 71 m
  out, orbit T+79, on the orbit at T+90; (c) 21:40:00, 46 m out, orbit T+85. With (b), County Rd 12
  and the live launch point follow the farm, so first contact moves 15 s later and 24 m further out,
  still inside both §1.2 windows. Test: `test_live_target_is_not_jittered`.

## D-034 · Data card and figures are committed · 2026-10-28
- Context: phase 1's exit evidence is the data card and the sample figures.
- Decision: commit `reports/data_card.md` and `reports/figures/pattern_*.png` (seven PNGs, 90 dpi,
  ≈0.55 MB in all). Colors come from the dataviz reference palette; blue and orange pass the validator on the
  light surface.
- Why: reviewers can see the evidence without running the generator.
- Consequences: rerunning `make data` rewrites them; commit them again when they change.

## D-035 · Swarm choreography, schedule and geometry · 2026-10-28
- Context: §8.7 names the formations and actions but not the swarm frame, how the center moves
  during the choreography, the orbit direction, how formations change, or where and when swarms fly.
- Decision: the swarm frame is fixed to the travel heading at the start of the choreography (entry
  point toward the target); formations are laid out in it (line abreast across the heading, trail
  along it, V at 45° half-angle with drone 0 at the apex, triangle on an equilateral lattice) and
  actions transform the current offsets (`rotate` cw adds to the bearing; `expand` scales; `split`
  moves the first group and the rest apart by `separation_m` across the heading, centroid fixed;
  `orbit_target` leaves them alone). Every change follows a smoothstep; a formation change blends
  over max(10 s, farthest drone ÷ 5 m/s), capped at 60% of its step, then holds. The center creeps
  from the entry point (target + first orbit radius + 300 m) to the orbit circle (or the target)
  during the steps before the first `orbit_target`, orbits clockwise at cruise (10 m/s) during it
  and holds after it. Drone = flown center + offset + a smooth wander (OU, σ 2 m, τ 10 s), faded in
  over the first 10 m of altitude. Each event draws a time warp in [0.7, 1.4] (planted events too),
  an approach bearing uniform in [0, 360), an altitude in the band and a ±10% factor per step; launch
  2 km from the target (pushed out per D-005), recovery within 300 m, launch time uniform in
  20:00-01:00. A team with a live planted event flies its random events only on later nights
  (D-009). Swarms broadcast no Remote ID.
- Why: the simplest reading that keeps formations meaningful relative to the approach, gives the
  §14 descriptors (spread, pairwise quartiles, rotation rate, center speed) a distinctive shape, and
  keeps drone speeds plausible (fastest drone 17 m/s at w = 0.79). The wander keeps "N(0, 2 m)" as
  a stationary spread without 3 m/s jitter between seconds.
- Consequences: spacing during holds stays within ±20% of spec (tested on every event); during
  S1's split the group gap reaches about 300 m, at §14's `max_spacing_m`, but every event has other
  windows of 60 s or more below it. Figures: `reports/figures/swarm_S1.png`, `swarm_S2.png`.

## D-036 · RF model details · 2026-10-28
- Context: §8.6 gives RF's range, rate, band table and bearing noise but no detection probability,
  SNR law or scan timing.
- Decision: one detection per scan (0.5 Hz, aligned to launch) while airborne (> 0.5 m), within
  4 km slant range of the RF sensor and outside the terrain mask; no detection probability. SNR =
  40 dB at 100 m minus 20 dB per decade, plus N(0, 2 dB), 0.1 dB steps; bearing to 0.1°. Planted
  `sensor_outage_s` windows stay radar-only (§8.6 lists them under radar). Families map to bands by
  their first digit; an unknown family is an error.
- Why: "emit detections at rate_hz" reads as deterministic; free-space falloff is the simplest SNR
  law that "falls with range" and stays positive at 4 km.
- Consequences: RF hears takeoff, which the radar cannot see below 15 m, so RF usually starts an
  incident (D-039). Volume in D-044.

## D-037 · Remote ID details · 2026-10-28
- Context: §8.6 says `on` broadcasts a stable per-drone serial, but not its form, whether it is
  stable across flights, or how the broadcast drone position relates to the truth.
- Decision: serials are `SN-` plus 16 upper-case hex digits. `on`: the drone's serial comes from
  `rng_for(seed, "rid-serial", actor, drone)`, so the same drone keeps it on every flight (copycats
  with Remote ID on share one serial per actor; each hobbyist flight is its own drone, D-026);
  operator fixed within 10 m of launch. `spoofed`: a new random serial per flight, operator 1-3 km
  from launch at a random bearing. Broadcasts at 1 Hz while airborne within 3 km slant range and
  outside the mask; drone position = truth + N(0, 2 m), 0.1 m steps.
- Why: stable across flights is what a real serial is; the `SN-` form cannot look like a plate.
- Consequences: phase 3's `rid_serial` links a copycat's Remote ID flights to each other, which is
  true (same drone). About 0.69 M broadcasts.

## D-038 · Incidents need a radar track; sensors log everything · 2026-10-28
- Context: D-028 moves incident boundaries to "any sensor", but tracks are radar tracks and §8.11
  says a flight no sensor detects makes no incident. A flight heard only by RF would be an incident
  with no track.
- Decision: an incident needs at least one radar point; its start and end are the first and last
  detection of any of its drones by radar, RF or Remote ID. `rf_detections` and `remote_id` log
  every flown drone, incident or not. Swarm drones share one incident; tracks are numbered `T1…Tn`
  in drone order over the drones the radar saw. The data card counts flights heard but never
  tracked (0 at seed 42).
- Why: keeps every incident matchable (it has a track) without dropping sensor data.
- Consequences: generated ids are the minute of the first detection by any sensor, usually the RF
  hearing takeoff (D-028 expected this).

## D-039 · Live T+0 stays first radar contact · 2026-10-28
- Context: §16.1 sets a replay's T+0 to `incidents.start_ts` (any sensor) while §1.2 sets it to
  first radar contact; RF could hear the live drone before the radar sees it.
- Decision: keep both definitions and measure the gap: `LiveTiming.radar_lag_s` (first radar contact
  minus first detection by any sensor). BRAVO's terrain mask hides the drone from RF too, so at seed
  42 the gap is 0 s and both definitions give 21:40:06. A test asserts it.
- Why: no change needed; the test guards the demo if sensors or the mask change.
- Consequences: phase 7 can use `incidents.start_ts` as T+0.

## D-040 · Report details and actor clue profiles · 2026-10-28
- Context: §8.8 and Appendix A leave open the source mix, the event time and place, the templates
  for the four bases Appendix A does not style, how blotters write directions, and where the truth
  of lights, sound, launch site and departure comes from.
- Decision: sources are drawn without repeats with weights BDOC 0.4, security forces 0.35, local
  PD 0.15, FAA 0.1; delays uniform in the source range after the incident end, whole minutes; grades
  uniform in the source list. `event_ts` is the incident start; the report position is the mean
  radar position (10 m steps); "near the …" names the target asset, or the side of the fence for
  fence targets. A hobbyist whose registered serial was received gets the hobbyist template
  (security forces 60%, local PD 40%). CHARLIE, HOTEL, INDIA and JULIET get a new terse
  security-forces line (`HH:MM SF: patrol observed sUAS near …`). Blotters are upper case with
  directions in full. Clue model: vehicle and road as §8.8 (true road: P1's `clues.road`, else the
  region road nearest the launch point; the true probability for roads is 0.8, like vehicles;
  wrong roads come from the region's other roads plus three minor roads outside the gazetteer);
  lights and departure in every security-forces report, sound in 30% of narrative ones, a local-PD
  witness clause half the time (launch site or sound); each is true with p = 0.8. Each actor has a
  stable lights, sound and launch-site profile from `rng_for(seed, "profile", actor)`; hobbyists'
  launch site is their park. Departure truth = compass direction from the mean radar position to
  the true recovery point. Swarm reports say how many drones flew in formation. The planted DELTA
  report adds the true lights and departure that the narrative template needs, so its text matches
  Appendix A's example. Every clue in a text has a `clue_truth` row, checked by reading the text
  back with `lexicon.find_clues`.
- Why: the simplest model that fills every template slot and keeps the clue truth complete.
- Consequences: 956 reports. Phase 5's clue extraction must be case-insensitive (blotters).
  Report counts per actor type, the delay histogram and clue rates are on the data card.

## D-041 · Live incidents get no reports or assessments · 2026-10-28
- Context: §8.8 gives every incident reports and an assessment, but the two live incidents are
  happening during the replay; paperwork recorded after them would leak the future into the demo
  and into the seeded memory (§15.5).
- Decision: no reports or assessments for `status = 'live'`; `assessment_truth` still has their
  correct labels.
- Why: nobody has written anything about tonight yet.
- Consequences: 1,876 assessments for 1,878 incidents.

## D-042 · Assessment rules and correct labels · 2026-10-28
- Context: §8.8 says "Remote ID with a stable serial" means hobbyist, but a spoofed serial is also
  consistent within a flight; it does not give copycats a correct label.
- Decision: "stable serial" means mode `on` (a registered serial) and at least one broadcast
  received; spoofed serials are "not registered" and stay `unknown`. The 20% mislabel applies to
  prober incidents only. Correct labels: hobbyist → hobbyist, prober and copycat → probing (a
  copycat flies the same probing pattern), swarm → swarm. Author `<BASE> BDOC`, recorded 2-36 h after
  the incident end; rationales are fixed sentences.
- Why: matches the planted author and keeps "unknown" the honest default.
- Consequences: no history incident is labeled `probing`; prober incidents labeled hobbyist: 18%
  at seed 42 (including the planted DELTA label).

## D-043 · LLM paraphrase waits for phase 9 · 2026-10-28
- Context: `reports_llm_paraphrase: true` needs an LLM client, which phase 9 builds (`llm.py`).
- Decision: the flag stays `false`; when it is `true`, `gen` stops with an error naming phase 9.
- Why: offline by default (CLAUDE.md rule 5); no half-built LLM path.
- Consequences: phase 9 adds the paraphrase, keyed and cached by `report_id`.

## D-044 · RF volume below §8.11 · 2026-10-28
- Context: §8.11 expects ≈0.5 M RF detections; the generator produces 415 k (83%).
- Decision: keep the specified rate, range and flight durations and report the real number, as
  for track points (D-030).
- Why: hobbyists are ≈95% of flights and fly 180-720 s; at 0.5 Hz that is ≈225 detections per
  flight. Reaching 0.5 M would mean longer flights or invented detections. The phase 2 exit check
  does not gate on volumes; incidents, tracks, reports and assessments are within ±15%.
- Consequences: the slow test asserts more than 380 k. Raise RF `rate_hz` to stress-test.

## D-045 · Guardrail scan for generated text · 2026-10-28
- Context: phase 2 asks for a forbidden-content scan of reports (no plates, no person names) using
  regex and lexicon checks, but blotter capitals ("EST 350 FT", "FARM RD 300") and NATO
  installation names (Charlie, Juliet) look like plates and names to naive rules.
- Decision: `lexicon.forbidden` removes world vocabulary (road, park and installation names) and
  Remote ID serials, then flags plate-like tokens without spaces, plate and registration words,
  street addresses, phone numbers, e-mail, a title before a capitalized name, words describing a
  person, and a lexicon of about 300 common given names and surnames. The lexicon leaves out English
  words used in the world (colors such as White and Gray, Park, Hill) and the NATO installation
  names; a test checks it shares no word with the clue lexicons or installation ids.
- Why: catches the realistic mistakes without false alarms on the synthetic world's own words.
- Consequences: every report text, rationale and author passes; the scanner is also tested on
  made-up offenders.

## D-046 · Target choice: where the drone lingers · 2026-10-28
- Context: §9.2's rule (smallest *mean* distance over the slowest 50% of seconds) picked the true
  target for only 48 of the 131 prober, copycat and swarm tracks at seed 42. For P1 at ALPHA it
  picked the fence: the radar sees takeoff and landing 2 km out, and those near-zero-speed seconds
  outweigh the orbit. That broke the planted-signature test and put ALPHA's distance channel in a
  different frame from DELTA's.
- Decision: candidate seconds are in flight (leading and trailing seconds below 0.8 × the track's
  median altitude are takeoff and landing), have a speed, and lie within 500 m of the fence (0
  inside); with fewer than 10 such seconds, every in-flight second counts. The slowest 50% of them
  vote, and the target with the smallest *median* distance wins (ties: asset id order, fence last).
- Why: compared on all 131 tracks (mean or median, with or without the in-flight mask, near the
  fence within 300, 500 or 800 m): this rule gets 93/131. Every P1 flight is right (CHARLIE picks
  the flight line, its target override), and so are all of P2, P3, P4, P5 and C1. Still wrong: P6
  picks the flight line on all 10 flights (consistent; its dips cover three assets), C2 mostly the
  fence (its figure-eight is flown at cruise after a long transit across the base), swarm drones
  are mixed (swarm matching uses its own descriptors, phase 9).
- Consequences: a partial live track recomputes its target every update (§9.2): the live P1 flight
  picks the fence while inbound and the fuel farm from T+90. Hobbyists launching from parks 2.2 km
  out fall back to all seconds, so 1,800 of 1,898 history tracks have the fence as target. Phase 4
  may revisit P6 and C2.

## D-047 · Signature details · 2026-10-28
- Context: §9.4 leaves the "target radius", loiter coverage, takeoff and landing, and the meaning of
  a stable Remote ID serial open.
- Decision:
  - `loiter_radius_m` is the median distance from the target *centroid* over the loiter seconds
    (at least 10, else no loiter). The spec's "median `dist_target_m` + target radius" gives about
    250 m for CHARLIE's 180 m orbit around the 1 km flight line.
  - `loiter_dir` sums the bearing change between consecutive loiter seconds outside the target
    polygon; under 180° net it is `none`, otherwise `ccw` when negative (D-024). A hover over its
    target therefore reads `none` instead of a random direction.
  - `dwell_s`: seconds with `dist_target_m` ≤ 1.5 × `loiter_radius_m` (0 without a loiter).
  - `alt_median_m`: median over in-flight seconds (D-046's mask).
  - `approach_bearing_deg`: first second with `dist_target_m` ≤ 1,000 m, bearing from the centroid.
  - `tod_minutes`: local times before noon add 1,440 (01:00 → 1500).
  - Launch: the Remote ID operator's median position when exactly one serial was heard on the
    track; else the first radar point if below 30 m; else unknown. Recovery: the last radar point
    if below 30 m.
- Why: the simplest reading that keeps the planted P1 values (approach 315°, radius 180 m, ccw)
  true for every P1 flight, including CHARLIE and the partial BRAVO 2025-11-14 flight.
- Consequences: the app cannot tell a spoofed serial from a registered one (both are stable within
  a flight), so P2's launch area comes from its fake operator position. That is how spoofing works.

## D-048 · RF and Remote ID association · 2026-10-28
- Context: §11.2 asks for a bearing check "with concurrent drones" but not which track point to
  compare with; the literal range joins took 19 s (RF) and 38 s (Remote ID).
- Decision: an RF detection belongs to a track if it is within ±30 s of one of its points at the
  same installation. When another track at that base is within ±60 s (their ±30 s windows can
  touch), the detection's bearing must also be within 15° of the bearing from the RF sensor to the
  track point nearest in time (ties go to the earlier point). `rf_family` is the most frequent
  family (ties alphabetical). Remote ID: broadcasts within ±5 s and 100 m of a track point; the
  most frequent serial wins. Both joins bucket time and repeat each track point for its own and
  both neighbor buckets inside the CTE, so DuckDB plans an equi-join: RF 1.6 s, Remote ID 0.9 s.
- Why: the nearest point is the best estimate of where the drone was when it was heard. With the
  bucket offset in the join condition, DuckDB 2.0 still plans a range join (37 s).
- Consequences: `rf_family` is known for all 1,898 history tracks (22 heard more than one family);
  Remote ID is present on 1,634 (10 heard more than one serial).

## D-049 · Derived tables hold history tracks only · 2026-10-28
- Context: §9.5 keeps live tracks out of LanceDB but says nothing about `track_features` and
  `track_signatures`, which would otherwise hold the live tracks' future (for example the live
  recovery point, which a forecast must never see).
- Decision: `index` skips live tracks everywhere. A live track's features and signature are
  computed from its points up to the replay time (`match/query.py`).
- Why: no table can leak tonight's future, whatever reads it later.
- Consequences: `TrackStore.features()` is empty for live tracks; phase 7's replay computes them
  on the fly. The planted-signature test computes the live P1 signature from its points.

## D-050 · Query start, T and early queries · 2026-10-28
- Context: §10.3 filters on the "live start", §19.2 counts T from the first point, and D-038 makes
  an incident's start its first detection by any sensor (usually RF hearing takeoff). §10.1's
  "largest window ≤ elapsed" has no answer before 60 s, yet §1.2 runs the matcher at T+45.
- Decision: a track starts at its first radar point, on both sides of the filter (`start_ts_ms` in
  LanceDB, `start_ts` in `track_signatures`), and T counts from it. The query is rebuilt from the
  points up to T (target, smoothing, derivatives), never sliced from full-track features. Before
  60 s are seen (T = 45 → 46 rows) the query uses every row against the 60 s windows; PAA
  normalizes the length. Below `min_track_s` (T = 30) the matcher does not run, and eval counts a
  miss. The prefilter raises `LookAheadError` if a store returns a row that did not start strictly
  earlier or that belongs to the query's own incident.
- Why: one consistent clock for both sides; the raise is defense in depth against an adapter that
  ignores the filter (tested with a leaky fake store).
- Consequences: the spec rule is kept as written, so a past track that started earlier but was
  still flying contributes all its windows. One drone per actor at a time means this cannot help a
  same-actor match.

## D-051 · Window vectors: NaN and PAA details · 2026-10-28
- Context: §9.5 does not say how to average 60 s into 16 segments or what to do with NaN.
- Decision: exact fractional PAA weights (3.75 s segments for 60 s). After z-normalizing and
  weighting, NaN is filled by linear interpolation along time and an all-NaN channel becomes 0
  (§10.4's rule for DTW). One function builds both indexed and query vectors (tested identical);
  windows of one size are built in a batch (strided view, one matrix product).
- Why: same answer for query and index by construction. Batching, a closed-form median of three
  in the smoothing and skipping an unneeded sort cut `index` from 96 s to 55 s.
- Consequences: 136,266 windows at seed 42 (57,462 / 51,297 / 27,507 for 60 / 120 / 300 s).

## D-052 · LanceDB 0.40 adapter details · 2026-10-28
- Context: `create_scalar_index` and `table_names` are deprecated in lancedb 0.40, and
  `table_exists` raises on a local connection.
- Decision: `LanceVectorStore.replace()` drops and rewrites a table, then adds scalar indexes
  (`window_s` bitmap; `start_ts_ms`, `incident_id` B-tree) with `create_index(column,
  config=...)`. `upsert()` merges by the table's key column. `search()` always pre-filters and
  drops the vector column. Tables are listed with `list_tables().tables`.
- Why: CLAUDE.md asks for a thin adapter around version differences.
- Consequences: scalar indexes cut filtered search from about 120 to 80 ms in a 160k-row test.

## D-053 · Index build uses the adapters; matching uses the ports · 2026-10-28
- Context: the ports (§4.1) are read-only plus `sql()`, but `index` must bulk-write DuckDB and
  LanceDB tables.
- Decision: `features/build.py` uses `DuckTrackStore` and `LanceVectorStore` directly (bulk RF and
  Remote ID association, `write_table`, `replace`). Matching and evaluation depend only on
  `TrackStore` and `VectorStore`; site geometry is read through `TrackStore.sql`.
- Why: the index build is I/O orchestration; the ports stay as §4.1 defines them.
- Consequences: a KDB-X swap needs a new build module or adapter-level bulk writers; matching and
  eval code do not change.

## D-054 · Euclidean baseline output · 2026-10-28
- Context: §10.8's `Match` is shaped for the fused DTW matcher.
- Decision: the baseline fills only what it computes: `score` = `shape_sim` = 1 − d²/4 (vectors
  are unit length, so this is the cosine mapped to 0..1), `features` = squared distance and
  window size, no reasons, `warp_ratio` NaN, `model_version` `euclidean-v1`.
- Why: no invented numbers (CLAUDE.md rule 10 in spirit).
- Consequences: phase 4's matcher fills the rest.

## D-055 · Evaluation definitions · 2026-10-28
- Context: §19 leaves several definitions open.
- Decision:
  - Months 13-18 are the local nights 2026-03-01 to 2026-08-31 (a night is local time minus 12 h).
    Query sets: prober tracks (23) and copycat tracks (10) of history incidents; swarm incidents
    (5) are listed for phase 9. Hobbyists are candidates only.
  - Time to match: a query's earliest protocol T with a same-actor track in the top 3; the metric
    is the share with that T ≤ 90 s.
  - Copycat-first: prober queries at T = 120 s where a copycat track ranks above every same-actor
    track among the returned candidates (up to 50), including queries whose own actor is not
    returned at all.
  - MRR counts 0 when no same-actor track is returned.
  - Latency: query build (resample, target, PAA), prefilter (LanceDB search plus grouping), end to
    end.
  - Demo assertions: first contact on the radar data, the orbit on the truth path with phase 1's
    definition, the live top 3 for information only.
- Why: the simplest readings of §19.
- Consequences: one query moves the prober metrics by about 4 points.

## D-056 · `baseline.json` waits for phase 4 · 2026-10-28
- Context: §19.4's gate fails a run that is more than 5% worse than `reports/baseline.json`.
- Decision: `eval --baseline` and the gate are built (gated: Recall@5, MRR, time to match,
  copycat-first, copycat Recall@5, prefilter and end-to-end p95 latency, plus any failed demo
  assertion), but phase 3 writes no `baseline.json`; phase 4's exit check does.
- Why: DTW makes the end-to-end latency slower by design, so a Euclidean baseline would fail
  phase 4's first run.
- Consequences: with 23 prober queries a single query changes Recall@5 by 0.043, more than 5% of
  0.80. Phase 4 should decide whether the gate needs an absolute floor.

## D-057 · Prefilter latency above the §10.9 budget · 2026-10-28
- Context: §10.9 asks for a prefilter p95 of at most 50 ms.
- Decision: no tuning in phase 3, which has no targets. Measured here (cloud sandbox, 4 threads):
  prefilter p50 64 ms, p95 83 ms; end to end 93 / 117 ms.
- Why: tried during planning on 160k synthetic rows: IVF_PQ was no faster and kept only 30-57% of
  the exact top 200; one table per window size gave about 42 / 50 ms; scalar indexes are in.
- Consequences: phase 4 or phase 9 (performance pass) decides between per-size tables, a cached
  numpy brute force (about 13 ms) or measuring on the laptop first.

## D-058 · Open: the Euclidean prefilter does not surface P1 for the live query · 2026-10-28
- Context: phase 4 re-ranks only the prefilter's 50 candidate tracks, and its exit check needs the
  three planted P1 flights in the live top 3 at T+90.
- Finding: best-window rank of each earlier P1 flight among 1,882 earlier tracks, live query:
  T+45: 501-1,775. T+60: ALPHA 05-02 8, ALPHA 03-03 53, DELTA 197. T+90: CHARLIE 176, others
  1,149-1,194. T+120: CHARLIE 59, ALPHA 03-03 84, DELTA 644. So at T+90 none of the three is in
  the 50 candidates. Diagnostic only, not adopted: speed and distance channels alone put DELTA at
  912; a 9 s mean on every channel gives 586-1,543. Radar noise in the turn and vertical channels
  is therefore not the main cause; per-window z-normalization probably erases what makes P1
  distinctive (orbit radius, speeds), so "approach, then circle" looks like many hobbyist windows.
- Decision: none yet; this needs phase 4's attention before DTW work starts.
- Options: (a) scale `dist_target_m` and speed by fixed units instead of per window; (b) pass more
  candidate tracks (200-500) to DTW, with LB_Keogh pruning to stay within 800 ms; (c) a longer or
  multi-window query for the prefilter. Ask the product owner if a fix changes the demo story.

## D-059 · Autopilot for phases 4 to 9 · 2026-10-28
- Context: the user wants the remaining phases to run unattended, one fresh Claude Code session per
  step, without approving each plan. They supplied an autopilot add-on (`scripts/autopilot.py`, skill
  `phase-auto`, `docs/AUTOPILOT.md`); a review before launch found gaps that would have stopped or
  misled the run.
- Decision: adopt the add-on, with these changes:
  - Gate times follow D-003: phase 4 runs `match … --at 90`, phase 5 `forecast … --at 105` (the add-on
    had 60 and 75).
  - `scripts/check_targets.py N` enforces the SPEC §19.3 and §10.9 targets and the demo assertions from
    the newest eval JSON, cumulatively from phase 4. `make eval` alone only fails on regressions.
  - The gate checks for a clean tree before its commands, since `make data` and `make eval` rewrite
    tracked reports and figures; the closing commit records those outputs.
  - Protected files (the scripts, the gate list, the autopilot settings and skill) must not change during
    a run; the passing count of fast Python tests must not drop; added skip or xfail markers are logged.
  - The allow and deny rules live in `.claude/settings.autopilot.json` and are passed with `--settings`
    to autopilot sessions only; a repo-wide `.claude/settings.json` also bound interactive sessions.
  - Child sessions run without `ANTHROPIC_API_KEY` (subscription login, not API billing), `GITHUB_TOKEN`
    or the launcher's `CLAUDE*` variables. `--dry-run` only prints (it used to mark every phase done and
    commit). `--push` lets the script, never Claude, push after each phase. The scripts pass ruff, which
    `make check` runs over the whole repo.
- Why: each change closes a way the run could fail for reasons unrelated to the phase, or pass while
  missing a target. Rejected: trusting REPORT.md to state targets honestly.
- Consequences: phase 4 must write `metrics.dtw_lift`, `latency_dtw_p95_ms` and the other keys
  `check_targets.py` names. Phase 3's prefilter p95 (83 ms) is above the 50 ms target, so phase 4 must
  speed it up. A phase that cannot meet a target stops the run with BLOCKED.md for a human decision.

## D-060 · Latency does not block; phase 10 documentation · 2026-10-28
- Context: the user asked the run to go to the end without them, not to worry about latency for now,
  and to finish with a user guide with screenshots, a one-pager, READMEs and rollback documentation.
  `test_cli_eval` also failed one run in three: eval flagged a 5% latency rise as a regression, and
  millisecond timings vary more than that between identical runs.
- Decision:
  - The §10.9 latency targets are still measured and printed by `scripts/check_targets.py` (WARN), but
    no longer fail a gate. The eval regression check treats latency as worse only above 1.5 × baseline
    + 2 ms; accuracy metrics keep the §19.4 5% rule.
  - New phase 10 (`docs/phases/PHASE_10.md`): `docs/USER_GUIDE.md` with at least 10 real screenshots
    captured by a Playwright spec, `docs/ONE_PAGER.md`, `docs/ROLLBACK.md`, root README links; gated by
    `scripts/check_docs.py`. `docs/phases/INDEX.md` lists every tag as a rollback point.
  - Phase 9's gate also runs `make test-all` (slow tests included).
- Why: the user's instructions; a gate that fails on timing noise sends fix sessions after nothing.
- Consequences: §19's latency row is a known, logged gap until a human revisits it. PROGRESS.md has a
  phase 10 row.

## D-061 · Phase 0 documentation backfill · 2026-10-28
- Context: the autopilot (D-059) expects every phase to leave `PLAN.md`, `REPORT.md` and
  `EXIT_CHECK.md` in `docs/phases/phase-NN/`, and every package to have a README. Phases 0 to 3 were
  built by hand before that convention existed. `phase-auto backfill 0` reconstructs phase 0's
  documents without changing code.
- Decision: `PLAN.md` is marked "as built" and is reconstructed from `f9258de`, PROGRESS.md and
  D-015 to D-022. The exit check was rerun at HEAD (`911aba1`) and today's output recorded beside the
  original numbers. READMEs are written for what phase 0 created: `src/kairos_defense/` (cli, ports,
  rng, geo), `config/`, `store/`, `eval/` and `web/`. Each describes the code as it is now, with a
  per-phase changelog, so it stays current. The `sim/`, `features/` and `match/` READMEs are left to
  the backfills of phases 1 to 3, which created those packages.
- Why: each backfill documents its own phase, and a README that described only phase 0's
  `store/guard.py` would already be wrong.
- Consequences: the autopilot's docs check (all subpackage READMEs) passes only after the phase 1 and
  3 backfills, or phase 4's build, add the remaining three.

## D-062 · Open: dtaidistance's C library does not load on the dev laptop · 2026-10-28
- Context: during the phase 0 backfill, the D-020 toolchain check was rerun on the dev laptop (macOS
  arm64, Python 3.12.12, dtaidistance 2.5.1 wheel). D-020 had verified the C path on the cloud Linux
  machine only. Here:
  - `dtw.try_import_c()` is False. `dtw_cc_omp` and `dtw_cc_numpy` cannot `dlopen`
    `/usr/local/lib/libomp.dylib`, the path baked into the wheel, and Homebrew `libomp` is not
    installed.
  - `dtaidistance.dtw.dtw_cc` is None, so `dtw.distance_fast` raises `CythonException`.
  - `dtw_ndim.distance(..., use_c=True)` logs "C-library not available, using the Python version" and
    silently runs pure Python. The values are the same; it is slower.
- Decision: none yet. The backfill changes no code and no machine state. Phase 4 must choose before it
  relies on the C path. Options, none tested here:
  - (a) Install `libomp` (`brew install libomp`) and make it loadable at the wheel's path, or through
    `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libomp/lib`. This changes the machine, so a human
    must do it.
  - (b) Build dtaidistance from source in this project (uv `no-binary-package = ["dtaidistance"]`),
    with or without OpenMP.
  - (c) Accept the pure-Python fallback on this laptop. Latency does not block (D-060), but D-020's
    "fail loudly when `try_import_c()` is false" would stop the matcher. That rule would have to become
    a loud warning, recorded in a new decision.
- Why: the phase 4 DTW re-rank and its latency (§10.4, §10.9) depend on the C path, and the autopilot
  runs phase 4 on this laptop.
- Consequences: phase 4's plan must cite D-062 and choose an option. Until then, any DTW latency
  measured on the laptop is pure-Python latency.

## D-063 · Target shortfalls are recorded gaps, not stops · 2026-10-28
- Context: the user asked that a missed accuracy target (phase 3's Recall@5 is 0.43 against 0.80) get a
  few honest attempts and then not stop the run, "unless something is seriously wrong", because many
  phases remain.
- Decision: `scripts/check_targets.py` exits 1 for target shortfalls (`GAP` lines: §19.3 metrics and
  demo assertions) and 2 when something is broken (no fresh eval report, DTW not running, a metric or
  demo row not produced). In `docs/phases/gates.json` the checker is a `soft:` command: when it is the
  only failure, the autopilot runs up to `--target-attempts` (3) fix sessions, then writes
  `docs/phases/phase-NN/GAPS.md`, marks the phase "done with gaps" and continues. Accepted gap keys go
  to `docs/phases/accepted_gaps.json` (written only by the script) and show as WARN in later phases
  instead of being retried. `make eval`'s own exit code no longer blocks; a crash is caught because the
  checker requires a report newer than the gate's start. Tests, crashes, missing metrics, e2e and
  documentation still block.
- Why: the user's instruction; fix sessions should not loop on a hard research target while the rest
  of the product waits.
- Consequences: §19 targets that end short are listed in GAPS.md files and in PROGRESS.md as "done with
  gaps"; phase 9's "gaps approved in DECISIONS.md" is satisfied by this entry plus those files.

## D-064 · dtaidistance built from source (resolves D-062) · 2026-10-28
- Context: D-062. The macOS wheel's C modules all link `/usr/local/lib/libomp.dylib`, which is absent on
  Apple Silicon, so dtaidistance silently ran pure Python on the laptop. Making that path exist needs
  `sudo`.
- Decision: installed Homebrew `libomp` on the laptop (`brew install libomp`, undo with
  `brew uninstall libomp`) and set `[tool.uv] no-binary-package = ["dtaidistance"]`, so uv builds it
  from source against the OpenMP the machine has. Verified in the project venv: `dtw.try_import_c()` is
  True, `dtw_cc_omp` imports, and C and Python `dtw_ndim.distance` agree.
- Why: keeps D-013's "use the C implementations and fail loudly without them" true on the dev laptop,
  without root and without patching installed files. Rejected: a symlink in `/usr/local/lib` (needs
  sudo); `DYLD_*` variables (macOS strips them through `/bin/bash` and `make`); accepting pure Python.
- Consequences: a fresh machine needs a C compiler (Xcode command-line tools or gcc) for `uv sync`; on
  macOS also `brew install libomp`, or dtaidistance builds without OpenMP. README prerequisites should
  say so (phase 10).

## D-065 · Phase 1 documentation backfill; figure fonts depend on the machine · 2026-10-28
- Context: `phase-auto backfill 1` reconstructs phase 1's documents (D-061 did the same for phase 0)
  and reruns the exit check on the dev laptop. `make data` there produced a `reports/data_card.md`
  byte-identical to the committed one (written on the cloud machine). It also rewrote all nine
  committed PNGs (seven pattern figures, two swarm figures): the pixels differ and the files are 12 to
  18% smaller. Compared side by side, the plotted paths, points and markers are the same; only the
  typeface differs. `sim/figures.py` sets no font family, so matplotlib's default `sans-serif` list
  applies. That is DejaVu Sans on the laptop and a different sans-serif on the cloud machine.
- Decision: `docs/phases/phase-01/PLAN.md` is marked "as built" and reconstructed from `1a13664`,
  PROGRESS.md and D-023 to D-034. The exit check was rerun at HEAD (`3b0f06c`) from `make clean`,
  and today's output is recorded beside the original numbers. `make index` and the web build then
  restored the working state. `src/kairos_defense/sim/README.md` describes the package as it is now,
  covering phases 1 and 2. Following D-034 ("commit them again when they change"), the laptop's
  figure renders are committed. No code changes.
- Why: the autopilot runs every later phase on this laptop, and phase 9's gate runs `make clean` and
  `make data`, so the laptop renders are what the repository will hold anyway. Committing them now
  keeps font-only churn out of later phase commits. Pinning a font would be a code change, which a
  backfill may not make.
- Consequences: follow-up for the next phase that touches `sim/`: set an explicit font family in
  `sim/figures.py`, for example DejaVu Sans, which matplotlib bundles. The figures will then be
  byte-stable across machines and can join the determinism checks. The `sim` README now exists, so
  only the `features/` and `match/` READMEs remain for D-061's documentation check; phase 3's
  backfill writes them.

## D-066 · Phase 2 documentation backfill · 2026-10-28
- Context: `phase-auto backfill 2` reconstructs phase 2's documents (D-061 and D-065 did phases 0
  and 1) and reruns its exit check on the dev laptop. Phase 2's exit-check filter (`-k "swarm or rf
  or rid or reports or assessments or planted"`) now selects 116 tests, against 109 at `06cc826`.
- Decision: `docs/phases/phase-02/PLAN.md` is marked "as built" and reconstructed from `06cc826`,
  PROGRESS.md, D-033's resolution and D-035 to D-045. The exit check was rerun at HEAD (`ba703ec`)
  from `make clean`, and today's output is recorded beside the original numbers. `make index` and
  the web build then restored the working state. The 116 are phase 2's 109 plus 7 phase 3 tests whose
  names match the filter: two in `test_duck_store.py` ("rf", "rid") and five
  `test_index.py::test_p1_planted_signatures` cases ("planted"). This was confirmed by collecting the
  same filter at `06cc826` in a temporary worktree (`109/286`). No new package README is needed,
  because phase 2 added modules only to `sim/`, whose README already covered it. The backfill adds
  the `nights=` option and the `planted` and `world_names` fixtures it left out. No code changes.
- Why: the exit check must be run exactly as SPEC §20 states it, so the filter cannot be narrowed.
  The extra tests pass and say nothing against phase 2. `sim/` and `config/` are byte-identical to
  `06cc826`, so every count, the data card and all nine figures came out identical. The figures
  match because phase 1's backfill committed the laptop renders (D-065).
- Consequences: none for later phases. The phase 2 gate in `docs/phases/gates.json` will also report
  116.

## D-067 · Phase 3 documentation backfill · 2026-10-28
- Context: `phase-auto backfill 3` reconstructs phase 3's documents (D-061, D-065 and D-066 did
  phases 0 to 2) and reruns its exit check on the dev laptop. Three things differ from phase 3's run
  at `e494995`:
  - the eval report is written as `reports/eval_2026-10-29.*`, because `write_reports` names it
    after the run's UTC date (00:07 UTC);
  - latency is much lower on the laptop (prefilter p95 15 ms against 83 ms);
  - `eval_recall_by_t.png` renders in a different typeface.
- Decision: `docs/phases/phase-03/PLAN.md` is marked "as built" and reconstructed from `e494995`,
  PROGRESS.md and D-046 to D-058. The exit check was rerun at HEAD (`53134b8`) after `make clean &&
  make data`, as phase 3's was, and today's output is recorded beside the original numbers. The new
  `eval_2026-10-29.md` and `.json` and the laptop render of the figure are committed. The original
  `eval_2026-10-28.*` files stay as phase 3's record. Every outcome in the new JSON except its
  latency fields was compared with the original, and all are identical. `features/README.md` and
  `match/README.md` are new, so every subpackage now has a README (D-061). The eval README gains two
  gotchas: report file dates are UTC, and the figure sets no font. No code changes.
- Why: the exit check must run as SPEC §20 states it. Committing its output keeps the tree clean for
  the autopilot gate (D-059) and keeps the evidence next to EXIT_CHECK.md. The figure follows
  D-065's precedent. Pinning a font is a code change, which a backfill may not make.
- Consequences:
  - D-057's prefilter shortfall was measured on the cloud sandbox. On the laptop where the
    autopilot runs, the Euclidean prefilter p95 is 15 ms, inside §10.9's 50 ms. D-059's "phase 4
    must speed it up" therefore does not apply there, though D-058's options may enlarge the
    candidate list and change that.
  - D-058 was rechecked with the same ranks, and phase 4 must still start there.
  - Follow-up: pin the font in `eval/report.py` together with `sim/figures.py` (D-065).
  - `scripts/check_targets.py` picks the newest eval JSON by modification time and requires it to
    be newer than the gate's start, so the committed `eval_2026-10-29.json` cannot stand in for
    phase 4's own run.

## D-068 · Fixed-unit window vectors and a wide candidate list (resolves D-058) · 2026-10-28
- Context: D-058. With per-window z-normalization the three planted P1 flights ranked 1,149 to
  1,194 of 1,882 earlier tracks for the live query at T+90, far outside the 50 candidates DTW
  sees. Planning found the normalization erases the orbit radius, speeds and altitude that make P1
  distinctive.
- Decision: `windows.normalize: fixed` divides each channel by a fixed unit,
  `features.channel_scales: [5.0, 10.0, 200.0, 30.0, 1.0]` (m/s, °/s, m, m, m/s), times its
  weight, with no centering. Then come the D-051 NaN fill, PAA and L2. `window` keeps phase 3's
  per-window z for comparison. `prefilter.k_windows` is 10,000 and `prefilter.candidate_tracks`
  500 (§6.5 says 200 and 50). Index and query share one function, so the recipe always matches.
- Why: in planning, the same-actor track was among the top 50 candidates for 91% of prober queries at
  T = 90 s (70% with per-window z). With 500 candidates the four 2026 P1 flights are candidates for
  the live query (prefilter ranks 5, 7, 122 and 314 at T+90). The partial BRAVO 2025-11-14 flight
  is a candidate at T+45 and T+60 but not at T+90. DTW plus fusion of 500 candidates
  costs about 80 ms at p95.
- Consequences: deviates from §9.3 (normalization "over the series being compared") for the
  prefilter vectors only; DTW keeps §9.3. `make index` must be rerun after a recipe change; D-075
  guards against a stale index. Window counts are unchanged (57,462 / 51,297 / 27,507). D-058 is
  resolved. The prefilter p95 is now 30 ms (15 ms with 200 windows), inside §10.9's 50 ms.

## D-069 · DTW details: relaxed ends, a speed-ratio warp, a dtaidistance quirk · 2026-10-28
- Context: §10.4 aligns tonight's W rows end to end with a 2W-row anchored segment and regresses
  the warping path for the pace. Neither worked as written.
- Decision:
  - Shape distance: §9.3 normalization of each series over itself, NaN filled (0 for a missing
    channel), banded C `dtw_ndim.distance` (window `int(0.25 × max(n, m))`), and **psi relaxation
    of the segment's two ends** (`(0, 0, m − n, m − n)` when the segment is longer).
    `d_norm = d / sqrt(n)`, `shape_sim = exp(−d_norm / τ)`.
  - Warp ratio: on the same alignment (full matrix), tonight's mean speed over the past flight's
    mean speed on the segment rows the path visits. §8.5 makes a warp w divide every speed by w,
    with geometry unchanged, so this ratio is w. Estimates outside 0.5 to 2.0 are not credible and
    become NaN. Text: k > 1.1 gives "flown X% slower" (X = round((1 − 1/k) × 100)); k < 0.9 gives
    "flown X% faster", the mirror formula.
  - It is computed for the top 20 fused matches only; the rest keep NaN (D-054).
  - `explain_alignment` (§10.4 step 6) wraps `subsequence_alignment` on raw `dist_target_m`, for
    phase 8.
  - The C extension is mandatory (`require_c`, `use_c=True` everywhere). LB_Keogh pruning is not
    built: 500 candidates take 80 ms at p95, and `lb_keogh` needs equal lengths.
- Why:
  - End to end, an exact time-warped copy of a flight scored *below* an unrelated flight at
    W = 120 (`test_relaxed_ends_rank_the_warped_copy_first`), which fails §20's "a time-warped copy
    of a flight scores high".
  - On real same-actor pairs of the training split, the path slope was off by 0.49 (median against
    truth), whatever the normalization (live-window σ, σ floored at the channel units, geometry
    channels only, whole tracks). The speed ratio was off by 0.091; it was chosen among five
    variants on the training split, and validation agrees (0.088). Orbits carry no timing
    information, and the best window often sits at another flight phase.
  - dtaidistance 2.5.1's C `warping_paths` with a `window` returns a paths matrix that differs from
    pure Python near the band edge (the distance is right). Without a window C equals Python,
    which `test_c_paths_match_python_without_band` checks.
- Consequences: deviates from §10.4 steps 3 and 5. Synthetic accuracy: within 0.2% at W = 120;
  at W = 60 up to 4.3% low, because a 60 s window holds less than one cycle of the orbit's speed
  wobble (the test allows 5%). P1's estimates stay weak: ALPHA-260303 reads 1.03 at T+90 against
  the planted 1.22, so the §1.2 "flown ~18% slower" caption does not appear yet. Phase 8's lens
  may revisit this with `explain_alignment`.

## D-070 · Settings are chosen on the training split only · 2026-10-28
- Context: the planning prototype looked at the month 13 to 18 queries and the demo; phase 4 must
  not tune on them.
- Decision: any choice among alternatives uses months 1 to 12 alone. The model is fitted on nights
  before 2026-01-01 and scored on the held-out nights 2026-01-01 to 2026-02-28 (prober and copycat
  queries). The criterion is Recall@5 at T = 120 s, with ties broken by candidate recall
  (D-078 adds MRR at T = 90 s for its one question). The shipped model is then refit on all of
  months 1 to 12. Pre-registered alternatives: prefilter scaling (fixed, dataset σ, per-window z),
  `candidate_tracks` (200, 500, 1,000) and the training T grid ({60, 90, 120} or {45, 60, 90,
  120, 180}). Defaults: fixed, 500, the wide grid. Nothing is special-cased for an incident,
  actor, base or the demo.
- Why: the demo and the §19 queries must stay honest measurements.
- Consequences: two questions were decided this way (D-078, and D-069's warp estimator). The
  defaults stand.

## D-071 · Partial live signatures · 2026-10-28
- Context: §10.5 says "live signatures are partial" but not what a live track knows.
- Decision: the query signature is `signature()` (§9.4) on the query's own features, its first
  radar point and its last point at or before T, and a sensor context bounded to T. RF and
  Remote ID detections, the track's own points and the other tracks' spans (the D-048 concurrency
  test) count only up to `until = first point + T`. A track that has not appeared by then cannot
  bearing-gate anything. Unknown fields fuse as 0.5. Candidate signatures are the stored ones
  (`tracks_before`, §11.3).
- Why: CLAUDE.md rule 3. Without the bound, the live track's RF family or Remote ID could come from
  after T.
- Consequences: at T+90 the live P1 loiter radius reads 250 m (the orbit has just begun), so
  `radius_sim` is low for every candidate. It reaches 187 m by T+120. A candidate that started
  before the query but was still flying contributes its full-track signature and later windows.
  That is allowed by rule 3 as written (filter on start), and it matters only for same-night eval
  and training pairs, never for the demo, whose candidates are all from earlier nights.

## D-072 · Two read-only `TrackStore` port methods · 2026-10-28
- Context: the matcher needs many candidates' features and a T-bounded sensor context. Through the
  existing port that is one round trip per candidate (50 calls take 76 ms) or SQL text in `match/`.
- Decision: `TrackStore.features_many(track_ids)` and
  `TrackStore.sensor_context_until(track_id, until) -> dict` (`rf_family`, `rid_serials`,
  `rid_operator_xy`). `DuckTrackStore` implements them by giving `rf_association`,
  `rid_association` and `sensor_context` an optional `until` bound (default None: phase 3's
  behavior and tests unchanged). The matcher caches candidate channels per process, since history
  features never change between index builds.
- Why: rule 6 (business logic depends on ports only), and speed: 17 ms per live query.
- Consequences: deviates from §4.1's port list. The KDB-X adapter (§22) must implement both.

## D-073 · Fusion training · 2026-10-28
- Context: §10.6 fixes the model but not the pair builder.
- Decision: `kairos_defense.eval.training` builds the pairs and is the only code that labels
  them with truth. It runs each query (history tracks, months 1 to 12) at T ∈ {45, 60, 90, 120,
  180} through the matcher's own `CandidateBuilder`: same prefilter, `start < q.start`, own
  incident excluded. The label is "same `actor_id`"; hobbyists, other probers and copycats are
  negatives. τ = median `d_norm` of the positives. The model is
  `LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000, C=1.0)` in
  `scoring.fusion.features` order, fitted on rows sorted by (query, T, candidate). The training
  hash is SHA-256 over keys, features and labels. Validation runs the same build on months 13 to
  18 and records pair counts, ROC AUC, log loss and prober Recall@5 at T = 120 s; it is reported,
  never used to choose. `models/fusion_v1.json` and `models/dtw_calibration.json` are both
  written, and only `created_at` changes between runs. `TrainSplit` makes the dates parameters
  for tests. Query kinds: D-078.
- Why: training and serving share code, so they cannot drift; determinism (CLAUDE.md rule 4).
- Consequences: 62 queries, 123,404 pairs (1,128 positive), τ 1.645, about 45 s on the laptop.
  Validation AUC 0.998, validation Recall@5 1.000. The coefficients are large (`tod_sim` +26,
  `rf_match` +19): probers keep schedules and radios and hobbyists do not, an honest signal in
  this synthetic world that is reported, not suppressed.

## D-074 · Explanations · 2026-10-28
- Context: §10.7 gives conditions and texts, not ties or values.
- Decision: a reason needs its §10.7 condition and a positive contribution `coef × x`. Reasons are
  ordered by contribution, at most three. The warp reason ranks with `shape_sim`'s contribution
  and needs a credible warp outside 0.9 to 1.1. Values come from the past flight's signature: its
  family, its approach bearing rounded to 5°, its radius rounded to 10 m.
- Why: a reason should never argue against the score it explains.
- Consequences: P1's top matches read "Same time of night; Same RF family (FAM-07); Same approach
  bearing (315°)".

## D-075 · Stale-index and missing-model guards · 2026-10-28
- Context: D-068 changed the vector recipe, and the autopilot gate reuses the build's `data/`
  without rerunning `make index`.
- Decision: `match.candidates.check_index` rebuilds the first window of each size of the earliest
  indexed track with the current configuration. It looks each one up by `window_id` (k = 1) and
  raises `IndexStale` ("index is stale: run `make index`") if a window is missing or more than
  1e-6 away. `DtwMatcher` and `kairos-defense models` call it. Without `models/fusion_v1.json` or
  `dtw_calibration.json`, `ModelError` says "run `make models`". A model whose feature order
  differs from `scoring.fusion.features`, or whose τ disagrees with the calibration, is refused.
  The CLI turns each into a one-line message and exit 1.
- Why: a stale index would give wrong numbers silently.
- Consequences: about 30 ms once per matcher. The test perturbs every stored vector, so it cannot
  pass by choosing a lucky probe.

## D-076 · Evaluation in phase 4 · 2026-10-28
- Context: §19.3's DTW lift needs a Euclidean Recall@5 to subtract, and §10.9's DTW latency is
  stated for 50 candidates.
- Decision:
  - `eval` and `match` default to `--method dtw`; `--method euclidean` still runs (§10.2).
  - **The lift is measured in one run**: the matcher returns the same candidates in prefilter
    order, the §10.2 baseline. New `Outcome` fields: `baseline_rank`, `baseline_copycat_rank`,
    `dtw_ms`, `candidates`. New metric keys: `recall_at_5_t120_baseline`, `dtw_lift`,
    `latency_dtw_p50_ms` and `latency_dtw_p95_ms` (over all 500 candidates, harder than §10.9's
    50). `dtw_lift` and `latency_dtw_p95_ms` are gated; the JSON gains `model_version` and
    `candidate_tracks`.
  - `live_top3_incidents` is an assertion for `dtw` (all three in the top 3, each with a score
    and a reason) and stays `info` for `euclidean`, which has no reasons.
  - D-056's question: the §19.4 5% rule stays as written, with no absolute floor. `gates.json`
    tolerates a non-zero `make eval`, and `check_targets.py` judges the targets.
  - The first `reports/baseline.json` is the DTW run's.
- Why: the same index and queries on both sides make the lift a clean comparison.
- Consequences: the in-run Euclidean Recall@5 is 0.478 (fixed vectors; phase 3's per-window z gave
  0.435). The lift over phase 3's frozen number would be +0.565.

## D-077 · Figure font pinned in `eval/report.py` · 2026-10-28
- Context: D-065 and D-067: the recall figure's bytes depended on the machine's default sans-serif.
- Decision: `plot_recall` draws inside `plt.rc_context({"font.family": "DejaVu Sans"})`;
  matplotlib bundles that font. The title names the method ("DTW + fusion").
- Why: the next change to `eval/report.py` was the moment D-067 asked for.
- Consequences: `sim/figures.py` still sets no font (D-065); phase 4 does not change `sim/`.

## D-078 · Phase 4 target miss: the live top 3; proposed fix registered before any tuning · 2026-10-28
- Context: the first full `make models && make eval` with the planned defaults (D-068 to D-073)
  meets every §19.3 phase 4 metric: Recall@5 1.000, DTW lift +0.522, copycat-first 0%, time to
  match 96%, end-to-end p95 146 ms. It misses one demo assertion: at T+90, P1-DELTA-260419 is
  first but P1-ALPHA-260303 is fifth and P1-ALPHA-260502 thirteenth, behind P3 flights. P3 flies
  RF family FAM-07 like P1, at the same time of night. The trained model gives `bearing_sim` a
  coefficient of −1.03 and `radius_sim` +0.001. P1's approach bearing (315°) is exactly what
  separates it from P3 here (`bearing_sim` 1.0 against 0.13 to 0.16).
- Diagnosis (training pairs only): with swarm-drone queries removed, the fit gives `bearing_sim`
  +2.65 and `radius_sim` +0.65. Same-team swarm drones in another swarm incident have mean
  `bearing_sim` 0.16 and `launch_sim` 0.02. One drone's approach and launch inside a formation are
  not traits of its team, yet the 87 to 132 swarm positives, upweighted by `class_weight="balanced"`,
  teach the linear model that a different approach bearing is normal for a true match. Swarm
  incidents are matched by their own choreography descriptors (§14, phase 9), and D-046 already
  notes that swarm drones' single-track targets are mixed.
- Proposed fix F1, registered here before it is evaluated: train the single-track fusion on prober
  and copycat queries only, keeping every candidate (swarm drones stay as negatives). This deviates
  from §10.6, which lists swarm drones among the queries.
- Selection rule (D-070's: the training split only, months 13 to 18 and the demo never consulted):
  refit both variants on nights 2025-03-01 to 2025-12-31 and evaluate on the held-out training
  nights 2026-01-01 to 2026-02-28, on answerable prober and copycat queries. F1 is adopted if it is
  no worse than the default in Recall@5 at T = 120 s and no worse in MRR at T = 90 s; otherwise the
  default stays and the miss is a soft gap (D-063). No other setting is changed in this step.
- Outcome: refit on 57 queries (nights 2025-03-01 to 2025-12-31), scored on the 11 answerable
  held-out prober and copycat queries (2026-01-01 to 02-28). Default: Recall@5 at T = 120 s 1.000,
  MRR at T = 90 s 1.000. F1: 1.000 and 1.000, with `bearing_sim` +2.13 instead of −1.63. F1 is no
  worse on both, so it is adopted: `kairos_defense.eval.training.QUERY_KINDS` is prober and
  copycat. The tie means the held-out split cannot tell the two apart. The choice rests on the
  diagnosis above, not on a measured gain.
- Result on the full data (`make models && make eval`): every §19.3 metric is unchanged (Recall@5
  1.000, DTW lift +0.522, copycat-first 0%, time to match 96%, MRR at T = 120 s up from 0.942 to
  1.000). At T+90 the top 4 are all P1 flights: DELTA-260419, ALPHA-260303, CHARLIE-260710,
  ALPHA-260502, each with "Same approach bearing (315°)" among its reasons. The P3 flights fall to
  fifth and below. The assertion still misses by one place: CHARLIE (planted as "weaker match on
  purpose") leads ALPHA-0502 by 0.80 in logit, 0.68 of it from `alt_sim`. Tonight's median
  altitude is 90 m; CHARLIE flew at 110 m and ALPHA-0502 at 118 m (§8.5's per-flight altitude
  band).
- A3 alternatives: the training T grid {60, 90, 120} ties the default on the held-out training
  nights (Recall@5 at T = 120 s 1.000, MRR at T = 90 s 1.000), so the default stays. Prefilter
  scaling and candidate count were not tried: the four 2026 P1 flights are already candidates at
  T+90 (prefilter ranks 5, 7, 122 and 314 of 500), so neither can change their fused order.
  Tuning stops here. The demo row is a soft gap under D-063, and REPORT.md shows the contribution
  breakdown. Nothing is special-cased for an incident, an actor or the demo.

## D-079 · Gate fix attempt 1: make the DTW shape informative; criterion registered first · 2026-10-28
- Context: the phase 4 gate (`gate-1.log`) passed everything except `demo:live_top3_incidents`:
  CHARLIE-260710 (#3) leads ALPHA-260502 (#4) at T+90, mainly on `alt_sim`. The shape term barely
  separates actors on the training pairs: median `d_norm` is 1.645 for same-actor pairs against
  1.689 for the rest. §9.3 z-normalizes each series over itself. In an orbit, distance to target,
  altitude and speed are nearly constant, so dividing by their tiny σ turns radar noise into
  shape. The prefilter had the same problem (D-058, fixed by D-068).
- Proposed alternatives, registered before evaluation:
  - `series`: the current §9.3 per-series z-normalization.
  - `floored`: per-series centering with σ floored at the channel's fixed unit (D-068's
    `channel_scales`), so a near-constant channel stays near zero instead of becoming noise.
  - `fixed`: raw / `channel_scales` × weight with no centering, as for the prefilter.
- Criterion (training split only; months 13 to 18 and the demo are not consulted):
  - Primary: on the held-out training nights 2026-01-01 to 2026-02-28, the pair-level ROC AUC of
    −`d_norm` (same actor against the rest) over prober and copycat queries at every training T.
    The shape term alone is what this change is meant to improve.
  - A variant is adopted only if it raises that AUC by at least 0.02 over `series`. It must also
    keep the fused model, refit on 2025-03-01 to 2025-12-31, no worse on the held-out Recall@5 at
    T = 120 s and MRR at T = 90 s (D-078's rule).
  - Among the variants that qualify, the highest AUC wins; otherwise `series` stays.
- This is a deviation from §9.3 for the DTW if adopted (D-069 kept §9.3 there).
- Outcome on the held-out training nights (AUC of −`d_norm`; fused Recall@5 at T = 120 s / MRR at
  T = 90 s): `series` 0.558 (1.000 / 1.000), `floored` 0.565 (1.000 / 1.000), `fixed` **0.786**
  (1.000 / 1.000). Only `fixed` clears the +0.02 bar, so `dtw.normalize: fixed` is adopted.
  Over all training pairs the AUC goes from 0.580 to 0.805, and the median `d_norm` is 2.23 for
  same-actor pairs against 3.47 for the rest (1.645 against 1.689 before). `floored` barely helps,
  which says the levels themselves (orbit radius, speed, altitude) carry the discrimination; this
  is D-068's finding again.
- Result on the full data (`make models && make eval`): Recall@5 1.000, DTW lift +0.522, MRR
  1.000, time to match 96% and copycat-first 0%, all unchanged. τ 2.227, `shape_sim` coefficient
  +6.81 (was +4.22), validation AUC 0.998. DTW p95 falls from 81 to 56 ms, end to end from 149 to
  125 ms. The demo row is not fixed: at T+90 DELTA #1, ALPHA-0303 #2, CHARLIE #3, a P3 flight
  (FOXTROT-251215) #4, ALPHA-0502 #5. ALPHA-0502 flew at 118 m against tonight's 90 m, and with
  fixed units that altitude gap now also lowers its shape similarity (0.418 against CHARLIE's
  0.459). The rule was registered first, so it decides; the demo is reported as observed, not
  used to reverse the choice.
- Consequences: deviates from §9.3 for the DTW shape distance. The warp alignment keeps
  `series`, because D-069's estimator was chosen with it. The §20 synthetic test also holds in
  `fixed` mode (`test_fixed_mode_scores_warped_copies_high`). `live_top3_incidents` stays a soft
  gap. The remaining cause is within-actor altitude spread: P1 draws each flight's altitude
  within 90 to 120 m (§8.5), and `alt_sim` uses a 30 m scale.

## D-080 · Gate fix attempt 2: a `target_match` fusion feature; criterion registered first · 2026-10-28
- Context: after D-079 the only gap is still `demo:live_top3_incidents`. §10.5's seven features
  never compare *what* a flight probed, yet the §9.4 signature stores `target_kind`, and it is very
  consistent within an actor on the indexed history (truth read in a diagnostic only): P2 flight
  line 12/12, P3 munitions 16/16, P5 HQ 12/12, P6 flight line 10/10, C1 fuel farm 15/15, P1 fuel
  farm 4/5, P4 fence 10/10, C2 fence 12/15. The fence is the fallback target of hobbyists (1,800
  of 1,898 tracks) and of a live track still inbound (D-046: the live P1 reads "fence" until
  about T+90), so it says nothing about the actor.
- Proposed alternative, registered before evaluation: an eighth feature, `target_match` = 1.0 when
  both signatures name the same non-fence target kind, 0.0 when they name different non-fence
  kinds, and 0.5 (unknown, as §10.5 treats unknowns) when either target is the fence. It is added
  to `scoring.fusion.features`, so the model's feature order changes and `make models` must be
  rerun. This deviates from §10.5's feature table.
- Criterion (training split only; months 13 to 18 and the demo are not consulted): refit both
  feature sets on nights 2025-03-01 to 2025-12-31 and score the held-out training nights
  2026-01-01 to 2026-02-28 (answerable prober and copycat queries, every training T).
  - Primary: mean average precision (MAP) of the same-actor candidates. It rewards ranking every
    true match above impostors and, unlike Recall@5 at T = 120 s and MRR at T = 90 s, is not
    already 1.000 there.
  - Adopt if MAP rises by at least 0.01, with Recall@5 at T = 120 s and MRR at T = 90 s no worse;
    otherwise the seven features stay.
- Outcome: fitted on 95,904 pairs from nights to 2025-12-31 (τ 2.258) and scored on 27,500
  held-out pairs (11 queries, 54 query-T groups with a same-actor candidate).
  - Seven features: MAP 0.9603, Recall@5 at T = 120 s 1.000, MRR at T = 90 s 1.000.
  - With `target_match`: MAP 0.9568, 1.000, 1.000. The feature's coefficient is **−0.91**.
  - Among held-out same-actor pairs, 306 have an unknown target match, 36 a match and 18 a
    mismatch. A partial query often still reads the fence, or a wrong asset, before its loiter
    settles (D-046), so a target mismatch is weak evidence against a match.
  - MAP falls, so the feature is **not adopted**. The seven §10.5 features stay; no code changes.
- Consequences: the gap stands. CHARLIE-260710 is a true P1 flight, and it is closer to tonight's
  flight on every measured dimension the training data supports: altitude 110 m against
  ALPHA-0502's 118 m (tonight 90 m), shape 0.459 against 0.418. Its "weaker on purpose" trait is
  its target (the flight line), which the training split says a partial-track matcher cannot use
  reliably. Tuning stops for this attempt.
