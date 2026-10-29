# Phase 7: exit-check evidence

Dev laptop (Apple M4 Max, 16 cores, 128 GB, macOS 26.5.2), 2026-10-29. Working copies of every
log are under `data/cache/exit7/` (git-ignored).

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Fast tests, lint, typecheck, Vitest (gate `always`) | `make check` | pass: ruff clean, 710 passed (586 at the start), web lint, typecheck, types current, Vitest 73 passed |
| Web build (gate) | `npm --prefix web run build` | pass: `vendor-3d` 1,181 kB (323 kB gzip), `vendor` 221 kB, app 69 kB |
| `make demo` serves everything offline from FastAPI | block 1 | pass: health ok, `/` and `/live/…` serve `index.html`, two live incidents, T+90 match from the cache, every stream type by T+50 at 5× |
| D-010 resets while the API runs | block 1 | pass: `replay --reset` and `memory reseed` went through the API; ledger back at seed head `a361b4bf…` |
| `make dev` | block 2 | pass: Vite :5173 proxies `/api/health` and the WebSocket (`hello`); both stopped, ports free |
| `make e2e` (gate) | `make e2e` | pass: 19 of 19 in 2.0 min (axe: no serious or critical violation on 7 routes) |
| Screenshots reviewed per §17.13 | `reports/figures/ui/phase07-*.png` | done: 8 screenshots; 9 findings fixed (below) |
| Median frame rate and machine | `reports/figures/ui/perf.json` | 59.9 fps median, 59.9 fps P5, ANGLE Metal on Apple M4 Max, 1920 × 1080 |
| Contract and generated types are current | dump, `gen:types`, hashes before and after | pass: byte-identical |
| Phase test bullets | `uv run pytest tests/unit -q -k "api or live or lens"` | 139 passed |
| Slow tests still pass | `make test-all` | 726 passed (601 at the start) |

## make check
```text
$ make check
uv run ruff check .                 All checks passed!
uv run ruff format --check .        196 files already formatted
uv run pytest -m "not slow" -q      710 passed, 16 deselected in 39.07s
npm --prefix web run check
  eslint . --max-warnings 0 && prettier --check .   (clean)
  tsc --noEmit -p tsconfig.json                    (clean)
  node scripts/check-types.mjs                     src/api/types.gen.ts is current.
  vitest run                                       Test Files 19 passed (19); Tests 73 passed (73)
exit 0 in 50 s
```

## npm --prefix web run build (inside make e2e)
```text
dist/index.html                                            0.75 kB │ gzip:   0.37 kB
dist/assets/b612-…-normal-*.woff, *.woff2 (6 files)        13–21 kB each, served from our origin
dist/assets/index-D0EBwHTM.css                            19.08 kB │ gzip:   4.94 kB
dist/assets/index-BHLceP2r.js                             68.62 kB │ gzip:  22.42 kB
dist/assets/vendor-D9RlOCBv.js                           220.89 kB │ gzip:  69.08 kB
dist/assets/vendor-3d-CnsmKGSS.js                      1,181.12 kB │ gzip: 323.40 kB
✓ built in 178ms
```

