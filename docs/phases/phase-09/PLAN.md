# Phase 9: Swarms, agent, MCP, hardening and runbook, plan

## Goal

Finish the product (SPEC §20 Phase 9): the swarm encore (§14 matching, the §17.9 Swarm view and
Director's ninth beat), the §18 agent tools and MCP server with the optional chat slide-over, a
performance pass on Python and the web app, and a rehearsed runbook (`docs/DEMO.md`, Appendix B)
with README run instructions. The phase passes when `make clean && make data index models eval &&
make demo`, then `make e2e`, show every §19 target met (the accepted `live_top3_incidents` gap
stays WARN, D-081/D-063), the encore works, an MCP client lists the tools from `make mcp`, and
`docs/DEMO.md` is complete.

## Inputs read

- CLAUDE.md (rules 1–10, conventions, library notes), `docs/CLOUD_HANDOFF.md`.
- SPEC §14 (swarm choreography matching), §17.9 (Swarm view), §17.10 (Director, encore beat),
  §17.11–§17.13 (motion, accessibility, visual QA), §18 (agent tools, MCP, chat), §19 (eval:
  swarm query set, protocol, `swarm_top1` ≥ 0.80), §21 (definition of done), Appendix B (runbook).
- `docs/phases/phase-08/REPORT.md` (Director has 8 beats; `/swarm` is a planned placeholder;
  known issues), PROGRESS.md (phase 8 evidence; 731 fast / 747 total Python tests; Vitest 153;
  e2e 29), DECISIONS.md up to D-147 (D-049 live tracks never in derived tables; D-060 latency
  never blocks; D-063 soft gaps; D-081 accepted top-3 gap; D-104 ports; D-106 swarm encore
  writes nothing; D-139 eval targets in Python).
- `scripts/check_targets.py` (phase 9: `time_to_match_t90` ≥ 0.70, `swarm_top1` ≥ 0.80, and every
  demo row must pass, `swarm_top1` included), `docs/phases/gates.json` (phase 9 gate list).
- Code: `sim/swarm.py`, `sim/formations.py` (S1: 5 drones, line abreast → rotate 90° → split →
  V → orbit; S2: 3 drones, triangle → expand → rotate 180° → trail), `features/channels.py`
  (`choose_target`, `load_site`), `features/resample.py`, `features/windows.py` (`paa_weights`),
  `features/build.py`, `store/lance.py` (`KEYS` already names `swarm_windows`), `store/ddl.py`,
  `eval/harness.py` (`QuerySets.swarm_incidents`), `eval/demo.py` and `eval/report.py`
  (`swarm_top1` pending), `eval/targets.py`, `memory/actions.py` (`propose_matches`),
  `api/services.py`, `api/routes*.py`, `web/src/director/*`, `web/src/app/routes.ts`,
  `web/e2e/*`, `web/playwright.config.ts`. Installed `mcp` is 2.3.0: FastMCP is renamed
  `MCPServer` (`mcp.server.mcpserver`).

## Assumptions and decisions

Each is recorded in `docs/DECISIONS.md` (numbers from D-148) during the build.

- A1 (swarm detection, §14): `detect_swarm` on the resampled drone positions: a swarm when at least
  `swarm.min_drones` tracks are airborne together for at least `swarm.min_duration_s` consecutive
  seconds with every pairwise distance under `swarm.max_spacing_m`. It runs on observable radar
  data only; `incidents.is_swarm` selects candidates, detection confirms them and is reported.
- A2 (descriptors): each drone track resampled to 1 Hz on the incident's common second grid
  (linear, gaps up to `features.max_interp_gap_s`); a second counts when at least
  `swarm.min_drones` drones have a position. Per second, permutation-invariant: centroid
  (target-relative), centroid speed (m/s, centered difference), spread (RMS distance to centroid,
  m), quartiles of pairwise distances q25/q50/q75 (m), principal-axis angle (PCA, degrees,
  unwrapped with period 180°), rotation rate (deg/s, derivative of the unwrapped angle over a
  5 s centered window). The target is `choose_target` on the centroid path (the same §9.2 rule as
  single tracks).
- A3 (series and vectors): matching series `[spread, pd_q25, pd_q50, pd_q75, rot_rate,
  centroid_speed]`, z-normalized per channel (a constant channel becomes zeros, never NaN); the
  prefilter vector is PAA 16 segments per channel = 96-d, L2-normalized.
- A4 (index): `make index` adds the DuckDB derived table `swarm_features` (history swarm incidents
  only, D-049: one row per incident second with the descriptors) and the LanceDB table
  `swarm_windows` (one row per history swarm incident: `incident_id`, `installation_id`,
  `region_id`, `start_ts_ms`, `n_drones`, `duration_s`, `together_s`, 96-d `vector`). Live
  incidents are never indexed; their descriptors are computed from raw points at query time,
  only up to the query second.
- A5 (search, §14): prefilter `swarm_windows` with `start_ts_ms < query start` (prefilter=True,
  rule 3), then `dtw_ndim.distance` against every candidate's series. A query seen up to T seconds
  is compared with candidate prefixes whose length is the query's times a pace in [0.7, 1.4] (the
  generator's swarm time-warp range is the reason; 15 steps), each prefix z-normalized on its
  own; the distance is the minimum of `d / sqrt(n + m)` (band 25% of the longer series,
  `dtw.band_fraction`). Similarity = `1 / (1 + distance)`. The best prefix gives the warp ratio
  (`m / n`) and the DTW path (`dtw_ndim.warping_path`) that aligns the formation snapshots and the
  descriptor curves. Ties break by start time, then incident id. No truth is read.
- A6 (eval, §19.1–§19.3): swarm queries are the history swarm incidents of months 13–18; the team
  label comes from `track_truth.actor_id` of the incident's tracks (read only in `eval/`). A query
  with no earlier history swarm of the same team is unanswerable (D-009) and counted apart.
  `swarm_top1` = share of answerable queries whose top-1 match is the same team, each query seen
  over its whole observed flight (the encore's view); the same share at each T of the §19.2 grid
  is written as `swarm_top1_by_t` (report only). The demo row `swarm_top1` runs the live
  `DEMO-SWARM-ECHO-0614` over its whole observed flight and passes when its top 1 is
  `S1-GOLF-260503`. `eval/targets.py` and `report.py` drop the `pending` marks.
- A7 (API): `GET /api/swarm/{incident_id}?at=` (default: the whole observed flight) returns the
  §14 output: detection (`is_swarm`, `together_s`), the query descriptors, per-drone
  target-relative positions per second, the target, the ranked matches (incident, base, region,
  start time, drones, distance, similarity, warp ratio), and for the selected match (`match=`,
  default rank 1) its descriptors, positions and the DTW path as `aligned[i]` = the matched second
  for query second i. 404 for an unknown incident, 422 when the incident is not a swarm. Results
  are cached in memory per (incident, at, match). `GET /api/swarms` lists swarm incidents (live
  and history) for the page's picker. Response models in `api/schemas_swarm.py`; OpenAPI and
  `types.gen.ts` regenerated (§16.5).
- A8 (Swarm view, §17.9): a lazy page `/swarm?incident=&match=` (default: the live swarm
  incident). A react-three-fiber scene in the incident's target-relative frame: drones in flash
  blue with formation edges to each drone's nearest neighbor (computed per second from the real
  positions), the matched past swarm as an afterglow ghost at the DTW-aligned second, a target
  marker, labels with base and date. A play/pause control and a scrubber over the observed
  seconds drive a playhead (requestAnimationFrame, real recorded seconds only, rule 10); reduce
  motion jumps without easing. Descriptor curves (spread, pair-distance quartiles, rotation rate)
  for tonight and the match, the match's curve resampled onto tonight's seconds through
  `aligned`, with the playhead; the match list with similarity and pace; a text table equivalent.
- A9 (encore, §17.10): Director gains a ninth page beat `encore` (route `swarm`, key element
  `swarm-ghost`, caption computed from the swarm response: "Same choreography, N weeks apart, in
  another region: <base> on <date> and <base> tonight." with N from the two start dates). → from
  Evidence opens it; the encore writes nothing to the ledger (§15.6).
- A10 (agent tools, §18.1): `kairos_defense.agent.tools` with the eight tools over a `ToolContext`
  (ports only: `TrackStore`, `VectorStore`, `CaseMemory`, plus the matcher, recall and forecast
  built from them). `find_similar_flights(incident_id, window_s=120, k=5)` runs the matcher at
  `window_s` seconds after the incident's first radar point (history filter: started before);
  `recall_reports(incident_id, match_incident_id, query=None, k=5)`; `forecast_recovery(incident_id,
  at_s=105)`; `as_of_view(case_id, as_of_ts)`; `diff_case(case_id, t1, t2)`;
  `shift_delta(since_ts, installation_id=None)`; `propose_link(case_id, incident_id, rationale)`
  appends one `match_proposed` (actor `agent:<name>`, object with the rationale, the matcher's
  score and reasons for that incident when it ranks, `model_version`); `propose_evidence_export
  (case_id)` appends nothing (only `match_proposed` may be appended by an agent, §20 tests) and
  returns a deterministic proposal id (`EXPORT-PROPOSAL-<case>-<head seq>`) with the human step
  (`kairos-defense export --case … --approve` or the Evidence page). Every output is plain JSON
  (lists, dicts, str, float, int, bool, None). Times need `Z` or an offset (D-100).
- A11 (MCP, §18.2): `kairos_defense.agent.mcp_server.build_server(ctx_factory, allow_proposals)`
  wraps mcp 2.x `MCPServer` (FastMCP renamed; thin adapter per CLAUDE.md library rule): the six
  read-only tools always, the two proposal tools only with `--allow-proposals`. Stores open
  lazily on the first tool call, so listing tools needs no data. `kairos-defense mcp
  [--allow-proposals] [--config]` runs it over stdio; `make mcp` stops echoing its recipe (`@`) so
  stdout carries only JSON-RPC. `python -m kairos_defense.agent.probe -- make mcp` is a small
  stdio MCP client that lists the tools (exit-check evidence). While the API holds
  `data/memory.duckdb`, ledger tools return a JSON error naming the cause (DuckDB allows one
  writer per file, D-010) instead of crashing.
- A12 (chat, §18.3): `agent/llm.py` adapters behind the `LLM` port: `none` (default, panel hidden),
  `anthropic` (Messages API), `openai` and `ollama` (OpenAI-compatible chat completions with
  `llm.base_url`), over `httpx`, keys only from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`;
  `agent/prompts.py` holds the §18.3 system prompt rules; `agent/chat.py` runs the tool loop
  through the same `tools.py` functions (read-only tools only; proposals stay human-approved).
  API `GET /api/chat/status` and `POST /api/chat` (409 when the provider is `none`). The web
  app shows an "Ask" button and slide-over only when the status says enabled. Nothing downloads
  or calls out unless a user configures a provider (rule 5).
- A13 (performance pass): profile `match --at 90`, the live rerun, the swarm match and `make eval`
  (cProfile, top functions recorded in REPORT.md); cache what is recomputed per request (site
  geometry and swarm results in the API). LB_Keogh pruning only if the DTW p95 exceeds its §10.9
  budget (it is 57–81 ms against 800 ms, so not expected). Web: bundle sizes per chunk, the swarm
  page lazy and its 3D in the existing `vendor-3d` chunk; frame rate measured with the existing
  probe here (software WebGL on this GPU-less container) and recorded; the laptop's 59.9 fps
  stands until re-measured there (handoff rule).
- A14 (runbook): `docs/DEMO.md` from Appendix B with this build's real commands, beat times from
  the phase 8 1× record plus the encore, keys, fallbacks, reset, the MCP demo
  (`claude mcp add kairos-defense -- uv run kairos-defense mcp`), and the likely questions; the root
  README gets run instructions (quick start, `make demo`, `make mcp`, `make e2e`).
- A15 (scope cut if time runs short, in this order): the chat slide-over UI stays behind the
  `none` default (backend and tests still built); swarm-view polish beyond the §17.9 elements.

## Work breakdown

1. Swarm features (`src/kairos_defense/features/swarm_features.py`): `resample_drones`,
   `detect_swarm`, `swarm_descriptors`, `swarm_series`, `swarm_vector`, `SwarmTrack` dataclass;
   `load_swarm(store, incident_id, until_s=None)` reads raw points through the `TrackStore` port.
   DDL `swarm_features` in `store/ddl.py`; `features/build.py` writes it and `swarm_windows`
   (`swarm_windows_table`).
2. Swarm matching (`src/kairos_defense/match/swarm.py`): `SwarmMatcher(store, vstore, scoring)`
   with `match(incident_id, at_s=None, k=5) -> SwarmResult` (`SwarmMatch`, path, aligned index,
   positions); `prefix_dtw`. CLI `kairos-defense swarm --incident ID [--at S] [--k 5]` prints the
   ranked swarms (`cli_swarm.py`, registered in `cli.py`).
3. Eval (`src/kairos_defense/eval/swarm.py`): swarm query cases with team labels and
   answerability, `swarm_outcomes`, `swarm_metrics`; `harness.evaluate` runs them; `demo.py`
   `swarm_row`; `report.py` / `report_md.py` write `swarm_top1`, `swarm_top1_by_t`,
   `swarm_queries`, `swarm_unanswerable`; `targets.py` drops `pending`.
4. API (`api/routes_swarm.py`, `api/schemas_swarm.py`, `api/services.py` swarm matcher and
   cache); OpenAPI dump and `npm --prefix web run gen:types`; contract test examples.
5. Agent (`src/kairos_defense/agent/`): `__init__.py`, `context.py` (`ToolContext`, lazy
   factory from config), `tools.py`, `mcp_server.py`, `probe.py`, `llm.py`, `prompts.py`,
   `chat.py`; `cli_agent.py` (`mcp`), `cli.py` loses the `mcp` stub; Makefile `mcp:` recipe
   silent; API `api/routes_chat.py`.
6. Web: `web/src/pages/SwarmView.tsx`, `web/src/swarm/` (`SwarmScene.tsx`, `swarmLayer.ts`,
   `swarmMath.ts`, `DescriptorCurves.tsx`, `SwarmMatches.tsx`, `SwarmTable.tsx`), REST client
   additions in `web/src/api/pages.ts`, route `/swarm` in `app/routes.ts` (placeholder removed),
   Director beat `encore` in `director/beats.ts`, its caption in `captions.ts`, its action in
   `actions.ts`; `web/src/chat/ChatPanel.tsx` and the command-bar button (only when enabled).
7. Tests (below) with each step; `make check` after each step; `make test-all` before the commit.
8. Performance pass (A13): profile, record, apply the caches.
9. Docs: `docs/DEMO.md`, root README (run instructions, status), package READMEs, phase docs.
10. Exit check (below), `EXIT_CHECK.md`, `REPORT.md`, PROGRESS.md session log and evidence line,
    DECISIONS.md D-148+, commit `phase 9: swarm encore, agent tools and MCP, hardening, runbook`.

## Tests

Python, fast (`tests/unit`):
- `test_swarm_features.py`:
  - `test_descriptors_of_a_square_formation`: four drones on a 40 m square → spread 40/√2 m,
    q25 = q50 = 40 m, q75 = 40√2 m (6 pairs: 4 sides, 2 diagonals, linear quantiles), centroid
    speed equals the translation speed.
  - `test_descriptors_are_permutation_invariant`: shuffling drone order changes nothing.
  - `test_rotation_rate_of_a_turning_line`: a line formation turning 3°/s → rot_rate ≈ 3 within
    0.2 deg/s away from the ends; the axis unwraps across 180° (no jump).
  - `test_detect_swarm_true_and_false`: together 60 s under 300 m → swarm; spacing 400 m, 50 s
    together, or two drones only → not a swarm.
  - `test_series_and_vector_shapes`: series `(n, 6)` z-normalized, a constant channel is zeros,
    the vector is 96-d with unit norm, no NaN.
- `test_swarm_match.py` (fixture: the planted swarm nights plus every S2 night from
  `swarm_plans`, generated, written and indexed in a temp folder):
  - `test_index_writes_history_swarms_only`: `swarm_windows` holds every history swarm and no live
    incident; `swarm_features` likewise.
  - `test_demo_swarm_top1_is_s1_golf` (the §20 test): `SwarmMatcher.match("DEMO-SWARM-ECHO-0614")`
    ranks `S1-GOLF-260503` first.
  - `test_swarm_search_has_no_look_ahead`: every candidate started before the query; a query
    seen up to T uses only points up to T (descriptor count ≤ T + 1).
  - `test_swarm_result_alignment`: the DTW path is monotone and covers both ends; `aligned` has
    one entry per query second; similarity in (0, 1]; positions are `(drones, seconds, 3)`.
- `test_eval_swarm.py`: team labels and answerability on a toy truth table (first event of a team
  unanswerable); `swarm_metrics` on hand-made outcomes; the demo row passes and fails as expected;
  `targets.py` has no pending target left.
- `test_api_swarm.py`: `GET /api/swarm/DEMO-SWARM-ECHO-0614` → 200, top match `S1-GOLF-260503`,
  curve, position and `aligned` lengths agree; `?at=120` uses at most 121 seconds; unknown →
  404; a single-track incident → 422; `GET /api/swarms` lists both demo swarms.
- `test_api_contract.py`: examples for the new response models (existing contract test extended).
- `test_agent_tools.py`:
  - `test_tool_outputs_are_json_serializable`: every tool's result survives `json.dumps` and
    round-trips.
  - `test_find_similar_flights_searches_only_earlier_flights` (rule 3).
  - `test_read_only_tools_do_not_write`: ledger row count and head hash unchanged after every
    read-only tool.
  - `test_propose_link_appends_one_match_proposed`: exactly one new row, `match_proposed`, actor
    `agent:…`; `test_propose_evidence_export_appends_nothing`: no new row, a proposal id and the
    human step.
  - `test_only_proposal_tools_append_and_only_match_proposed` (the §20 test): across all tools,
    the only new event types are `match_proposed`.
  - `test_bad_times_and_unknown_ids_return_errors`.
- `test_mcp.py`:
  - `test_mcp_server_registers_every_read_only_tool` (the §20 test): default server lists exactly
    the six read-only tools.
  - `test_mcp_allow_proposals_adds_the_two_proposal_tools`.
  - `test_mcp_call_tool_returns_json` (in-process call through the server).
  - `test_mcp_stdio_client_lists_tools`: `probe.list_tools(["uv", "run", "kairos-defense",
    "mcp"])` over stdio returns the six names.
  - `test_mcp_cli_help` (`kairos-defense mcp --help` shows `--allow-proposals`).
- `test_agent_llm.py`: `none` → disabled; a scripted fake LLM drives one tool call then an answer;
  the Anthropic and OpenAI adapters build the right request (httpx `MockTransport`), read keys
  only from the environment, and fail clearly without one; the system prompt carries the §18.3
  rules.
- `test_api_chat.py`: status disabled by default; `POST /api/chat` → 409 when disabled; with a fake
  LLM injected → reply and tool-call list.
- `test_cli.py`: the `mcp` stub test becomes a real-command test; `swarm` CLI prints the ranked
  swarms on the fixture.
- `test_truth_isolation.py` (existing) keeps every new package (agent, swarm) away from truth.

Python, slow (`tests/slow/test_full_swarm.py`): on the full seeded data, `swarm_top1` ≥ 0.80 over
the answerable queries and the demo row passes.

Web, Vitest (`web/tests/`):
- `swarmMath.test.ts`: nearest-neighbor edges on known points (no duplicates, symmetric pairs
  once), aligned-second lookup and clamping, curve scaling.
- `SwarmView.test.tsx`: from a real fixture (`web/tests/fixtures/swarm.json`, dumped by
  `dump_fixtures.py`): match list order and similarity text, curves drawn, the ghost's label, the
  text table.
- `beats.test.ts` / `director.test.ts` updated: nine beats, `encore` last, a page beat on route
  `swarm`; `captions.test.ts`: the encore caption computed from the fixture ("six weeks"), no
  placeholder when data is missing.
- `ChatPanel.test.tsx`: hidden when disabled; shows reply and tool calls when enabled (mocked
  fetch).
- `router.test.ts`: `/swarm?incident=…&match=…` parses; no planned placeholder left.

Playwright (`web/e2e/`):
- `swarm.spec.ts`: the Swarm view at 1920 × 1080 and 1440 × 900: the top match is
  `S1-GOLF-260503`, the ghost (`swarm-ghost`) and the curves are visible, play advances the
  playhead, screenshots `reports/figures/ui/phase09-swarm-*.png`, axe has no serious or critical
  violation.
- `director.spec.ts`: after Evidence, → opens the encore beat; its key element `swarm-ghost` and
  computed caption are visible; screenshot `phase08-beat-09-encore-*` style at both sizes; the
  ledger head is unchanged by the encore.
- `pages.spec.ts`: `/swarm` joins the axe route list.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence |
|---|---|---|
| Rebuild from scratch | `make clean && make data index models eval` | counts (incidents, swarm incidents, `swarm_windows` rows), eval summary with `swarm_top1`, `time_to_match_t90` |
| Serve offline | `make demo` in the background (300 s limit), curl `/api/health`, `/api/swarm/DEMO-SWARM-ECHO-0614`, `/swarm`; stopped; port free | health JSON, top swarm match, HTTP 200 |
| `make e2e` | `make e2e` | pass count, encore and swarm specs, axe clean list |
| All §19 targets met (or approved gaps) | `python3 scripts/check_targets.py 9` | PASS lines; `live_top3_incidents` WARN (accepted, D-081/D-063, phase 4 GAPS.md) |
| The encore works | `director.spec.ts` encore step and `swarm.spec.ts` | pass lines, screenshots reviewed |
| An MCP client lists the tools (`make mcp`) | `uv run python -m kairos_defense.agent.probe -- make mcp` and `uv run pytest tests -q -k mcp` | the six tool names; with `--allow-proposals`, eight; tests pass |
| `docs/DEMO.md` complete | file review against Appendix B | every Appendix B section present with real commands |
| Definition of done (§21) | `make check`, `make test-all` | pass counts (≥ 731 fast) |

## Documentation to write or update

- `docs/phases/phase-09/PLAN.md` (this), `REPORT.md`, `EXIT_CHECK.md`, `PLAN_REVIEW-*.json`.
- `docs/DEMO.md` (new, Appendix B), root `README.md` (run instructions, Status section).
- Package READMEs: new `src/kairos_defense/agent/README.md`; updated `features`, `match`, `eval`,
  `api`, `store`, root package `src/kairos_defense/README.md` (CLI `mcp`, `swarm`), `web/README.md`.
- `docs/PROGRESS.md` session log and evidence line (not the Status cell), `docs/DECISIONS.md`
  D-148 onward.

## Risks and mitigations

- Swarm top-1 short of 0.80: few swarm queries (S1 and S2 differ in drone count and
  choreography), so the descriptors should separate them; if not, inspect per-channel distances
  and weights honestly (no change to query sets or truth handling).
- mcp 2.x API differences: thin adapter, tests that list and call tools in-process and over stdio.
- `make mcp` stdout pollution: the recipe is silenced and the stdio test drives the real command.
- DuckDB single-writer: the MCP ledger tools return an explicit error while the API runs; tests
  cover the error path.
- Time: the phase 9 gate rebuilds everything (`make clean`) and runs slow tests and e2e (15–30
  min); run the slow parts locally once before gating.
- Software WebGL in this container: the frame-rate spec records rather than asserts on software
  renderers (D-145); the laptop's 59.9 fps stands (handoff rule), logged as a decision.

## Out of scope

- KDB-X and Kairos adapters (§22), real LLM provider calls in tests (adapters are tested with mock
  transports), downloading embedding models, any change to the §19 protocol, query sets for the
  single-track metrics, truth handling or metric definitions, the accepted `live_top3_incidents`
  gap (handoff: optional extra after phase 10).

## Review changes

(none yet)
