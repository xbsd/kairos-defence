# Kairos Defense (demo)

Cross-installation drone pattern memory: DTW shape matching, hybrid report search and a
bitemporal, tamper-evident case memory, built on DuckDB and LanceDB. **Synthetic data only.**

## Status

| Phase | Title | Status | Docs |
|---|---|---|---|
| 0 | Scaffold | done | [report](docs/phases/phase-00/REPORT.md) |
| 1 | World, flights and radar | done | [report](docs/phases/phase-01/REPORT.md) |
| 2 | Swarms, RF, Remote ID, reports and assessments | done | [report](docs/phases/phase-02/REPORT.md) |
| 3 | Features, windows, Euclidean baseline and eval skeleton | done | [report](docs/phases/phase-03/REPORT.md) |
| 4 | DTW matcher and fusion model | done with one accepted gap (live top 3, [GAPS](docs/phases/phase-04/GAPS.md)) | [report](docs/phases/phase-04/REPORT.md) |
| 5 | Report recall and analog forecast | done | [report](docs/phases/phase-05/REPORT.md), [exit check](docs/phases/phase-05/EXIT_CHECK.md) |
| 6 | Case memory (Kairos-lite) | done | [report](docs/phases/phase-06/REPORT.md), [exit check](docs/phases/phase-06/EXIT_CHECK.md) |
| 7 | Streaming API and Command Center foundation | built; awaiting the autopilot gate | [report](docs/phases/phase-07/REPORT.md), [exit check](docs/phases/phase-07/EXIT_CHECK.md) |
| 8 to 10 | Memorable moments through the user guide | not started | `docs/SPEC.md` §20, `docs/phases/PHASE_10.md` |

Works today: `make check`, `make data` (seeded synthetic world, flights, swarms, sensors, paperwork
and truth), `make index` (tracks, windows, and the report index with full-text search), `make
models` (fusion model and DTW calibration, about 45 s), `make eval` (DTW + fusion: Recall@5 1.000,
DTW lift +0.522, copycat-first 0%, report linkage 1.000, forecast median 340 m at T = 90 s),
`uv run kairos-defense match --incident DEMO-BRAVO-0828 --at 90` (DTW by default; `--method
euclidean` for the baseline), `uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105`
(the recovery zone, 2.2 km northwest of BRAVO's fuel farm, with County Rd 12 crossing it) and
`uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120` (the DELTA report at rank 1,
clues linked), and the case memory: `uv run kairos-defense memory reseed` (4,681 history events,
hash-chained), `memory verify`, `memory show CASE-P1-DELTA-260419 --as-of 2026-04-20T10:00-05:00`
(hobbyist, closed, no links), `memory demo --approve` (the case "known then" and "known now" side
by side, on a scratch copy), `export --case … --approve` (a signed evidence package) and
`verify-evidence <dir>`. From phase 7 the Command Center runs: `make demo` (http://localhost:8000,
one offline process: the FastAPI REST API, the `/ws/replay/{incident}` stream and the built web
app) opens Live watch for `DEMO-BRAVO-0828`: a 3D theater fed by the real replay (radar sweep, RF
bearings, the drone and its phosphor trail, data packets into the Kairos core), the Stream,
Signals, Recorder and Ledger chain instruments, and the match list with Approve and Reject that
write to the ledger. `make dev` runs the API and Vite with hot reload; `make e2e` runs Playwright
(screenshots and a frame-rate probe in `reports/figures/ui/`, axe checks). `uv run kairos-defense
replay --reset` and `memory reseed` work while the demo runs (through the API). Everything runs
offline; `kairos-defense fetch-models` is the only command that downloads (an optional embedding
model). Each
phase's plan, report and exit-check evidence is in `docs/phases/phase-NN/`, and the per-session log
is in `docs/PROGRESS.md`.

## Run it (after Phase 9)

Prerequisites: git, uv, Python 3.11+, Node 22 LTS.

```bash
uv sync && npm --prefix web install
make data index models eval
make demo      # http://localhost:8000 (Director mode, D, arrives in phase 8)
make dev       # API on :8000 and Vite on :5173 with hot reload
make e2e       # first time: npx --prefix web playwright install chromium
make mcp       # optional: MCP server over stdio
```

## Build it with Claude Code

1. Copy this kit into an empty git repo (`CLAUDE.md`, `docs/`, `.claude/`).
2. Run `claude` in the repo and paste the kickoff prompt from `docs/SPEC.md` §0.1, then type `/phase 0`.
3. Approve each plan, review the exit check, then `/clear` and `/phase <next>`.

Everything else is in `docs/SPEC.md`.
