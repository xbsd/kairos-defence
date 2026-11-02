# Kairos Defense — instructions for Claude Code

Kairos Defense is a demo product: a cross-installation memory of drone behavior. It matches a live drone
track against every past track (DTW shape matching), retrieves the written reports tied to those past
flights (hybrid vector + keyword search), forecasts where the drone will be recovered, and keeps a
bitemporal, tamper-evident case memory ("Kairos-lite"). **All data is synthetic.**

- Full specification: `docs/SPEC.md` (sections are numbered; cite them as §N).
- Progress tracker: `docs/PROGRESS.md`. Decision log: `docs/DECISIONS.md`.
- Build phases: `docs/SPEC.md` §20. Run one with the `/phase N` skill.

## How we work

1. Build **one phase at a time** (SPEC §20). Never start a phase until the previous phase's exit check passed.
2. Begin every phase with a plan: read the phase block, the SPEC sections it lists, PROGRESS.md and
   DECISIONS.md (DECISIONS.md wins where it and the SPEC differ);
   propose files, tests and risks; **wait for approval** before writing code.
3. Write tests with (or before) the code. A phase is done only when `make check` passes **and** its
   exit check is demonstrated with real output pasted into PROGRESS.md.
4. When a phase is done: update PROGRESS.md, add any decisions to DECISIONS.md, commit once:
   `phase N: <summary>`. Do not start the next phase in the same session.
5. If the spec is ambiguous, pick the simplest option that satisfies the exit check, log it in
   DECISIONS.md, and continue. Ask me only when a choice would change the demo story (SPEC §1.2).

## Commands

| Command | Purpose |
|---|---|
| `uv sync` | Install dependencies |
| `make check` | Python: ruff and fast pytest. Web: lint, typecheck, Vitest |
| `make data` | Generate synthetic data from `config/` (seeded) |
| `make index` | Build features, signatures and LanceDB indexes |
| `make models` | Train the fusion model and calibrate DTW (phase 4+) |
| `make eval` | Run the evaluation harness → `reports/eval_<date>.md` |
| `make dev` | API on :8000 and Vite dev server on :5173 together, with hot reload |
| `make demo` | Build the web app and serve everything from FastAPI on :8000 (offline) |
| `make e2e` | Playwright end-to-end tests, UI screenshots and accessibility checks |
| `make mcp` | Run the MCP server over stdio |
| `uv run kairos-defense --help` | CLI help |

## Non-negotiable rules

