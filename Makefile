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
.PHONY: help check test-all data index models eval api web dev demo demo-video e2e mcp live live-check clean

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

demo-video: ## Record the narrated 2-minute demo video to docs/demo/ (DEMO_SLOW=1 on a GPU machine)
	$(NPM) run build
	$(KD) replay --precompute
	mkdir -p data/cache/demo
	cd web && npx playwright test -c demo/playwright.config.ts
	cd web && node demo/encode.mjs

live: ## Live mode: build the web app and serve it on :8000; open /live and launch a scenario
	$(NPM) run build
	@echo "Live mode: open http://127.0.0.1:8000/live and launch a scenario (Ctrl-C stops the API)"
	$(KD) api --static web/dist

live-check: ## Fly every live scenario headless at 50x and score it (PASS or GAP per scenario)
	$(KD) live check --scenarios all --speed 50

e2e: ## Playwright end-to-end tests, UI screenshots and accessibility checks
	$(NPM) run build
	$(KD) replay --precompute
	$(NPM) run e2e

mcp: ## MCP server over stdio (silent recipe: stdout carries only the protocol)
	@$(KD) mcp

clean: ## Remove generated data, exports, builds and caches
	rm -rf data exports web/dist .pytest_cache .ruff_cache
