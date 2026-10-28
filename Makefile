# Kairos Defense. Python targets call `uv run kairos-defense …`; web targets call `npm --prefix web …`.
SHELL := /bin/bash

# Node 22 LTS: prefer the keg-only Homebrew install on the dev laptop (D-002); elsewhere use PATH.
NODE22_BIN := /opt/homebrew/opt/node@22/bin
ifneq ($(wildcard $(NODE22_BIN)/node),)
export PATH := $(NODE22_BIN):$(PATH)
endif

UV  ?= uv
KD  := $(UV) run kairos-defense
NPM := npm --prefix web
SEED ?= 42

.DEFAULT_GOAL := help
.PHONY: help check test-all data index models eval api web dev demo e2e mcp clean

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

check: ## Python: ruff and fast pytest. Web: lint, typecheck, Vitest
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run pytest -m "not slow" -q
	$(NPM) run check

test-all: ## All Python tests, slow ones included
	$(UV) run pytest -q

data: ## Generate synthetic data from config/ (seeded)
	$(KD) gen --seed $(SEED)

index: ## Build features, signatures and LanceDB indexes
	$(KD) index

models: ## Train the fusion model and calibrate DTW (phase 4+)
	$(KD) models

eval: ## Run the evaluation harness -> reports/eval_<date>.md
	$(KD) eval

api: ## FastAPI on :8000
	$(KD) api

web: ## Vite dev server on :5173
	$(NPM) run dev

dev: ## API on :8000 and Vite on :5173 together, with hot reload
	trap 'kill 0' INT TERM EXIT; $(KD) api --reload & $(NPM) run dev & wait

demo: ## Build the web app and serve everything from FastAPI on :8000 (offline)
	$(NPM) run build
	$(KD) replay --precompute
	$(KD) api --static web/dist

e2e: ## Playwright end-to-end tests, screenshots and accessibility checks (phase 7)
	@if grep -q '"e2e"' web/package.json; then $(NPM) run e2e; \
	else echo "e2e is not built yet: phase 7 adds Playwright."; fi

mcp: ## MCP server over stdio
	$(KD) mcp

clean: ## Remove generated data, exports, builds and caches
	rm -rf data exports web/dist .pytest_cache .ruff_cache
