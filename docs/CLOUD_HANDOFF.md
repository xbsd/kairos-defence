# Cloud handoff: build phases 11 and 12 in one Claude Code session

Updated 2026-11-02. The user starts this session on Claude Code on the web and wants it to run to the
end without them. **Do not wait for them and do not ask questions: use your best judgement, log
decisions in `docs/DECISIONS.md`, and keep going until phase 12 is closed.** (Phases 9 and 10 were
built the same way on 2026-10-29; their reports show what a good run looks like.)

## What is left

Read `docs/phases/INDEX.md` and the Status column of `docs/PROGRESS.md` first; they are the truth.
Phases 0 to 10 are done (phase 4 with one accepted gap, `docs/phases/phase-04/GAPS.md`). Remaining, in
order, each fully finished before the next:

| Phase | Block | What it is |
|---|---|---|
| 11 | `docs/phases/PHASE_11.md` | Live mode MVP: a separate simulator process streams sensor detections through an ingest interface; live incidents, live matching on unseen flights with the existing models, learned live history, five scenarios, `live check` |
| 12 | `docs/phases/PHASE_12.md` | DTW workbench (matcher trace, slow-motion replay of the real computation) and live-mode documentation with new screenshots |

Decision D-169 explains why and how. Run phase 12 straight after phase 11 closes.

## Rules (in addition to CLAUDE.md)

For this handoff, two CLAUDE.md and skill rules are overridden on the user's instruction: run phases
11 and 12 **in this one session** (CLAUDE.md "do not start the next phase in the same session"), and
**push** your branch after every phase (the skill's "never push"), because pushed commits are the only
way the work survives the session. Never force-push.

- Follow `.claude/skills/phase-auto/SKILL.md` for every step: the procedure the autopilot uses (plan,
  revise, build, fix), including the documentation each phase must leave in `docs/phases/phase-NN/` and
  the package READMEs. For N ≥ 10 the phase block is `docs/phases/PHASE_N.md`.
- **Only `scripts/cloud_gate.py` decides that a phase passed.** Never mark a phase done in PROGRESS.md
  yourself. Never edit `scripts/*.py`, `docs/phases/gates.json`, `docs/phases/PHASE_*.md`,
  `docs/phases/accepted_gaps.json` or `.claude/`. Never weaken, skip or delete tests; never change the
  SPEC §19 protocol, query sets, truth handling, metric definitions or a scenario's expectation to
  make a check pass.
- All CLAUDE.md rules hold, especially truth isolation (while a live flight is open the app never
  learns who flew it; only `eval/` reads truth; the one exception is the on-screen reveal of a
  **closed** incident, D-170, served through `eval` and never stored), no look-ahead (live flights are
  stamped after the last history night), truthful animation and humans approve.
- The on-screen reveal is a required phase 11 feature: the user asked for it for the demo.
- Target shortfalls are soft (D-063): `live check` prints `GAP` lines for missed scenario
  expectations; after three honest gap-only gates, accept them and move on. Latency never blocks
  (D-060). Anything broken (tests, crashes, e2e, docs) is hard and must be fixed.
- Processes and ports: phase 11 runs the API and a separate simulator process. Tests and checks must
  start and stop their own servers on their own ports, and no command may leave a server running.
- Commit after every step. **Push after every phase** (`git push origin HEAD`). Tags may be refused by
  the remote here; that is fine (they are recreated on the laptop).

## Step 1: set up the machine (about 5 to 10 minutes)

```bash
bash scripts/cloud_setup.sh
```

It installs uv and the Python and web dependencies, builds dtaidistance from source (D-064, needs a C
compiler and OpenMP; gcc's libgomp is enough on Linux), installs the Playwright Chromium browser,
regenerates the git-ignored data, indexes and models (seeded, so identical to the laptop), reseeds the
case memory and runs `make check`. It must end with `SETUP OK`; if not, fix the environment (not the
code) and rerun. A Node version other than 22 is only a warning. Then confirm `make e2e` runs here (if
a browser dependency is missing: `cd web && npx playwright install --with-deps chromium`).

## Step 2: try the real autopilot first

```bash
claude --version && claude -p "Reply with OK" --output-format json | head -c 300
```

If that prints a successful result, run `nohup python3 scripts/autopilot.py run --from 11 > .autopilot/cloud-run.log 2>&1 &`
and supervise `docs/phases/AUTOPILOT.log`, pushing after each phase closes. If `claude -p` does not work
here (the usual case), use step 3.

## Step 3: run each phase yourself, with the script as the judge

For phase N (11, then 12):

1. **Plan:** follow `phase-auto plan N` (block: `docs/phases/PHASE_N.md`). Check the plan against the
   current code: read the package READMEs and the modules the block names before deciding file layout.
2. **Independent review:** start a subagent (Agent tool, general-purpose) with the reviewer prompt from
   `review_prompt()` in `scripts/autopilot.py`, telling it not to modify files. Save its verdict as
   `docs/phases/phase-NN/PLAN_REVIEW-k.json` (`approved`, `blocking_issues`, `suggestions`, `summary`).
   If it has blocking issues, revise (`phase-auto revise N`) and review again, up to 3 rounds.
3. **Build:** follow `phase-auto build N` completely, in small steps with tests, running `make check`
   after each step and committing checkpoints. Then the exit check, `EXIT_CHECK.md`, `REPORT.md`,
   READMEs, a PROGRESS.md session-log entry (not the Status cell), DECISIONS.md, and
   `git add -A && git commit -m "phase N: <summary>"`. The tree must be clean. Push.
4. **Gate:** `python3 scripts/cloud_gate.py gate N`
   - exit 0: passed, go to 6.
   - exit 2 (hard failure): read the gate log it names, find the root cause, fix, commit, gate again.
     After 3 failed fixes of the same hard failure, write `docs/phases/phase-NN/BLOCKED.md` (what failed,
     what you tried, the decision a human must make), commit, push, and stop.
   - exit 1 (only target gaps): improve the method honestly, commit, gate again. After 3 gap-only
     gates, go to 5.
5. **Accept gaps:** `python3 scripts/cloud_gate.py accept N`.
6. **Close:** `python3 scripts/cloud_gate.py close N` (marks the phase done, writes the index, commits,
   tags). Then `git push origin HEAD`.

## State at handoff (2026-11-02)

- `main` is at the commit that added PHASE_11.md, PHASE_12.md, their gates and D-169. Nothing of
  phase 11 is built: a local autopilot start was cancelled seconds into planning and its files removed,
  so `docs/phases/phase-11/` does not exist yet. Start phase 11 from planning.
- Every §19 target is met (Recall@5 1.00, time to match 96%, copycat-first 0%, DTW lift +0.52, report
  linkage 1.00, forecast median 340 m, swarm top-1 1.00) except the accepted phase 4 gap
  `demo:live_top3_incidents` (D-081). Fast tests at start: 803 Python, 169 web.
- The matcher is driven by `match.query.query_at(points, site, at, scoring, ids)` and
  `DtwMatcher.match(q)`; history is searched with `store.tracks_before(q.start_ts, …)`. The live replay
  (`live/replay.py`, `loop.py`, `session.py`) loads a complete stored incident: phase 11 needs an
  open-ended, growing incident instead. The simulator's building blocks are `sim/actors.make_flight`,
  `sim/kinematics.fly`, `sim/sensors.radar_track`, `rf_track`, `rid_track` and the swarm choreography.

## When everything is done

Add a session-log entry to `docs/PROGRESS.md` summarizing phases 11 and 12 (what a presenter can now do
live, the `live check` results per scenario, any GAPS.md), then commit and push. Leave the tree clean.