## Block 1: make demo (background, stopped afterwards)
```text
$ make demo > data/cache/exit7/demo.log 2>&1 &     # build, replay --precompute, api --static web/dist
  demo.log: DEMO-BRAVO-0828 │ BRAVO │ 515 s │ 696 │ 95 │ 95/95 fresh │ 0 computed, 95 cached, 515 feature s
  demo.log: Kairos Defense API on http://127.0.0.1:8000 serving web/dist
$ curl -sf --retry 240 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/api/health
{"status":"ok","version":"0.0.1","live_incidents":["DEMO-BRAVO-0828","DEMO-SWARM-ECHO-0614"],"matching":true,"problems":[],"ledger_rows":4681,"ledger_head_seq":4681}
$ curl -s http://127.0.0.1:8000/ | grep -o '<title>[^<]*</title>'
<title>Kairos Defense</title>
$ curl -s http://127.0.0.1:8000/live/DEMO-BRAVO-0828 | grep -c 'id="root"'
1
$ curl -s 'http://127.0.0.1:8000/api/incidents?status=live'
DEMO-BRAVO-0828 BRAVO 2026-08-29T02:40:06.000Z 515.0 single
DEMO-SWARM-ECHO-0614 ECHO 2026-06-15T03:50:02.000Z 830.0 swarm
$ curl -s 'http://127.0.0.1:8000/api/match/DEMO-BRAVO-0828?at=90'
t_s 90.0 cached True elapsed_ms 123 case CASE-P1-DELTA-260419
  1 P1-DELTA-260419 1.0 Closed as hobbyist on Apr 20
  2 P1-ALPHA-260303 0.999 Open, unattributed
  3 P1-CHARLIE-260710 0.997 Open, unattributed
$ websocket client: speed 5, seek 40, play, 6 s
{'clock': 55, 'dtw': 4, 'features': 69, 'forecast': 5, 'hello': 1, 'ingest': 36, 'ledger': 5, 'match': 5, 'point': 55, 'recall': 5, 'rf': 35}
$ uv run kairos-defense replay --reset
… is held by the running API: reset through http://127.0.0.1:8000 (POST /api/admin/reset, D-010)
emptied live_points (54 rows), live_rf (35 rows), live_rid (0 rows) in …/data/live.duckdb; the ledger is untouched
$ uv run kairos-defense memory reseed
…/data/memory.duckdb is held by the running API: reseeded through http://127.0.0.1:8000
(POST /api/admin/reseed, D-010): 4,681 rows, head seq 4681 hash a361b4bfe3b2…e923 (verified)
$ pkill -f 'kairos-defense api --static web/dist'
port 8000 free
$ uv run kairos-defense memory verify
chain intact: 4,681 rows in …/data/memory.duckdb, head seq 4,681 hash a361b4bfe3b2…e923 recorded 2026-08-29 00:33:38Z
```
The five `ledger` messages are tonight's `incident_recorded`, `model_registered` and the first
three `match_proposed` (T+45), written to `data/memory.duckdb` by the stream, then removed by
the reseed. `rid` is absent because P1 broadcasts no Remote ID. `make demo` exits 143 because it
was stopped with SIGTERM.

## Block 2: make dev (background, stopped afterwards)
```text
$ make dev > data/cache/exit7/dev.log 2>&1 &
$ curl -sf --retry 120 --retry-delay 1 --retry-connrefused http://127.0.0.1:5173/api/health
{"status":"ok","version":"0.0.1","live_incidents":["DEMO-BRAVO-0828","DEMO-SWARM-ECHO-0614"],"matching":true,"problems":[],"ledger_rows":4681,"ledger_head_seq":4681}
$ curl -s http://127.0.0.1:5173/ | grep -o '<title>[^<]*</title>'
<title>Kairos Defense</title>
$ websocket through the Vite proxy (ws://127.0.0.1:5173/ws/replay/DEMO-BRAVO-0828): first message
hello
$ pkill -f 'kairos-defense api --reload'
dev.log: Shutting down … Application shutdown complete … Stopping reloader process
$ curl -s -o /dev/null --max-time 2 http://127.0.0.1:5173/ || echo "port 5173 free"
port 5173 free
$ curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/api/health || echo "port 8000 free"
port 8000 free
```
`make dev`'s `trap 'kill 0' INT TERM EXIT` stops its whole process group when the API exits,
which also ended the probe script before its own port check; the checks above were rerun by
hand.

