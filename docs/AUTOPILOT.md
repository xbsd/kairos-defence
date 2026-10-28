# Autopilot: run the remaining phases unattended

`scripts/autopilot.py` runs each remaining build phase with Claude Code, with no one at the keyboard,
and stops only when a phase cannot pass its gate.

## What happens in each phase

1. **Plan.** A fresh Claude Code session writes `docs/phases/phase-NN/PLAN.md` (skill `phase-auto plan N`).
2. **Independent review.** A second, read-only session checks the plan against the phase block in SPEC §20,
   CLAUDE.md and the templates, and returns a structured verdict. If it is clean, the plan is approved
   automatically. If not, the planning session revises the plan and it is reviewed again (up to 3 rounds).
3. **Build.** A fresh session implements the plan, runs the exit check, writes `REPORT.md` and
   `EXIT_CHECK.md`, updates the package READMEs, and commits.
4. **Gate.** The script itself, not Claude, runs `make check` plus the phase's commands from
   `docs/phases/gates.json`. It then checks that the phase documents and package READMEs exist and that the
   tree is clean.
5. **Fix loop.** If the gate fails, the build session is resumed with the gate log (up to 3 attempts).
6. **Close.** The script marks the phase done in `docs/PROGRESS.md`, commits its logs and tags
   `phase-NN-done`. Then it starts the next phase in a new session.

Only the script can mark a phase done, and only after its own gate passes. Claude never approves its own
work.

## Where to run it

Run it in a terminal on your own machine (macOS, Linux or WSL), with the Claude Code CLI installed and
signed in. The script starts every session with `claude -p`, which uses your normal Claude subscription
login. Don't launch it from inside a Claude Code session, the desktop app's chat or a cloud session on
claude.ai/code: those can't start and chain new sessions on their own.

If you've been building in cloud sessions, push from there, then `git pull` into a local clone first.

## One-time setup

1. Copy the add-on files into the repository root, then `git add -A && git commit -m "add autopilot"`.
2. Update Claude Code (`claude update`). The script needs v2.1.259 or later.
3. Run `python3 scripts/autopilot.py init`. It checks the toolchain and appends the autopilot section to
   CLAUDE.md, checks that `.claude/settings.autopilot.json` exists (the allow and deny rules, passed to
   every autopilot session with `--settings`, so they never bind your interactive sessions) and runs a
   one-line smoke session. Read its output, then commit: `git add -A && git commit -m "autopilot init"`.
4. Optional but recommended: run `python3 scripts/autopilot.py backfill --phases 0-3` to write
   REPORT/EXIT_CHECK documents for the phases you built by hand, so every phase has the same paper trail.

## Run it

```bash
tmux new -s autopilot                         # so it keeps running if the terminal closes
python3 scripts/autopilot.py run              # from the first phase not done in PROGRESS.md, through 9
python3 scripts/autopilot.py run --from 5 --to 7
python3 scripts/autopilot.py run --dry-run    # print what it would do (changes nothing)
python3 scripts/autopilot.py run --push       # also push the branch and tags after each phase
```

Useful flags: `--model <id>`, `--budget <usd per session>`, `--review-rounds`, `--fix-attempts`,
`--gate-minutes`, `--build-hours`, `--limit-wait <minutes to wait after a usage limit>`.

## Watch it

```bash
tail -f docs/phases/AUTOPILOT.log            # live progress, including the tool Claude is using
python3 scripts/autopilot.py status          # phase table with costs and links to reports
```

## What gets written

| Path | Written by | Contents |
|---|---|---|
| `docs/phases/INDEX.md` | script | One row per phase: status, times, estimated cost, link to its report |
| `docs/phases/AUTOPILOT.log` | script | Timestamped run log |
| `docs/phases/phase-NN/PLAN.md` | Claude | The approved plan, including review changes |
| `docs/phases/phase-NN/PLAN_REVIEW-k.json` | reviewer | Each verdict: approved, blocking issues, suggestions |
| `docs/phases/phase-NN/REPORT.md` | Claude | What was built, decisions, tests, exit check, metrics, known issues, how to debug |
| `docs/phases/phase-NN/EXIT_CHECK.md` | Claude | Exit-check commands and their output |
| `docs/phases/phase-NN/gate-k.log` | script | Every gate command with full output, plus the documentation check |
| `docs/phases/phase-NN/transcripts/*.jsonl.gz` | script | Complete session transcripts (plan, revise, build, fix) |
| `docs/phases/phase-NN/meta.json` | script | Session ids, costs, durations, permission denials, git SHAs before and after |
| `docs/phases/phase-NN/diffstat.txt` | script | Files changed by the phase |
| `src/kairos_defense/<pkg>/README.md`, `web/README.md` | Claude | Package documentation, updated every phase |

