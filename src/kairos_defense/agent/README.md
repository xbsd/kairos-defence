# kairos_defense.agent

Agent tools, the MCP server and the optional chat panel (SPEC §18): the product's memory, opened
to AI agents without giving them the right to commit anything.

## Responsibilities

- `flight_tools.py` (similar flights, recall, forecast) and `memory_tools.py` (as-of view, diff,
  shift delta, the two proposals): the eight §18.1 tools as functions over a `ToolContext`, JSON
  in and out, no truth access; `common.py` holds their helpers (JSON safety, argument and time
  checks, the query loader, ledger reads).
- `tools.py`: the registry (`TOOLS`, `READ_ONLY`, `PROPOSALS`, re-exporting the tools),
  `TOOL_SPECS` (JSON Schemas for the chat) and `call_tool` (dispatch, argument checks, errors as
  `{"error": …}`).
- `context.py`: `ToolContext`, the agent's composition root (extends D-104): lazy adapters from
  the config, or the API's own handles; the ledger opened per call; the REST fallback while the
  API holds the ledger; the lock that serializes tool calls.
- `mcp_server.py`: `build_server` and `serve`, a thin adapter over the `mcp` 2.x `MCPServer` (§18.2's
  `FastMCP`, renamed): read-only tools by default, proposal tools with `--allow-proposals`.
- `probe.py`: a minimal stdio MCP client that lists a server's tools (exit-check evidence).
- `llm.py`, `prompts.py`, `chat.py`: the optional chat panel (§18.3): provider adapters behind the
  `LLM` port, the system prompt rules, and the tool loop over the read-only tools.

## Public API

