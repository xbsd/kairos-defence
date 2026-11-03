# kairos_defense.api

The FastAPI backend (SPEC §16): REST endpoints, the replay WebSocket and the built web app on one
origin.

## Responsibilities

- Compose the adapters once (`services.py`, the composition root, rule 6): the read-only main
  store, LanceDB, the matcher and recall (when models and indexes exist), the live sink, the result
  cache and the broadcasting ledger (D-104, D-110).
- Serve every §16.4 route plus `/api/health`, `/api/ledger/tail` and `/api/ledger/{seq}`
  (`routes.py`, `routes_memory.py`, D-108), and the phase 8 page routes: the Match explainer
  (`routes_explain.py`, D-135), the case list, decisions, the evidence list and verify (D-136);
  phase 9: the Swarm view (`routes_swarm.py`, D-152) and the optional chat (`routes_chat.py`,
  §18.3).
- Stream `/ws/replay/{incident_id}` (`stream.py`, §16.3, D-107).
- Define the message and REST models (`schemas.py`, §16.5): `StreamMessage`, `ClientMessage`;
  the page models in `schemas_pages.py`, the Swarm view's in `schemas_swarm.py`, the chat's in
  `schemas_chat.py`.
- Serve `web/dist` with a client-route fallback (`static.py`, D-112).
- Phase 11, live mode (D-169, D-172 to D-184): the sensor-adapter ingest contract
  (`schemas_ingest.py`), the live stream and routes (`routes_live.py`, `schemas_live.py`), the
  simulator launcher (`launcher.py`) and live mode's composition root (`live_services.py`).

## Public API

- `app.create_app(cfg=None, *, static_dir=None, memory_path=None, live_path=None, reseed=False,
  exports_path=None)`: `cfg=None` builds a schema-only app (`--dump-openapi`). `app.factory()`
  for `uvicorn --reload` (`KD_CONFIG`, `KD_STATIC`, `KD_MEMORY`, `KD_LIVE_DB`, `KD_EXPORTS`).
- `services.Services(cfg, *, memory_path=None, live_path=None, reseed=False, exports_path=None)`:
  `exports` (the evidence root, `paths.exports` unless overridden, D-137), `incident(id)`,
  `loop(id)`, `session(id)`, `reset_live()`, `reseed()`, `health()`, `close()`; raises
  `ServiceError` with the fix when data is missing or a file is locked.