## Debugging recipes

- **Ask the session what it did:** `claude --resume <session_id>`, with the id from that phase's
  `meta.json`. This reopens the build session interactively with its full context.
- **Read a transcript:** `gzip -dc docs/phases/phase-04/transcripts/build.jsonl.gz | jq -c 'select(.type=="assistant")' | less`
- **See what a phase changed:** `git diff phase-03-done phase-04-done --stat`, or `cat diffstat.txt`.
- **Find blocked actions:** `permission_denials` in `meta.json`, or search the transcript for `permission_denied`.
- **Roll back everything:** `git reset --hard autopilot-start-<timestamp>`. A tag is created at the start of each run.
- **Redo a phase from scratch:** `python3 scripts/autopilot.py run --from 6 --redo`.

## When it stops

The script stops when a plan isn't approved after the review rounds, a session fails repeatedly, or a gate
still fails after the fix attempts. It writes `docs/phases/phase-NN/BLOCKED.md` with the reason and marks the
phase `blocked` in PROGRESS.md. It commits the logs and rings the terminal bell. Fix the cause or make the
decision, commit, then rerun `run`. It picks up at the gate if the phase was already built.

Target shortfalls do not stop the run (D-063). When the only failures are `GAP` lines from
`scripts/check_targets.py`, the phase gets `--target-attempts` (3) fix sessions; anything still short is
written to `docs/phases/phase-NN/GAPS.md`, the phase is marked "done with gaps", and the run continues.
Later phases show accepted gaps as WARN. Latency targets are report-only (D-060). Read every GAPS.md
when the run ends. Hard failures (tests, crashes, a metric not produced, e2e, docs) still stop it.

## Safety

- Sessions run in Claude Code's **auto mode**: a classifier reviews each action before it runs and blocks
  risky ones, such as force pushes, `git reset --hard` and downloading and running scripts.
  `--permission-prompts none` means a blocked action is denied rather than waiting for you.
- Deny rules in `.claude/settings.autopilot.json` (passed with `--settings`) forbid `git push`, tags,
  history rewrites, and edits to `.claude/`, the scripts and the gate list. These rules hold in every
  permission mode.
- Before every gate the script checks that `scripts/autopilot.py`, `scripts/check_targets.py`,
  `docs/phases/gates.json` and the autopilot settings and skill are unchanged since the run started,
  and blocks if not. Review any such change before rerunning: a rerun starts from the current commit.
- `scripts/check_targets.py N` (in the gate for phases 4, 5, 8 and 9) enforces the SPEC §19.3 and §10.9
  targets and the demo assertions from the newest `reports/eval_<date>.json`, cumulatively.
- The gate fails if fewer fast Python tests pass than at the start of the run, and lists every skip or
  xfail marker added during the run in the gate log.
- Sessions and gate commands run without `ANTHROPIC_API_KEY` (so they use the subscription login),
  `GITHUB_TOKEN` or the launching session's `CLAUDE*` variables.
- The skill forbids weakening or skipping tests or lowering targets to pass a gate.
- Claude never pushes. With `--push`, the script itself fast-forward pushes the branch and tags after
  each phase (never forced); a failed push is logged and the run continues.

## If auto mode is unavailable

Auto mode needs a supported model, and your organization must not have turned it off. `init` reports the
mode its smoke session actually got. Alternatives:

- `--mode dontAsk` runs only the commands allowed in `.claude/settings.autopilot.json` and denies everything else. It's
  safer but may block a phase that needs a new command; add the rule and rerun.
- `--mode bypassPermissions` skips all checks. Use it only inside a container or VM, such as Claude Code's
  dev container, running as a non-root user with `KD_IN_CONTAINER=1`. The script refuses it elsewhere.

## Costs and limits

Each phase runs at least three sessions: plan, review and build. Fixes and review rounds add more.
`meta.json` and INDEX.md record each session's estimated cost. `--budget` caps each session. If your plan's
usage limit is reached, the script waits (`--limit-wait`, 30 minutes by default) and continues the same
session.
