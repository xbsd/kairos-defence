# kairos_defense.eval

The evaluation harness (SPEC §19) and the fusion training (§10.6). This is the only package
allowed to read ground truth (CLAUDE.md rule 2).

## Responsibilities

- Read `data/truth.duckdb` (`truth.py`). No other app code may open it; the §7.6 scan enforces this.
- Build the query sets and run the §19.2 protocol: each query is treated as live at T seconds and
  matched only against history that started before it (`harness.py`).
- Build the fusion training pairs from history, label them with truth, calibrate τ, fit the
  logistic model, validate it, and write `models/fusion_v1.json` and `models/dtw_calibration.json`
  (`training.py`, D-073, D-078).
- Compute the §19.3 metrics as pure functions (`metrics.py`).
- Label the forecast error and the report linkage after each ranked query (`downstream.py`,
  phase 5, D-088), and run the pre-registered forecast-anchor comparison (`forecast_choice.py`,
  D-090).
- Check the demo assertions from `scenario_demo.yaml`, as far as the current phase can (`demo.py`).
- Write `reports/eval_<date>.md` (`report_md.py`), `.json` and the recall figure, and gate
  regressions against `reports/baseline.json` (`report.py`, §19.4).

## Public API

- `truth.track_truth(app) -> DataFrame` (`track_id, incident_id, actor_id, actor_type,
  launch_ts, recovery_x_m, recovery_y_m`), `truth.true_path(app, track_id) -> DataFrame` (`t_s`,
  `x_m`, `y_m`, `alt_m`) and `truth.clue_truth(app) -> DataFrame` (`report_id, clue_type,
  clue_value, is_true`).
- `harness`:
  - `evaluate(cfg, store, vstore, truth, method, models_dir=None, reports=None) -> EvalRun`
    (`method`, `model_version`, `candidate_tracks`, `reports_indexed`, `sets`, `outcomes`, `demo`,
    `elapsed_s`); `reports` is a `ReportIndex` and enables report linkage;
  - `METHODS`: `{"euclidean": euclidean, "dtw": dtw}`, factories returning `(ranker, model
    version)`; a ranker maps a `Query` to a `MatchResult` (fused order, prefilter order, timings);
  - `T_GRID = (30, 45, 60, 90, 120, 180)` s; `FIRST_NIGHT`, `LAST_NIGHT` (months 13–18);
  - `track_list(store)`, `labelled_tracks(tracks, truth)`, `query_cases(t, kinds, first, last)`,
    `query_sets(tracks, truth) -> QuerySets`,
    `run_case(case, at_s, store, cfg, ranker, truth, downstream=None)`,
    `night_of(ts_utc, utc_offset_hours)`.
- `training`:
  - `TrainSplit` (frozen): `train_first` 2025-03-01, `train_last` 2026-02-28, `valid_first`
    2026-03-01, `valid_last` 2026-08-31, `t_grid` (45, 60, 90, 120, 180);
  - `QUERY_KINDS = ("prober", "copycat")` (swarm drones are candidates only, D-078);
  - `training_queries(store, truth, first, last)`, `build_pairs(builder, queries, truth, t_grid) ->
    Pairs` (`keys`, `context (n, 6)`, `d_norm (n,)`, `y (n,) int8`; `X(tau, order)`, `hash()`),
    `calibrate_tau(pairs)`, `fit(pairs, tau, order)`, `validate(model, pairs)`,
    `recall_at(scores, pairs, k=5, at_s=120)`;
  - `train_models(cfg, store, vstore, truth, split=None, models_dir=None) -> TrainSummary`.
- `metrics.Outcome`: one query at one T: `ran`, `true_rank`, `copycat_rank`, `baseline_rank`,
  `baseline_copycat_rank` (same candidates in prefilter order), `window_s`, `query_ms`,
  `prefilter_ms`, `dtw_ms`, `total_ms`, `candidates`, `top`; phase 5: `forecast_error_m` (m,
  `inf` without a forecast), `forecast_ms`, `linkage_hits`, `linkage_total`, `recall_ms`.
- Metric functions: `recall_at_k`, `mrr`, `times_to_match`, `time_to_match_share`,
  `copycat_first_rate`, `dtw_lift(outcomes, k=5, at_s=120) -> (lift, fused, baseline)`,
  `percentiles`; phase 5: `report_linkage(outcomes, at_s=120) -> (value, retrieved, relevant)`,
  `forecast_summary(outcomes, at_s) -> (median, p80, n, missing)` and `inf_percentile(sorted, q)`
  (a linear percentile that keeps `inf` instead of NaN).
