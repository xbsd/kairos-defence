# Phase 12: exit-check evidence

Run in the Claude Code cloud container (4 vCPU, Ubuntu, no GPU: Chromium renders WebGL with
SwiftShader), 2026-11-03 02:39 to 03:03 UTC, as one command chain, exactly the block's exit check:

```bash
make check && npm --prefix web run build && make e2e && python3 scripts/check_docs.py
```

It took 24 min 23 s and exited 0. Playwright started and stopped its own server and, in
`livemode.spec.ts`, `workbench.spec.ts` and the guide's live-mode test, one simulator each. No
server or child was left running.

| Criterion (PHASE_12.md) | Command | Result |
|---|---|---|
| All checks pass | `make check` | pass: ruff clean, 273 files formatted; 929 fast Python tests (914 at the start of the phase), 19 slow deselected; web lint, typecheck, generated types current, Vitest 203 (184) |
| The web app builds | `npm --prefix web run build` | pass: built in 1.71 s |
| The end-to-end tests pass, including the workbench during a live scenario | `make e2e` | pass: 38 passed in 19.0 min (35 before this phase, plus `workbench.spec.ts` ×2 and the guide's live-mode test) |
| The documentation is complete | `python3 scripts/check_docs.py` | pass: "Documentation complete." (guide 8,091 words, 24 images; one-pager 538 words) |
| The guide's new screenshots were produced by this run's `make e2e` | file times below | pass: all four written between 02:53:57 and 02:55:40 UTC, inside the `make e2e` step (02:44:07 to 03:03:24) |

## `make check`

```text
uv run ruff check .                 → All checks passed!
uv run ruff format --check .        → 273 files already formatted
uv run pytest -m "not slow" -q      → 929 passed, 19 deselected in 250.56s (0:04:10)
npm --prefix web run check          → eslint and prettier clean; tsc clean; src/api/types.gen.ts is current;
                                      Test Files 42 passed (42), Tests 203 passed (203)
make check: 296 s, 02:39:01 → 02:43:57 UTC
```

## `make e2e`

```text
npm --prefix web run build          → ✓ built
uv run kairos-defense replay --precompute
  DEMO-BRAVO-0828: 95/95 fresh, 0 computed, 95 cached (cache format 2, with the matcher trace)
npm --prefix web run e2e
Running 38 tests using 1 worker
  ✓   1 e2e/director-1x.spec.ts › Director at 1x through every §1.2 row (2.2m)
  ✓   6 e2e/guide.spec.ts › guide: Live watch at T+90 (both sizes) and T+120 (2.1m)
  ✓   9 e2e/guide.spec.ts › guide: live mode at 1920x1080 (launcher, incident, workbench, reveal) (1.8m)
  ✓  10 e2e/lens.spec.ts › lens connectors follow the DTW path (36.0s)
  ✓  16 e2e/livemode.spec.ts › a returning prober flown live is recognized and revealed (1.2m)
  ✓  17 e2e/pages.spec.ts › axe and the command bar on /live/DEMO-BRAVO-0828 (3.2s)
  ✓  19 e2e/pages.spec.ts › axe and the command bar on /explainer?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1 (1.9s)
  ✓  27 e2e/pages.spec.ts › layout holds at 1440 x 900 (1.5s)
  ✓  37 e2e/workbench.spec.ts › the workbench replays a live rerun, pinned, and settles on the Matches panel's (1.4m)
  ✓  38 e2e/workbench.spec.ts › the workbench from the Match explainer replays that replay second (9.6s)
  … (38 tests; every one passed)
  38 passed (19.0m)
make e2e: 1157 s, 02:44:07 → 03:03:24 UTC
```

`workbench.spec.ts`, first test: launched `returning-prober` at 20× at Bravo from the Live page;
once the "DTW workbench" button under the matches was enabled, opened it and read the pinned
rerun from `data-t` and the header ("DTW workbench: LIVE-BRAVO-…, rerun T+…"); saw
`data-stage=align`, `data-step` reach 3 and more, the warping path, the curves and the readout;
saw "Newer rerun available (T+…): replay it" appear while `data-t` stayed the pinned rerun; ran axe
on the open dialog (no serious or critical violation); set 10 per second and waited for
`data-stage=done` with the pinned rerun unchanged and five fused entries; took screenshots at
1440 × 900 and 1920 × 1080. After the incident closed (no fresh rerun follows), it reopened the
workbench, let it settle, and checked that its rerun second equals the Matches panel's "At T+…"
and its fused top 3 equal the panel's three entries, with no newer rerun offered. Second test: the
Match explainer at T+90, "Watch the matcher work", `data-t` 90 and "rerun T+01:30" in the header,
Pause then two Steps (one candidate each), axe, Play to the end, Close.

## `python3 scripts/check_docs.py`

```text
user guide: 8091 words
user guide: 24 images
one-pager: 538 words

Documentation complete.
```

## The guide's live-mode screenshots

Written by `web/e2e/guide.spec.ts` ("guide: live mode at 1920x1080 …") in this run, each 1920 × 1080:

| Image | Written (UTC) | Bytes |
|---|---|---|
| `docs/guide/img/live-mode-launcher.png` | 2026-11-03 02:53:57 | 1,739,675 |
| `docs/guide/img/live-mode-incident.png` | 2026-11-03 02:54:14 | 400,972 |
| `docs/guide/img/live-mode-workbench.png` | 2026-11-03 02:54:37 | 316,989 |
| `docs/guide/img/live-mode-reveal.png` | 2026-11-03 02:55:40 | 306,957 |

## Screenshot review (§17.13)

Reviewed `docs/guide/img/live-mode-*.png` and `reports/figures/ui/phase12-workbench-*.png`
(1440 × 900 and 1920 × 1080). Fixed after review:

1. The workbench's connectors fanned between the two curves' baselines; they now join each
   aligned pair of samples on the curves, as the time-warp lens does.
2. Once fused, the workbench showed the last candidate computed (often a poor match); it now
   shows the fused #1's alignment and says "fused rank 1".
3. The fused entries' reasons were cut at one line; they now take up to two.
4. "DTW workbench" wrapped onto two lines in the Matches footer; it no longer wraps.
5. The header said "rerun T+80" while the rest of the app says "T+01:20"; it uses the app's
   format now.
6. The Live page's Stream panel showed blank rows at 20× (also in phase 11's screenshot): with
   about 8 frames a second here, every visible row's fade had not started. Rows now appear
   without the fade when they arrive faster than 10 a second, and never at more than 10× (D-191).
   The final incident shot shows every row.
7. The shortlist repeated a swarm's incident name once per drone (`ECHO-260806-2049` four times);
   an incident with several shortlisted tracks now shows each track (`ECHO-260806-2049 T3`).

The layout holds at 1440 × 900: the dialog fits (shortlist, alignment and ranking in three
columns), and nothing overflows the page.