## make e2e
```text
$ make e2e        # build, replay --precompute (95/95 fresh), npm run e2e
Running 19 tests using 1 worker
  ✓  1 live.spec.ts › streams real data at 5x (4.0s)
  ✓  2 live.spec.ts › matches appear by T+90 and the ledger gains a block (18.7s)
  ✓  3 live.spec.ts › approve link adds a block and turns the ring verified (10.9s)
  ✓  4 live.spec.ts › reduce motion › reduce motion keeps the data (3.0s)
  ✓  5 live.spec.ts › no request leaves the origin (10.7s)
  ✓  6–12 pages.spec.ts › axe and the command bar on /live/DEMO-BRAVO-0828, /explainer, /cases, /swarm, /evidence, /delta, /eval
  ✓ 13 pages.spec.ts › the root opens Live watch for the live incident
  ✓ 14 pages.spec.ts › layout holds at 1440 x 900
  ✓ 15 pages.spec.ts › rails stack under the theater below 1280 px
  ✓ 16 pages.spec.ts › shortcuts dialog lists M and closes with Escape
  ✓ 17 perf.spec.ts › frame rate over 10 s of 1x playback (11.8s)
  ✓ 18 screens.spec.ts › screenshots at 1920x1080 (27.4s)
  ✓ 19 screens.spec.ts › screenshots at 1440x900 (27.4s)
  19 passed (2.0m)
```
The first run had 4 failures (an ambiguous approve locator; axe `label-content-name-mismatch`
on ledger blocks; the perf spec clicking Play while playing; the shortcuts spec pressing `?`
before the page settled). All were fixed; see REPORT.md.

## Frame rate (reports/figures/ui/perf.json)
```text
fps_median 59.9, fps_p5 59.9, frame_ms_p50 16.7, frame_ms_p95 16.7, frames 601 in 10 s
viewport 1920x1080, chromium 156.0.8078.4 (Playwright headless shell)
webgl: ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Max, Unspecified Version)
theater_perf_level: full (bloom and vignette on), cpu Apple M4 Max, 16 cores, darwin 25.5.0, 128 GB
$ sysctl -n machdep.cpu.brand_string; sw_vers -productVersion
Apple M4 Max
26.5.2
```

## Screenshot review (§17.13)
Screenshots: `phase07-{first-contact,t045,t090,approved}-{1920x1080,1440x900}.png` (D-113; the
Director beats arrive in phase 8). Findings on the first set and the fixes:

| # | Finding | Fix |
|---|---|---|
| 1 | 3D labels (Housing, Flight line, Munitions, "Kairos core") cut by grid lines at 1440 × 900 | labels derive from a base material with depth testing off (D-120) |
| 2 | Fence and long ground lines drawn as dashes far from the camera | the grid no longer writes depth (D-120) |
| 3 | "No Remote ID" tag overlapped the "Fuel farm" label during the orbit | asset labels under their footprints, the tag above the drone |
| 4 | The base was small in the overview shot | overview camera about 25% closer; ring, base and core still framed |
| 5 | Signals meta read "Loiter since loiter at T+01:27" | "Loiter since T+01:27" |
| 6 | Recorder stats wrapped at 1440 px; "1 rows" | label and value rows; singular "row" |
| 7 | Ledger chain title wrapped and its badge was truncated | titles never wrap; badge "Chain verified", rows in the footer |
| 8 | Stream table tight at 1440 px | the instrument rail gives the Stream more width |
| 9 | Ledger blocks failed axe `label-content-name-mismatch` | the visible seq and hash start the accessible name |

The second set shows crisp labels, a solid fence, no overlaps, readable numbers (13–15 px
mono) and glow only on live elements; the approved entry's ring turns `--verified`. Remaining
notes: B612 Mono gives the period a full cell ("1. 00"), which is the typeface; the three scores
read 1.00 because the fusion model is very confident on these P1 flights (known since phase 6).

## Contract and generated types
```text
$ a=$(shasum -a 256 web/openapi.json web/src/api/types.gen.ts)
$ uv run kairos-defense api --dump-openapi web/openapi.json && npm --prefix web run gen:types
wrote web/openapi.json (20 paths)
febb455e…bd4c  web/openapi.json
44115381…c564  web/src/api/types.gen.ts
regenerated files identical
```

## Phase test bullets
```text
$ uv run pytest tests/unit -q -k "api or live or lens"
139 passed, 571 deselected in 11.93s
```

## make test-all
```text
$ make test-all
726 passed in 4 min (slow tests included; 601 at the start of the phase)
```
