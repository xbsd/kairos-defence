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

## D-081 · Gate fix attempt 3: the live top-3 gap cannot be closed honestly at T+90 · 2026-10-28
- Context: the third gate (`gate-3.log`) again has one GAP, `demo:live_top3_incidents`.
  CHARLIE-260710 (planted "weaker on purpose": it orbits the flight line, not the fuel farm) is
  #3, and ALPHA-260502 #5. D-079 made the shape informative; D-080 showed a `target_match` feature
  hurts on the training split.
- Diagnosis (training queries, months 1 to 12, truth read in a diagnostic only):
  - Target. Among same-actor pairs where both targets are a named asset, all 48 mismatches come
    from partial queries whose target was **not yet its final one**: P5 reads flight line or
    munitions before HQ (23), P6 reads housing before the flight line (25). Once the partial target
    equals the final one, same-actor pairs agree 108/108.
  - Loiter radius. A partial track's radius differs from its own full-track radius by a median of
    1,415 m at T = 45 s, 1,116 m at 90 s, 894 m at 120 s and 275 m at 180 s. The loiter mask
    (slower than 1.2 × the median speed, within 600 m of the current target) catches approach
    seconds and transient targets until the orbit dominates the track.
  - The live P1 track reads the fence as its target until T+80 and the fuel farm from T+90, with
    its loiter direction unestablished until about T+200.
- Decision: no method change in attempt 3. The one trait that makes CHARLIE the weaker match is its
  target, and at T+90 the training split shows a partial track's target is not yet reliable
  evidence. A causal "settled target" rule would treat tonight's target as unknown at T+90 and
  leave the order unchanged. Weighting a target signal anyway, or the altitude feature less, only
  for this beat would be tuning toward the demo (D-070). On every dimension the training data
  supports, CHARLIE is closer to tonight's flight: altitude 110 m against ALPHA-0502's 118 m
  (tonight 90 m), shape 0.459 against 0.418.
- Consequences:
  - The gap goes to GAPS.md (D-063). All four top matches at T+90 are P1, each with a score and
    three reasons, which meets §1.2's acceptance text ("All three are actor P1 (any order)") in
    spirit but not `scenario_demo.yaml`'s exact incident list.
  - Follow-up for phase 7 or 8 (live replay and Match Explainer): partial signatures should mark
    target-dependent fields (target, loiter radius, the "Same orbit radius" reason) as unknown
    until the loiter at the current target is established. The radius error above makes today's
    early radius reasons unreliable; FOXTROT-251215's "Same orbit radius (~240 m)" at T+90 is one
    example. A target-aware re-rank can then be tested on the training split once a settled
    target exists.

## D-082 · Recall filter: §12.3 plus no look-ahead · 2026-10-28
- Context: §12.3's filter (the match's base, ±3 h around its flight, a 5 km box) bounds where and
  when a report is about the match, but not what existed tonight. An FAA summary can be filed days
  after its event, and a same-night match's paperwork may still be unwritten at the replay time.
- Decision: `recall.search.recall_filter` builds, from the match's **stored** signature:
  `installation_id = '<m base>' AND event_ts_ms BETWEEN <m.start − 3 h> AND <m.end + 3 h> AND x_m
  BETWEEN … AND y_m BETWEEN …` (a box around the match's target centroid and, when known, its
  launch point, widened by `recall.radius_m`), plus `AND event_ts_ms < <tonight's first contact>
  AND report_ts_ms <= <tonight's replay time>`. Installation ids are checked against a safe
  pattern before they enter the filter.
- Why: CLAUDE.md rule 3 applied to paperwork: a report filed after T did not exist at T.
- Consequences: `test_recall_never_returns_later_reports` checks every recalled report for every
  P1-night track at T = 120 s, and a tamper test checks that points after T change nothing. The
  `reports` table holds history reports only (D-041); live reports are appended by the phase 7
  replay.

## D-083 · Hashing embedder details · 2026-10-28
- Context: §12.1 says "tokens plus character 3-grams; each feature hashed (`stable_int`) to an
  index and a ±1 sign; sum; L2-normalize" without fixing the tokenizer or the sign bit.
- Decision: lowercase; tokens are `[a-z0-9]+`; features `t:<token>` and the 3-grams of `<token>`
  as `g:<gram>` (the prefixes keep a token and a gram apart); `h = stable_int(f)`, index
  `h % dim`, sign −1 when bit 32 of `h` is set; sum, L2-normalize, float32. A text with no
  feature is an all-zero row (never NaN). `stable_int` is memoized per feature. Name
  `hashing-v1-384`.
- Why: deterministic across runs and platforms (SHA-256), offline, and robust to blotter capitals
  and punctuation.
- Consequences: a pinned known answer (`test_hashing_known_answer`). Changing any of these rules
  changes every report vector; `check_reports_index` then asks for `make index`.

## D-084 · FastEmbed never downloads at runtime; `fetch-models`; reports-index guard · 2026-10-28
- Context: §12.1 allows FastEmbed "when the model is cached locally" and forbids downloads except
  by `kairos-defense fetch-models`. `fastembed` is not installed (optional extra), so its
  `local_files_only` keyword could not be checked against the installed version.
- Decision:
  - `FastEmbedEmbedder` imports `fastembed` lazily, **refuses to start unless a folder for the model
    already exists in `paths.cache/fastembed`** (a check in our adapter, independent of the
    package), and then constructs `TextEmbedding(model_name, cache_dir, local_files_only=True)`.
  - `fetch_model` (`kairos-defense fetch-models [--model M]`) is the only code path that downloads,
    into the same cache. Without the package it exits 1 naming `uv sync --extra fastembed`.
  - With `embeddings.provider: fastembed` and no cached model, `make_embedder` raises
    `EmbedderUnavailable` naming `fetch-models`; there is no silent switch to hashing (index and
    query vectors must come from one embedder).
  - New key `paths.cache: data/cache` (§5 lists `data/cache/`), resolved against the project root.
  - `recall.index.check_reports_index` raises `ReportIndexStale` ("run `make index`") unless the
    LanceDB `reports` table holds exactly the history reports (a search with k = n + 1 through
    the `VectorStore` port) and the lowest `report_id`'s stored vector is within 1e-6 (squared
    L2) of its text embedded now. `recall` and `eval` call it.
- Why: CLAUDE.md rule 5 (offline by default) and D-075's reasoning: a stale index would give wrong
  numbers silently.
- Consequences: tests use a fake `fastembed` module (no skip). If the installed `fastembed` rejects
  `local_files_only`, the cache check still keeps the no-download guarantee.

## D-085 · Hybrid search: native LanceDB, a deterministic tie-break, and the §12.5 fallback · 2026-10-28
- Context: CLAUDE.md's library note uses `tbl.create_fts_index("text")`, which LanceDB 0.40
  deprecates. Phrase queries ("County Rd 12") need token positions. LanceDB's `RRFReranker` sorts
  the fused rows by score alone and then cuts to k, so a tie at the cut follows merge order.
- Decision:
  - `LanceVectorStore.replace` builds the `reports` FTS index with
    `create_index("text", config=FTS(with_position=True))` (0.40's replacement; the default
    tokenizer lowercases, so blotter capitals match).
  - `LanceReportIndex` (the `ReportIndex` port): `hybrid()` runs LanceDB's native hybrid search with
    `ReportRRF`, a thin `RRFReranker` subclass (K = 60) that orders equal scores by `report_id`
    before LanceDB's k cut; `fts()` runs native FTS. Both pre-filter. Empty results keep the
    §7.5 columns.
  - If the native hybrid builder raises `AttributeError`, `TypeError` or `ValueError`, the adapter
    raises `NotImplementedError` (a builtin, so `ports.py` is unchanged). `recall.search` then runs
    `VectorStore.search` and `ReportIndex.fts` with the same filter and k and fuses them with
    `rrf_fuse` (Σ 1/(60 + rank), 1-based ranks; scores rounded to float32 as LanceDB stores them;
    ties by `report_id`).
  - Keyword text is sanitized to `[a-z0-9]+` tokens joined by spaces, so report text with colons
    or quotes cannot break the FTS parser. With no token left, the vector list alone is
    RRF-scored.
- Why: LanceDB 0.40 has native hybrid search (verified); the fallback keeps an older or newer
  LanceDB working. The tie-break makes the two paths identical row for row
  (`test_fallback_equals_native_hybrid` checks order and scores exactly on 5 queries over 40 rows).
- Consequences: a KDB-X adapter may implement `hybrid` natively or raise `NotImplementedError`.

## D-086 · Clue extraction and linking · 2026-10-28
- Context: §12.4 lists "road names from the `roads` table" and "`<color> <type>`" vehicles. The
  generator's paperwork also writes a bare "a motorcycle" (4 reports carry the clue
  `vehicle/motorcycle` in `clue_truth`).
