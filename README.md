# Kairos Defense (demo)

Cross-installation drone pattern memory: DTW shape matching, hybrid report search and a
bitemporal, tamper-evident case memory, built on DuckDB and LanceDB. **Synthetic data only.**

## Status

| Phase | Title | Status | Docs |
|---|---|---|---|
| 0 | Scaffold | done | [report](docs/phases/phase-00/REPORT.md) |
| 1 | World, flights and radar | done | [report](docs/phases/phase-01/REPORT.md) |
| 2 | Swarms, RF, Remote ID, reports and assessments | done | see `docs/PROGRESS.md` |
| 3 | Features, windows, Euclidean baseline and eval skeleton | done | see `docs/PROGRESS.md` |
| 4 to 10 | DTW and fusion through the user guide | not started | `docs/SPEC.md` §20, `docs/phases/PHASE_10.md` |

Works today: `make check`, `make data` (seeded synthetic world, flights, swarms, sensors, paperwork
and truth), `make index`, `make eval` (Euclidean baseline) and
`uv run kairos-defense match --method euclidean --incident DEMO-BRAVO-0828 --at 90`. The web app is
a placeholder Live watch screen. Each phase's plan, report and exit-check evidence is in
`docs/phases/phase-NN/`, and the per-session log is in `docs/PROGRESS.md`.

## Run it (after Phase 9)

Prerequisites: git, uv, Python 3.11+, Node 22 LTS.

```bash
uv sync && npm --prefix web install
make data index models eval
make demo      # http://localhost:8000, then press D for Director mode
make mcp       # optional: MCP server over stdio
```

## Build it with Claude Code

1. Copy this kit into an empty git repo (`CLAUDE.md`, `docs/`, `.claude/`).
2. Run `claude` in the repo and paste the kickoff prompt from `docs/SPEC.md` §0.1, then type `/phase 0`.
3. Approve each plan, review the exit check, then `/clear` and `/phase <next>`.

Everything else is in `docs/SPEC.md`.
