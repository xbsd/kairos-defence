---
name: phase
description: Run one Kairos Defense build phase from docs/SPEC.md §20 end to end — plan, approval, build, tests, exit check, progress update, commit. Use when the user types /phase N or asks to start the next build phase.
---

# Run a Kairos Defense build phase

Requested phase: $ARGUMENTS
If no phase number was given, use the first phase not marked `done` in `docs/PROGRESS.md`.

1. **Read** `CLAUDE.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md` (it wins where it and the SPEC differ),
   the phase block in `docs/SPEC.md` §20, and every SPEC
   section the block lists under "Read first". Check that the previous phase is `done`; if not, stop and say so.
2. **Plan.** List the files you will create or change, the tests you will write, and the risks.
   Stop and wait for my approval.
3. **Build** in small steps. Write tests alongside code. Run `make check` after each step.
4. **Exit check.** Run the phase's exit check exactly as written. Paste the command and its key
   output (counts, metrics, timings) into `docs/PROGRESS.md` and set the status to `done`.
5. **Decisions.** Add one `docs/DECISIONS.md` entry per non-obvious choice.
6. **Commit** once: `phase N: <one-line summary>`.
7. **Report** what was built, the exit-check evidence, open issues, and the next phase.
   Do not start the next phase in this session.
