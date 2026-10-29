# Phase 9: Swarms, agent, MCP, hardening and runbook, report

Status: done (awaiting the gate, `scripts/cloud_gate.py`) · Date: 2026-10-29 · Commits:
`4e814f5` (plan and review), `28be4d7` (checkpoint), the phase commit
`phase 9: swarm encore, agent tools and MCP, hardening, runbook`

## Summary

Phase 9 finishes the product:

- **Swarm encore (§14, §17.9, §17.10).** Swarm descriptors and detection, the `swarm_features` and
  `swarm_windows` tables, prefix-DTW swarm matching, the swarm evaluation (swarm top-1 1.000, 4 of
  4 answerable queries) and the demo row (`DEMO-SWARM-ECHO-0614` → `S1-GOLF-260503`), the
  `/api/swarm` routes and `kairos-defense swarm`, the Swarm view page and Director's ninth beat.
- **Agent tools and MCP (§18).** The eight §18.1 tools over the ports, an MCP server (read-only by
  default, `--allow-proposals` for the two proposal tools, mcp 2.x `MCPServer`), a stdio probe, and
  the optional chat (LLM adapters, read-only tools, a slide-over hidden unless a provider is set).
- **Hardening.** A performance pass (no pruning needed), two slow-machine fixes in e2e
  synchronization, CLI messages that never hard-wrap, stale "phase 9" texts removed.
- **Runbook.** `docs/DEMO.md` from Appendix B with this build's commands, times, keys and fallbacks;
  README run instructions.

The phase was built in one Claude Code cloud session (D-148): the main session built the swarm
backend, evaluation, API, CLI and documents and integrated everything; two forked helpers built the
agent/MCP/chat backend and the web part in parallel.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Swarm features | §14 per-second descriptors (permutation-invariant), detection, series, 96-d vectors, `load_swarm` (raw points up to T) (D-149) | `features/swarm_features.py`, `features/build.py`, `store/ddl.py` |
| Swarm matching | `swarm_windows` prefilter (started before), prefix DTW over `swarm.pace_range`, full-matrix alignment (D-150) | `match/swarm.py`, `match/dtw_rerank.py` (`series_distance`, `series_path`), `config/scoring.yaml` |
| Swarm evaluation | Query set, team labels from truth (eval only), answerability, `swarm_top1`, `swarm_top1_by_t`, the demo row (D-151) | `eval/swarm.py`, `eval/harness.py`, `eval/demo.py`, `eval/report.py`, `eval/report_md.py`, `eval/targets.py` |
| Swarm routes and CLI | `GET /api/swarms`, `GET /api/swarm/{id}?at=&match=`, cached; `kairos-defense swarm`; swarm counts in `index` (D-152) | `api/routes_swarm.py`, `api/schemas_swarm.py`, `cli_swarm.py`, `cli.py`, `cli_tables.py` |
| Agent tools | The eight §18.1 tools, JSON out, ports only, a lock, ledger per call, REST fallback while the API holds the ledger (D-158) | `agent/context.py`, `agent/tools.py`, `agent/flight_tools.py`, `agent/memory_tools.py`, `agent/common.py` |
| MCP server | `MCPServer` adapter, six read-only tools, `--allow-proposals`, the stdio probe; `make mcp` silent (D-157) | `agent/mcp_server.py`, `agent/probe.py`, `cli_agent.py`, `Makefile` |
| Chat | LLM adapters (none, anthropic, openai, ollama), §18.3 prompt rules, read-only tool loop, `/api/chat` (D-159) | `agent/llm.py`, `agent/prompts.py`, `agent/chat.py`, `api/routes_chat.py`, `api/schemas_chat.py` |
| Swarm view | `/swarm?incident=&match=`: 3D swarm with nearest-neighbor formation edges, the matched swarm as an afterglow ghost at its DTW-aligned second, a 60 s trail, playback at 5/10/20× from a store, descriptor curves with the match dashed, ranked swarms, an sr-only table (D-160) | `web/src/pages/SwarmView.tsx`, `web/src/swarm/`, `web/src/state/swarmStore.ts` |
| Encore and chat UI | Director's ninth beat with its computed caption (D-161); the Ask button and chat slide-over, shown only when a provider is enabled (D-162); the swarm Live watch points to the Swarm view | `web/src/director/{beats,actions,captions}.ts`, `web/src/chat/`, `web/src/panels/MatchList.tsx`, `web/src/app/{routes.ts,App.tsx,CommandBar.tsx}` |
| Hardening | Performance pass (D-153); e2e synchronization (D-154); CLI soft wrap (D-156); paraphrase stays off (D-155) | `cli.py`, `web/e2e/helpers.ts`, `web/e2e/lens.spec.ts`, `sim/paperwork.py` |
| Runbook | Appendix B as this build runs it | `docs/DEMO.md`, `README.md` |