- `downstream`: `Downstream(cfg, store, vstore, truth, reports=None, embedder=None)` with
  `forecast(q, result) -> (Forecast | None, error_m, ms)`, `linkage(q, result, zone_roads) ->
  (retrieved, relevant, ms per match, RecallResult)`, `relevant(incident_ids, until)`,
  `outcome_fields(q, result)`; `forecast_error(fc, true_xy)`, `linkage_counts(recall, relevant)`.
- `forecast_choice`: `compare_anchors(cfg, store, vstore, truth, first, last, models_dir=None,
  at_s=90) -> dict`, `verdict(stats)`, `main(argv=None, split=None)` (`uv run python -m
  kairos_defense.eval.forecast_choice`, writes `reports/forecast_choice.json`).
- `demo.demo_rows(cfg, store, truth, ranker, assert_top3=True, downstream=None)`,
  `demo.top3_row(cfg, matches, assert_top3)`, `demo.rank1_report_row(cfg, recall, asserting)`,
  `demo.forecast_row(cfg, fc, error_m, asserting)`. Statuses: `pass`, `fail`, `info (...)`,
  `pending (...)`.
- `report`: `summarize(run)`, `write_reports(run, dir)`, `regressions(metrics, baseline)`,
  `gate(summary, baseline_path)`, `GATED`, `PENDING`, `BUDGET_MS`. `report_md.markdown(s, fig)`.
- `targets` (D-139): `Target` (key, op, value, label, spec, phase, fmt, report_only, pending;
  `met(v)`, `text()`), `TARGETS` (§19.3 and §10.9, the same numbers as
  `scripts/check_targets.py`), `BY_KEY`, `target_text(key)`, `targets_json()` (written into the
  eval JSON as `targets`; the Eval page reads them).

## Data in and out

- In: `data/kairos_defense.duckdb` (`TrackStore`), `data/lancedb/flight_windows` (`VectorStore`),
  `data/lancedb/reports` (`ReportIndex`, phase 5), `data/truth.duckdb` (read-only, here only),
  `models/*.json` for `--method dtw`.
- Out: `reports/eval_<date>.md` and `.json` (`method`, `model_version`, `candidate_tracks`,
  `metrics`, `counts`, `recall_by_t`, `per_actor`, `demo`, `pending`, every outcome);
  `reports/figures/eval_recall_by_t.png`; `reports/baseline.json` (`eval --baseline`);
  `models/fusion_v1.json` and `models/dtw_calibration.json` (`kairos-defense models`);
  `reports/forecast_choice.json` (`forecast_choice`).
- `scripts/check_targets.py N` reads `metrics` from the newest `eval_<date>.json`. Phase 4 keys:
  `recall_at_5_t120`, `dtw_lift`, `copycat_first_t120`, `latency_prefilter_p95_ms`,
  `latency_dtw_p95_ms`, `latency_end_to_end_p95_ms`, plus `recall_at_5_t120_baseline`. Phase 5
  keys: `report_linkage` (with `report_linkage_retrieved` and `_relevant`),
  `forecast_median_t90_m` (with `forecast_p80_t90_m`, `forecast_queries_t90`,
  `forecast_missing_t90` and the same at T = 120 s), and the report-only
  `latency_forecast_p50/p95_ms`, `latency_recall_p50/p95_ms`; demo rows `live_rank1_report_for`
  and `forecast_error_max_m`.

## How it works

- Query sets: prober and copycat tracks of history incidents on the nights 2026-03-01 to
  2026-08-31, local time (D-055). Swarm incidents are listed for phase 9. Each answerable query
  runs at every T in `T_GRID`; below `min_track_s` it counts as a miss.
- **DTW lift is measured on one run** (D-076): the matcher returns both the fused order and the
  prefilter order of the same 500 candidates (the §10.2 baseline), so `dtw_lift` = Recall@5 fused
  − Recall@5 Euclidean on the same index and queries.
- **Training** (§10.6): prober and copycat queries on months 1–12, at T ∈ {45, 60, 90, 120, 180},
  through the matcher's own `CandidateBuilder`; label = same actor. τ = median same-actor `d_norm`;
  `LogisticRegression(class_weight="balanced", lbfgs, C=1)` on rows sorted by (query, T,
  candidate); the training hash covers keys, features and labels. Validation repeats the build on
  months 13–18 and is reported only (D-070).
- `live_top3_incidents` is an assertion for `dtw` (all three expected incidents in the top 3, each
  with a score and a reason) and stays `info` for `euclidean`, which has no reasons. The same
  holds for the phase 5 rows: `live_rank1_report_for` (live query at T+120: the expected incident
  is among the top 3 matched incidents and its recall rank 1 is its own report) and
  `forecast_error_max_m` (live forecast at T+105 within 400 m of the true recovery).