1. **Synthetic only.** No real people, names, plates, addresses, real installations or real coordinates.
2. **Truth isolation.** Ground truth lives only in `data/truth.duckdb`. Only `src/kairos_defense/eval/` may
   read it (the generator's writer may write it). The matcher, recall, memory, UI and agent must never
   open it. A test enforces this. One exception (D-170): after a live incident closes, on an explicit
   user action, the API may serve `eval`'s reveal of who flew it; nothing revealed is stored or used.
3. **No look-ahead.** Any search for "past" flights or reports must filter to records that started before
   the query flight started. Tests enforce this.
4. **Determinism.** Every random draw uses a seeded `numpy.random.Generator` passed in explicitly,
   derived per component from the global seed. Same seed ⇒ identical data hashes.
5. **Offline by default.** The app runs with no network. LLMs and downloadable embedding models are
   optional behind `config/app.yaml`; the hashing embedder is the offline default. No CDNs: fonts come
   from `@fontsource` and 3D shapes are procedural.
6. **Ports and adapters.** Business logic depends on the Protocols in `src/kairos_defense/ports.py`, never on
   DuckDB or LanceDB directly. (We will later swap in KDB-X and Kairos; see SPEC §22.)
7. **Append-only memory.** Never UPDATE or DELETE ledger rows. Corrections are new events that supersede.
8. **Humans approve.** Agents and the matcher may *propose* links, closures and exports; only an explicit
   user action (UI button or CLI flag) commits them.
9. **Link flights, never people.** No feature may infer, store or display a person's identity.
10. **Truthful animation.** Every moving or changing element in the UI is driven by a real stream event
    or computed result (SPEC §16–§17). Never fake numbers or decorative data.

## Code conventions

- Python 3.11+, `from __future__ import annotations`, type hints on all public functions.
- Units: meters, seconds, degrees. Bearings are degrees clockwise from north in [0, 360).
- Geometry is local ENU meters (`x_m` east, `y_m` north) in each region's frame. No lat/lon in v1.
- Time: UTC `TIMESTAMP` in DuckDB; int64 epoch **milliseconds** in LanceDB (`*_ts_ms` columns).
- Algorithms are pure functions over numpy/pandas; I/O lives in adapters under `kairos_defense.store`.
- Keep modules under ~400 lines. Docstrings state units and shapes, e.g. `(n, 5) float64`.
- Use `logging` (no `print` in library code). Configuration via pydantic models in `kairos_defense.config`.
- Tests: `tests/unit` (fast, default) and `tests/slow` (marked `@pytest.mark.slow`, run by `make test-all`).
- Front end (`web/`): TypeScript strict; tokens from `web/src/theme/tokens.css` only; high-frequency data in
  Zustand, read inside `useFrame` or requestAnimationFrame, never as per-message React state; honor reduced motion.
- UI work is not done until you have reviewed Playwright screenshots against SPEC §17 and fixed what you saw.

## Library notes (verified: duckdb 2.0.0, lancedb 0.40.0, dtaidistance 2.5.1)

```sql
-- DuckDB as-of join (latest weather at or before each point)
SELECT p.*, w.wind_ms FROM track_points p
ASOF LEFT JOIN weather w ON p.region_id = w.region_id AND p.ts >= w.ts;
-- DuckDB window join (RF detections within ±30 s)
SELECT p.track_id, p.ts, r.protocol_family FROM track_points p JOIN rf_detections r
  ON r.installation_id = p.installation_id
 AND r.ts BETWEEN p.ts - INTERVAL 30 SECOND AND p.ts + INTERVAL 30 SECOND;
```

```python
import lancedb
from lancedb.rerankers import RRFReranker
tbl.search(vec).where("installation_id = 'DELTA' AND start_ts_ms < 1745100000000", prefilter=True).limit(k)  # -> _distance
tbl.create_fts_index("text")                                   # native FTS
tbl.search("white pickup", query_type="fts").limit(k)          # -> _score
(tbl.search(query_type="hybrid").vector(vec).text(q)
    .where(flt, prefilter=True).rerank(RRFReranker()).limit(k))  # -> _relevance_score

from dtaidistance import dtw, dtw_ndim
from dtaidistance.subsequence.dtw import subsequence_alignment
dtw.distance_fast(a, b, window=w)          # 1-D float64 arrays
dtw_ndim.distance(A, B, window=w)          # (n, d) and (m, d) arrays
m = subsequence_alignment(query, series).best_match(); m.value; m.segment
dtw.lb_keogh(a, b, window=w)               # equal lengths
```

If an installed version behaves differently, wrap it in a thin adapter, add a test, and log it in DECISIONS.md.

```text
Web stack (current majors, Oct 2026): React 19.3, Vite 8, Tailwind CSS 4 (@tailwindcss/vite, CSS-first @theme),
three 0.186, @react-three/fiber 9 (peer: react >=19 <19.4, so pin React 19.3.x), drei 10, postprocessing 3,
Motion 14 (import { motion } from "motion/react"), D3 7, Zustand 5, Vitest 5, Playwright 1.64.
DTW lens data: d, paths = dtw.warping_paths(a, b, window=w); path = dtw.best_path(paths).
```

## Autopilot and documentation

- Unattended runs use the `phase-auto` skill, driven by `scripts/autopilot.py` (see `docs/AUTOPILOT.md`).
  In those runs never wait for approval: record assumptions in the plan and in `docs/DECISIONS.md`.
- Every phase leaves `docs/phases/phase-NN/PLAN.md`, `REPORT.md` and `EXIT_CHECK.md`
  (templates in `docs/phases/TEMPLATES.md`).
- Every package under `src/kairos_defense/`, and `web/`, has a current `README.md` (template in
  `docs/phases/TEMPLATES.md`). The root README keeps a "Status" section.
- Never push, never rewrite history, never edit `.claude/`, `scripts/autopilot.py`,
  `scripts/check_targets.py` or `docs/phases/gates.json`, and never weaken or skip a test or lower a target to pass a gate.
- End-to-end tests start and stop their own servers (Playwright `webServer`), so gates never hang.
  Serving commands in exit checks (`make demo`, `make mcp`) run in the background with a time limit
  and are stopped afterwards.
- From phase 4 the gate runs `scripts/check_targets.py N`, which enforces the SPEC §19 targets from
  `reports/eval_<date>.json`; `make eval` must write the metric keys it names.
- If truly blocked, write `docs/phases/phase-NN/BLOCKED.md` (what failed, what you tried, the decision a
  human must make) and stop.