- Decision:
  - Two clue types, each with a canonical value and its character span: `vehicle` from the
    generator's lexicons (`sim.lexicon.VEHICLE_COLORS` × `VEHICLE_TYPES`) with the color
    **optional**, and `road` from the `roads` table only ("Ridge Rd" and the other minor roads are
    false clues outside the gazetteer). Case-insensitive (D-040). **Deviation from the plan (A5),
    which said colored vehicles only**: the planned agreement test with `clue_truth` failed on the
    bare motorcycle.
  - `report_clues` (§7.2 DDL) is written by `make index` from the same function: one row per
    distinct (report, type, value). Spans are recomputed from the text when shown.
  - Linking, among the reports recalled for the top 3 matched incidents: a clue is linked when the
    same (type, value) appears in another report recalled for another matched incident ("white
    pickup also appears in reports of P1-ALPHA-260303."), or when it is a road that crosses
    tonight's predicted zone ("County Rd 12 runs through tonight's predicted zone."). A report
    recalled for two matches does not link with itself.
- Why: the agreement test against the generator's truth is the strongest check available, and it
  holds exactly on the full data (82 of 82 vehicle and gazetteer-road clues).
- Consequences: the UI (phase 8) gets spans and link sentences from `RecallResult.to_dict()`.

## D-087 · Forecast details (§13) · 2026-10-28
- Context: §13 leaves open which matches count as "known recovery", which alignment gives j*, and
  where the matcher's work is reused.
- Decision:
  1. Step 1 walks the fused ranking and keeps the first `top_k` matches whose stored signature has
     a recovery point **and whose flight had ended by tonight's replay time** (`end_ts <= until`;
     a history flight still in the air at T has no known recovery yet: rule 3).
  2. Step 2: j* is the segment row paired with tonight's last row on `dtw_rerank.warp_path`, with
     relaxed ends and **the shape distance's scaling** (`dtw.normalize: fixed`, D-079), on the
     match's anchored segment; `j*_track = lo + j*`. **Deviation from the plan (A6)**, which named
     the warp ratio's §9.3 per-series z: on an exact copy (tonight = rows 100 to 159 of a flight),
     that alignment put j* at row 164, because a 60 s window and a 180 s segment z-normalize
     differently; the shape's fixed scaling puts it at 159, also with radar-like noise. j* moves
     only the exit path: the center uses recovery points alone.
  3. Step 3: the remainder is the match's `track_features` `(x_rel_m, y_rel_m)` after `j*_track`,
     gap and NaN rows dropped, ending at the stored recovery point.
  4. Step 4: rotate the remainder clockwise by `wrap180(tonight − match approach)` when its size
     exceeds 30°; no rotation when either approach is unknown. Anchor: D-090.
  5. Step 5: weights are the fused scores (equal weights if they sum to zero); radius =
     max(150, 1.5 × weighted RMS distance to the center).
  6. Step 6: the top analog's mapped remainder, resampled to 60 points by arc length.
  7. Step 7: roads of tonight's region whose line intersects the circle.
  8. `None` when no match qualifies.
  - `MatchResult` gains optional `signature` (the query's partial signature) and `signatures`
    (the candidates' stored signatures), filled by the DTW matcher from `Candidates`; the
    forecast and recall reuse them, and read them through the ports when absent (Euclidean).
  - `dtw_rerank.warp_path` gains optional `mode` and `scales` (default `series`, so the warp ratio
    is unchanged).
- Why: the plan's alignment failed its own known-answer test; the shape's scaling is the §10.4
  path the score comes from.
- Consequences: `test_aligned_index_on_a_shifted_copy` and `test_top_k_counts_only_known_recoveries`
  (which also checks the end-time rule).

## D-088 · Evaluation of phase 5: linkage, forecast error, demo rows · 2026-10-28
- Context: §19.3 defines report linkage ("share of true clue-bearing reports of matched incidents
  retrieved in the top 5") and forecast error (median and P80 at T = 90 s) loosely.
- Decision:
  - Report linkage: answerable prober queries at T = 120 s; the top 3 distinct matched incidents
    of the fused ranking; *relevant* = that incident's reports with at least one
    `clue_truth.is_true` clue, filed by the replay time; *retrieved* = relevant reports in the
    recall top 5 for that match with tonight's default query. `report_linkage` = Σ retrieved /
    Σ relevant, reported with both counts.
  - Forecast error: the §13 center to `track_truth.recovery_{x,y}_m` (truth, eval only), at
    T = 90 s (gated) and 120 s (information). A query without a forecast counts as an infinite
    error (a percentile next to it is infinite, never NaN). Keys: `forecast_median_t90_m`,
    `forecast_p80_t90_m`, `forecast_queries_t90`, `forecast_missing_t90`, the same at 120, and
    `report_linkage`, `report_linkage_retrieved`, `report_linkage_relevant`.
  - Labelling lives in `eval/downstream.py` and runs after the ranker's timing, so the §10.9
    latency keys keep their meaning. New report-only keys: `latency_forecast_p50/p95_ms` and
    `latency_recall_p50/p95_ms` (per matched incident). Copycat queries are not labelled.
  - Demo rows: `live_rank1_report_for` (live query at T+120: the expected incident is among the
    top 3 matched incidents and its recall rank 1 is its own report) and `forecast_error_max_m`
    (live forecast at `forecast_at_s` = T+105 within 400 m of the true recovery). Both assert under
    DTW and are `info (Euclidean baseline)` under `--method euclidean`, as D-076 did for the top 3.
  - `GATED` adds `report_linkage` (higher is better) and `forecast_median_t90_m` (lower is
    better); keys missing from an older `baseline.json` are skipped. `PENDING` keeps only
    `swarm_top1`.
  - `kairos-defense eval` refuses a missing or stale reports index (D-084).
  - `eval/truth.py`: `track_truth` adds `recovery_x_m`, `recovery_y_m`; new `clue_truth(app)`.
- Why: per-incident labels make the metric auditable; a missing forecast must not look good.
- Consequences: linkage is close to trivial on this data. Within each match's filter window no
  incident has more than 4 reports (k = 5), so every relevant report reaches the top 5 once the
  filter admits it. REPORT.md says so; the DELTA rank-1 beat rests on the same fact (D-011: DELTA
  has a lone report in its window).

## D-089 · Index build wiring for reports · 2026-10-28
- Context: §12.2 rebuilds the `reports` table on `make index`.
- Decision: `kairos-defense index` runs `features.build.build_index`, then
  `recall.index.build_reports_index`, which (like D-053) uses the adapters directly: history
  reports through `DuckTrackStore.sql`, `report_clues` through `write_table` (it joins
  `DERIVED_DDL`), LanceDB `reports` through `replace` (with its FTS index). Reports are sorted by
  `report_id`; nothing is random. The `p1_index` test fixture and the slow `full` fixture build it
  too.
- Why: one command builds every derived table, as the Makefile promises.
- Consequences: about 0.1 s for 956 reports with the hashing embedder.

## D-090 · Forecast anchor while tonight's target is unsettled; rule registered before measuring · 2026-10-28
- Context: §13 step 4 adds each analog's target-relative remainder to "tonight's target centroid".
  Every prober query reads its target as the fence pseudo-asset until its loiter settles (D-046,
  D-081), while an analog's stored recovery point is relative to its own final target (a P3 flight:
  the munitions area). Added to tonight's fence centroid, such a vector lands 0.9 to 1.4 km off.
- Registered here, in the phase 5 build, before any build code that could measure it:
  - New key `forecast.anchor: target | match_kind`. Initial value `target` (§13 as written).
  - `match_kind`: when tonight's target is the fence pseudo-asset and the analog's stored target
    kind is a named asset (not the fence) that exists at tonight's installation, add the analog's
    relative vectors to tonight's asset of that kind. In every other case both modes are
    identical. Nothing is special-cased for an incident, actor, base or the demo (D-070).
  - Criterion: prober queries on the training nights 2025-03-01 to 2026-02-28 (answerable, as
    §19.1 defines them, but on months 1 to 12), T = 90 s, the shipped model
    (`models/fusion_v1.json`). Adopt `match_kind` if and only if its median forecast error is at
    least 50 m lower than `target`'s **and** its P80 is not higher. Otherwise `target` stays.
  - The comparison is `uv run python -m kairos_defense.eval.forecast_choice`; it prints both modes
    and writes `reports/forecast_choice.json`.
- Disclosure: the phase 5 plan (fact 5) already measured both modes on the training split with a
  scratch script (median 502 m against 311 m, P80 1,000 m against 492 m), so the verdict this rule
  would give was known when it was written. The rule is the plan's A9 unchanged; the build reruns
  it with the shipped code and records the result below, whatever it is. The plan also looked at
  the evaluation queries and the demo under the as-written mode (fact 4); that is not an input to
  this rule.
- Outcome (build step 12, `uv run python -m kairos_defense.eval.forecast_choice`, shipped model
  `418c5edf`, 36 answerable prober queries on the training nights, none without a forecast):
  - `target`: median 502 m, P80 1,000 m;
  - `match_kind`: median 311 m, P80 492 m.
  - The median is 191 m lower and the P80 lower, so by the rule **`match_kind` is adopted**:
    `config/scoring.yaml` ships `forecast.anchor: match_kind`. The result is in
    `reports/forecast_choice.json`. This is the planning number of fact 5, reproduced by the
    shipped code.
- Consequences: a deviation from §13 step 4 only while tonight's target reads the fence. The demo
  is unaffected: the live target is BRAVO's fuel farm from T+90 (D-046), so both modes give the same
  live forecast at T+105 and T+120. REPORT.md gives both modes' month 13 to 18 numbers for the
  record; they were not used to choose.

## D-091 · CLI shapes for `forecast`, `recall` and `fetch-models` · 2026-10-28
- Context: §20 names `kairos-defense recall …` and `forecast --incident <id> --at <s>`.
- Decision:
  - `forecast --incident ID --at S [--track T] [--method dtw|euclidean]` prints tonight's target,
    the center (region meters, and "2,164 m at 320° (northwest) of BRAVO-fuel_farm"), the radius,
    the anchor mode, an analog table (incident, score, own recovery, rotation, anchor, j*, mapped
    recovery), the exit path's ends and the roads crossing the zone.
  - `recall --incident ID --at S [--track T] [--matches 3] [--k 5] [--query TEXT] [--method …]`
    prints tonight's keyword text and the forecast zone, then per matched incident a table (rank,
    report, source, grade, local event time, score, text with clue spans underlined and linked
    spans bold) and the link sentences.
  - `fetch-models [--model M]`: D-084.
  - Fix-it exits (exit 1): unknown incident or track, unknown method, missing models, stale or
    missing index, missing or stale reports index, DTW unavailable, embedder unavailable.
  - The three commands live in `cli_recall.py` and are registered on the Typer app by `cli.py`;
    shared helpers are looked up on `kairos_defense.cli` at call time, so tests that patch
    `cli._load_config` cover them. `cli.py` stays under 400 lines.
- Why: the CLI is the phase 5 demo surface until the UI exists; it never reads truth, so it prints
  no error.
- Consequences: the agent tools `recall_reports` and `forecast_recovery` (phase 9) wrap the same
  functions.

## D-092 · Where the case-memory code lives · 2026-10-28
- Context: SPEC §5 lists `memory/ledger.py` as the ledger writer; CLAUDE.md rule 6 ("I/O lives in
  adapters under `kairos_defense.store`") and D-053 put DuckDB code in `store/`.
- Decision: the DuckDB adapter `DuckCaseMemory` (DDL, lock, reads, inserts) is
  `store/ledger_duck.py`; the §15.1 DDL and macro are `store/ddl.py` (`LEDGER_DDL`,
  `LEDGER_ASOF_MACRO`, verbatim). `memory/ledger.py` keeps the store-free parts: event validation,
  `seal` (seq, `recorded_at`, hash) and `verify_rows`. Snapshots, diffs, delta, seed, actions and
  evidence are pure functions over the `CaseMemory` port.
- Why: swapping in `KairosCaseMemory` (§22) replaces one adapter.
- Consequences: `store` imports `memory` (adapter depends on domain), never the reverse.

## D-093 · `CaseMemory` port additions and the typed `CaseSnapshot` · 2026-10-28
- Context: §4.1's `CaseMemory` has `append`, `as_of`, `diff`, `verify_chain`; seeding 4,681 rows
  needs one atomic transaction, and delta, valid time and evidence need the rows.
- Decision (as D-072 did for `TrackStore`): add `append_many(events) -> list[int]` (validated,
  sealed and inserted in one transaction, all or nothing) and `events(after=None, until=None)`
  (rows with `after < recorded_at <= until`, seq order, `object_json` parsed). `CaseSnapshot` gets
  typed fields (`exists`, `status`, `founder`, `members`, `links`, `pending`, `claims`,
  `contradictions`, `decisions`, `exports`, `reports`, `events`, `head_seq`, `head_hash`) and
  `to_dict()` (JSON-safe, ISO `Z`); the unused `state` placeholder is gone.
- Why: a future adapter implements one read; everything else stays pure.
- Consequences: phase 7's `GET /api/cases/{id}` and phase 9's `as_of_view` serve `to_dict()`.

## D-094 · Ledger event conventions and actor permissions · 2026-10-28
- Decision: the event table in `src/kairos_defense/memory/README.md` (one row per §15.2 type:
  `recorded_at`, `case_id`, `subject_id`, `object_json`, valid time, actor). Times are naive UTC.
  Rules:
  - members are the founder (`case_opened`) plus subjects of active `link_approved` rows;
    `link_approved` names its proposal in `object_json.proposal_seq` (an approval is not a
    retraction); a proposal is pending while active, undecided and not about a member;
  - status: `unknown` before `case_opened`; `closed` after an active `close` until a later
    `reopen`; `escalate` and `notify_law_enforcement` do not change it; linking never reopens;
  - claims are active assessments of members valued by `label`; a contradiction is two active
    claims on the same subject and predicate with different values, never resolved automatically;
  - a row touches a case if its `case_id` is the case, its incident (subject, or a report's
    `incident_id`) is a member, or it supersedes a row that touches;
  - actors (rule 8): `generator` writes the seeded types and `claim_retracted`; `system` writes
    `incident_recorded`, `report_recorded`, `evidence_exported`, `model_registered`;
    `matcher@<v>` and `agent:<m>` write **only** `match_proposed`; `analyst:<h>` writes
    assessments, cases, links, retractions and decisions;
  - ids match `^[A-Z0-9][A-Z0-9-]*$` and case ids `CASE-<founder>` (rule 9: a person's name
    cannot be a subject); handles match `[a-z0-9_.-]{1,32}`; `link_rejected` supersedes a
    proposal, `claim_retracted` an assessment, link or decision, and a row can be superseded once.
- Why: §15.2 names the fields but not their values; these are the simplest that serve §15.4.

## D-095 · Canonical JSON and chain details · 2026-10-28
- Decision: §15.3 as written, plus: `object_json` is hashed as a parsed object and stored as its
  canonical text; timestamps `%Y-%m-%dT%H:%M:%S.%fZ` (always 6 digits); floats rounded to 9
  decimals **before storing**, so a round trip recomputes exactly, and `-0.0` becomes `0.0`; NaN
  and infinities raise (callers map them to null: `Match.warp_ratio` is NaN beyond the top 20);
  numpy scalars become Python numbers. `seq` starts at 1, genesis `prev_hash` is 64 zeros. The
  writer stamps `recorded_at = max(clock, head)` (D-010); every event carries a clock.
  `verify_rows` returns the first expected seq whose row is missing, does not link, does not
  recompute, or is recorded before its predecessor; a deleted middle row is reported at its own seq.
- Consequences: a truncated tail is invisible to the chain alone; an evidence package's head (and
  phase 7's `ledger` stream) catches it. Documented in the README.

## D-096 · What the seed contains · 2026-10-28
- Decision: every history event recorded **strictly before the live incident's first contact**
  (2026-08-29 02:40:06 UTC): 1,866 incidents, 949 reports, 1,864 assessments. The 29 later
  history events would be look-ahead at demo time; leaving them out also keeps the replay clock
  ahead of the chain head. Live incidents are not seeded.
- Planted cases come from the scenario: each `p1_flights` entry with an `assessment` gets
  `case_opened` (`CASE-<incident>`) and `decision_recorded {decision: close, rationale: "assessed
  <label>", by: <author>}` at the generator's assessment time, actor `generator`. Only the
  base-side fields of the generator's assessment row are used (label, author, assessed time),
  never P1 membership as a label. Missing row → `SeedError` naming `make data`.
- Order: `(recorded_at, type rank, subject_id)` with incidents, reports, cases, assessments,
  decisions; the planted trio shares one rank so nothing recorded at the same instant can split
  it: case, assessment, decision at 09:10 local (D-011). Reads go through `TrackStore.sql` only.
- Outcome: 4,681 rows, seeded in 0.14 s on the laptop; deterministic head
  `a361b4bf…5e923`.

## D-097 · Live proposals and analyst decisions · 2026-10-28
- Context: §15.6 says both "only when the top-3 set changes or a score moves by more than 0.05" and
  "a proposal already in the ledger for the same query incident and top-3 set is not appended".
- Decision: `propose_matches` appends a batch (one `match_proposed` per top-3 match, sharing `top3`
  and `recorded_at`) unless an earlier batch for the same query **and case** has the same top-3
  set with every score within 0.05. A re-run or seek back appends nothing; a changed set or a real
  score move appends. `register_model` writes once per (version, sha256). `decide_link` accepts any
  active, undecided proposal for the case, **whether or not its incident is already a member** (the
  founder can be confirmed; it stays one member); errors `ProposalNotFound`, `WrongCase`,
  `ProposalAlreadyDecided`. `open_case` refuses an existing id.
- Consequences: which case a live proposal targets, and opening cases from the UI, are phase 7/8
  choices.

## D-098 · The terminal demo · 2026-10-28
- Decision: `memory demo [--at 90] [--approve] [--analyst demo] [--case …] [--scratch …]` copies the
  seeded ledger to `data/cache/memory_demo.duckdb` (ATTACH read-only, rows unchanged, head checked),
  records tonight's incident at first contact, registers the model, proposes the **real**
  `DtwMatcher` top 3 at T+90 into the planted case and, only with `--approve` (rule 8), approves
  them. "Known then" is the case's `case_opened` time (09:10 local); "known now" is the scratch head.
  `data/memory.duckdb` stays at seed state.
- Outcome: the shipped model proposes DELTA, ALPHA-260303 and CHARLIE-260710 (the accepted phase 4
  gap, D-081), so the demo links CHARLIE rather than ALPHA-260502. The SPEC unit test uses the
  scenario's three ids with hand-written proposals and does not depend on the matcher.

## D-099 · Evidence packages · 2026-10-28
- Decision: §15.7 files (`case.json`, `case.html`, `pubkey.pem`, `manifest.json`, `manifest.sig`),
  format `kairos-evidence/1`. `export_evidence` raises `ApprovalRequired` unless `approve=True`
  and then writes and appends nothing. `case.html` is self-contained (no scripts, no external
  references; one PNG map inlined as base64, DejaVu Sans, `metadata={"Software": None}`, colors
  from the validated dataviz palette with direct labels). The export appends `evidence_exported`
  after writing, so the package records the head before its own export event.
- Signing key: `signing.key_path`, PKCS8 PEM, created on first use with mode 0600 from the OS
  CSPRNG, never the seeded generator: rule 4 governs the generated data, and a key derived from a
  public seed would be forgeable. The seed, `case.json` and `case.html` are deterministic;
  `pubkey.pem`, `manifest.json` (it lists the key's hash), `manifest.sig` and the
  `evidence_exported` row depend on the key. `signing.enabled: false` writes an unsigned package
  that verification FAILs.
- Verification: files (hashes, nothing extra), signature (with the key fingerprint; `--pubkey`
  pins the expected key), chain continuity of the included rows and head, and with a ledger: every
  row equals the ledger's, the head still exists there, the ledger chain verifies. A missing or
  locked ledger is SKIP, not FAIL.

## D-100 · CLI shapes for the phase 6 commands · 2026-10-28
- Decision: `memory seed|reseed|verify|show|delta|demo`, `export`, `verify-evidence` (shapes in
  `src/kairos_defense/README.md`). `reseed` checks the file lock, seeds `<memory>.reseed.tmp`,
  verifies it, closes it (DuckDB checkpoints on close), removes stale WAL files and `os.replace`s.
  CLI times must carry `Z` or an offset (naive times exit 1 with the hint); output shows the case's
  local time and UTC. `export` without `--approve` exits 1 before opening anything.
- Deviation from the plan: three modules, not two. `cli_memory.py` (seed, reseed, verify, show,
  delta, helpers), `cli_memory_demo.py` (demo, export, verify-evidence) and `cli_memory_view.py`
  (tables), so each stays well under 400 lines. `cli.py` is 370 lines.

## D-101 · Shift delta and case diff groups · 2026-10-28
- Decision: `delta` groups rows in `(since, until]` into `incidents`, `reports`, `proposals`,
  `links_approved`, `links_rejected`, `assessments_added`, `assessments_retracted`, `retractions`
  (a retracted link or decision), `contradictions_opened` (present at `until`, absent at `since`,
  keyed to the claim that opened it), `decisions` (including `case_opened`), `exports` and
  `models`. The installation filter keeps a row when the base of its subject incident, its query
  incident, its report or its case's founder is the installation; `model_registered` is dropped
  when filtering. `case_diff` groups the rows touching the case's members as of t2 into
  `members_added` (with `new_member`), `proposals`, `claims_added`, `claims_retracted`,
  `contradictions`, `decisions`, `exports` and `facts` (incidents, reports, rejections and the
  models its proposals used).
- Deviation from the plan: `retractions` and `models` are extra delta groups (a retracted link is
  not an assessment; the plan's evidence named the model registration), and `case_opened` sits
  under `decisions` in both.

## D-102 · `guard.refuse_truth` for the ledger copy · 2026-10-28
- Context: `DuckCaseMemory.copy_from` reaches another file through DuckDB `ATTACH`, which bypasses
  `connect_app_db`; the truth-isolation scan forbids the substring `truth_path` outside `eval/`
  and the guard, so the adapter cannot call `is_truth_path` itself.
- Decision: `store/guard.py` gains `refuse_truth(path, app)` (raises `TruthAccessError`), which
  `connect_app_db` now calls too; the adapter calls it before `ATTACH` and on open. The scan is
  unchanged. Test: `test_copy_from_refuses_truth`.

## D-103 · Live scratch tables in their own file · 2026-10-29
- Context: §16.2 records each replay tick into `live_points` and `live_rf`; DuckDB allows one
  writing process per file (D-010), and the CLI must keep reading the main database while
  `make demo` runs.
- Decision: new key `paths.live: data/live.duckdb` (the distinct-files validator now covers four
  files). Tables `live_points`, `live_rf` and `live_rid` (Remote ID detections are detections too)
  with exactly the §7.1 columns of `track_points`, `rf_detections` and `remote_id`. The API opens
  `data/kairos_defense.duckdb` read-only. Each WebSocket session keeps a high-water mark: a tick
  writes the detections in (mark, clock]; a seek forward writes the skipped ones in one batch; a
  seek back writes nothing. `replay --reset` and `POST /api/admin/reset` empty only `live_*`.

## D-104 · Live ports and adapters · 2026-10-29
- Decision: `ports.py` gains `IngestStat`, `LiveSink` (`append`, `count`, `reset`) and
  `ResultCache` (`get`, `put`, `clear` of named JSON documents). Adapters:
  `store/live_duck.py` (`DuckLiveSink`, through `connect_app_db`) and `store/live_cache.py`
  (`FileResultCache`, atomic writes under `data/cache/live/<incident>/`, strict JSON). The reseed
  core moved from `cli_memory.reseed_cmd` to `store/ledger_duck.reseed_ledger` (plus
  `check_unlocked`), shared by the CLI and `POST /api/admin/reseed`; behavior unchanged. Only
  `api/services.py` and the CLI construct adapters (rule 6).
- Found while building: DuckDB 2.0 refuses `register()` while a previous result is not fully
  fetched (`fetchone()` leaves it open), so the sink uses `fetchall()` throughout.

## D-105 · The live loop, its schedule and its cache · 2026-10-29
- Decision: reruns at `min_track_s, min_track_s + rerun_every_s, …` (45, 50, …, 515 for BRAVO:
  95). Between reruns the latest rerun at or before the second is current (REST reports the second
  it used). A result holds `t_s`, `model_version`, the top 10 matches (§10.8 fields plus `rank`,
  `local_start` and ISO `start_ts` with `Z`), `forecast`, `recall` (top 3 distinct incidents),
  `dtw` (the top match's lens on `dist_target_m`), `target_asset_id` and `elapsed_ms` measured
  when computed; a cache hit adds `cached: true` and keeps the original `elapsed_ms` (rule 10).
  Features at every whole second come from `query_at(points ≤ s)`. `replay --precompute` fills
  `t0045.json` … and `features.json`; the manifest fingerprint is the SHA-256 of the model and
  calibration file bytes, the scoring and embeddings config, the incident's point count and last
  time, the `track_signatures`, `track_features`, `reports` and `report_clues` counts and
  `CACHE_FORMAT`. A loop that finds another fingerprint clears the cache and starts a fresh
  manifest. The swarm incident streams detections only (`matching: false`; swarm matching is
  phase 9).
- Deviation from the plan: the fingerprint counts `track_features` instead of LanceDB
  `flight_windows` (the vector port has no count; the windows are built from those rows).

## D-106 · Which case receives live proposals · 2026-10-29
- Decision (left open by D-097): the case, as known at the replay clock, whose founder or member is
  the best-ranked top-3 incident that belongs to any case (ties: earliest opened). For BRAVO that
  is `CASE-P1-DELTA-260419`. Before the first proposal the session records tonight's incident
  (`incident_recorded`, actor `system`, valid from its start) and registers the model
  (`model_registered`, SHA-256 of `models/fusion_v1.json`); both dedupe, and the check reads the
  ledger rows, so it holds after a reseed. Proposals go through `propose_matches` (§15.6 dedup),
  actor `matcher@<version>`, clock = start + t_s. No case means no proposal and `case_id: null`.

## D-107 · Stream protocol details · 2026-10-29
- Decision, beyond the §16.3 fields (all present): `hello` adds `region_id`, `tracks`, `is_swarm`,
  `matching`, `min_track_s`, `rerun_every_s`, `utc_offset_hours` and `playing: false` (the server
  starts paused at T+0). `clock` adds `seeked`; after a seek or reset the server sends `clock` with
  `seeked: true`, then the detections and features of the last 120 s and the current result. `point`
  adds `incident_id`; `rf` adds `band`; `rid` adds `t_s` and the drone position; `features` adds
  `track_id`, `target_asset_id`, `heading_deg`; `match` adds `cached`, `case_id`, `query_track`,
  `target_asset_id` and per match `rank`, `local_start`, `proposal_seq`, `decision`,
  `memory_status`; `dtw` adds `shape`, `overlap`, `warp_text`; `recall` reports add ISO `event_ts`.
  Speed is 1, 2 or 5; anything else is a recoverable `error`. `dtw` and `recall` are sent only when
  their content hash changes; a `dtw` request is always answered. Every ledger append anywhere is
  broadcast as `ledger`.
- Deviation from the plan: play and pause answer with a plain `clock` (no `seeked`, no catch-up),
  because the position does not change.

## D-108 · REST details · 2026-10-29
- Decision: extra routes `GET /api/health`, `GET /api/ledger/tail?n=12`, `GET /api/ledger/{seq}`.
  Times need `Z` or an offset (naive is a 422, as in the CLI); `as_of`, `t2`, `until` and the link
  `clock` default to the ledger head. Errors: unknown proposal, case or incident 404; wrong case or
  already decided 409; evidence without `approve: true` 400 (nothing written). The evidence POST
  streams NDJSON: one `file` line per file as it is written and hashed (`export_evidence` gained a
  `progress` callback; five files), then `done` with the verification checks. `GET
  /api/cases/{id}/graph` returns case, incident, report and assessment nodes and `member_of`,
  `proposed`, `report_of` and `assessed` edges (`memory/graph.py`). No authentication (§2); the
  server binds 127.0.0.1 by default.

## D-109 · Coordinates for the theater · 2026-10-29
- Decision: the API sends region-frame meters (the database convention); the scene adds the
  installation origin and the web maps `x = x_m − ox`, `z = −(y_m − oy)`, `y = alt_m`. Roads are
  clipped and parks kept within 6 km of the origin. The radar shadow is the world config's terrain
  mask sector, out to the radar's range, minus the fence buffered by `beyond_fence_m`
  (configuration, not truth). Asset heights by kind are web presentation constants.

## D-110 · Concurrency in the API · 2026-10-29
- Decision: one re-entrant lock guards the read-only main store, LanceDB, the matcher and recall;
  the ledger (`DuckCaseMemory`) and the live sink keep their own locks; when two are held the store
  lock is taken first. Sessions run `handle` and `step` in Starlette's thread pool; REST handlers
  are sync. No DuckDB connection is used by two threads at once.
- Deviation from the plan: locks instead of two single-thread executors (same guarantee, less
  plumbing). A reseed takes the store lock, then the memory lock, closes the ledger, rebuilds and
  reopens it; the wrapper (`PublishingMemory`) swaps its adapter under the same lock.

## D-111 · CLI shapes for `api` and `replay` · 2026-10-29
- Decision: `kairos-defense api [--host 127.0.0.1] [--port 8000] [--static DIR] [--reload]
  [--dump-openapi PATH] [--memory PATH] [--live-db PATH] [--reseed]`; `--reload` runs uvicorn with
  `api.app:factory` and passes options through `KD_*` variables. `kairos-defense replay
  [--incident] [--precompute] [--force] [--reset] [--api URL]` lists live incidents (duration,
  detections, reruns, cache state) without a flag. `replay --reset` and `memory reseed` try the
  file first; when DuckDB reports it locked they `POST` to the loopback API (stdlib `urllib`,
  loopback hosts only) and say so; both exit 1 if nothing answers. The new commands live in
  `cli_live.py`.
- Not in the plan: the API seeds an empty or missing ledger at startup (logged), so a fresh
  checkout serves without a separate `memory seed`.

## D-112 · Web foundation · 2026-10-29
- Decision: an in-house history-API router (`app/routes.ts`, `app/Link.tsx`); routes `/`
  (redirects to the first live single-track incident), `/live/:incidentId`, and `/explainer`,
  `/cases`, `/swarm`, `/evidence`, `/delta`, `/eval`, which say in one sentence which phase builds
  them. FastAPI serves `index.html` for any other non-`/api`, non-`/ws`, extension-less path.
  Vanilla Zustand stores (`replayStore`, `matchStore`, `caseStore`, `uiStore`) are written outside
  React by `state/dispatch.ts`; buffers are mutated in place with a `version` counter; the theater
  reads `getState()` in `useFrame`; DOM panels use `useThrottledStore` (≤ 10 Hz). The analyst
  handle is `demo`. The memory rail holds only the match list in phase 7. Bloom and vignette only;
  film grain waits for phase 8. ESLint bans `setInterval`; the stream's reconnect uses
  `setTimeout`. Canvas and 3D colors are read from `tokens.css` at runtime (`theme/colors.ts`), so
  the tokens stay the only vocabulary.

## D-113 · Test and evidence plumbing · 2026-10-29
- Decision: Playwright's `webServer` starts `kairos-defense api --static web/dist --port 8765
  --memory data/cache/e2e/memory.duckdb --live-db data/cache/e2e/live.duckdb --reseed` from the repo
  root (timeout 240 s, never reused), so e2e never touches `data/memory.duckdb` or `make demo`'s
  port. One worker, not fully parallel: the specs share that server and ledger, and each spec
  that writes calls `POST /api/admin/reseed` first. `make e2e` = build, `replay --precompute`,
  `npm run e2e`. Screenshots and `perf.json` go to `reports/figures/ui/` (git-ignored: they change
  every run); test artifacts go to the already ignored `web/test-results/`. The frame rate is
  sampled with requestAnimationFrame for 10 s of 1× playback in Playwright's Chromium (launched
  with `--ignore-gpu-blocklist --use-angle=metal --enable-unsafe-swiftshader`), with the WebGL
  renderer string; phase 7 records it and asserts nothing. `web/openapi.json` is committed;
  `test_openapi_json_is_current` and `npm run check:types` keep it and `types.gen.ts` current.
- Screenshot moments (the plan review's suggestion): first contact, T+45, T+90 and after an
  approval, at 1920 × 1080 and 1440 × 900, stand in for §17.13's Director beats, which arrive with
  Director mode in phase 8; the phase 8 reviewer should restore the per-beat set.

## D-114 · Web dependency pins · 2026-10-29
- Decision: three `~0.186.1`, @react-three/fiber `~9.8.2`, drei `~10.7.9`,
  @react-three/postprocessing `~3.2.2`, postprocessing `~6.39.5`, motion `~14.7.1`, d3 `^7.9.0`,
  zustand `^5.0.16`; dev: @playwright/test `1.64.1`, @axe-core/playwright `^4.14.0`,
  openapi-typescript `^7.13.0`, @types/three `~0.186.0`, @types/d3 `^7.4.3`. React stays 19.3.1
  (D-019). Vite puts three, R3F, drei and postprocessing in a `vendor-3d` chunk.
- Found while installing: openapi-typescript 7.13 (the latest) declares a TypeScript `^5` peer and
  the project pins `~6.0.3` (D-019). `package.json` `overrides` points it at the project's
  TypeScript; its output typechecks under 6.0 and `check:types` would catch a change.

## D-115 · Flight phase for the `features` message · 2026-10-29
- Decision: `loiter` when at least 7 of the last 10 seconds pass `signatures.loiter_mask` and the
  chosen target is an asset; once a loiter run of 10 s has happened, `egress` when `dist_target_m`
  is above 600 m and rose over the last 5 s, otherwise still `loiter`; `approach` before. On the
  real live track: approach to T+86, loiter from T+87, egress from T+475.
- Deviation from the plan: two conditions added. (a) The asset condition: a partial track's target
  is the fence until the drone settles over an asset (D-081), and the fence pseudo-target is
  within 600 m of every inbound drone, so the plain rule called T+45 a loiter. (b) No flicker back
  to approach mid-orbit: radar noise makes single orbit seconds fail the mask.

## D-116 · Memory status per match · 2026-10-29
- Decision: `memory.views.incident_statuses(rows, at, offsets)`: a member of a closed case reads
  "Closed as <label> on <Mon D>" (label: the case's active assessment of that incident, else the
  close rationale; date: the close decision, local to the case's base); a member of an open case
  "Open case, <n> linked" (approved links); anything else "Open, unattributed".

## D-117 · Lens payload · 2026-10-29
- Decision (`match/lens.py`): query = tonight's last `rows_used` seconds of the channel; candidate =
  the matched track's anchored segment (`CandidateBuilder.segment`, the rows the shape distance
  used), raw units; NaN gaps interpolated; series above 128 averaged down (PAA). Band `max(|n − m|
  + 1, ceil(band_fraction × max(n, m)))`. `cost` = `dtw.warping_paths(a, b, window=w)` without the
  padding row and column (accumulated cost; `cost[n−1, m−1]` is the DTW distance), float32 LE
  row-major base64 with `shape`; `path` = `dtw.best_path`; `euclid_distance` over the first
  `min(n, m)` samples (`overlap`). dtaidistance's pure-Python `warping_paths` is used (about 5 ms
  at 128 × 128): `dtw_rerank` records a C bug near the band edge, and on these 1-D inputs both
  agree.

## D-118 · Replay clock semantics · 2026-10-29
- Decision: the clock is per session and server-side: `t_s` advances by `speed × wall seconds`
  while playing, from an injectable monotonic source (tests drive it without waiting); `seek`
  clamps to [0, duration]; `reset` = seek 0 and pause; the replay pauses itself at the end; a
  detection is sent once its `t_s ≤ clock`. The web interpolates between 10 Hz clocks for drawing,
  at most one tick ahead.

## D-119 · `make dev` keeps its recipe · 2026-10-29
- Context: §16.6 says `make dev` starts both servers with `concurrently`.
- Decision: keep the existing `trap 'kill 0' INT TERM EXIT; api --reload & npm run dev & wait`
  recipe: same effect, one less dependency. Vite proxies `/api` and `/ws` to :8000.

## D-120 · Live theater rendering choices · 2026-10-29
- Decision (`web/src/three/`): only detections within 1.5 replay seconds of the clock spawn radar
  flashes, packets and RF rings, so a seek's 120 s catch-up does not set off a burst. Packet
  flights (0.9 s + 0.6 s) and RF rings (0 → 300 m over 1.2 s) run in wall time from arrival;
  bearing lines (4 s) and the 60 s trail fade in replay time, so they freeze when paused. The
  drone glyph sits at its latest real radar point (a 0.1 s ease, a snap in reduce motion); heading
  from the latest feature row. The sweep's bearing is the last detection's bearing + 360° × rate ×
  replay seconds since it (busy at 5×, hidden in reduce motion; the flashes stay). Asset heights:
  hq 20, fuel farm 12, housing 9, munitions 8, flight line 6 m. The core sits 2.4 km south-east at
  120 m and turns only per `ingest`. Auto-degrade uses a ~10-frame smoothed frame time (2 s above
  25 ms drops bloom, 2 s more halves packets, never back up within a session). "No Remote ID" is
  shown when no `rid` message arrived in the last 10 replay seconds (Remote ID is not tied to a
  track, so a multi-drone incident tags every drone).
- Found in the screenshot review (§17.13) and fixed: (a) labels were cut by the grid and the
  asset boxes at 1440 × 900, because troika derives its fill and outline materials from a base
  material by prototype and `material-depthTest={false}` reached only one of them: labels now use
  a shared base material with depth testing off; (b) drei's `Grid` writes depth, which turned the
  fence and ground lines into dashes far from the camera: its material no longer writes depth;
  (c) asset labels moved under their footprints and the "No Remote ID" tag above the drone (they
  overlapped while the drone orbited the fuel farm); (d) the overview shot moved about 25% closer
  (the base was small).

## D-121 · Panel choices · 2026-10-29
- Decision (`web/src/panels/`): panel motion uses `element.animate()` behind a guard (skipped in
  reduce motion and in jsdom). The Stream folds kind and sensor into one badge ("Radar 1", full id
  in the tooltip and screen-reader text). The Signals loiter marker appears only when the switch
  into loiter is inside the 120 s window. The phosphor fade erases the left part of each lane with
  a gradient, so canvas colors still come from the tokens. Match entries are keyed on the entrance
  counter and the incident, so a new top-3 set remounts and staggers in while reruns update in
  place. Approve and Reject are disabled, with a reason, without a proposal seq, while busy, or
  once decided. Ledger blocks' accessible name starts with their visible text (axe
  `label-content-name-mismatch`).
- Found in the screenshot review and fixed: the Recorder's three stats became label and value
  rows (they wrapped at 1440 px) and "1 rows" became "1 row"; the Ledger chain badge says "Chain
  verified" with the row count in the footer (it was truncated); panel titles never wrap; the
  Signals meta reads "Loiter since T+01:27".

## D-122 · Director beats: one per §1.2 row, the encore in phase 9 · 2026-10-29
- Context: §17.10 lists nine beats; §20 phase 9 owns "the Director encore beat".
- Decision (`web/src/director/beats.ts`): eight beats as data: detection (T+0), recording (T+15),
  recognition (T+45), time warp (T+90), forecast (T+105), recall (T+120), known then and now
  (Case board), evidence. Each has a camera shot, the panels it keeps lit, the layers it reveals
  and the test id of its key element. §1.2's T+80 row (orbit established) has no beat of its own:
  it is observed during recognition (the Signals loiter marker; the 1× run records when). Phase 9
  appends the encore entry.

## D-123 · How beats advance; Director never commits · 2026-10-29
- Decision (`director/engine.ts`, `actions.ts`, `useDirector.ts`): the current beat is derived:
  a page beat once the presenter moved there, else the last clock beat whose start is at or
  before the replay clock. → on a clock beat seeks to the next beat's time (results are cached per
  second, D-013); → from recall opens `/cases/<case>`, then `/evidence?case=<case>`; ← walks
  back, from the Case board to Live watch at T+120 (a pending seek applied when the new stream is
  open). After a Director seek the driver waits until the clock lands near the target before it
  activates anything (a stale clock never logs a wrong beat). The Director only seeks, plays,
  sets the camera and the lens: it never approves, rejects, decides or exports (rule 8). An e2e
  test checks that a Director run with no clicks appends only `incident_recorded`,
  `model_registered` and `match_proposed`.

## D-124 · Progressive reveal in Director · 2026-10-29
- Decision: in Director, layers appear cumulatively: ghosts, core beams, the lens and the
  constellation's arcs from the time-warp beat; the forecast and the road highlight from the
  forecast beat; the recall overlay and its beam from the recall beat. Without Director every
  layer shows as soon as its data exists. Hiding computed data until its beat changes no number.
  Panels a beat does not feature dim to 45% opacity (`data-dimmed`).

## D-125 · Captions are computed · 2026-10-29
- Decision (`director/captions.ts`, `context.ts`): one pure function per beat from store state
  to one sentence; every value comes from the stream, the scene, the installations or what the
  Case board and Evidence pages publish (`directorStore.facts`: the case's base, its known-then
  label and close date, the pending count). A missing value drops its clause; a test checks that
  no caption contains "undefined", "NaN", "null" or braces. The forecast caption measures from
  tonight's target-asset centroid (the phase 5 CLI's 2,164 m northwest at T+105) and adds "in
  Bravo's radar shadow" only when the zone center is inside the scene's shadow polygon. The
  detection caption names the fence side from the first radar point's bearing (`compass8`, the
  same rule as Python's `sim/lexicon.compass8`).

## D-126 · Lens connectors and morph · 2026-10-29
- Decision (`lens/lensMath.ts`, `LensCurves.tsx`): connectors are the DTW path subsampled evenly
  to at most 48 pairs (first and last kept). Each keeps its query index i; "Same time" puts its
  candidate end at i (shown only for i < `overlap`, what the Euclidean distance compares),
  "Warped" at its path partner j; a mode change moves only that end over 1.2 s with an
  ease-in-out, written by requestAnimationFrame (a 240 ms cross-fade in reduce motion). One x
  scale for both series (`L = max(n, m)` samples), so a faster flight visibly overhangs. The pace
  readout is the payload's `warp_text` capitalized, or "Same pace (within 10%)". The cost matrix
  is drawn one canvas pixel per cell (scaled up, pixelated), NaN cells (outside the band) clear,
  an OKLab ramp from `--scope` to `--afterglow` on the square root of the normalized accumulated
  cost (min to the 95th percentile), and the path drawn on over 1 s with a flash head.

## D-127 · Which match the lens shows · 2026-10-29
- Decision: by default the stream's `dtw` (the top match on distance to target). The match and
  channel selectors send `{"type":"dtw"}`; the store keeps every payload by match and channel and
  re-asks on each new rerun. In the time-warp beat, Director picks the top-3 match whose
  `warp_ratio` is farthest from 1 in log terms (T+90: DELTA, 0.84, "flown 19% faster") and shows
  "Same time" for 1.5 s before the morph to "Warped".
- Deviation from §1.2, recorded: §1.2 says "ALPHA 2026-03-03 (flown ~18% slower)". The 60 s
  window at T+90 computes ALPHA-260303 at 1.03 (no pace text) and DELTA at 0.84. The UI shows the
  computed ratio, never the scenario's wording (rule 10). The live top 3 at T+90 stays DELTA,
  ALPHA-260303, CHARLIE-260710 (the accepted gap, D-081).

## D-128 · Ghost mapping · 2026-10-29
- Decision (`three/ghostMath.ts`, `ghostLayer.ts`, `Ghosts.tsx`): `GET /api/history/{track}?
  frame=target` points placed at tonight's target-asset centroid plus the relative vector
  (translation only; the P1 approaches agree within 5°, and the forecast keeps its own §13
  rotation). No ghosts while tonight's target is the fence pseudo-target. Ghosts are the current
  top 3, re-mapped when the target changes; each is a 2 px `Line2` whose per-segment colors carry
  the dissolve (a fixed hash per segment, 1.2 s, ghosts 150 ms apart; a plain fade in reduce
  motion) and the hover brightness. Labels sit at each recovery point, stacked 16 px apart so
  they never overprint. Mapped specs are cached by target, track and fetched path, so a ghost is
  rebuilt only when it really changes (the screenshot review found ghosts going dark after a
  top-3 change: every 4 Hz re-render had rebuilt the line after its dissolve had finished).

## D-129 · Core beams · 2026-10-29
- Decision (`three/beams.ts`, `CoreBeams.tsx`): on each `match` message three afterglow beams
  leave the core along an arc for 1.2 s, a bright head with a short tail, toward each top-3
  ghost's point at `window_offset_s + window_s` (where that flight was at the matched moment),
  else toward tonight's target. Off in reduce motion and Performance mode (§17.11 particles).

## D-130 · Region constellation · 2026-10-29
- Decision (`panels/constellation.ts`, `RegionConstellation.tsx`): the live region's
  installation origins scaled into the panel, north up, east-west stretched at most 2.5 times
  (the panel is short; the map is stylized). On a new top-3 set, arcs draw from each matched base
  to the live base with a travelling light (Web Animations, 1.2 s, 120 ms apart; plain arcs in
  reduce motion). A base matching itself loops. Each base's label carries the dates of the
  flights matched from it ("Delta, Apr 19"). Matches from another region gather at an "Other
  regions" node. Panel height 150 px at 1536 px wide and up, 116 px below.

## D-131 · Report recall overlay · 2026-10-29
- Decision (`overlay/clues.ts`, `scramble.ts`, `RecallOverlay.tsx`, `RecallBeam.tsx`): the
  report shown is the rank-1 report of the first recall match whose rank-1 report has a linked
  clue, else the first match's rank-1 report (T+120: `R-P1-DELTA-260419-1`). Clue spans are cut
  from `text[start:end]` (vehicles afterglow, roads bone). The zone note is the server's linked
  note for a road in `zone_roads` (§12.4). The text resolves over 600 ms by deterministic glyph
  substitution (spaces never scramble, so the layout holds); a 240 ms fade in reduce motion. The
  overlay sits at the theater's lower left (raised above the Director caption) and can be
  collapsed. The bone beam joins the zone road's span to the road's in-zone midpoint, drawn
  above the overlay every frame from the span's rectangle and the projected point.

## D-132 · Road highlight and projection · 2026-10-29
- Decision (`three/forecastMath.ts`, `forecastLayer.ts`, `Forecast.tsx`, `Projector.tsx`): each
  zone road's polyline is clipped to the zone circle client-side; its in-zone parts are drawn as
  bone dashes with slowly moving dots, in `Forecast.tsx` (the plan's separate `RoadHighlight.tsx`
  was folded in: one component owns the forecast's shapes). The longest part's midpoint is
  projected to the screen in `useFrame` and written by mutation into `overlayStore` (no React
  state); off when behind the camera or outside the theater.

## D-133 · Forecast motion · 2026-10-29
- Decision: the exit path's flowing dash, the road's dots and the zone's 1.6 s pulse advance in
  playback time only (they freeze when the replay pauses) and are static in reduce motion. The
  zone label is computed: "Predicted recovery zone, 2.2 km northwest, from 3 matches", placed
  east of the zone and reading away from it (clear of the ghost labels and the overlay).

## D-134 · Computed camera shots · 2026-10-29
- Decision (`three/camera.ts`, `CameraRig.tsx`): `frameBox(points, fov, aspect)` frames a
  bounding sphere from the south. "Memory" frames every ghost (sampled) and the target; a new
  "Forecast" preset frames the target, the zone's edge and the exit path, then shifts so the
  content sits right of center and a little high (the recall overlay at the lower left never
  covers the zone or its road). Both re-aim once per change of their data (the forecast only when
  the zone moves by about 100 m), never every frame. 1.2 s damped, instant in reduce motion.

## D-135 · Match explainer route · 2026-10-29
- Decision: `GET /api/explain/{incident}/{track}?at=` (`api/routes_explain.py`) returns the
  decorated match; `match/explain.contribution_table` (per model feature: value, coefficient,
  coef × value, sorted by |contribution|; the intercept, the logit and sigmoid(logit) = the
  score); tonight's target-relative path to the rerun second only (rule 3); the past flight's
  whole path, the matcher's anchored window and `explain_alignment` (§10.4 step 6). 404 as
  `/api/dtw`. The page binds incident, second and match to the URL; with no second it opens at
  T+90 (the demo's time-warp moment).

## D-136 · Case list, decisions, evidence list and verify routes · 2026-10-29
- Decision: `GET /api/cases` (`memory/asof.case_summaries`, as of the head or `as_of`);
  `POST /api/cases/{id}/decisions` (close, reopen, escalate, notify_law_enforcement through
  `memory.actions.record_decision`, `analyst:<handle>`; 422 for another value or a bad handle,
  404 for an unknown case); `GET /api/evidence` (packages under the exports root, from each
  `manifest.json`, newest first); `POST /api/evidence/verify` with a folder name, resolved and
  refused with 400 unless it stays inside the exports root (`..`, absolute paths, symlinks out).
  Response models live in `api/schemas_pages.py`. `case_summaries` takes no offsets (the plan
  listed them): the UI formats local times from `/api/installations`.

## D-137 · e2e exports go to scratch · 2026-10-29
- Decision: `kairos-defense api --exports PATH` (and `KD_EXPORTS` under `--reload`) points the
  evidence exports elsewhere; Playwright's server uses `data/cache/e2e/exports`, and the reseed
  helper empties it, so package counts are deterministic and e2e never writes into `exports/`.

## D-138 · Case board mechanics · 2026-10-29
- Decision (`pages/CaseBoard.tsx`, `case/`): the scrubber runs from the case's first event to
  the ledger head with a tick at each diff item's `recorded_at` (`diff?t1=2025-01-01`). Known then
  is the `case_opened` time (09:10 local on 2026-04-20, D-011); Known now is the head. Each scrub
  refetches the graph and the diff since Known then (debounced 150 ms), so every state is the
  server's own as-of. The d3-force layout is computed once over the head's graph plus anything
  only the scrubbed moment has, from seeded ring positions with a fixed random source and 300
  synchronous ticks: a node keeps its place while you scrub, and nodes new to a moment fade in
  over 600 ms when they mount. Incidents are colored by base from four tokens; approved members
  ring green, contradictions red. Approve and Reject per pending proposal (each shows its rank
  and rerun second: one incident can be proposed by several reruns, and approving it settles them
  all); decisions need a confirm dialog. A hidden list is the graph's text equivalent.

## D-139 · Eval targets live in Python · 2026-10-29
- Decision: `eval/targets.py` holds the §19.3 and §10.9 targets (key, operator, value, label,
  section, phase, format, report-only for latency per D-060, pending for `swarm_top1`).
  `eval/report.py` writes them into the eval JSON as `targets`; `report_md.py` renders its target
  column and latency budgets from them (the Markdown is unchanged). A test loads
  `scripts/check_targets.py` (read, never edited) and asserts the same keys, operators, values,
  phases and report-only set; its message says to update `targets.py`, never the script. No
  metric definition, query set or protocol changed.

## D-140 · Eval page · 2026-10-29
- Decision (`pages/Eval.tsx`, `eval/`): tiles show value against target with a status word and
  an icon (meets, below, reported not gating, pending); recall against seconds of flight (Recall@5
  and top 3 for probers); DTW against Euclidean (the two numbers the eval wrote and the lift); the
  forecast error histogram (100 m bins of prober `forecast_error_m` at T = 90 s) with the median,
  P80 and target as lines and a key above; the demo rows as written, the accepted
  `live_top3_incidents` gap included. Nothing is recomputed beyond binning. A report without
  `targets` says "rerun make eval". Charts follow the dataviz method: one axis, thin marks, a
  legend and direct labels for two series, text in ink tokens, a `<title>` tooltip on every
  mark, a table view. The validator on the token pair (`--afterglow`, `--ink-mid` on `--scope`)
  fails its lightness band and chroma floor (the §17.1 tokens are bright on scope glass) and
  passes CVD separation (ΔE 17.4) and contrast, so the two series also differ by dash and marker.

## D-141 · Routes and code splitting · 2026-10-29
- Decision (`app/routes.ts`, `App.tsx`): new routes `/explainer?incident=&at=&track=`, `/cases`,
  `/cases/:caseId?focus=`, `/evidence?case=`, `/delta?since=`, `/eval`; `/swarm` stays a phase 9
  placeholder. Every page is `React.lazy`, Live watch included, so only Live watch loads the
  `vendor-3d` chunk. Each match entry has an "Explain" link at the current rerun second.

## D-142 · Director across pages; keys · 2026-10-29
- Decision: `directorStore` lives outside React; `useDirector` (reading the stores at most 10
  times a second), the progress rail and the page caption are mounted by `App`, the theater
  caption by Live watch, so Director survives navigation. D toggles it from any page (Live watch
  for the open or first live incident, T+0, the selected speed) and drops keyboard focus so Space
  is the presenter's. Space plays and pauses on Live watch; → and ← act only in Director; R
  resets; F toggles full screen; M and ? as before. Keys are ignored while typing; Space is left
  to a focused button or link. Pages pad their bottom while a page beat's caption shows.

## D-143 · R reset · 2026-10-29
- Decision: R calls `POST /api/admin/reset` and `POST /api/admin/reseed` (D-010), clears this
  session's decisions, reloads the ledger tail and seeks to T+0; in Director it returns to beat 1
  (and to Live watch from a page beat).

## D-144 · Performance mode and grain · 2026-10-29
- Decision: a command-bar toggle "Performance mode" (`uiStore.perfMode`) turns off bloom,
  vignette, grain and the core beams and halves packets; auto-degrade (D-120) still applies; the
  theater's `data-perf` reads "performance". §17.10 assigns it no key. Film grain is a custom
  static effect: a hash of the pixel coordinate, no time uniform (D-012), amplitude ±0.3%
  (the review found 3% visibly speckled). Off in reduce motion and Performance mode.

## D-145 · Frame-rate criterion and the 1× record · 2026-10-29
- Decision: `e2e/director-1x.spec.ts` runs Director at 1× at 1920 × 1080 with bloom on through
  the six Live watch beats, presses → only on the page beats, and writes
  `reports/figures/ui/director_1x.json`: per beat its activation replay second and local time,
  wall seconds and when its key element was visible; the loiter marker's second for §1.2's T+80
  row; the median and P5 frame rate overall and per beat; the renderer, CPU and OS. It asserts a
  median of at least 50 fps on a hardware renderer; on software WebGL it records the number and
  annotates that the GPU was not used. Memory rail budget at 1440 × 900 (decided before the
  review): matches 1.6 parts, lens 1 part, constellation 116 px; the compact lens splits what is
  left after its controls 62/38 between curves and matrix.

## D-146 · Phase 8 screenshot review: findings and fixes · 2026-10-29
- Round 1 (all beats at 1440 × 900): grain too strong (now ±0.3%); Space did not pause because a
  clicked speed button kept focus (D blurs; e2e keys blur first); three match entries did not fit
  (the incident id moved to the tooltip and screen-reader text, chips and buttons tightened); lens
  controls wrapped and the matrix was cut (short channel names, narrower selects, a measured
  height budget); the recall overlay covered the zone and road (forecast shot shifted, D-134);
  ghost labels overprinted (stacked); the case graph was cramped and its labels overlapped
  (longer links, stronger repulsion, 58 px collide radius); duplicate proposals were
  indistinguishable (rank and rerun second shown); the page caption covered the last controls
  (bottom padding); the self-match arc had no date.
- Round 2 (both sizes): ghosts went dark after a top-3 change (spec cache, D-128); the zone label
  collided with a ghost label (moved east of the zone); constellation names and dates collided
  (one label per base); the recall beam was faint and under the overlay (above it, 1.6 px).
- Pages: the explainer drew tonight's path at 45% opacity (full now); the Eval recall chart
  clipped its direct label and the histogram's rule labels collided (wider margin, a key above).
- An axe run on Live watch at T+120 (every layer showing) found the Stream's scrolling list was
  not keyboard-reachable (`scrollable-region-focusable`): it is now a focusable, named region that
  pauses scrolling while focused, as it does under the pointer.

## D-147 · Lint-driven structure in the web code · 2026-10-29
- Context: the React compiler lint rules (react-hooks 7) refuse mutating hook-dependency values
  in render callbacks, reading refs during render, impure calls in render and synchronous
  setState in effects; react-refresh wants component files to export only components.
- Decision: per-frame three.js mutation lives in module functions called from `useFrame`
  (`stepGhost`, `stepBeams`, `stepForecast`); non-component helpers moved to `.ts` modules
  (`ghostLayer.ts`, `beams.ts`, `director/context.ts`, `case/time.ts`); pages keep fetched results
  keyed by the URL they belong to instead of resetting state in effects. A `sceneStore` (not in
  the plan) shares the scene and the installations with the theater, the constellation and the
  captions.

## D-148 · Phases 9 and 10 run in one cloud session · 2026-10-29
- Context: the laptop autopilot stopped at phase 9 planning; the build moved to one Claude Code on
  the web session (`docs/CLOUD_HANDOFF.md`). The handoff's step 2 (`claude -p` works → run
  `scripts/autopilot.py`) succeeded here, but the nested `claude -p` reported this session's own
  session id, and the user's instruction for this session was to finish phases 9 and 10 in this
  same session with `scripts/cloud_gate.py` as the only judge.
- Decision: step 3 of the handoff. Plan, independent review (a subagent with `review_prompt()`,
  read-only), build, exit check, then `cloud_gate.py gate|accept|close` per phase. Work happens on
  branch `claude/cloud-phases-9-10`, pushed after each phase (the user merges). The build used two
  forked helpers (agent and MCP backend; web) in parallel with the main session (swarm backend,
  eval, docs); the main session integrated, reviewed and committed everything.
- Environment: this container's temp folder is the short `/tmp`. Three CLI tests failed or passed
  depending on the temp path's length, because the CLI hard-wrapped messages at 120 columns off a
  terminal and the wrap fell inside an asserted phrase. A longer `TMPDIR` fixed two and broke the
  third, so the cause was fixed in code instead (D-156); the tests are unchanged.
- Environment: the container has no GPU (Chromium falls back to SwiftShader), so the phase 8
  frame-rate target cannot be re-measured here; the laptop's 59.9 fps median (phase 7 and 8, Apple
  M4 Max) stands until re-measured there. The models retrained here differ slightly from the
  laptop's (training hash differs, coefficients within about 2%: cross-platform floating point);
  every §19 number agrees with the laptop's within rounding (forecast median 340.5 m here, 340.4 m
  there; the others identical).

## D-149 · Swarm descriptors, detection and tables (§14) · 2026-10-29
- Decision: `features/swarm_features.py`. Each drone track is resampled with §9.1 `resample` and
  placed on the incident's common 1 Hz grid; a second counts when at least `swarm.min_drones`
  drones have a position. Per second, independent of drone order: the target-relative centroid
  (the target is `choose_target` on the centroid path), its speed (central difference), the RMS
  spread, the linear quartiles of the pairwise distances, the PCA principal axis as a bearing
  unwrapped with period 180°, and its rate of turn (5 s centered mean, clipped to ±20 °/s because
  a near-round formation has an ill-defined axis that would otherwise spike the series).
  Detection runs on observable radar positions: the longest run of seconds with at least
  `min_drones` drones all within `max_spacing_m` of each other must last `min_duration_s`.
- Tables: DuckDB `swarm_features` with exactly the §7.2 columns; LanceDB `swarm_windows` with the
  §7.5 columns plus `region_id`, `duration_s`, `together_s` and `is_swarm` (additive, used by the
  Swarm view and the index summary). History swarms only; a live swarm's descriptors are computed
  from raw points up to the query second (D-049, rule 3).
- At seed 42: 8 history swarm incidents indexed, all 8 detected; the live `DEMO-SWARM-ECHO-0614`
  is never indexed.

## D-150 · Swarm matching: prefilter, prefix DTW, alignment · 2026-10-29
- Decision: `match/swarm.py`. Query: the swarm seen up to `at_s` (default its whole observed
  flight). Prefilter `swarm_windows` with `start_ts_ms <` the query's first radar point
  (prefilter=True); every pre-filtered swarm is re-ranked (there are few). Re-rank: z-normalized
  series `[spread, pd_q25, pd_q50, pd_q75, rot_rate, centroid_speed]` against candidate prefixes of
  m = n × pace seconds, pace over `swarm.pace_range` (new `scoring.yaml` key, `[0.7, 1.4]`: ±40%,
  the same pace band one operator shows across flights, §8.5 and `dtw_rerank.WARP_RANGE`), 15
  steps, each prefix z-normalized on its own; banded C DTW (`dtw.band_fraction`, at least the
  length difference plus one); distance = min `d / sqrt(n + m)`; similarity `1 / (1 + distance)`;
  ties by start time, then incident id. The best prefix gives the pace (m / n) and the alignment
  for the Swarm view, taken from the full DTW matrix (`dtw_rerank.series_path`): dtaidistance
  2.5.1's C `warping_paths` is wrong near a band edge (phase 4), and a test checks the path costs
  exactly the full DTW distance. `dtw_rerank` stays the only module that imports dtaidistance.
- Why prefixes: a query seen for T seconds covers the start of the choreography; comparing it with
  whole candidate flights would penalize a correct but partial match. On the full data the
  whole-flight view ranks the right team first for all 4 answerable queries; shorter views are
  weaker (report only, D-151).

## D-151 · Swarm evaluation · 2026-10-29
- Context: §19.3 defines swarm top-1 ("correct team ranked first for swarm queries") with no T;
  §19.2's T grid is written for single tracks.
- Decision: `eval/swarm.py`. Queries are the history swarm incidents of months 13–18; truth labels
  each with its team (read in `eval/` only). A query with no earlier history swarm of its team is
  unanswerable (D-009). The headline `swarm_top1` sees each query over its whole observed flight,
  which is what the encore shows; `swarm_top1_by_t` reports the same share at every T of the §19.2
  grid (report only). The demo row runs the live `DEMO-SWARM-ECHO-0614` the same way and passes when
  `S1-GOLF-260503` ranks first; on a partial dataset without that night it is `pending (no data)`.
  `swarm_top1` joins the regression-gated metrics; `targets.py` has no pending target left.
- Arithmetic: 5 queries (JULIET-260316, S1-GOLF-260503, JULIET-260511, ECHO-260806,
  HOTEL-260829); S1-GOLF-260503 is its team's first event, so 4 are answerable and the 0.80 target
  needs 4 of 4. Result: 1.000 (4 of 4); the demo row passes (S1-GOLF-260503 at similarity 0.476,
  pace 0.75; the best S2 swarm 0.426).

## D-152 · Swarm routes and CLI · 2026-10-29
- Decision: `GET /api/swarms` (every swarm incident, newest first) and
  `GET /api/swarm/{incident_id}?at=&match=` (`api/routes_swarm.py`, models in
  `api/schemas_swarm.py`): detection, the query's descriptor curves and target-relative drone
  positions per observed second, the ranked earlier swarms, and for the selected match (default
  rank 1) its whole flight, `aligned` (matched descriptor row per query row) and the DTW path. 404
  unknown incident, 422 not a swarm or a match not among the results, 503 without the swarm
  index. Results are cached in memory per (incident, at, match) (at most 64); nothing writes to
  the ledger (§15.6, D-106). `kairos-defense swarm --incident ID [--at S] [--k 5]` prints the
  ranking (`cli_swarm.py`); `kairos-defense index` prints the swarm counts.

## D-153 · Performance pass (phase 9) · 2026-10-29
- Measured (cProfile and timers, this container, 4 vCPU, while the eval and two test suites ran):
  live query + match at T+90 about 0.5 s (prefilter 140 ms, signature 124 ms, DTW of 500
  candidates 144 ms); swarm match over the whole flight about 0.27 s (raw points and resampling
  100 ms, DTW over 15 prefixes × 8 candidates 137 ms). The eval's p95: DTW 258 ms, end to end
  654 ms, both inside §10.9; prefilter 173 ms (WARN, report only, D-060; 30 ms on the laptop).
- Decision: no LB_Keogh pruning: the DTW re-rank is far inside its 800 ms budget on both machines.
  Caching where results repeat: swarm results per request in the API, the live loop's per-second
  result cache (phase 7) and `replay --precompute` for the demo incidents. Nothing else changed.

## D-154 · Slow-machine synchronization in two e2e specs · 2026-10-29
- Context: the untouched phase 8 suite failed 2 of 29 tests here (27 passed in 11.5 min). At 5×
  the replay clock passes T+91 and reaches about T+100 before the pause lands, so the lens shows
  the T+100 rerun while `lens.spec.ts` asked the API for T+90; and `openLive` returned once the
  command bar was ready while the lazy Live watch chunk still showed "Loading".
- Decision: `openLive` also waits for the Live theater region; `lens.spec.ts` asks the API for
  the paused clock's second. The assertions are unchanged (the connectors still equal the DTW
  path's pairs at the second shown). Both pass here.

## D-155 · LLM report paraphrase stays off in v1 · 2026-10-29
- Context: D-043 deferred `reports_llm_paraphrase: true` to phase 9, when an LLM adapter would exist.
  Phase 9 built the adapter (`agent/llm.py`) for the optional chat.
- Decision: the flag stays refused (`gen` exits with a clear error); D-043's consequence is
  superseded. The message now says why.
- Why: paraphrased text would move the clue spans the recall overlay highlights, change the
  planted DELTA report that the demo and its assertions depend on, and make generation depend on a
  remote model (rule 4 determinism, rule 5 offline). The chat panel is the only LLM use, and it is
  off by default.

## D-156 · CLI messages are never hard-wrapped · 2026-10-29
- Context: off a terminal the CLI console is 120 columns wide (phase 0), and rich wrapped long
  messages at word boundaries, so a message's line breaks depended on the length of the paths in it.
  On this machine's short temp paths, "run `npm --prefix web run build`" and "through
  http://127.0.0.1:8000" were split across lines (two tests failed); with a longer temp folder,
  "signed, key" was split instead (a third test failed). The laptop's long macOS paths happened to
  pass all three.
- Decision: the console keeps its 120-column width for tables but uses `soft_wrap=True`, so a
  message (a path, a fix-it command, a hash) prints on one line whatever its length. No test
  changed; the three pass with both temp folders, and every CLI test passes.
- Why: a fix-it command split across lines is also worse for a person copying it from a log.

## D-157 · MCP server over mcp 2.x `MCPServer` · 2026-10-29
- Context: the installed `mcp` is 2.3.0, where §18.2's `FastMCP` (`mcp.server.fastmcp`) is renamed
  `MCPServer` (`mcp.server.mcpserver`); the §18.2 import fails.
- Decision: `agent/mcp_server.py` is a thin adapter (CLAUDE.md library rule): one small wrapper per
  tool with an explicit signature (the server derives the input schema), each calling
  `tools.call_tool`, so a bad id or time comes back as `{"error": …}` JSON instead of a failed call;
  read-only tools carry `read_only_hint=True`. `build_server(ctx_factory, allow_proposals)` builds
  the context on the first tool call, so listing tools needs no data, models or ledger. Six
  read-only tools always; `propose_link` and `propose_evidence_export` only with
  `--allow-proposals`. `make mcp` is silent (`@`) so stdout carries only JSON-RPC.
  `python -m kairos_defense.agent.probe [--expect N] -- CMD…` is a small stdio client used as the
  exit-check evidence. Tested in process and over stdio with a real client (deadline 60 s).
- Dependencies: `mcp>=2.3,<3` (the 1.x path is not used) and `httpx>=0.28` in `[project]
  dependencies` (the LLM adapters import it at runtime). `uv.lock` changed only in the project's
  metadata.

## D-158 · Agent tools: context, lock, meanings · 2026-10-29
- `agent/context.py` (`ToolContext`) is a third composition root next to `api/services.py` and the
  CLI (extends D-104): lazily built from the config for the MCP server, or reusing the API's handles
  (store, LanceDB, matcher, recall, ledger, lock) for the chat. The tool functions
  (`flight_tools.py`, `memory_tools.py`, registry in `tools.py`) use only port-typed attributes.
- `call_tool` holds the context's lock: MCPServer may run sync tools on worker threads, and a DuckDB
  connection is never shared by two threads (D-110). The ledger is opened per call (read-only for
  reads, read-write for `propose_link`) and closed after, so the MCP server never holds
  `data/memory.duckdb` between calls.
- `find_similar_flights(incident_id, window_s=120, k=5)`: `window_s` is the seconds of track since
  the incident's first radar point (the replay second), not the matcher's window W (returned as
  `search_window_s`); at least `live.min_track_s`. `recall_reports` and `forecast_recovery` take
  `at_s` (defaults 120 and 105, the §1.2 beats). A swarm needs `track_id` or the Swarm view.
- `propose_link` appends exactly one `match_proposed` (actor `agent:<name>`, `source_type` agent,
  the rationale, the matcher's evidence for that incident when it has any); refused for an unknown
  case or incident, an existing member or an empty rationale; no dedup (each call is one proposal a
  human approves or rejects). `propose_evidence_export` appends nothing (only `match_proposed` may
  be appended by an agent, D-094 and the §20 test): it returns `EXPORT-PROPOSAL-<case>-<head seq>`,
  the head hash, members, status and the human step (`kairos-defense export --case … --approve` or
  the Evidence page).
- While the API holds the ledger (DuckDB's lock error), `as_of_view`, `diff_case` and
  `shift_delta` read through `GET /api/cases/{id}?as_of=`, `/diff` and `/api/delta` on the loopback
  API (D-010); `propose_link` is refused with the cause. With nothing answering, the error names
  both causes.

## D-159 · Optional chat: read-only tools, adapters, default model · 2026-10-29
- `POST /api/chat` runs `agent.chat.run_chat` with the six read-only tools only; a proposal the model
  asks for comes back "not available". Client messages are reduced to user and assistant text; tool
  results sent to the model are cut at 30,000 characters; at most 6 tool rounds. Off by default
  (`llm.provider: none`: status `enabled: false`, POST 409, nothing calls out); a configured but
  unusable provider (no key or model) shows `problem` and POST answers 503. The system prompt
  carries the §18.3 rules (answer only from tool results with ids, flights not people, no
  identity, propose never commit, "unknown" when evidence is missing).
- Adapters over `httpx`, keys only from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`. Anthropic: the
  Messages API as the `claude-api` skill describes it (version header `2026-10-21`, default model
  `claude-opus-5-5` when `llm.model` is empty, `max_tokens` 16000, no sampling parameters or forced
  tool choice, the assistant's content replayed unchanged, all tool results of a turn in one user
  message, refusals reported). OpenAI and Ollama: the OpenAI-compatible
  `POST {base}/chat/completions` (`llm.base_url`), `llm.model` required. Tested only with mock
  transports; no test calls a network.

## D-160 · Swarm view (§17.9) · 2026-10-29
- Decision (`pages/SwarmView.tsx`, `swarm/`, `state/swarmStore.ts`): `/swarm?incident=&match=`
  (no incident: the live swarm from `/api/swarms`; the phase 8 placeholder and `PLANNED` are gone).
  Scene left, "Earlier swarms, best first" and "Choreography descriptors" right (stacking below
  1280 px). The scene is the query's target-relative frame: tonight's drones as flash discs, the
  matched swarm as an afterglow ghost of rings, formation edges joining each drone to its nearest
  neighbor (unique pairs, recomputed every frame from the real positions), a 60 s centroid trail,
  the target ring and label, a follow camera about 490 m out (free orbit; no easing in reduce
  motion). The ghost is the matched formation at its DTW-aligned second (the `aligned` row, linear
  between rows) re-centered on tonight's centroid, not rotated: the §14 descriptors are
  rotation-free and §17.9 asks for time alignment only, so at the split the two groups can appear
  mirrored. Positions between two recorded seconds are linear (display only).
- The playhead lives in `swarmStore`, advanced by requestAnimationFrame at 5, 10 or 20× over the
  described seconds, read in `useFrame` and at most 10 times a second in the DOM; the page opens
  paused at the first described second and autoplays at 20× in Director. Curves: spread, the
  pair-distance quartile band with its median, rotation rate; the match drawn dashed on tonight's
  seconds through `aligned`; legend, direct labels (base only), a crosshair tooltip, click to
  seek; an sr-only table every 30 s. The flash and afterglow pair fails the palette validator's
  lightness and chroma checks but passes CVD separation and contrast (as D-140), so the series also
  differ by dash.
- Screenshot review (§17.13, both sizes): seven findings fixed (a non-focusable scroll region, a
  clipped direct label, unused chart height, a jagged full centroid path, a wrapping ghost chip,
  formations too small, a double Play on fast clicks). The fixture `swarm.json` is the real route's
  output trimmed to 180 s of positions (179 kB).

## D-161 · The encore beat · 2026-10-29
- Decision: Director's ninth beat `encore`, a page beat on the Swarm view (key element
  `swarm-ghost`, the ghost's DOM chip; canvas text is not testable), opened by → from Evidence for
  the live swarm incident; it reads only (the e2e checks the ledger head is unchanged). Caption
  computed from the §14 result and the installations' offsets: "Same choreography, N weeks apart,
  in another region: Golf on May 3 and Echo on Jun 14." (N = round(days / 7), spelled out to
  twelve; "at another base" when the region is the same; no "apart" clause under a week; never
  "tonight", which is BRAVO's night). Without a result: "Every earlier swarm, searched for the same
  choreography." `director-1x.spec.ts` still records the phase 8 rows; the 5× spec covers the
  encore at both sizes.

## D-162 · Chat slide-over visibility · 2026-10-29
- Decision: the command bar's Ask button and `ChatPanel` render only when `GET /api/chat/status`
  returns `enabled: true`; any failure (no route, an error, offline) counts as disabled, so the
  default `llm.provider: none` shows nothing. Each reply lists its tool calls; the panel states the
  §18.3 rules. Live watch's match list for a swarm incident now points to the Swarm view.

## D-163 · Guide screenshots come from the running app on every `make e2e` · 2026-10-29
- Decision: `web/e2e/guide.spec.ts` (three tests) drives the real app on Playwright's own server
  (scratch ledger and exports, D-137) and writes 20 PNGs to `docs/guide/img/`: Live watch at T+90
  (1920 × 1080 and 1440 × 900, the screen whose layout changes most between the two sizes, D-145)
  and T+120, the nine Director beats at 5×, the Match explainer, the Case board (Known then and
  Known now), Evidence after an approved export and a verify, Shift delta, Eval, the Swarm view and
  the shortcuts dialog. Every shot first waits for the element that proves its state (three
  ghosts, lens curves, forecast label, recall overlay, case graph, the proposals diff, a passing
  verify, the swarm ghost, an eval tile, a delta group, the dialog), then lets fades settle (1.6 s);
  Live watch plays at 2× so a slow machine overshoots the target second by little (D-154), and
  Director pauses each beat with Space as `director.spec.ts` does. No mock-ups, no editing, no
  placeholder or loading state.
- The PNGs are committed. Every `make e2e`, the gate's included, rewrites them, and
  `cloud_gate.py close` commits the rewritten files, so the committed images are the gate run's.

## D-164 · Documentation tests · 2026-10-29
- Decision: `tests/unit/test_docs.py` parses links and images with `scripts/check_docs.py`'s
  pattern and checks every relative target in `README.md`, `docs/USER_GUIDE.md`,
  `docs/ONE_PAGER.md` and `docs/ROLLBACK.md` exists; it walks the Typer app's command tree (every
  command and `memory` subcommand, not the help text, whose layout depends on the terminal) and
  requires `kairos-defense <command>` in the guide; and it checks the guide's images are PNGs of at
  least 20 kB with distinct hashes (the gate's own rule, early in `make check`).

## D-165 · README and user documents · 2026-10-29
- Decision: the root README leads with what the product is and a table of the documents (user
  guide, one-pager, runbook, rollback guide, autopilot, spec, progress, decisions, phase index),
  then every package README, a three-command quick start, the status table and the latest
  evaluation. The guide's command-line examples are real output from this build (trimmed); its
  numbers are the phase 9 eval's. The one-pager's hero image is `live-watch-t120`. The rollback
  guide names phases 0 to 3 by commit (they have no done tag) and tells merges to avoid squashing
  so the phase 9 and 10 tags stay on the main line.

## D-166 · Fixes from the guide's screenshot review (§17.13) · 2026-10-29
- Context: reviewing the first `guide.spec.ts` run showed (a) the ghost labels of two matched
  flights overprinting ("Delta, Apr 19" over "Alpha, Mar 3") at both sizes: the stack offset per
  index assumed the recovery points sit on top of each other, but they lie tens of pixels apart;
  (b) at 1440 × 900 the "Radar shadow" label running into the ghost labels; (c) the compact lens
  overflowing the rail (a guessed 96 px header: at 1440 the controls wrap, so the cost matrix was
  hidden below the fold, and its caption was cut at 1920); (d) the "No Remote ID" tag drawn over
  the drone's orbit ring; (e) the Live watch shot at T+120 repeating the T+90 shot, because outside
  Director the forecast and the report already show from the first rerun.
- Decision: (a) `labelSlots` (`three/ghostMath.ts`, unit-tested): a ghost whose end point lies
  within 400 m of an earlier ghost's end point hangs its label from that ghost's end point, one
  16 px row higher per member, so the labels of one cluster can never overprint; a far ghost keeps
  its own anchor. (b) The radar shadow label is right-anchored 8 px left of the wedge's center, so
  it reads away from the recovery zone inside the shadow. (c) `TimeWarpLens` measures its header
  (controls and readouts) with a ResizeObserver and splits what remains, less a two-line caption,
  the gaps and the padding, between the curves and the matrix; `LensPanel` passes its whole box
  height. (d) The tag sits 28 px above the drone instead of 16. (e) The T+120 shot uses the
  Forecast camera (orbit, zone and County Rd 12), and the guide says when each result appears
  outside and inside Director. No number or behavior changed; every element still shows real
  results.
- Consequences: the screenshots of the gate run (and of `director.spec.ts` and `screens.spec.ts`)
  show the stacked labels and the full lens. At 1440 × 900 the lens caption may still need a scroll
  when the readouts wrap; the matrix itself is visible.

## D-167 · Tags the cloud session could not push · 2026-10-29
- Context: in this Claude Code cloud session the git remote accepts branch pushes but refuses tag
  pushes (`send-pack: unexpected disconnect while reading sideband packet`, every retry, while
  branch pushes succeed and the proxy reports no failure). `cloud_gate.py close` creates
  `phase-09-done` and `phase-10-done` locally.
- Decision: push the branch after every phase (the handoff's requirement) and record the tags'
  commits in `docs/phases/INDEX.md` (written by `close`) and in `docs/ROLLBACK.md`, which gives the
  two commands that recreate and push them from any clone. No tag is moved or rewritten.
- Consequences: until someone runs those commands, the remote lists tags up to `phase-08-done`;
  both commits are on `claude/cloud-phases-9-10`.

## D-168 · The narrated demo video: slow-motion capture and an honest overlay · 2026-10-29
- Context: the user asked for a 1.5 to 2 minute screen-recorded demo with automated selections and
  overlays that explain how it works. In the cloud container Chromium renders the Live watch
  scene at about 7 frames per second (SwiftShader, no GPU), far too choppy to record in real time.
- Decision: `make demo-video` records the real app in slow motion and plays it back at its real
  pace. The API runs replays with `--time-scale 1/K` (`live.replay.scaled_clock`; default 1, real
  time); the recorder slows the page by the same K (`web/demo/timeshim.ts`: performance.now,
  Date.now, requestAnimationFrame and timers; CSS and Web Animations through CDP
  `Animation.setPlaybackRate`) and captures every painted frame over the CDP screencast with its
  wall time (`web/demo/kit.ts`); `web/demo/encode.mjs` divides those times by K and encodes a
  constant 30 fps H.264 file, `docs/demo/kairos-defense-demo.mp4`, with its chapter times. K is 5
  here (`DEMO_SLOW`); on a machine with a GPU `DEMO_SLOW=1` records in real time.
- The story is Director mode at 5× (`web/demo/record.spec.ts`): the recorder pauses on each beat
  while a narration layer (`web/demo/overlay.ts`, a shadow root outside the app, no pointer
  events) shows a chapter pill in the command bar's free space, rings the element that matters
  and explains the mechanism in a card, and moves a visible pointer to every element it clicks
  (Known then, Known now, each Approve, Export and its confirm, Verify, the Pages menu). The
  overlay draws words and shapes only: every number or name in a card is read from the app's
  screen at that moment (rule 10), the app's own Director captions stay, and the recorder runs
  against its own scratch ledger, live tables and exports (`data/cache/demo`, port 8766).
- Found by the recording and fixed: the command bar's Pages menu opened behind the Swarm view's
  panels (the header's blur makes it a stacking context painted below later panels), so it could
  not be clicked there. The header is now `relative z-30`. Choosing a page in that menu now also
  closes it (it stayed open over the new page).
- Capture detail: CDP's document-timeline slow-down also slows the browser's own
  requestAnimationFrame timestamps, so the time shim gives every frame callback the slowed
  `performance.now()` instead; code that mixes the two clocks (the report's text resolve) otherwise
  stalled at its first frame.

## D-169 · Live mode MVP and the DTW workbench (phases 11 and 12) · 2026-11-02
- Context: the user asked for a live version, not only the replay demo, built MVP style: no user
  accounts, no retraining, past patterns assumed to exist (or generated), and scenarios such as a
  swarm repeating a past formation, demonstrable in a short time in real time. They also asked to
  watch the matcher do DTW.
- Decision: two new phases with blocks in `docs/phases/PHASE_11.md` and `PHASE_12.md`, built and
  gated by the autopilot like phases 4 to 10. Phase 11: a separate simulator process streams only
  sensor detections through a documented ingest interface (the seam for real sensor adapters); the
  app forms incidents, matches unseen flights live with the existing models, learns closed incidents
  into history, and records them in the case memory; five scenarios, scored by `live check` in
  `eval/`. Phase 12: an optional matcher trace streamed per rerun and a workbench that replays it in
  labelled slow motion; live-mode documentation and screenshots.
- Why: the matcher only needs the points seen so far, so live data can drive the existing pipeline
  unchanged; the simulator-as-sensor split keeps truth isolation and gives a real ingest seam. Live
  flights are stamped after the last history night so no look-ahead holds. Rejected: in-process
  generation (the app would hold the actor), retraining on live data (not needed for synthetic
  flights from the same generator).
- Consequences: live rows are separable and `live reset` removes them; the 18-month history,
  evaluation and replay demo are unchanged. `scripts/autopilot.py` reads blocks for N >= 10 from
  `docs/phases/PHASE_N.md` (LAST_PHASE = 12). Scenario expectations are soft (D-063).
