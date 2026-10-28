# kairos_defense.eval

The evaluation harness (SPEC §19), and the only package allowed to read ground truth (CLAUDE.md
rule 2).

## Responsibilities

- Read `data/truth.duckdb` (`truth.py`). No other app code may open it; the §7.6 scan enforces this.
- Build the query sets and run the §19.2 protocol: each query is treated as live at T seconds and
  matched only against history that started before it (`harness.py`).
- Compute the §19.3 metrics as pure functions (`metrics.py`).
- Check the demo assertions from `scenario_demo.yaml`, as far as the current phase can (`demo.py`).
- Write `reports/eval_<date>.md`, `.json` and the recall figure, and gate regressions against
  `reports/baseline.json` (`report.py`, §19.4).

## Public API

- `truth.track_truth(app) -> DataFrame`: one row per track with `track_id, incident_id, actor_id,
  actor_type, launch_ts`.
- `truth.true_path(app, track_id) -> DataFrame`: the noiseless 1 Hz path, with `t_s` (s after launch),
  `x_m`, `y_m` and `alt_m` (m, region frame).
- `harness.evaluate(cfg, store: TrackStore, vstore: VectorStore, truth, method) -> EvalRun`.
- `harness.METHODS`: `{"euclidean": euclidean_ranker}`. Phase 4 adds `dtw`.
- `harness.T_GRID = (30, 45, 60, 90, 120, 180)` s.
- `harness.query_sets(tracks, truth) -> QuerySets`, `harness.run_case(...) -> Outcome`.
- `harness.QueryCase` (`answerable` when an earlier same-actor track exists, D-009) and `EvalRun`.
- `metrics.Outcome`: one query at one T. Fields: `ran`, `true_rank`, `copycat_rank`, `window_s`, and
  the latencies `query_ms`, `prefilter_ms` and `total_ms`.
- Metric functions over outcomes:
  - `recall_at_k(outcomes, k, at_s)` and `mrr(outcomes, at_s)` return `(value | None, n)`.
  - `times_to_match(outcomes, top=3)` and `time_to_match_share(...)`.
  - `copycat_first_rate(outcomes, at_s)`.
  - `percentiles(...)`.
- `demo.demo_rows(cfg, store, vstore, truth, ranker) -> list[DemoRow]`. Each row has `key`,
  `expected`, `observed` and `status`, which is `pass`, `fail`, `info` or `pending (phase N)`.
- In `report.py`:
  - `summarize(run) -> dict`.
  - `write_reports(run, reports_dir) -> (md, json, summary)`.
  - `regressions(metrics, baseline)`.
  - `gate(summary, baseline_path) -> list[str]`: the problems that make `eval` exit non-zero.
  - `GATED`: the regression-checked metrics.
  - `PENDING`: the keys later phases fill in.

## Data in and out

- In:
  - `data/kairos_defense.duckdb` through the `TrackStore` port;
  - `data/lancedb/flight_windows` through the `VectorStore` port;
  - `data/truth.duckdb`, read directly with read-only `duckdb.connect`, which is allowed here only.
- Out:
  - `reports/eval_<date>.md` and `reports/eval_<date>.json`, with `metrics`, `counts`,
    `recall_by_t`, `per_actor`, `demo`, `pending` and every outcome;
  - `reports/figures/eval_recall_by_t.png`;
  - `reports/baseline.json`, with `eval --baseline`.
- `scripts/check_targets.py N` reads the newest `eval_<date>.json` under `metrics` (D-059).

## How it works

- Query sets are the prober and copycat tracks of history incidents on the nights from 2026-03-01 to
  2026-08-31, local time (D-055). Swarm incidents are listed for phase 9.
- Each answerable query runs at every T in `T_GRID`. Below `scoring.live.min_track_s` the matcher
  does not run, which counts as a miss.
- Truth labels the outcomes only after ranking. The best same-actor rank is `true_rank`; the best
  copycat rank is `copycat_rank`.
- Regression gate:
  - accuracy metrics fail when more than 5% worse, relative to the baseline;
  - latency fails only above 1.5 × baseline + 2 ms (D-060);
  - any failed demo assertion also fails.
- The §10.9 latency targets are enforced by `scripts/check_targets.py`, as WARN only (D-060), not here.

## Configuration

- `app.paths.truth`, `app.paths.reports`, `app.paths.duckdb` and `app.paths.lancedb`.
- `scoring.live.min_track_s` and `scoring.windows` / `prefilter` (via the matcher).
- `scenario.expectations` and `scenario.live_incident` (demo rows).

## Tests

- `tests/unit/test_eval_metrics.py`: known-answer metrics.
- `tests/unit/test_eval_harness.py`: query sets, protocol, outputs, the gate and the CLI.
- `tests/slow/test_full_index.py`: a full eval passes the gate.
- Run: `uv run pytest tests/unit -q -k eval`. End to end: `make data index eval`.

## Gotchas

- Never import `eval` from app code to get truth. The dependency points one way: eval imports the
  matcher, never the reverse.
- The prober set has 23 answerable queries and the copycat set 10. One prober query moves Recall@5
  by about 4%, close to the 5% gate (D-056).
- `baseline.json` does not exist until phase 4's exit check writes it, so until then only demo
  failures fail the gate.
- Copycat-first counts queries whose own actor is not among the candidates at all (D-055).

## Changelog

- Phase 0: empty package marking the only allowed truth reader.
- Phase 3: `truth.py`, `harness.py`, `metrics.py`, `demo.py`, `report.py`, and the `eval [--baseline]`
  CLI (D-055, D-056).
- Autopilot (`911aba1`): the latency regression tolerance became 1.5 × baseline + 2 ms (D-060).
