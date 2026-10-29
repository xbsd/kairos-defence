# Phase 5: Report recall and analog forecast, report

Status: done · Date: 2026-10-28 · Commits: the single `phase 5: report recall and analog forecast`
commit

## Summary

Phase 5 finds the paperwork behind each match and predicts where tonight's drone will land:

- an offline hashing embedder (default), a FastEmbed adapter that never downloads, and
  `kairos-defense fetch-models`;
- the LanceDB `reports` table with full-text search and the DuckDB `report_clues` table, built by
  `make index`;
- hybrid search per match with the §12.3 filter plus no look-ahead, LanceDB's native RRF and a
  row-for-row identical §12.5 fallback;
- clue extraction with spans and linking across matches and to the forecast zone;
- the §13 analog forecast, the real `recall`, `forecast` and `fetch-models` commands, and the
  phase 5 metrics and demo rows in `make eval`.

Against the targets: report linkage **1.000** (≥ 0.70), forecast median at T = 90 s **340 m**
(≤ 400 m). Both demo rows pass: the DELTA report is rank 1 for the DELTA match at T+120, and the
live forecast at T+105 is **139 m** from the true recovery, with County Rd 12 crossing the zone.
`check_targets.py 5`: 12 PASS, 1 WARN (phase 4's accepted `live_top3_incidents`), exit 0. Every
phase 4 metric is unchanged.

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Embedders | `HashingEmbedder` (tokens + 3-grams, `stable_int` index and sign, L2), `FastEmbedEmbedder` (cache only), `make_embedder`, `fetch_model` (D-083, D-084) | `recall/embed.py` |
| Reports index | history reports → `report_clues` (DuckDB) and LanceDB `reports` with FTS; `check_reports_index` (D-084, D-089) | `recall/index.py`, `store/ddl.py`, `store/lance.py` |
| Report search port | `LanceReportIndex` (`hybrid` with `ReportRRF`, `fts`), FTS index built in `replace` (D-085) | `store/lance.py` |
| Recall | keyword text, §12.3 filter + no look-ahead, `rrf_fuse`, `hybrid_search` with fallback, `ReportRecall.for_matches` → `RecallResult.to_dict()` (D-082, D-085) | `recall/search.py` |
| Clues | `extract_clues` (vehicles, gazetteer roads, spans), `link_clues` (D-086) | `recall/clues.py` |
| Forecast | §13 steps 1–7, `Forecast.to_dict()`, pure helpers (D-087, D-090) | `forecast/analog.py` |
| Matcher hand-off | `MatchResult.signature`, `signatures`; `warp_path` scaling mode (D-087) | `match/matcher.py`, `match/dtw_rerank.py` |
| Evaluation | `downstream.py` (forecast error, linkage), `clue_truth` and recovery columns, new metrics and keys, Markdown section, two demo assertions, `forecast_choice.py` (D-088, D-090) | `eval/*` |
| CLI | `forecast`, `recall`, `fetch-models` (`cli_recall.py`); `index` builds reports; `eval` needs the reports index; tables (D-091) | `cli.py`, `cli_recall.py`, `cli_tables.py` |
| Config | `paths.cache`, `forecast.anchor: match_kind` | `config/app.yaml`, `config/scoring.yaml`, `config/app.py`, `config/scoring.py` |
| Artifacts | refreshed baseline with the phase 5 keys; the anchor comparison | `reports/baseline.json`, `reports/forecast_choice.json`, `reports/eval_2026-10-29.*` |

## Decisions and deviations from SPEC

- [D-082](../../DECISIONS.md): the recall filter adds `event_ts_ms < tonight's first contact` and
  `report_ts_ms <= replay time` to §12.3 (rule 3 for paperwork).
- [D-083](../../DECISIONS.md): hashing embedder details.
- [D-084](../../DECISIONS.md): FastEmbed refuses to start unless the model is cached (a check in our
  adapter, plus `local_files_only=True`); `fetch-models`; `paths.cache`; the reports-index guard.
- [D-085](../../DECISIONS.md), **deviation** from CLAUDE.md's `create_fts_index` note (deprecated in
  LanceDB 0.40: `create_index(..., FTS(with_position=True))`), and an RRF tie-break by `report_id`
  so native and fallback agree row for row.
- [D-086](../../DECISIONS.md), **deviation** from §12.4's `<color> <type>`: the color is optional,
  because the paperwork writes "a motorcycle" and `clue_truth` has that clue.