- `schemas.StreamMessage` (14 types: §16.3's 13 and `matcher_trace`, D-188), `schemas.MESSAGE_MODELS`, `schemas.ClientMessage`, and the
  REST models (`Scene`, `MatchResponse`, `LedgerBlock`, `LedgerRecord`, `LinkRequest`,
  `EvidenceLine` …); `schemas_pages` (`ExplainResponse`, `ContributionRow`, `ExplainFlight`,
  `CaseSummary`, `DecisionRequest`, `DecisionResponse`, `EvidencePackage`,
  `EvidenceVerifyRequest`, `EvidenceVerifyResponse`).
- `schemas_trace` (phase 12): `MatcherTraceMsg`, `MatcherTrace`, `TraceQuery`, `TracePrefilter`,
  `TraceDtw`, `TraceDetail`, `TraceFusion`, `TraceRank` (D-187).
- `stream.encode(msg, validate=False) -> str` (NaN-free JSON).
- Routes (all JSON unless noted):
  - `GET /api/health`, `/api/installations`, `/api/installations/{id}/scene`,
    `/api/incidents?status=live|history&limit=`, `/api/match/{incident}?at=`,
    `/api/dtw/{incident}/{match_track}?at=&channel=`, `/api/history/{track}?frame=target|region`,
    `/api/eval/latest` (the newest eval JSON, with `targets` from phase 8), `/api/schema/stream`,
    `/api/trace/{incident}?at=` (`MatcherTraceMsg`: the matcher trace of the latest rerun at or
    before `at`; 422 before the first rerun, 404 unknown; D-188),
    `/api/explain/{incident}/{track}?at=` (`ExplainResponse`: the decorated match, the fusion
    contributions, intercept, logit and score, tonight's path to the rerun second, the past
    flight, its window and the §10.4 step 6 alignment; 404 as `/api/dtw`).
  - `GET /api/cases?as_of=` (`CaseSummary` list), `/api/cases/{case}?as_of=`,
    `/api/cases/{case}/diff?t1=&t2=`,
    `/api/cases/{case}/graph?as_of=`, `/api/ledger/verify`, `/api/ledger/tail?n=`,
    `/api/ledger/{seq}`, `/api/delta?since=&until=&installation=`, `/api/evidence?case=`
    (`EvidencePackage` list, newest first).
  - `POST /api/cases/{case}/links` (`LinkRequest`), `POST /api/cases/{case}/evidence`
    (`{"approve": true}`; NDJSON `file` lines then `done`), `POST /api/cases/{case}/decisions`
    (`DecisionRequest`: close, reopen, escalate, notify_law_enforcement; 422 otherwise),
    `POST /api/evidence/verify` (`{"dir": name}`, 400 outside the exports root),
    `POST /api/admin/reset`, `POST /api/admin/reseed`.
  - Phase 9: `GET /api/swarms` (`SwarmIncident` list: every swarm incident, newest first) and
    `GET /api/swarm/{incident}?at=&match=` (`SwarmResponse`: detection, the query's descriptor
    `curves` and target-relative `positions` per observed second, ranked `matches`, the selected
    `match`'s whole flight, `aligned` and the DTW `path`; 404 unknown, 422 not a swarm or a match
    not among the results, 503 without the swarm index; cached per (incident, at, match); writes
    nothing). `GET /api/chat/status` (enabled, provider, model, tools) and `POST /api/chat`
    (messages → reply and the tool calls made; 409 while `llm.provider` is `none`, §18.3).
  - `WS /ws/replay/{incident}`.
- Phase 11, live mode:
  - **The ingest contract v1** (`schemas_ingest.py`, D-173): what a real radar, RF or Remote ID
    adapter sends. JSON objects with `v: 1`, `type`, `installation_id` and `ts` (ISO 8601 with `Z`
    or an offset); region-frame meters; bearings clockwise from north. Extra fields are refused,
    so no message can carry an operator, a name or an incident (the app forms incidents).

    | `type` | Fields |
    |---|---|
    | `point` | `sensor_id` (the installation's radar), `sensor_track_id` (the radar's own id, stable per track), `x_m`, `y_m`, `alt_m` (0 to 20,000), `quality` (0 to 1) |
    | `rf` | `sensor_id` (the installation's RF sensor), `band`, `protocol_family`, `bearing_deg` [0, 360), `snr_db` |
    | `rid` | `serial`, `drone_x_m`, `drone_y_m`, `op_x_m`, `op_y_m` |
    | `heartbeat` | `rate` (feed seconds per wall second, default 1): advances the installation's feed time, on which incidents close |

    Send on `WS /ws/ingest` (one object or an array per frame) or `POST /api/ingest`
    (`{"messages": [...]}`, at most 10,000). Each frame or batch gets an `IngestAck`:
    `{"type": "ack", "accepted": n, "detections": n, "rejected": [{"index": i, "reason": "…"}]}`.
    Besides schema errors the app rejects unknown installations, a sensor that is not that
    installation's sensor of that kind, timestamps at or before the end of the history (rule 3)
    and messages more than `live.max_lateness_s` behind the installation's feed time.
  - `WS /ws/live/{installation}`: `LiveStreamMessage` (the §16.3 types, a `hello` per incident with
    `duration_s` 0, plus `incident_opened`, `incident_closed`, `swarm_match`); a 120 s catch-up on
    connect; 4404 for an unknown installation.
  - `GET /api/live/status` (`LiveStatus`: feeds, incidents since the last reset, `pending`,
    `learned_tracks`, the simulator without the actor), `GET /api/live/scenarios`
    (`ScenarioInfo` list), `POST /api/live/reset` (`LiveResetResponse`; stops a running simulator),
    `POST /api/sim/launch` (`SimLaunchRequest` → `SimLaunchResponse`; 409 while one runs, 422 for a
    bad scenario, actor, base or speed), `POST /api/sim/stop` (`SimStopResponse`: `stopped` and the
    simulator state; keeps every live row, and the launcher's exit hook closes the incidents it fed,
    D-192), `GET /api/live/incidents/{id}/reveal` (`RevealResponse`
    through `kairos_defense.eval.reveal`; 404 unknown, 409 until closed; never stored, D-170),
    `GET /api/live/trace?installation=` (`MatcherTraceMsg`: the latest fresh live rerun's trace;
    404 before any, D-188), `GET /api/schema/live-stream`.
  - `launcher.SimLauncher(folder, config_dir, *, on_exit, command)`: `launch(args) -> {pid}`
    (`SimulatorBusy`), `state()`, `running()`, `wait(timeout)`, `stop()`.
  - `live_services.LiveServices(svc, folder, *, threaded, sim_command, config_dir)`: `feed`,
    `vectors`, `store` / `rest_store` (composite), `matcher`, `recall`, `swarm_matcher`, `hub`,
    `worker`, `compute`, `launcher`; `status()`, `reset()`, `close()`.
  - `create_app(..., live_mode_path=, live_threaded=, sim_command=, config_dir=)`;
    `Services.live` (None when live mode cannot start; `/api/live/*` then answer 503). CLI
    `api --live-mode-dir`, env `KD_LIVE_MODE`.

## Data in and out

Reads the main database read-only, LanceDB, `models/`, `reports/eval_*.json`; writes
`data/live.duckdb`, `data/memory.duckdb` (appends only), `data/cache/live/`, `exports/` (or the
`--exports` folder).
Live mode writes only under `paths.live_mode` (D-172) and the ledger (proposals); the reveal
reads the truth file through `kairos_defense.eval` and stores nothing.

## How it works

The lifespan builds `Services` on startup. REST handlers are sync (thread pool) and hold the store
lock for reads. The WebSocket accepts, sends `hello`, then every 100 ms applies the client messages
that arrived and runs `Session.step` in the thread pool, sending what it returns. Ledger appends
from any route are published to every open session as `ledger` messages. `POST /api/admin/reseed`
closes the ledger under the locks, rebuilds it with `store.ledger_duck.reseed_ledger` and reopens
it (D-010). Times in queries and bodies need `Z` or an offset (422 otherwise).

## Configuration

`config/app.yaml` paths (`duckdb`, `memory`, `live`, `lancedb`, `models`, `reports`, `exports`,
`cache`, `signing`), `replay.default_speed`; `config/scoring.yaml` (`live`, the matcher's keys).

## Tests

`tests/unit/test_api_rest.py`, `test_api_ws.py` (real WebSocket through `TestClient`, validated
messages), `test_api_static.py`, `test_api_contract.py` (one example of every message type; the
union is exactly §16.3; `web/openapi.json` is current). Fixture `api` in `tests/conftest.py`
(module scope; tests that write call `POST /api/admin/reseed`). `KD_VALIDATE_STREAM=1` validates
every outgoing message against `StreamMessage`. Phase 8: `test_api_explain.py` (contributions
reproduce the score, no look-ahead, window and alignment, 404s), `test_api_cases.py` (case list,
the known-then graph, decisions), `test_api_evidence.py` (list, verify passes then fails after
one byte, path traversal refused). Phase 9: `test_api_swarm.py` (the demo swarm's top match,
alignment and position lengths, `at`, another match, errors, the cache, no ledger write) on the
`swarm_index` fixture; `test_api_chat.py` (disabled by default, a fake LLM's reply and tool
calls).
Phase 11: `test_api_live.py` (ingest WS and REST acks, the live stream from open to close
validated against `LiveStreamMessage`, 409 then the reveal, nothing revealed stored, learned
history in `/api/history`, launch one at a time and validation, a launched child's log never
names the actor, reset), `test_api_live_contract.py`, `test_ingest_schema.py`.
Phase 12: `test_api_trace.py` (a `matcher_trace` after each replay `match` with the same top 3,
`GET /api/trace` at the latest rerun at or before `at`, 404 and 422, `GET /api/live/trace` 404
before a rerun), `test_api_live.py` (the live trace after a flight equals the last streamed one),
and the contract tests' type sets with `matcher_trace`.

## Gotchas

- After changing `schemas.py`: `uv run kairos-defense api --dump-openapi web/openapi.json && npm
  --prefix web run gen:types` (the contract test and `npm run check:types` fail otherwise).
- A process holding the main database read-write (`make index`) stops the API from starting.
- The server binds 127.0.0.1 and has no authentication (§2: not in v1).
- Lock order: the store lock before the memory lock.
- `POST /api/evidence/verify` takes a folder name from `GET /api/evidence`, never a path: anything
  that resolves outside the exports root is a 400.
- The launcher passes the actor on the child's command line only: never log the argv, never read
  the child's log (D-182). A `random` prober is resolved in the child.
- `GET /api/history/{track}` serves a `LIVE-` track only once its incident is closed and learned.

## Changelog

- Phase 7: package created.
- Phase 8: `routes_explain.py`, `schemas_pages.py`; `/api/cases`, decisions, evidence list and
  verify; `--exports` / `exports_path` (D-135 to D-137).
- Phase 9: `routes_swarm.py`, `schemas_swarm.py` (D-152); `routes_chat.py`, `schemas_chat.py`
  (§18.3); `Services.swarm_matcher` and `swarm_cache`.
- Demo video (D-168): `create_app(..., time_scale=)` and `Services(time_scale=)`: below 1 the replay
  WebSocket's sessions run on `live.replay.scaled_clock` (slow motion for frame-perfect screen
  capture, `api --time-scale`); `KD_TIME_SCALE` under `--reload`.
- Phase 11: `schemas_ingest.py`, `schemas_live.py`, `routes_live.py`, `launcher.py`,
  `live_services.py`; `/api/history` reads learned live tracks; `create_app` and `Services` take
  the live-mode folder, the worker mode, a launcher command and the config folder (D-172 to
  D-184).
- Phase 12: `schemas_trace.py`; `matcher_trace` on the replay and live streams; `GET
  /api/trace/{incident_id}?at=` and `GET /api/live/trace?installation=` (D-188).
