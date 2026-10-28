# Phase 10 — User guide, one-pager and rollback guide

Added for the autopilot on 2026-10-28 at the user's request (D-060). It plays the role of a SPEC §20
phase block: the `phase-auto` skill and the plan reviewer read this file for N = 10. Edited by humans only.

**Goal.** Documentation that a new user, a presenter and a maintainer can each use without reading the
spec: a complete user guide with real screenshots, a one-page summary, and a rollback guide.
**Read first.** CLAUDE.md, SPEC §1, §2, §16.4, §17, §18, §19, §23 and Appendix B, `docs/DEMO.md`,
`docs/AUTOPILOT.md`, `docs/phases/INDEX.md`, every `docs/phases/phase-*/REPORT.md`, `README.md`, every
package README.

- [ ] `docs/USER_GUIDE.md`, written for an operator or analyst who has never seen the product, in plain
  language. Sections, in order:
  1. What Kairos Defense is (all data synthetic) and who uses which screen (§1.3).
  2. Install and first run: prerequisites, `uv sync`, `npm --prefix web install`,
     `make data index models eval`, `make demo`, opening http://localhost:8000.
  3. A tour of every screen with at least one real screenshot each: Live watch (theater, memory rail,
     instrument rail, command bar), Match explainer (time-warp lens), Case board (known then / known now),
     Swarm view, Evidence, Shift delta, Eval. For each: what every element means, what the colors mean
     (§17.1: flash = live, afterglow = memory, dotted bone = forecast, red = alert, green = verified),
     and what the user can do there.
  4. Running the demo: Director mode, every §1.2 beat with its screenshot, keyboard shortcuts, reset
     between runs.
  5. Approving links and building an evidence package; verifying it (`kairos-defense verify-evidence`).
  6. Command-line reference: every `kairos-defense` command, its options and a real example output.
  7. Agent tools and the MCP server: `make mcp`, `claude mcp add …`, the tool list, the approval rule.
  8. Configuration: the five YAML files and the settings people actually change.
  9. Data, guardrails and truth isolation, in plain words (§23).
  10. Evaluation: what each §19 metric means, the latest numbers, how to rerun.
  11. Troubleshooting: the ten most likely problems with their fixes (ports in use, missing data,
      stale precompute cache, Node version, Playwright browsers, a failed gate, and so on).
  12. Glossary.
- [ ] Screenshots are captured from the real running app by a repeatable script
  (`web/e2e/guide.spec.ts`, run by `make e2e`, using the Playwright `webServer`), saved as PNG under
  `docs/guide/img/` at 1920 × 1080 (and 1440 × 900 where layout differs). No mock-ups, no edited images,
  no screenshots of placeholder states. Review every image against §17 before using it.
- [ ] `docs/ONE_PAGER.md`: one printed page (250 to 700 words) for a non-technical reader: the problem,
  what the product does, the demo story in five beats, what is synthetic, how to run it in three
  commands, one hero screenshot.
- [ ] `docs/ROLLBACK.md`: how the history is organized (one commit per phase plus fix commits; tags
  `phase-NN-done` and `autopilot-start-<time>`; `docs/phases/INDEX.md` lists every tag); how to inspect
  a phase (`git diff phase-03-done phase-04-done --stat`, the phase folder); how to roll back safely
  (a new branch at a tag, or `git revert` of a phase's range, never a forced push); what to regenerate
  after a rollback (`make clean data index models eval`, `npm --prefix web install`); and a table of
  phases 0 to 10 with tag name and what each phase added. Name every tag from `phase-04-done` to
  `phase-10-done` explicitly.
- [ ] Root `README.md`: what it is, status table, quick start, and links to the user guide, the
  one-pager, the rollback guide, `docs/DEMO.md`, `docs/AUTOPILOT.md` and every package README.
- [ ] Every package README under `src/kairos_defense/` and `web/README.md` is current (template in
  `docs/phases/TEMPLATES.md`).

**Tests.** `tests/unit/test_docs.py`: every relative link and image in `README.md`, `docs/USER_GUIDE.md`,
`docs/ONE_PAGER.md` and `docs/ROLLBACK.md` resolves; every `kairos-defense` command in the CLI help is
documented in the user guide.

**Exit check.**
```bash
make check && npm --prefix web run build && make e2e && python3 scripts/check_docs.py
```
All pass; the screenshots in `docs/guide/img/` were produced by this run's `make e2e`.