## Decisions and deviations from SPEC

- [D-148](../../DECISIONS.md): one cloud session, step 3 of the handoff; the branch; the
  environment (no GPU, models retrained on Linux).
- [D-149](../../DECISIONS.md) to [D-152](../../DECISIONS.md): the swarm features, matching,
  evaluation, routes and CLI as built. Deviations: `swarm_windows` carries four columns beyond §7.5
  (`region_id`, `duration_s`, `together_s`, `is_swarm`); swarm top-1 is measured over each
  query's whole observed flight because §19.3 gives swarms no T (the per-T values are reported).
- [D-153](../../DECISIONS.md): the performance pass; no LB_Keogh.
- [D-154](../../DECISIONS.md): two e2e specs wait for the state they measure (slow machine).
- [D-155](../../DECISIONS.md): `reports_llm_paraphrase` stays refused (supersedes D-043's plan).
- [D-156](../../DECISIONS.md): CLI messages never hard-wrap (three tests depended on the temp
  path's length).
- [D-157](../../DECISIONS.md) to [D-159](../../DECISIONS.md): MCP over mcp 2.x, the agent tools,
  the chat.
- [D-160](../../DECISIONS.md) to [D-162](../../DECISIONS.md): the Swarm view, the encore beat and
  the chat panel's visibility. The ghost is re-centered on tonight's swarm but not rotated (§17.9 asks
  for time alignment; the descriptors are rotation-free).
- The plan named `tests/slow/test_full_swarm.py`; the full-data swarm check lives in
  `tests/slow/test_full_index.py::test_full_swarm_matching`, which reuses that module's full build
  instead of generating everything twice.

Plan-review suggestions (`PLAN_REVIEW-1.json`, approved with no blocking issue), applied: the
exit-check sequencing note (`make demo` as its own step); deadlines on the stdio MCP test and the
probe, and a slow test that drives `make mcp`; the chat panel built (hidden by default), not cut;
the whole-flight swarm metric decided and recorded before measuring, with the 4-of-4 arithmetic;
the full-matrix DTW path with a cost test; the §7.2 column names; the dependency changes; the
composition-root and lock decision; the REST fallback; the deliberate updates of tests whose
behavior changes; the encore caption with ECHO's real date; the playhead in a store; the pace range
as a config key; the tool-level rule-3 test for `recall_reports`; the DEMO.md command check.

## Tests

- New fast Python tests:
  - swarm: `test_swarm_features.py` (8), `test_swarm_match.py` (10), `test_eval_swarm.py` (5),
    `test_api_swarm.py` (6), `test_cli_swarm.py` (2), `test_config.py` (+2 pace-range variants);
  - agent: `test_agent_tools.py` (12), `test_mcp.py` (8), `test_agent_llm.py` (9),
    `test_api_chat.py` (3).
- New slow tests: `test_full_index.py::test_full_swarm_matching`, `test_full_mcp.py` (drives
  `make mcp` through the probe).
- Changed tests, all for intended behavior changes: `test_eval_targets.py` (no target is pending;
  the Markdown's swarm row), `test_cli.py` (the `mcp` stub test became a real-command test),
  `engine.test.ts` (nine beats, the encore page step), `router.test.ts` (the swarm route),
  `MatchList.test.tsx` (the swarm text and link), `captions.test.ts` (the encore caption),
  `evalView.test.ts` (`swarm_top1` is a real tile; the pending branch is still tested with a
  synthetic target), `director.spec.ts` (the encore step), `pages.spec.ts` (the `/swarm` ready
  marker), and the two synchronization fixes of D-154 (`helpers.ts`, `lens.spec.ts`).
- Counts: TEST-COUNTS
- No skip or xfail marker was added.

## Exit check

EXIT-TABLE

Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

`make eval` on this machine (models retrained here, D-148):

| Metric | Target | Phase 8 (laptop) | Phase 9 |
|---|---|---|---|
| Recall@5 at T = 120 s | ≥ 0.80 | 1.000 | 1.000 |
| DTW lift | ≥ +0.10 | +0.522 | +0.522 |
| Copycat-first rate | ≤ 5% | 0% | 0% |
| Time to match (top 3 by T = 90 s) | ≥ 70% | 96% | 96% |
| Report linkage | ≥ 0.70 | 1.000 | 1.000 |
| Forecast median at T = 90 s | ≤ 400 m | 340 m | 341 m |
| Swarm top-1 (whole flight, 4 answerable) | ≥ 0.80 | pending | 1.000 |
| Latency p95 prefilter / DTW / end to end | report only | 30 / 57 / 124 ms | 173 / 258 / 654 ms |
| Swarm match p95 | report only | – | 290 ms |

The latency rise is this container (4 vCPU, loaded by concurrent test runs while the eval ran), not
a code change: the single-track matcher is untouched. Swarm top-1 by T (report only): see
`swarm_by_t` in the eval JSON; shorter views are weaker because a partial choreography is mostly
transit (D-150).

## Known issues and follow-ups

- The accepted gap stays: at T+90 the live top 3 is DELTA, ALPHA-260303, CHARLIE-260710 (all P1),
  ALPHA-260502 fifth (phase 4 GAPS.md, D-081).
- The frame-rate target was not re-measured: this container has no GPU (SwiftShader). The laptop's
  59.9 fps (phase 8) stands until re-measured there (D-148).
- Swarm top-1 before the whole flight is weaker (report only): the opening seconds are transit in a
  fixed formation.
- The chat has been tested only against mock transports (no key in this environment).
- At the split the ghost's two groups can appear mirrored relative to tonight's (not rotated, D-160).
- `director-1x.spec.ts` records the phase 8 rows; the encore is covered at 5× (D-161).
- `web/tests/fixtures/swarm.json` is the largest fixture (179 kB, trimmed to 180 s of positions).
- Live watch for the swarm incident itself has no swarm camera preset; the Swarm view is the place.

## How to debug this phase

- **Swarm matching.** `uv run kairos-defense swarm --incident DEMO-SWARM-ECHO-0614 [--at 300]`
  prints the ranking; `SwarmMatcher.match(...).timings` splits load, prefilter and DTW;
  `swarm_features` (DuckDB) and `swarm_windows` (LanceDB) hold the indexed history. "swarm_windows
  is missing" means `make index`. A swarm with fewer than 20 described seconds gets no match.
- **Swarm route.** `curl ':8000/api/swarm/DEMO-SWARM-ECHO-0614'` (or `?at=120&match=…`); results are
  cached per (incident, at, match) in `Services.swarm_cache` (restart the API after `make index`).
- **Eval.** `reports/eval_<date>.json` has `metrics.swarm_top1`, `swarm_by_t` and `swarm` (every
  outcome with its top 1 and team); `check_targets.py 9` reads them.
- **MCP.** `timeout 120 uv run python -m kairos_defense.agent.probe -- make mcp` lists the tools;
  add `--allow-proposals` to the server command for eight. A tool returning
  `{"error": "ledger busy …"}` means the API holds the ledger and the REST fallback could not
  reach it.
- **Chat.** `curl :8000/api/chat/status`; `enabled: false` is the default; `problem` names a
  missing key or model.
- **Swarm view.** `swarmStore.getState()` holds the result and the playhead; the ghost chip
  (`swarm-ghost`) shows whenever a match exists; `/swarm` without `incident` opens the live swarm
  from `/api/swarms`. e2e: `npx --prefix web playwright test e2e/swarm.spec.ts`; screenshots go to
  `reports/figures/ui/phase09-swarm-*` and `phase08-beat-09-encore-*`.
- **Chat panel.** Hidden unless `/api/chat/status` returns `enabled: true` (any error hides it).

## Fix attempts

<!-- appended by fix steps: cause, change, evidence -->