- [D-087](../../DECISIONS.md), **deviation** from the plan's j* alignment (see below), plus the
  "ended by the replay time" rule for known recoveries.
- [D-088](../../DECISIONS.md): evaluation definitions and the two demo assertions.
- [D-089](../../DECISIONS.md): index build wiring.
- [D-090](../../DECISIONS.md), **deviation** from §13 step 4 while tonight's target reads the fence:
  `forecast.anchor: match_kind`, adopted by the rule registered before the build measured it.
- [D-091](../../DECISIONS.md): CLI shapes.

### Plan changes during the build (honest list)

- **Vehicles (A5):** the plan said colored vehicles only, and its test said a bare "pickup" is not
  extracted. The planned agreement test with `clue_truth` failed on four reports that mention "a
  motorcycle" (a true clue). The color became optional, matching the generator's lexicon; the test
  became `test_only_lexicon_vehicles_and_gazetteer_roads` (a car, a bicycle, "purple van" reads
  "van", minor roads and "County Rd 120" are not extracted). Agreement holds exactly on the full
  data: 82 of 82 vehicle and gazetteer-road clues (`test_full_report_clues_equal_clue_truth`).
- **j* (A6):** the plan used the warp ratio's §9.3 per-series z alignment. Its own known-answer
  test (an exact copy, tonight = rows 100–159) gave row 164, five off: a 60 s window and a 180 s
  segment z-normalize differently. j* now uses the shape distance's configured scaling (`fixed`,
  D-079), which gives 159, also with radar-like noise. Only the exit path depends on j*; every
  forecast center and error is unchanged.
- **RRF ties (A4):** the planned `test_fallback_equals_native_hybrid` failed at the k cut on tied
  scores: LanceDB orders ties by merge order before cutting. A thin `RRFReranker` subclass
  (`ReportRRF`) now orders ties by `report_id`, and the fallback rounds scores to float32 like
  LanceDB, so the two paths agree exactly (5 queries over 40 rows, order and scores).
- **Look-ahead in analogs (review suggestion, adopted):** a history flight still in the air at the
  replay time does not count as a known recovery (`end_ts <= until`).
- **Reports-index guard (review suggestion, adopted):** the row count goes through the
  `VectorStore` port (a search with k = n + 1), not an adapter-only `count`.
- **CLI layout:** the three commands live in `cli_recall.py` (registered by `cli.py`, which is
  372 lines); `eval` refuses a missing or stale reports index, so report linkage is always measured.
- Other review suggestions applied: D-085 records the FTS call change; D-090 says the verdict was
  known when the rule was written and reports both modes' month 13–18 numbers (below); this report
  says the DELTA rank-1 beat is structural; EXIT_CHECK.md confirms the latency keys moved by less
  than 2%; the baseline comparison skips keys an older baseline lacks; FastEmbed keeps its
  no-download guarantee without relying on `local_files_only`.

## Tests

- Fast: **497 passed** (443 at the start of the run), 12 slow deselected (10 before).
  `make test-all`: **509 passed** in 3 min 12 s.
- New files:
  - `test_embed.py`, 9: determinism, unit float32 rows, pinned known answer, case and punctuation,
    empty text, similar reports closer, FastEmbed never downloads (fake module), missing package,
    `fetch_model`.
  - `test_clues.py`, 6: spans, blotter capitals, lexicon and gazetteer only, agreement with the
    generator's `clue_truth`, cross-match links (and no self-link), the road-zone link.
  - `test_recall_index.py`, 6: schema and history-only rows, exact phrase, filters on base and
    time (hybrid, FTS, vector), `report_clues`, stale guard (embedder, row count, no table),
    deterministic rebuild.
  - `test_recall_search.py`, 9: filter known answer, signature words, tonight's filed report,
    `TARGET_WORDS`, sanitizing, RRF known answer, native equals fallback, the fallback path, the
    DELTA report at rank 1 for the DELTA match.
  - `test_forecast.py`, 10: `combine`, weighted center, rotation beyond 30°, j* on a shifted copy,
    the exit path, roads crossing, anchor modes, top k counts only known recoveries (and ended
    flights), None without one, the live forecast (and the same through the ports).
  - `test_forecast_choice.py`, 2: the rule's known answers and a run on the P1 nights.