| Name | Purpose |
|---|---|
| `tools.find_similar_flights(ctx, incident_id, window_s=120, k=5, track_id=None)` | DTW matches of the incident's track as seen `window_s` s after first contact (the replay second); only earlier flights |
| `tools.recall_reports(ctx, incident_id, match_incident_id, query=None, k=5, at_s=120)` | Reports of one matched incident with clue spans; event before the query start, filed by start + `at_s` |
| `tools.forecast_recovery(ctx, incident_id, at_s=105)` | §13 zone: center and radius (region m), exit path, roads, distance and bearing from the target |
| `tools.as_of_view(ctx, case_id, as_of_ts)` | `CaseSnapshot.to_dict()` at a transaction time (the API's `/api/cases/{id}` shape) |
| `tools.diff_case(ctx, case_id, t1, t2=None)` | `{case_id, t1, t2, items, groups}` (the API's diff shape) |
| `tools.shift_delta(ctx, since_ts, installation_id=None, until_ts=None)` | The §15.8 shift delta |
| `tools.propose_link(ctx, case_id, incident_id, rationale)` | Appends one `match_proposed` (actor `agent:<name>`), with the matcher's evidence when one flight ranks the other |
| `tools.propose_evidence_export(ctx, case_id)` | Appends nothing; `EXPORT-PROPOSAL-<case>-<head seq>` and the human step |
| `tools.call_tool(ctx, name, arguments, allowed=…)` | Run a tool under the lock; errors as JSON |
| `context.ToolContext(cfg, *, store=None, vstore=None, matcher=None, recall=None, memory=None, memory_path=None, agent="mcp", api_base=…, lock=None, clock=utc_now)` | What the tools run on |
| `context.ToolError`, `ToolUnavailable`, `LedgerBusy` | Bad input; missing data or models; the ledger held by another process |
| `mcp_server.build_server(ctx_factory, allow_proposals=False)` | The `MCPServer`; `ctx_factory()` is called on the first tool call |
| `probe.list_tools(cmd, timeout_s=90)`, `probe.main(argv)` | List an MCP server's tools over stdio |
| `llm.make_llm(llm_cfg, *, transport=None, env=None)` | `NoLLM`, `AnthropicLLM` or `OpenAICompatibleLLM` (OpenAI, Ollama) |
| `chat.run_chat(llm, ctx, messages, max_steps=6)` | `{reply, tool_calls, stop_reason, provider, model}` |

Times given to tools need `Z` or an offset (D-100). Every output is plain JSON: numbers, strings,
booleans, null, lists and objects; times as ISO 8601 UTC with `Z`; positions in region meters.

## Data in and out

- Reads, through the ports: `track_points`, `incidents`, `track_features`, `track_signatures`,
  LanceDB `flight_windows` and `reports`, the ledger (`data/memory.duckdb`), the models.
- Writes: only `propose_link`, one `match_proposed` row per call. Nothing else, ever (rule 7 and
  rule 8; the ledger itself refuses any other event type from an `agent:` actor, D-094).
- Never opens `data/truth.duckdb` (rule 2; `tests/unit/test_truth_isolation.py` scans this package).

## How it works

- The MCP server registers one small wrapper per tool with an explicit signature (the server
  derives each input schema from it); the wrapper calls `call_tool`, so a bad id or time comes back
  as `{"error": …}` JSON. The `ToolContext` is built on the first call, so `make mcp` lists the
  tools on a machine with no data.
- Track data and indexes stay open read-only; the ledger is opened per call and closed after, so
  the server never holds it between calls. While the API holds it, the read tools ask
  `/api/cases/{id}`, `/api/cases/{id}/diff` and `/api/delta` on 127.0.0.1:8000 (D-010) and a
  proposal is refused with the cause.
- `propose_link` looks for evidence both ways: the proposed incident's own earlier matches among
  the case's members, else the founder's earlier matches that include it (at T+120 s).
- The chat (`POST /api/chat`) offers only the six read-only tools; a requested proposal comes back
  as "not available". Off by default (`llm.provider: none`): nothing calls out (rule 5).
- Anthropic: `POST https://api.anthropic.com/v1/messages`, `anthropic-version: 2026-10-21`, model
  `claude-opus-5-5` unless `llm.model` names another, no sampling parameters, the server-side
  refusal fallback on (`fallbacks: "default"`). OpenAI and Ollama: `POST {base}/chat/completions`.

## Configuration

- `config/app.yaml`: `llm.provider` (`none` | `anthropic` | `openai` | `ollama`), `llm.model`,
  `llm.base_url`; `paths.duckdb`, `paths.lancedb`, `paths.models`, `paths.memory`.
- `config/scoring.yaml`: `live.min_track_s` (the smallest `window_s`/`at_s`), the matcher, recall
  and forecast settings the tools inherit.
- Environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (never from files or the config).
- CLI: `kairos-defense mcp [--allow-proposals] [--agent NAME] [--memory PATH] [--api URL]`.

## Tests

- `tests/unit/test_agent_tools.py`: JSON outputs, no look-ahead (matches and recalled reports),
  read-only tools never write, `propose_link` appends exactly one `match_proposed`,
  `propose_evidence_export` appends nothing, errors, the API fallback, the per-call ledger.
- `tests/unit/test_mcp.py`: registered tools (6, or 8 with proposals), hints and schemas, calls
  return JSON, a stdio client lists the tools, the probe's exit codes, `mcp --help`.
- `tests/unit/test_agent_llm.py`: adapters on `httpx.MockTransport`, keys from the environment,
  the chat loop on a scripted LLM, the system prompt rules.
- `tests/unit/test_api_chat.py`: the routes; `tests/slow/test_full_mcp.py`: `make mcp` itself.
- Run: `uv run pytest tests -q -k "mcp or agent or chat"`.

## Gotchas

- `mcp` 1.x code (`from mcp.server.fastmcp import FastMCP`) does not import on 2.x: use
  `mcp_server.build_server`.
- Anything printed to stdout corrupts the MCP stream: log to stderr, and keep `make mcp` silent.
- DuckDB allows one writer per file: a proposal while `make demo` runs is refused; stop the API or
  approve on the Case board.
- The chat's tool results are cut at 30,000 characters before they go back to the model.

## Changelog

- Phase 9: the package (tools, context, MCP server, probe, LLM adapters, prompt, chat loop).
