# Rollback guide

How the history of this repository is organized, how to inspect what a phase changed, and how to go
back to an earlier phase safely. Nothing here rewrites history: every rollback is a new branch or a
new commit.

## How the history is organized

- **One build commit per phase**, named `phase N: <summary>`, plus the commits around it:
  `phase N: plan and independent review` (phases 9 and 10), `phase N: checkpoint (…)` (work in
  progress saved during a long build), `phase N: fix gate (<cause>)` (a gate failed and was
  fixed), and the commits that set up the build itself (`autopilot: …`, `cloud handoff: …`).
- **Gate artifacts.** After a phase passes its gate, one more commit records the gate's logs and
  documents: `phase N: autopilot artifacts (…)` for phases 4 to 8 (run by `scripts/autopilot.py`
  on the dev laptop) and `phase N: gate artifacts (cloud session)` for phases 9 and 10 (run by
  `scripts/cloud_gate.py` in one Claude Code session, D-148).
- **Tags.** The gate tags the last commit of every phase it closes:
  `phase-04-done`, `phase-05-done`, `phase-06-done`, `phase-07-done`, `phase-08-done`,
  `phase-09-done` and `phase-10-done`. Phases 0 to 3 were built by hand before the autopilot
  existed and have no done tag; use their commits (table below). Each autopilot run also tagged
  where it started, `autopilot-start-<yyyymmdd-hhmm>` (for example
  `autopilot-start-20261028-2017`), so a whole run can be undone at once.
- **The index.** [`docs/phases/INDEX.md`](phases/INDEX.md) lists every phase with its status, times and report, and
  every tag with its commit. `docs/phases/phase-NN/` holds each phase's plan, plan reviews, report,
  exit-check evidence, gate logs and `diffstat.txt` (the files the phase changed).
- **Data is not in git.** `data/`, the LanceDB indexes and `web/dist` are generated (seeded, so
  identical on every machine); `models/*.json` and `reports/` are committed outputs that the next
  `make` regenerates.

Tags are pushed with the branch. In a fresh clone, run `git fetch origin --tags` if `git tag` lists
nothing.

**Phases 9 and 10 in the cloud session.** The git remote of the Claude Code cloud session that built
phases 9 and 10 accepted branch pushes but refused tag pushes (`send-pack: unexpected disconnect`),
so `phase-09-done` and `phase-10-done` were created in that session's clone and may be missing from
the remote (phases 4 to 8 were pushed from the laptop and are there). Each is the last commit of its
phase, `phase N: gate artifacts (cloud session)`, listed in `docs/phases/INDEX.md`. Recreate them
once from any clone:

```bash
git tag -a phase-09-done "$(git log --format=%h -1 --grep='^phase 9: gate artifacts')" -m phase-09-done
git tag -a phase-10-done "$(git log --format=%h -1 --grep='^phase 10: gate artifacts')" -m phase-10-done
git push origin phase-09-done phase-10-done
```

## Inspect a phase

```bash
git tag -l 'phase-*' 'autopilot-start-*'           # the rollback points
git show --stat phase-08-done                      # the commit a tag names
git diff phase-04-done phase-05-done --stat        # everything phase 5 changed
git log --oneline phase-08-done..phase-09-done     # the commits of phase 9
cat docs/phases/phase-09/REPORT.md                 # what phase 9 built, and how to debug it
```

For phases 0 to 3, use the commit names in the table (for example
`git diff e494995 phase-04-done --stat` for phase 4, since phase 3 has no tag).

## Roll back safely

Pick one of two ways. Never force-push and never rewrite a published branch.

**A. Look at or work from an earlier phase: a new branch at its tag.**

```bash
git switch -c rollback-to-phase-07 phase-07-done
```

Your current branch is untouched; switch back with `git switch -`.

**B. Undo a phase on the current branch: `git revert` its range.**

```bash
git revert --no-edit phase-08-done..phase-09-done   # one revert commit per phase 9 commit
# or, to undo a whole autopilot run:
git revert --no-edit autopilot-start-20261029-0239..phase-08-done
```

`git revert` adds new commits that undo the old ones, so the history stays intact and anyone who
pulled keeps a valid checkout. Resolve conflicts if a later phase touched the same lines, then
`git revert --continue`.

[`docs/AUTOPILOT.md`](AUTOPILOT.md) also shows `git reset --hard autopilot-start-…` for a local, unpublished
experiment. That command is **destructive**: it throws away every commit and uncommitted change
after the tag on your current branch. Prefer A (`git switch -c rollback <tag>`) or B.

## After a rollback: regenerate

The generated data must match the code you rolled back to:

```bash
uv sync                          # dependencies of that phase
npm --prefix web install
make clean data index models eval
```

`make clean` removes `data/`, `exports/`, `web/dist` and the caches. Before phase 4 there is no
`make models`, and before phase 3 no `make index` or `make eval`: run only the targets that exist
(`make help` lists them). Then `make check` to confirm the tree is sound.

## Phases and their tags

| Phase | Tag (or commit) | What it added |
|---|---|---|
| 0 | commit `f9258de` (no tag) | Scaffold: package layout, CLI stubs, ports, config, web app shell, `make check` |
| 1 | commit `1a13664` (no tag) | Synthetic world, calendar, actors, flights and radar, with ground truth |
| 2 | commit `06cc826` (no tag) | Swarms, RF, Remote ID, reports and assessments; the planted demo scenario |
| 3 | commit `e494995` (no tag) | Features, signatures, PAA windows, the Euclidean baseline and the evaluation skeleton |
| 4 | `phase-04-done` | DTW matcher and fusion model (one accepted gap: the live top 3, [GAPS](phases/phase-04/GAPS.md)) |
| 5 | `phase-05-done` | Report recall (hybrid search, clues) and the analog recovery forecast |
| 6 | `phase-06-done` | Case memory (Kairos-lite): ledger, hash chain, as-of views, evidence packages |
| 7 | `phase-07-done` | Streaming API and the Command Center foundation (Live watch) |
| 8 | `phase-08-done` | Time-warp lens, ghosts, forecast and recall overlay, Case board, Evidence, Director mode |
| 9 | `phase-09-done` | Swarm matching and the Swarm view encore, agent tools, MCP server, chat slide-over, runbook |
| 10 | `phase-10-done` | User guide with real screenshots, one-pager, this rollback guide, README |

Phases 9 and 10 were built on the branch `claude/cloud-phases-9-10` and their tags point at commits
on that branch. Merge it with a merge commit or a fast-forward (not a squash) to keep those tags on
the main line's history.