- Changed files: `test_config.py` +2 variants; `test_no_lookahead.py` +2 (every recalled report
  predates tonight and was filed by T; tampering after T changes neither the forecast nor the
  recall); `test_eval_metrics.py` +2; `test_eval_harness.py` +3 (`test_phase5_summary_keys`,
  `test_demo_recall_and_forecast_rows`, `test_downstream_labels_use_filed_true_clue_reports`);
  `test_cli.py` +6 (forecast and recall on the P1 nights, missing reports index for `recall` and
  `eval`, unknown incident or track or method, missing models, `fetch-models` without the extra).
- Slow (`tests/slow/test_full_models.py`), +2: `test_full_demo_recall_and_forecast` (T+105 error
  ≤ 400 m, County Rd 12 in the zone, DELTA report rank 1 with its County Rd 12 span linked) and
  `test_full_report_clues_equal_clue_truth`; `test_full_eval_dtw` asserts the phase 5 keys and rows.
- Test-count arithmetic: three parametrized cases of `test_stub_names_its_phase` left with their
  stubs (−3); 57 tests were added (50 in new files, 7 in changed ones, of which 2 are config
  variants): 443 − 3 + 57 = 497.
- Adapted, not weakened: `test_cli_eval`'s last check became "exit 0 if and only if no demo row
  failed" (three rows assert now, not one); the `run` and `dtw_run` fixtures pass the report
  index; `p1_index` and the slow `full` fixture also build the reports index (setup, as A8 says).
- No test was skipped, marked xfail or deleted.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| Reports indexed with FTS (`make index`) | pass | 956 reports, `report_clues` 82 rows, `hashing-v1-384`, FTS on `text` |
| Report linkage ≥ 0.70 | pass | 1.000 (65 of 65) |
| Forecast median ≤ 400 m | pass | 340 m at T = 90 s (P80 495 m) |
| Demo: DELTA report rank 1 for the DELTA match | pass | `R-P1-DELTA-260419-1 rank 1 of 1`, County Rd 12 linked to the zone |
| Demo: forecast error ≤ 400 m at T+105 | pass | 139 m, radius 370 m |
| `forecast --incident DEMO-BRAVO-0828 --at 105` | pass | exit 0; 2,164 m at 320° (northwest) of the fuel farm; roads County Rd 12 |
| `check_targets.py 5` | pass | 12 PASS, 1 WARN (accepted), exit 0 |
| `make check`, `make test-all` | pass | 497 fast; 509 in all |

`make eval` exits non-zero only for the accepted phase 4 row, so the SPEC `&&` chain was run as
separate commands (as the gate does). Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Probers, 23 answerable queries (months 13 to 18).

| Metric | Phase 4 | Phase 5 | Target |
|---|---:|---:|---|
| Report linkage (T = 120 s, top 3 matched incidents, k = 5) | – | **1.000** (65 / 65) | ≥ 0.70 |
| Forecast error at T = 90 s, median / P80 | – | **340 / 495 m** | median ≤ 400 m |
| Forecast error at T = 120 s, median / P80 | – | 346 / 532 m | report |
| Queries without a forecast | – | 0 | report |
| Live forecast error at T+105 | – | 139 m (radius 370 m) | ≤ 400 m |
| Recall@5 / DTW lift / copycat-first / MRR / time to match | 1.000 / +0.522 / 0% / 1.000 / 96% | unchanged | |
| p95 prefilter / DTW / end to end | 30 / 56 / 124 ms | 30 / 55 / 123 ms | §10.9 |
| p50 / p95 forecast; recall per matched incident | – | 8 / 9 ms; 5 / 6 ms | report |

Forecast errors at T = 90 s, sorted (m): 86, 95, 115, 122, 132, 156, 227, 273, 273, 314, 327,
340, 342, 353, 367, 396, 462, 474, 509, 561, 620, 633, 644. Sixteen of 23 are within 400 m. The
median's margin to the target is 60 m: one more query above 400 m would move it to 342 m, two to
353 m.

**Both anchor modes, for the record (not used to choose; D-090 chose on the training split):**

| Nights | T | `target` (§13 as written) median / P80 | `match_kind` (shipped) median / P80 |
|---|---:|---:|---:|
| Training, 2025-03-01 to 2026-02-28 (36 queries) | 90 s | 502 / 1,000 m | 311 / 492 m |
| Evaluation, 2026-03-01 to 08-31 (23 queries) | 90 s | 384 / 910 m | 340 / 495 m |
| Evaluation | 120 s | 410 / 845 m | 346 / 532 m |

