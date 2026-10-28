# Kairos Defense (demo)

Cross-installation drone pattern memory: DTW shape matching, hybrid report search and a
bitemporal, tamper-evident case memory, built on DuckDB and LanceDB. **Synthetic data only.**

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
