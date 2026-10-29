#!/usr/bin/env bash
# One-time setup for a fresh machine or a Claude Code cloud session (docs/CLOUD_HANDOFF.md).
# Installs dependencies, checks the toolchain, regenerates the git-ignored data and indexes, and
# runs `make check`. Safe to rerun. Prints a summary at the end; exits non-zero only on a hard problem.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
problems=()
note() { printf '\n== %s\n' "$*"; }

note "toolchain"
command -v uv >/dev/null || { echo "installing uv"; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
uv --version
command -v node >/dev/null && node --version || problems+=("node missing")
node_major=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
if [ "$node_major" != "22" ]; then
  echo "Node $node_major found; the project pins Node 22 (D-002). Trying to install Node 22 with nvm or n."
  if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" && nvm install 22 && nvm use 22;
  else npx -y n 22 >/dev/null 2>&1 && hash -r; fi
  node --version || true
  [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)" = "22" ] || echo "WARNING: still not Node 22; continuing (engines is a warning, not an error)."
fi
command -v cc >/dev/null || command -v gcc >/dev/null || problems+=("no C compiler: dtaidistance builds from source (D-064)")

note "python dependencies (dtaidistance builds from source, D-064)"
uv sync || problems+=("uv sync failed")
uv run python -c "from dtaidistance import dtw; import sys; ok = dtw.try_import_c(); print('dtaidistance C path:', ok); sys.exit(0 if ok else 1)" \
  || problems+=("dtaidistance C path unavailable (install a compiler and OpenMP: libgomp on Linux, brew libomp on macOS)")

note "web dependencies and Playwright browser"
npm --prefix web install --no-audit --no-fund || problems+=("npm install failed")
(cd web && npx playwright install chromium) || (cd web && npx playwright install --with-deps chromium) \
  || echo "WARNING: Playwright browser install failed; make e2e will fail until it works."

note "data, indexes, models (git-ignored; seeded, so identical everywhere)"
make data index || problems+=("make data index failed")
make models || problems+=("make models failed")
uv run kairos-defense memory reseed >/dev/null 2>&1 || echo "note: memory reseed skipped or failed (phase 6 command)"

note "make check"
make check || problems+=("make check failed")

note "summary"
if [ ${#problems[@]} -eq 0 ]; then echo "SETUP OK"; else printf 'PROBLEM: %s\n' "${problems[@]}"; exit 1; fi