As written, §13 would also pass the target on the evaluation nights (384 m), by 16 m.

**Report linkage is close to trivial on this data, and the DELTA beat is structural.** Within a
match's filter window (its base, ±3 h, 5 km) no history incident has more than 4 reports, and
k = 5, so every relevant report reaches the top 5 once the filter admits it (planning fact 2). A
linkage of 1.000 therefore says the filter and the no-look-ahead bounds keep the right reports;
it says little about the ranking. Likewise `R-P1-DELTA-260419-1` is the only report in DELTA's
window (D-011), so it is rank 1 whenever DELTA is among the top 3 matched incidents; at T+120
DELTA is match #1. The ranking itself is tested where it matters: native hybrid equals the §12.5
fusion, and an exact phrase finds only its rows.

**The demo forecast uses two P3 flights.** Only ALPHA-260303 and ALPHA-260502 of the five earlier
P1 flights have a known recovery point (their last radar point is below 30 m, D-003). At T+105
the analogs are ALPHA-260303 (P1), HOTEL-250818 (P3) and FOXTROT-251215 (P3), the last two rotated
by −133° and −134° onto tonight's approach. The error is 139 m; at T+120, with ALPHA-260502 in the
set, it is 8 m.

**Disclosure (plan facts 4 and 5):** the as-written forecast was computed during planning on the
evaluation queries and the demo, and both anchor modes on the training split. The build reran the
pre-registered rule with the shipped code and got the same numbers; nothing was tuned on months 13
to 18 or the demo.

## Known issues and follow-ups

- Report linkage cannot distinguish a good ranker from a filter (above). A harder test would
  widen the window or drop the base from the filter (phase 9's agent may search across bases).
- The forecast median's margin is 60 m. A ranking change that swaps one analog can move the demo
  forecast; `test_full_demo_recall_and_forecast` and the eval demo row catch it.
- `FastEmbedEmbedder` is tested against a fake module only (`fastembed` is an optional extra and
  not installed). Its no-download guarantee does not depend on the package (D-084).
- The accepted phase 4 gap (`live_top3_incidents`, ALPHA-260502 #5 at T+90) is unchanged; the
  phase 5 rows do not depend on it.
- The exit path follows the top analog's remainder from j*, so it starts at ALPHA-260303's mapped
  position at j*, not at tonight's last point: at T+105 the start is 187 m from the fuel farm's
  centroid (on the orbit) and 210 m from the live drone. Phase 8's dashed path may want to start at
  tonight's last point.
- Phase 7 sends `Forecast.to_dict()` and `RecallResult.to_dict()` as the §16.3 `forecast` and
  `recall` messages; phase 9 wraps the same functions as `forecast_recovery` and `recall_reports`.

## How to debug this phase

- **Rebuild:** `make index` (7 s, reports 0.1 s), `make eval` (36 s). A changed embedder or
  `embeddings.provider` needs `make index`; `recall` and `eval` say so ("reports index is stale").
- **One live forecast:** `uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105`
  (analogs, rotations, anchors, j*). `--method euclidean` uses the baseline's order.
- **One recall:** `uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120 --matches 5`;
  `--query "white pickup"` overrides tonight's keyword text, `--k` the number of reports.
- **In Python:** build `DtwMatcher`, `res = m.match(load_query(store, tid, T, cfg.scoring))`, then
  `forecast(store, q, res, cfg.scoring)` and `ReportRecall(store, LanceReportIndex(uri), lance,
  make_embedder(cfg.app), cfg.scoring).for_matches(q, res, fc.roads)`. Each `MatchRecall.where` is
  the exact LanceDB filter used.
- **Eval numbers move:** compare `outcomes` in two `reports/eval_*.json`: each prober row at
  T = 90 and 120 s has `forecast_error_m`; at 120 s `linkage_hits` and `linkage_total`.
- **Likely failures:** `ReportIndexStale` (run `make index`); `EmbedderUnavailable` (set
  `embeddings.provider: hashing`, or `uv sync --extra fastembed` and `fetch-models`); a LanceDB
  filter error on a float literal for an int64 column; `NotImplementedError` from `hybrid` is
  handled by the fallback, not an error.

## Fix attempts
