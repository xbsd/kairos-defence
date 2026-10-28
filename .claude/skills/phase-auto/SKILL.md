---
name: phase-auto
description: Unattended version of the phase skill, driven by scripts/autopilot.py. Arguments are "plan N", "revise N", "build N", "fix N <gate-log>" or "backfill N". Never waits for a human; records assumptions instead.
---

# Kairos Defense autopilot step

Arguments: $ARGUMENTS
The first word is the step, the second is the phase number N. NN is N zero-padded (phase 4 → `phase-04`).

You are running unattended inside `scripts/autopilot.py`. Nobody will answer questions. Do not ask for
approval, do not enter plan mode, and do not stop to wait. When something is ambiguous, apply CLAUDE.md
"How we work" rule 5: choose the simplest option that satisfies the exit check, record it in
`docs/DECISIONS.md`, and continue.

## Every step

- Read `CLAUDE.md`, `docs/PROGRESS.md`, the Phase N block in `docs/SPEC.md` §20 (for N = 10: `docs/phases/PHASE_10.md`) and every section it lists
  under "Read first", `docs/phases/TEMPLATES.md`, and the previous phase's `docs/phases/phase-(N-1)/REPORT.md`
  if it exists.
- Work only inside this repository. Never push. Never rewrite git history (no `reset --hard`, rebase or
  amending earlier commits). Never edit `.claude/`, `scripts/autopilot.py` or `docs/phases/gates.json`.
- Never weaken, skip, delete or mark as expected-to-fail a test, and never lower a target in SPEC §19, to
  make a gate pass. Fix the code. If a target genuinely cannot be met, say so with evidence in REPORT.md and
  DECISIONS.md and let the gate decide.
- End-to-end tests start and stop their own servers (Playwright `webServer`); no command may block on a
  running server. Exit checks that name a serving command (`make demo`, `make dev`, `make api`,
  `make mcp`) are run in the background with a time limit: start it, wait for it to answer (curl the
  port, or list the MCP tools), record the evidence, then stop it. Never leave a server running.
- The gate (`docs/phases/gates.json`) also runs `scripts/check_targets.py N` in phases 4, 5, 8 and 9. Read
  it before planning: it enforces the SPEC §19.3 and §10.9 targets (cumulatively) and the demo assertions,
  and names the exact metric keys `make eval` must write into `reports/eval_<date>.json` under
  `metrics` (for example `dtw_lift`, `latency_dtw_p95_ms`, `report_linkage`, `forecast_median_t90_m`,
  `swarm_top1`). Use those keys.
- Target shortfalls are soft (D-063): when `check_targets.py` reports only `GAP` lines, you get up to
  three fix attempts to close them honestly; after that the autopilot records them in
  `docs/phases/phase-NN/GAPS.md` and the run continues. Gaps accepted in earlier phases show as WARN; do
  not spend the current phase on them unless the plan says so. Never touch the §19 protocol, query sets,
  truth handling or metric definitions to raise a number. Broken things (tests, crashes, a metric not
  produced, e2e) still block.
- The gate also fails if the number of passing fast Python tests drops below its count at the start of
  the run, and it lists every skip or xfail marker added during the run.

- Test thoroughly: unit tests with known answers and edge cases for every new function, tests for every
  CLI command and API route you add, Vitest for components and Playwright for every page and Director
  beat you touch. Run `make test-all` (slow tests included) before committing.
- The user's standing instruction (2026-10-28): use your best judgement and do not wait for them; latency
  targets are reported but do not block (D-060); keep every README current so a phase can be rolled back.

## plan N

Write `docs/phases/phase-NN/PLAN.md` from the PLAN template in TEMPLATES.md. Change no other file. Be
concrete: file paths, test names, the exact exit-check commands and the evidence each one produces.

## revise N

The prompt lists blocking issues from an independent reviewer. Edit `docs/phases/phase-NN/PLAN.md` to
resolve every one, and record each under "Review changes". Change no other file.

## build N

1. Read `docs/phases/phase-NN/PLAN.md` and the newest `PLAN_REVIEW-*.json`; apply cheap suggestions.
2. Implement in small steps, writing tests with the code. Run `make check` after each step.
3. Run the phase's exit check exactly as SPEC §20 states it. Record commands and key output in
   `docs/phases/phase-NN/EXIT_CHECK.md` (template).
4. Write `docs/phases/phase-NN/REPORT.md` (template).
5. Create or update `README.md` in every package you touched under `src/kairos_defense/`, and
   `web/README.md` for web work (package README template). Update the "Status" section of the root README.
6. Update `docs/PROGRESS.md`: add a session-log entry and the one-line exit-check evidence. Do not change
   the phase's Status cell: the autopilot marks it done only after its own gate passes. Add
   `docs/DECISIONS.md` entries for every non-obvious choice.
7. Commit everything with `git add -A && git commit -m "phase N: <summary>"`. Leave the tree clean.

## fix N <gate-log>

Read the gate log at the path given. Find the root cause and fix it. Rerun the failing command, then the
full gate list for phase N from `docs/phases/gates.json` (the `always` list plus the phase's list). Append a
"Fix attempt" entry to REPORT.md (cause, change, evidence). Commit: `phase N: fix gate (<cause>)`.

## backfill N

Phase N was built by hand earlier. Reconstruct its documentation from `git log`, `git show --stat`,
`docs/PROGRESS.md`, `docs/DECISIONS.md` and the code. Write `PLAN.md` (as built), `REPORT.md` and
`EXIT_CHECK.md` in `docs/phases/phase-NN/` (rerun the exit-check commands now and record today's output),
plus any missing package READMEs. Change no code. Commit: `phase N: backfilled docs`.

## If truly blocked

Write `docs/phases/phase-NN/BLOCKED.md`: what failed, what you tried, the exact error, and the one decision
a human must make. Then stop.
