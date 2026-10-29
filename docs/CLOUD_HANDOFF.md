# Cloud handoff: finish the build in one Claude Code session

Written 2026-10-29 ~03:30 local, when the build moved from the laptop (local autopilot, phases 4 to 7
done) to Claude Code on the web. **The user is away until about 09:00. Do not wait for them, do not ask
questions: use your best judgement, log decisions in `docs/DECISIONS.md`, and keep going to the end.**

## What is left

Read `docs/phases/INDEX.md` and the Status column of `docs/PROGRESS.md` first; they are the truth.
At handoff: phases 0 to 7 are done (phase 4 with one accepted gap, see `docs/phases/phase-04/GAPS.md`).
Remaining, in order, each fully finished before the next:

| Phase | Block | Notes |
|---|---|---|
| 8 | SPEC §20 Phase 8 | May be partly built: see "Phase 8 state" below |
| 9 | SPEC §20 Phase 9 | Swarms, agent, MCP, hardening, runbook (`docs/DEMO.md`) |
| 10 | `docs/phases/PHASE_10.md` | User guide with real screenshots, one-pager, rollback guide |

Run phase 10 straight after phase 9 passes.

## Rules (in addition to CLAUDE.md)

For this handoff only, two CLAUDE.md and skill rules are overridden on the user's instruction
(2026-10-29): run phases 8, 9 and 10 **in this one session** (CLAUDE.md "do not start the next phase in
the same session"), and **push** your branch after every phase (the skill's "never push"), because the
laptop is off and pushed commits are the only way the work survives. Never force-push.

- Follow `.claude/skills/phase-auto/SKILL.md` for every step: it is the procedure the local autopilot
  used (plan, revise, build, fix), including the documentation each phase must leave in
  `docs/phases/phase-NN/` and the package READMEs.
- **Only `scripts/cloud_gate.py` decides that a phase passed** (below). Never mark a phase done in
  PROGRESS.md yourself. Never edit `scripts/*.py`, `docs/phases/gates.json`, `docs/phases/PHASE_10.md`,
  `docs/phases/accepted_gaps.json` or `.claude/`. Never weaken, skip or delete tests, never change the
  SPEC §19 protocol, query sets, truth handling or metric definitions to raise a number.
- Target shortfalls are soft (D-063): after three honest gap-only attempts, accept them and move on.
  Latency never blocks (D-060). The phase 8 frame-rate target (≥ 50 fps) cannot be measured on a
  machine without a GPU: if phase 8 runs here, measure what you can, record the number and the machine
  in PROGRESS.md and REPORT.md, and log a decision that the laptop measurement (59.9 fps at phase 7, Apple
  M4 Max) stands until re-measured there.
- Commit after every step. **Push after every phase** (`git push origin HEAD`, plus the new tag if the
  remote accepts tags). The user reviews and merges in the morning.

## Step 1: set up the machine (about 5 minutes)

```bash
bash scripts/cloud_setup.sh
```

It installs uv, Python and web dependencies, builds dtaidistance from source (D-064, needs a C compiler
and OpenMP; on Linux gcc's libgomp is enough), installs the Playwright Chromium browser, regenerates the
git-ignored data, indexes and models (seeded, so identical to the laptop), reseeds the case memory and
runs `make check`. It must end with `SETUP OK`. If it does not, fix the environment (not the code) and
rerun. If the Node version is not 22 and cannot be installed, continue: it is a warning.

Then confirm the end-to-end tests run here: `make e2e`. If a browser dependency is missing, try
`cd web && npx playwright install --with-deps chromium`.

## Step 2: try the real autopilot first

```bash
claude --version && claude -p "Reply with OK" --output-format json | head -c 300
```

If that prints a successful result, the full autopilot works here. Run it in the background and supervise:

```bash
nohup python3 scripts/autopilot.py run --push > .autopilot/cloud-run.log 2>&1 &
tail -f docs/phases/AUTOPILOT.log
```

It continues from the first phase not done and stops only with `docs/phases/phase-NN/BLOCKED.md`. If it
stops, read that file, fix the cause, commit, and rerun the same command. If `claude -p` does not work
here (no CLI, not signed in), use step 3.

## Step 3: run each remaining phase yourself, with the script as the judge

For phase N (8, then 9, then 10):

1. **Plan** (skip if `docs/phases/phase-NN/PLAN.md` exists and a `PLAN_REVIEW-*.json` approved it):
   follow `phase-auto plan N`. For N = 10 the phase block is `docs/phases/PHASE_10.md`.
2. **Independent review:** start a subagent (Agent tool, general-purpose) with the reviewer prompt in
   `review_prompt()` in `scripts/autopilot.py`, telling it not to modify files. Save its verdict as
   `docs/phases/phase-NN/PLAN_REVIEW-k.json` (`approved`, `blocking_issues`, `suggestions`, `summary`).
   If it has blocking issues, revise the plan (`phase-auto revise N`) and review again, up to 3 rounds.
3. **Build:** follow `phase-auto build N` completely: tests with the code, exit check, `EXIT_CHECK.md`,
   `REPORT.md`, READMEs, PROGRESS.md session log (not the Status cell), DECISIONS.md, then
   `git add -A && git commit -m "phase N: <summary>"`. The tree must be clean.
4. **Gate:** `python3 scripts/cloud_gate.py gate N`
   - exit 0: passed, go to 6.
   - exit 2 (hard failure): read the gate log it names, find the root cause, fix, commit, gate again.
     After 3 failed fixes of the same hard failure, write `docs/phases/phase-NN/BLOCKED.md` (what failed,
     what you tried, the decision a human must make), commit, push, and stop.
   - exit 1 (only target gaps): improve the method honestly, commit, gate again. After 3 gap-only
     gates, go to 5.
5. **Accept gaps:** `python3 scripts/cloud_gate.py accept N`.
6. **Close:** `python3 scripts/cloud_gate.py close N` (marks the phase done, writes the index, commits,
   tags). Then push: `git push origin HEAD` and the tag.

## State at handoff (2026-10-29 04:08 local)

- **Phases 0 to 8 are done**, tagged `phase-00-done`… `phase-08-done` (phases 0 to 3 have no done tag;
  they were built by hand) and pushed. Phase 8 passed its gate on the first attempt: Director at 1×
  through every §1.2 row, median 59.9 fps at 1920 × 1080 on the laptop, 30 screenshots reviewed.
- Every §19 target measured so far is met (Recall@5 1.00, DTW lift +0.52, copycat-first 0, report
  linkage 1.00, forecast median 340 m) except one accepted gap: `demo:live_top3_incidents`
  (P1-ALPHA-260502 ranks #5 at T+90; phase 4 GAPS.md). It shows as WARN and is not retried, but phase 9's
  "all §19 targets met (or gaps approved in DECISIONS.md)" is satisfied by D-063 plus that GAPS.md. If
  you have time left after phase 10, improving it honestly (shape over time-of-night weighting) is the
  most valuable extra.
- **Start with phase 9 from planning.** The local run was stopped seconds into phase 9's planning; the
  partial files were removed, so `docs/phases/phase-09/` does not exist yet.
- Phase 9's gate starts with `make clean` and rebuilds everything, and includes `make test-all` (slow
  tests). Allow 15 to 30 minutes for it.
- The laptop is off from about 04:30 to 09:00. Nobody can answer questions.

## When everything is done

Add a session-log entry to `docs/PROGRESS.md` summarizing phases 8 to 10, the final §19 numbers and
every GAPS.md, then commit and push. Leave the tree clean.