- **Forecast and recall labels** (phase 5, D-088): after each prober query is ranked and timed,
  `Downstream` forecasts at T = 90 and 120 s (error = center to `track_truth.recovery_*`; no
  forecast counts as infinite) and, at T = 120 s, recalls the top 3 matched incidents' reports;
  linkage = Σ retrieved true-clue reports filed by T / Σ such reports. Copycats are not labelled.
- Regression gate: accuracy fails when more than 5% worse than `baseline.json`; latency only above
  1.5 × baseline + 2 ms (D-060); any failed demo assertion fails. `dtw_lift` and
  `latency_dtw_p95_ms` are gated from phase 4; `report_linkage` and `forecast_median_t90_m` from
  phase 5 (a key missing from an older baseline is skipped).

## Configuration

- `app.paths.truth`, `reports`, `duckdb`, `lancedb`, `models`.
- `scoring.live.min_track_s`, `scoring.prefilter`, `scoring.windows`, `scoring.dtw`,
  `scoring.fusion.features` (through the matcher and training).
- `scenario.expectations` and `scenario.live_incident` (demo rows).
- Through `forecast` and `recall`: `scoring.forecast` (`top_k`, `min_radius_m`, `radius_factor`,
  `anchor`), `scoring.recall` (`hours_window`, `radius_m`, `k`) and `app.embeddings`.

## Tests

- `tests/unit/test_eval_metrics.py`: known-answer metrics, including `dtw_lift`,
  `report_linkage` and `forecast_summary` (infinite errors).
- `tests/unit/test_eval_harness.py`: query sets, protocol, outputs, the gate, the DTW summary keys,
  the demo assertions and the CLI sequence; phase 5: `test_phase5_summary_keys`,
  `test_demo_recall_and_forecast_rows`, `test_downstream_labels_use_filed_true_clue_reports`.
- `tests/unit/test_forecast_choice.py`: the D-090 rule and a run on the P1 nights.
- `tests/unit/test_training.py`: pairs respect time and the split, τ known answer, determinism,
  artifacts (P1 nights with a `TrainSplit`).
- `tests/slow/test_full_index.py` and `tests/slow/test_full_models.py`: full data.
- Run: `uv run pytest tests/unit -q -k "eval or training"`. End to end: `make data index models
  eval`.

## Gotchas

- Never import `eval` from app code to get truth. The dependency points one way: eval imports the
  matcher, never the reverse. The `models` CLI gets truth through `truth.track_truth`.
- One prober query moves Recall@5 by about 4%, close to the 5% gate (D-056).
- `eval_<date>` is the run's **UTC** date, so an evening run in America/New_York writes the next
  day's file, and a rerun on the same UTC day overwrites it. Phase 4's DTW run replaced the phase
  3 backfill's `eval_2026-10-29.*` (still in git at `dc38d34`).
- The figure is drawn in DejaVu Sans, bundled with matplotlib, so its bytes no longer depend on
  the machine (D-077).
- `kairos-defense models` takes about 45 s on the laptop (123,404 pairs); only `created_at`
  changes between two runs.
- Copycat-first counts queries whose own actor is not among the candidates at all (D-055).
- Report linkage is close to trivial on this data: no incident has more than 4 reports in a
  match's filter window, and k = 5, so every relevant report reaches the top 5 once the filter
  admits it (D-088). It measures the filter and the no-look-ahead bounds more than the ranking.
- `forecast_choice` reads truth and the training nights only; never rerun it to pick a mode on
  months 13 to 18 (D-070, D-090).

## Changelog

- Phase 0: empty package marking the only allowed truth reader.
- Phase 3: `truth.py`, `harness.py`, `metrics.py`, `demo.py`, `report.py`, and the `eval [--baseline]`
  CLI (D-055, D-056).
- Autopilot (`911aba1`): the latency regression tolerance became 1.5 × baseline + 2 ms (D-060).
- Phase 3 backfill: no code change; the two gotchas on report dates and figure fonts (D-067).
- Phase 4: `training.py`, `report_md.py`; `dtw` method (default), in-run DTW lift, new `Outcome`
  fields and metric keys, the top-3 demo assertion, pinned figure font (D-073, D-076 to D-078).
- Phase 5: `downstream.py`, `forecast_choice.py`; `clue_truth` and the recovery columns; report
  linkage and forecast error keys, the "Forecast and recall" section, two demo assertions
  (D-088, D-090).
- Phase 8: `targets.py`; the eval JSON gains `targets`; the Markdown's target column and latency
  budgets come from it (unchanged text). `tests/unit/test_eval_targets.py` keeps it equal to
  `scripts/check_targets.py` (D-139). No metric, query set or protocol changed.
