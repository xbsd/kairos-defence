# Phase 10: exit-check evidence

Run in the Claude Code cloud container (4 vCPU Intel Xeon @ 2.80 GHz, Ubuntu 24.04, no GPU:
Chromium renders WebGL with SwiftShader), 2026-10-29, as one command chain started at
10:49:10 UTC (`START` below). Playwright started and stopped its own server; no server was left
running.

| Criterion (PHASE_10.md) | Command | Result |
|---|---|---|
| All checks pass | `make check` | pass: ruff clean, 237 files formatted; 801 fast Python tests passed (795 at the start of the phase); web lint, typecheck, generated types current, Vitest 169 passed (168); 222 s |
| The web app builds | `npm --prefix web run build` | pass: 11 s |
| `make e2e` passes | `make e2e` | pass: 34 passed in 16.3 min (31 from phase 9 plus the 3 `guide.spec.ts` tests); axe clean on every route; 993 s with the build |
| Documentation complete | `python3 scripts/check_docs.py` | pass: "Documentation complete." (guide 6,098 words outside code blocks, 20 images; one-pager 508 words) |
| The screenshots in `docs/guide/img/` were produced by this run's `make e2e` | `ls -l --time-style=+%H:%M:%S docs/guide/img` against the chain's start | pass: all 20 PNGs written between 10:59:59 and 11:03:41 UTC, after the chain started at 10:49:10 (sizes 61 kB to 572 kB) |
| Every image reviewed against §17 | the review notes below | pass: all 20 reviewed after the first run and again after this run; five defects found on the first run and fixed (D-166) |

## The chain

```text
$ make check && npm --prefix web run build && make e2e && python3 scripts/check_docs.py   # one chain; each step's exit and time printed
START 2026-10-29T10:49:10Z
uv run ruff check .
All checks passed!
uv run ruff format --check .
237 files already formatted
uv run pytest -m "not slow" -q
801 passed, 18 deselected in 171.03s (0:02:51)
npm --prefix web run check
eslint . --max-warnings 0 && prettier --check .  → All matched files use Prettier code style!
tsc --noEmit -p tsconfig.json
node scripts/check-types.mjs                     → src/api/types.gen.ts is current.
vitest run                                       → Test Files 38 passed (38), Tests 169 passed (169)
=== [exit 0 after 222 s] make check
=== [exit 0 after 11 s] npm --prefix web run build
=== make e2e
Running 34 tests using 1 worker
  ✓   1 e2e/director-1x.spec.ts:48:1 › Director at 1x through every §1.2 row (2.3m)
  ✓   2 e2e/director.spec.ts:40:3 › Director at 5x shows every beat's key element at 1440x900 (1.0m)
  ✓   3 e2e/director.spec.ts:40:3 › Director at 5x shows every beat's key element at 1920x1080 (1.0m)
  ✓   4 e2e/director.spec.ts:144:1 › Director never commits by itself (33.4s)
  ✓   5 e2e/director.spec.ts:162:1 › Director keys and modes: ←, Space, M, Performance mode, R (42.3s)
  ✓   6 e2e/guide.spec.ts:75:1 › guide: Live watch at T+90 (both sizes) and T+120 (2.3m)
  ✓   7 e2e/guide.spec.ts:102:1 › guide: the nine Director beats at 1920x1080 (1.0m)
  ✓   8 e2e/guide.spec.ts:159:1 › guide: the pages at 1920x1080, Eval at 1440x900 (1.4m)
  ✓   9 e2e/lens.spec.ts:8:1 › lens connectors follow the DTW path (42.8s)
  ✓  10 e2e/live.spec.ts:8:1 › streams real data at 5x (9.6s)
  ✓  11 e2e/live.spec.ts:25:1 › matches appear by T+90 and the ledger gains a block (26.8s)
  ✓  12 e2e/live.spec.ts:49:1 › approve link adds a block and turns the ring verified (18.4s)
  ✓  13 e2e/live.spec.ts:71:3 › reduce motion › reduce motion keeps the data (6.7s)
  ✓  14 e2e/live.spec.ts:83:1 › no request leaves the origin (16.3s)
  ✓  15 e2e/pages.spec.ts:31:3 › axe and the command bar on /live/DEMO-BRAVO-0828 (6.0s)
  ✓  16 e2e/pages.spec.ts:31:3 › axe and the command bar on /explainer (2.2s)
  ✓  17 e2e/pages.spec.ts:31:3 › axe and the command bar on /explainer?incident=DEMO-BRAVO-0828&at=90&track=P1-DELTA-260419-T1 (2.2s)
  ✓  18 e2e/pages.spec.ts:31:3 › axe and the command bar on /cases (1.3s)
  ✓  19 e2e/pages.spec.ts:31:3 › axe and the command bar on /cases/CASE-P1-DELTA-260419 (2.0s)
  ✓  20 e2e/pages.spec.ts:31:3 › axe and the command bar on /swarm (2.0s)
  ✓  21 e2e/pages.spec.ts:31:3 › axe and the command bar on /evidence (1.3s)
  ✓  22 e2e/pages.spec.ts:31:3 › axe and the command bar on /delta (1.9s)
  ✓  23 e2e/pages.spec.ts:31:3 › axe and the command bar on /eval (1.7s)
  ✓  24 e2e/pages.spec.ts:52:1 › the root opens Live watch for the live incident (201ms)
  ✓  25 e2e/pages.spec.ts:57:1 › layout holds at 1440 x 900 (5.1s)
  ✓  26 e2e/pages.spec.ts:70:1 › rails stack under the theater below 1280 px (5.9s)
  ✓  27 e2e/pages.spec.ts:86:1 › shortcuts dialog lists M and closes with Escape (529ms)
  ✓  28 e2e/pages8.spec.ts:29:3 › phase 8 pages at 1920x1080 (40.8s)
  ✓  29 e2e/pages8.spec.ts:29:3 › phase 8 pages at 1440x900 (39.6s)
  ✓  30 e2e/perf.spec.ts:10:1 › frame rate over 10 s of 1x playback (19.4s)
  ✓  31 e2e/screens.spec.ts:20:3 › screenshots at 1920x1080 (43.8s)
  ✓  32 e2e/screens.spec.ts:20:3 › screenshots at 1440x900 (40.9s)
  ✓  33 e2e/swarm.spec.ts:23:3 › Swarm view at 1440x900 (7.6s)
  ✓  34 e2e/swarm.spec.ts:23:3 › Swarm view at 1920x1080 (8.7s)
  34 passed (16.3m)
=== [exit 0 after 993 s] make e2e
=== python3 scripts/check_docs.py
user guide: 6098 words
user guide: 20 images
one-pager: 508 words

Documentation complete.
=== [exit 0 after 0 s] python3 scripts/check_docs.py
END 2026-10-29T11:09:36Z
```

