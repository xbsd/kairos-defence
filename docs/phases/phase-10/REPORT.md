# Phase 10: User guide, one-pager and rollback guide, report

Status: done (gate passed, `scripts/cloud_gate.py gate 10`: see `gate-1.log`) · Date: 2026-10-29 · Commits: `5c16a7a`
(plan and review), `phase 10: user guide, one-pager and rollback guide`, and the exit-check commit

## Summary

Phase 10 writes the documentation a new user, a presenter and a maintainer need without reading
the spec (`docs/phases/PHASE_10.md`):

- `docs/USER_GUIDE.md`: twelve sections in plain language, about 6,000 words outside code blocks,
  20 real screenshots;
- `web/e2e/guide.spec.ts`: captures those screenshots from the running app on every `make e2e`
  (Playwright's own server, scratch ledger), waiting for the element that proves each state first;
- `docs/ONE_PAGER.md` (about 510 words, one hero screenshot) and `docs/ROLLBACK.md` (history, tags
  `phase-04-done` to `phase-10-done`, inspection, branch and `git revert` rollbacks, regeneration);
- the root README rewritten around the documents (what it is, documents, quick start, status);
- `tests/unit/test_docs.py`: links, images and anchors resolve, every CLI command is in the guide,
  the screenshots are real, distinct PNGs written by the guide spec.

The screenshot review (§17.13) found five presentation defects, all fixed in the web app (D-166):
overprinting ghost labels, the radar shadow label running into them, the compact lens overflowing
the rail, the "No Remote ID" tag over the orbit ring, and a duplicate-looking T+120 shot. No
matcher, memory, API or data code changed; no number changed.

## What was built

| Item | Purpose | Key files |
|---|---|---|
| Screenshot spec | 20 real screenshots: Live watch at T+90 at both sizes and at T+120 with the Forecast camera, the nine Director beats, every page, the shortcuts dialog, Eval at 1440 × 900 | `web/e2e/guide.spec.ts` |
| User guide | The twelve PHASE_10.md sections: what it is, install, every screen, the demo, links and evidence, CLI reference with real output, agent tools and MCP, configuration, guardrails, evaluation, troubleshooting, glossary | `docs/USER_GUIDE.md`, `docs/guide/img/*.png` |
| One-pager | Problem, product, the demo in five beats, what is synthetic, three commands, hero image | `docs/ONE_PAGER.md` |
| Rollback guide | History, tags (and the two the cloud remote refused), inspect, roll back, regenerate, phase table | `docs/ROLLBACK.md` |
| README | What it is, the documents, every package README, quick start, status, latest evaluation | `README.md` |
| Docs tests | Links and anchors, CLI coverage from the Typer tree, screenshots | `tests/unit/test_docs.py` |
| Review fixes | Ghost label stacking, shadow label, lens sizing, tag offset | `web/src/three/ghostMath.ts`, `Ghosts.tsx`, `Installation.tsx`, `Drone.tsx`, `web/src/lens/TimeWarpLens.tsx`, `web/src/panels/LensPanel.tsx`, `web/tests/ghostMath.test.ts` |
| Package READMEs | Brought current: `sim` (the paraphrase setting), `live` (the swarm replay), `web` (the guide spec, the fixes), the root package (the docs test) | `src/kairos_defense/{sim,live}/README.md`, `src/kairos_defense/README.md`, `web/README.md` |

## Decisions and deviations from SPEC

- [D-163](../../DECISIONS.md): the guide's screenshots come from the running app on every
  `make e2e`; the PNGs are committed and `close` commits the gate run's.
- [D-164](../../DECISIONS.md): documentation tests (links, anchors, CLI coverage, screenshots).
- [D-165](../../DECISIONS.md): README and user documents (contents, real CLI output, hero image,
  rollback guidance for phases 0 to 3 and for merging the branch).
- [D-166](../../DECISIONS.md): fixes from the screenshot review (§17.13).
- [D-167](../../DECISIONS.md): the cloud remote refuses tag pushes; how to recreate
  `phase-09-done` and `phase-10-done`.

No deviation from the SPEC. PHASE_10.md asks for the guide's screenshots at 1920 × 1080; the
guide adds two at 1440 × 900 (Live watch and Eval), the size whose layout differs most.

## Tests

- New: `tests/unit/test_docs.py` (6 tests: links and anchors in each of the four documents, CLI
  coverage, screenshots), `web/tests/ghostMath.test.ts` gained the label-stacking test, and
  `web/e2e/guide.spec.ts` (3 Playwright tests, part of `make e2e`).
- At the exit check: 801 fast Python tests (795 at the start of the phase), Vitest 169 (168), e2e
  34 (31); slow tests unchanged (18). No skip or xfail marker was added.

## Exit check

| Criterion (PHASE_10.md) | Result | Evidence |
|---|---|---|
| `make check` | pass | ruff clean; 801 fast Python tests (795 at the start); web lint, typecheck, types current, Vitest 169 |
| `npm --prefix web run build` | pass | 11 s |
| `make e2e` | pass | 34 passed in 16.3 min, the 3 guide tests included; axe clean on every route |
| `python3 scripts/check_docs.py` | pass | "Documentation complete." (guide 6,098 words, 20 images; one-pager 508 words) |
| Screenshots from this run's `make e2e` | pass | all 20 PNGs written 10:59:59 to 11:03:41 UTC, after the chain began at 10:49:10 |
| Every image reviewed against §17 | pass | first run: five defects and one spec wait fixed (D-166); final images reviewed again |

Full output: [EXIT_CHECK.md](EXIT_CHECK.md). The gate (`scripts/cloud_gate.py gate 10`) reruns the
four commands.

## Metrics

Documentation only. `python3 scripts/check_docs.py`: the guide has about 6,000 words outside code
blocks and 20 distinct images of at least 20 kB; the one-pager about 510 words. The §19 numbers
are phase 9's (no matcher change): Recall@5 1.000, DTW lift +0.52, copycat-first 0%, time to match
96%, report linkage 1.000, forecast median 341 m, swarm top-1 1.000 (4 of 4); the accepted
`live_top3_incidents` gap stays (phase 4 GAPS.md).

## Known issues and follow-ups

- At 1440 × 900 the compact lens's caption can still need a scroll when the pace readout wraps;
  the curves and the matrix are visible (D-166).
- The remote of this cloud session refused tag pushes: `phase-09-done` and `phase-10-done` must be
  recreated once from a clone (`docs/ROLLBACK.md`, D-167).
- Screenshots depend on the machine's WebGL (SwiftShader here); a GPU renders the same scene with
  smoother lines.

## How to debug this phase

- `python3 scripts/check_docs.py` names every missing document, broken link, short guide, missing
  term, small or duplicate image and missing README link.
- `uv run pytest -q tests/unit/test_docs.py` checks the same links plus anchors, CLI coverage and
  the screenshots; a new CLI command fails it until the guide's section 6 documents it.
- Rerun only the screenshot spec: `npm --prefix web run build && uv run kairos-defense replay
  --precompute && cd web && npx playwright test e2e/guide.spec.ts`; images land in
  `docs/guide/img/` (each name is a literal in the spec's `snap` calls).
- A screenshot showing "Loading" or an empty theater means a wait in the spec did not hold: each
  shot first waits for its state's element (see the spec). On a slow machine Live watch plays at
  2× and the clock check allows the target second plus 7.

## Fix attempts

<!-- appended by fix steps: cause, change, evidence -->