## Screenshot timestamps

```text
$ ls -l --time-style=+%H:%M:%S docs/guide/img
155616 11:03:24 case-board-known-now.png
90214 11:03:22 case-board-known-then.png
288334 11:01:27 director-01-detection.png
313033 11:01:33 director-02-recording.png
206927 11:01:42 director-03-recognition.png
543202 11:01:54 director-04-time-warp.png
531812 11:02:01 director-05-forecast.png
550515 11:02:08 director-06-recall.png
104000 11:02:11 director-07-known.png
122683 11:02:16 director-08-evidence.png
325137 11:02:20 director-09-encore.png
87998 11:03:41 eval-1440x900.png
148427 11:03:34 eval.png
110784 11:03:30 evidence.png
185249 11:02:24 explainer.png
450079 11:01:18 live-watch-t090-1440x900.png
465747 10:59:59 live-watch-t090.png
571568 11:00:22 live-watch-t120.png
148992 11:03:32 shift-delta.png
61847 11:03:39 shortcuts.png
311849 11:03:38 swarm-view.png
```

## Screenshot review (§17.13)

Reviewed for alignment, overlap, contrast, glow restraint and legibility, against §17.1 (colors),
§17.3 (theater), §17.7 (lens), §17.9 (swarm), §17.10 (Director) and §17.12 (accessibility).

First run (10:31 to 10:36, before the fixes), findings and fixes (D-166):

1. Ghost labels overprinted ("Delta, Apr 19" over "Alpha, Mar 3") at both sizes: the per-index
   stack assumed the recovery points coincide. Fixed: nearby end points share one anchor and stack
   (`labelSlots`, unit-tested).
2. At 1440 × 900 "Radar shadow" ran into the ghost labels. Fixed: right-anchored, reading leftward
   from the wedge's center.
3. The compact lens overflowed the rail: at 1440 × 900 the cost matrix sat below the fold (the
   controls wrap), at 1920 × 1080 its caption was cut. Fixed: the header is measured and the curves
   and matrix share what remains.
4. The "No Remote ID" tag sat on the orbit ring of the trail. Fixed: 28 px above the drone.
5. The T+120 Live watch shot looked like the T+90 one (outside Director the forecast and report
   show from the first rerun). Fixed: the Forecast camera frames the orbit, the zone and County Rd 12;
   the guide explains when each result appears.
6. The Director run stopped at the time-warp beat: the spec waited for a vertical (zero-width)
   lens connector to be "visible". Fixed in the spec: it waits for the lens curves, then for the
   warped mode.

This run's images: the 20 PNGs above, reviewed again after the run. The ghost labels
stack cleanly at both sizes and through Director (beat 5 shows two clusters: Alpha and Delta in
the zone, BRAVO November on its own anchor); "Radar shadow" stands clear; the lens shows its curves,
the matrix and the full caption at 1920 × 1080 and the curves and matrix at 1440 × 900; the T+120
shot frames the orbit, the zone and County Rd 12; the "No Remote ID" tag reads clearly, though in
the Forecast camera at 1920 × 1080 it still touches the top of the orbit ring. Every caption,
number and label is computed by the app; no image shows a loading or placeholder state.

After the run, section 6 of the guide gained real example outputs for `gen`, `index`, `models`,
`eval`, `api`, `memory seed`, `memory reseed` and `memory demo` (the plan's "one real example per
command"); `models` retrained to identical weights (same training hash, only `created_at` differed,
so the committed model files were kept). `check_docs.py` and `tests/unit/test_docs.py` pass on the
final text; the gate reruns all four commands.
