# Phase 5: Report recall and analog forecast, plan

Autopilot plan step, 2026-10-28. Written without a human in the loop (CLAUDE.md rule 5, `phase-auto`):
every assumption below is recorded in `docs/DECISIONS.md` during the build.

## Goal

Find the paperwork behind each match and predict the recovery zone (SPEC §12, §13):

- an offline hashing embedder, an optional FastEmbed adapter and `kairos-defense fetch-models`;
- a LanceDB `reports` table with full-text search, built by `make index`;
- hybrid (vector + keyword) search with base, time and distance filters, plus the §12.5 RRF fallback;
- clue extraction into `report_clues`, and clue linking across matches and to the forecast zone;
- the analog forecast (`forecast/analog.py`);
- the real `kairos-defense recall` and `kairos-defense forecast` commands;
- the two phase 5 metrics and the two demo assertions in `make eval`.

Phase 5 targets (SPEC §20, `scripts/check_targets.py 5`, cumulative with phase 4):

- `metrics.report_linkage` ≥ 0.70;
- `metrics.forecast_median_t90_m` ≤ 400 m;
- demo rows `live_rank1_report_for` and `forecast_error_max_m` must be `pass`;
- every phase 4 row still passes. `live_top3_incidents` is an accepted gap (WARN, `accepted_gaps.json`).

## Inputs read

- `CLAUDE.md`, `docs/PROGRESS.md` (phases 0 to 4 and the backfills), `docs/phases/TEMPLATES.md`,
  `docs/phases/phase-04/REPORT.md` and `GAPS.md`, `docs/phases/gates.json`, `scripts/check_targets.py`,
  `docs/phases/accepted_gaps.json`.
- SPEC §1.2 (beats T+105 and T+120), §4.1, §4.2, §5, §6.1, §6.5, §7.2 (`report_clues`), §7.5
  (`reports`), §8.8, §8.10, §10.4, §10.8, §12, §13, §16.3 (the `forecast` and `recall` messages
  phase 7 will send), §17.8, §18.1 (`recall_reports`, `forecast_recovery`), §19, §20 phase 5,
  Appendix A.
- `docs/DECISIONS.md`, in particular D-003 (recovery known only below 30 m), D-006, D-007 and D-031
  (County Rd 12), D-011 (DELTA has a lone report), D-038, D-040 (blotters are upper case: extraction
  must be case-insensitive), D-041 (no reports for live incidents), D-046 (partial targets read
  "fence"), D-047, D-049, D-050, D-052, D-053, D-055, D-060, D-063, D-069, D-070, D-075, D-076,
  D-079 and D-081. Next free number: **D-082**.
- Code: `ports.py`, `store/lance.py`, `store/duck.py`, `store/ddl.py`, `features/build.py`,
  `features/signatures.py`, `features/channels.py`, `match/` (matcher, candidates, dtw_rerank,
  query, live_signature, baseline, types), `eval/` (harness, demo, metrics, report, report_md,
  truth, training), `sim/lexicon.py`, `sim/facts.py`, `rng.py`, `geo.py`, `config/app.py`,
  `config/scoring.py`, `cli.py`, `pyproject.toml`, `Makefile`, `tests/conftest.py` and the tests
  that touch these modules.

### Facts checked during planning

These checks were read-only, with scratch scripts in `/tmp`. Nothing in the repo or `data/` was written.

1. **LanceDB 0.40 does everything §12 asks, natively.** On a scratch table:
   - `create_index("text", config=FTS(with_position=True))` builds the FTS index.
     `create_fts_index` still works but is deprecated.
   - `search('"County Rd 12"', query_type="fts")` matches only rows with that exact phrase, and the
     upper-case blotter "COUNTY RD 12" matches too, because the default tokenizer lowercases.
   - `search(query_type="hybrid").vector(v).text(q).where(flt, prefilter=True).rerank(RRFReranker())`
     applies the filter to both sides and returns `_relevance_score`.
   - The native RRF score is Σ 1/(60 + rank) with 1-based ranks. Two first places score 2/61 =
     0.032787, so §12.5's fallback formula gives identical numbers.
   - Hybrid search with a text that has no keyword hits returns the vector hits alone. A filter that
     matches nothing returns an empty frame.
2. **The filter, not the ranking, decides report linkage on this data.** I counted reports at the
   same installation within ±3 h of each history incident's tracks. 938 incidents have 0 such
   reports, 740 have 1, 132 have 2, 53 have 3 and 13 have 4. None has more than k = 5. Every
   matched incident's reports therefore reach the top 5 once the filter admits them. Linkage should
   be close to 1.0, and REPORT.md will say why rather than present it as a ranking result.
3. **Recovery points are known for only two of the five earlier P1 flights.** §9.4 knows a recovery
   point only when the last radar point is below 30 m (D-003, D-047).
   - Known: ALPHA-260303 (−1,442, 1,320) and ALPHA-260502 (−1,490, 1,431) m from the fuel farm.
   - Unknown: DELTA-260419 (last point at 65 m), CHARLIE-260710 (38 m) and BRAVO-251114 (89 m, the
     outage).
   - §13 step 1 ("top k among matches with a known recovery point") therefore fills the third slot
     with another actor's flight. §13 step 4 rotates that flight onto tonight's approach.
4. **A scratch §13 forecast (steps 1, 4 and 5, as written), on the real data and the shipped model:**

   | Query | Analogs used (top 3 with a known recovery) | Error | Radius | County Rd 12 |
   |---|---|---:|---:|---|
   | Live, T+90 | ALPHA-0303, FOXTROT-251215 (P3, rotated), ALPHA-0502 | 58 m | – | – |
   | **Live, T+105** | ALPHA-0303, HOTEL-250818 (P3, rotated), FOXTROT-251215 (P3, rotated) | **139 m** | 370 m | crosses (26 m from the center) |
   | Live, T+120 | ALPHA-0303, ALPHA-0502, HOTEL-250818 | 8 m | 324 m | crosses |

   At T+105 the center is 2,164 m from the fuel farm at a bearing of 320°, which matches §1.2's
   "about 2.1 km northwest".

   Over the 23 month 13 to 18 prober queries at T = 90 s, the method as written has a median error of
   **384 m** and a P80 of 910 m. Every query reads its target as "fence" at T = 90 s (D-046). Each
   analog's recovery point is relative to its own asset (P3: munitions), but it is added to tonight's
   fence centroid. P3 queries are off by 0.9 to 1.4 km for that reason.
5. **One alternative, measured on the training split only (months 1 to 12, 36 prober queries,
   T = 90 s):**
   - as written (anchor on tonight's target): median 502 m, P80 1,000 m;
   - with tonight's asset of the analog's target kind as the anchor while tonight's target is still
     the fence (`anchor: match_kind`, A9): median 311 m, P80 492 m.

   I did not compute that alternative on the month 13 to 18 queries. It does not change the demo,
   because the live target is BRAVO's fuel farm from T+90 on (D-046).

   **Disclosure:** the as-written numbers in fact 4 looked at the evaluation queries and the demo.
   The build chooses between the two anchors by the training-split rule in A9, never by fact 4.
6. **Environment.** `fastembed` is not installed. It is the optional extra `fastembed` in
   `pyproject.toml`, so tests use a fake module, not a skip. `shapely` 2 is present. There are 956
   reports, all on history incidents (D-041). `clue_truth` has 798 reports with at least one true
   clue, from security forces and local PD only, since BDOC and FAA texts carry none. The roads
   table has four roads, one per region: County Rd 12 (COASTAL), State Hwy 7, Farm Rd 300 and
   Route 66B.
7. **Starting point.** HEAD `5d1f9b5`; `make check` has 443 fast tests passing (10 slow deselected).

## Assumptions and decisions

Each assumption is written to `docs/DECISIONS.md` as the build reaches it. A9 is written **before**
anything is measured, like D-078 to D-080.

- **A1 (D-082) · Recall filter and no look-ahead.** For tonight's query `q` and a matched track `m`,
  the filter is built from `m`'s stored signature (`TrackStore.tracks_before`):

  ```text
  installation_id = '{m.installation_id}'
  AND event_ts_ms BETWEEN {m.start − 3 h} AND {m.end + 3 h}        -- recall.hours_window
  AND x_m BETWEEN {min x − 5 km} AND {max x + 5 km}               -- recall.radius_m
  AND y_m BETWEEN {min y − 5 km} AND {max y + 5 km}
  AND event_ts_ms < {q.start_ms}                                  -- rule 3: started before tonight
  AND report_ts_ms <= {q.until_ms}                                -- filed by the replay time
  ```

  - The box spans `m`'s loiter point (its target centroid) and its launch point (target + launch
    offset, when known).
  - The last two lines go beyond §12.3. A report filed after tonight's replay time does not exist
    yet: an FAA summary can come days after its event, and a same-night match's paperwork may still
    be unwritten.
  - The `reports` table holds history reports only (D-041). Live reports are appended by the phase 7
    replay, if any appear.
- **A2 (D-083) · Hashing embedder.**
  - Lowercase the text and split it into tokens with `[a-z0-9]+`.
  - Features: each token (`t:<token>`), plus the character 3-grams of each token padded as
    `<token>` (`g:<gram>`). The prefixes keep a token and a 3-gram from colliding.
  - Each feature `f` gives `h = stable_int(f)` (§8.9); `index = h % dim` and `sign = +1` if bit 32
    of `h` is 0, else −1.
  - Sum the signed features, then L2-normalize. A text with no features stays an all-zero vector,
    never NaN. Rows are `(n, dim)` float32. `stable_int` is memoized per feature.
  - `name = "hashing-v1-384"`.
- **A3 (D-084) · FastEmbed and `fetch-models`.**
  - `FastEmbedEmbedder` imports `fastembed` lazily and always constructs
    `TextEmbedding(model, cache_dir=paths.cache/"fastembed", local_files_only=True)`, so the app never
    downloads.
  - `kairos-defense fetch-models [--model M]` is the only code path that downloads (no
    `local_files_only`), into the same cache.
  - When `fastembed` is missing, `fetch-models` exits 1 with `uv sync --extra fastembed`.
  - With `embeddings.provider: fastembed` and no cached model, `make_embedder` raises
    `EmbedderUnavailable` naming `fetch-models`. There is no silent switch to hashing: index and
    query vectors would stop agreeing.
  - New config key `paths.cache: data/cache` (§5 already lists `data/cache/`). Its value is resolved
    against the project root like the other paths.
  - **Reports-index guard (like D-075):** before searching, `check_reports_index` checks two things,
    and raises `ReportIndexStale` ("run `make index`") if either fails:
    - the LanceDB row count equals the history-report count in DuckDB;
    - the lowest `report_id`'s stored vector is within 1e-6 (squared L2) of the current embedder's
      vector for its text.
- **A4 (D-085) · Hybrid search.**
  - `store/lance.py` gains `LanceReportIndex`, implementing the `ReportIndex` port.
    - `hybrid()` uses LanceDB's native hybrid search with `RRFReranker()` (K = 60).
    - `fts()` uses native FTS.
  - `LanceVectorStore.replace` builds the FTS index for `reports` (`FTS(with_position=True)`, needed for
    phrase queries).
  - **Fallback (§12.5):** if the native call raises `AttributeError`, `TypeError` or `ValueError` from
    the hybrid builder, the adapter raises `NotImplementedError`. A builtin keeps `ports.py`
    unchanged. `recall/search.py` then runs `VectorStore.search("reports", …)` and
    `ReportIndex.fts(…)` with the same filter and k, and fuses them with `rrf_fuse` (Σ 1/(60 + rank),
    1-based). The columns are the same either way.
  - Results are sorted by (−`_relevance_score`, `report_id`), so ties are deterministic, and cut to
    k = 5.
  - The keyword text is sanitized to `[a-z0-9]+` tokens joined by spaces. Report text with colons or
    quotes cannot break the FTS parser.
- **A5 (D-086) · Clues and links (§12.4).**
  - **Extraction:**
    - vehicles are `<color> <type>` only, from `sim.lexicon.VEHICLE_COLORS` × `VEHICLE_TYPES` (the
      generator's lexicon, which is §12.4's list and its "…");
    - roads are names from the `roads` table only, so "Ridge Rd" (a false clue outside the gazetteer)
      is not a road;
    - matching is case-insensitive (D-040). Each clue has a canonical value (`white pickup`,
      `black SUV`, `County Rd 12`) and its character span.
  - `report_clues` (the §7.2 DDL) is written by `make index` from the same function.
  - **Linking**, among the reports recalled for the top **3** matched incidents (the three §17.8
    entries):
    - a clue is linked when the same (type, value) appears in reports of two or more of those
      incidents. The link reads "white pickup also appears in reports of P1-BRAVO-251114";
    - a road clue is linked when that road, in tonight's region, intersects the forecast circle
      (`LineString.intersects(Point.buffer(r))`). The link reads "County Rd 12 runs through tonight's
      predicted zone."
  - **Tonight's keyword query (§12.3):** the text of tonight's most recent report, if one was filed
    by `q.until`. Otherwise it is built from the partial signature:
    - `drone`;
    - `orbit`, if a loiter radius is known;
    - the target words (`fuel farm`, `flight line`, `munitions area`, `headquarters`,
      `housing area`, `fence`; a test checks that these agree with `sim.facts.ASSET_NAMES`);
    - `vehicle road launch`;
    - the compass word of the approach bearing, if known.

    For the demo at T+120 this gives "drone orbit fuel farm vehicle road launch northwest", §12.3's
    example.
- **A6 (D-087) · Forecast details (§13).**
  1. Step 1: walk the fused ranking and keep the first `top_k` = 3 matches whose stored signature
     has a recovery point.
  2. Step 2: j* is the segment row paired with tonight's last row on
     `dtw_rerank.warp_path(live, seg, weights)`. This is the same alignment the warp ratio uses
     (§9.3 normalization, relaxed ends, D-069). `seg` is the match's anchored segment (best window
     `window_offset_s`, `features["window_s"]`, `anchor_bounds`). `j*_track = lo + j*`.
  3. Step 3: the remainder is the match's `track_features` `(x_rel_m, y_rel_m)` after `j*_track`,
     with gap rows dropped. The stored recovery point is appended, so the remainder ends exactly
     there.
  4. Step 4: if |wrap180(tonight's approach − the match's approach)| > 30°, rotate the remainder and
     the recovery point clockwise by that difference (`geo.rotate`). If either approach is unknown,
     do not rotate.
  5. Step 5: the weights are the fused scores. Radius = max(150, 1.5 × weighted RMS distance of the
     mapped recovery points to the center).
  6. Step 6: resample the top analog's mapped remainder to 60 points, evenly by arc length.
  7. Step 7: list the roads in tonight's region that intersect the circle.
  8. Return `None` when no match has a known recovery point.

  `MatchResult` gains `signature` (the query's partial signature) and `signatures` (the candidates'
  stored signatures), both optional. The DTW matcher fills them from `Candidates`, so the forecast
  and recall reuse what the matcher already computed. The Euclidean baseline leaves them `None`, and
  the forecast computes them through the ports.
- **A7 (D-088) · Evaluation definitions for phase 5.**
  - **Report linkage:** prober queries at T = 120 s; the top 3 distinct matched incidents of the
    fused ranking.
    - Relevant reports: the reports of that incident with at least one `clue_truth.is_true` clue,
      filed by `q.until`.
    - Retrieved: those in the recall top 5 for that match, using tonight's default query.
    - `report_linkage` = Σ retrieved / Σ relevant, with the count reported beside it.
  - **Forecast error:** prober queries at T = 90 s (and 120 s for information). The error is the
    distance from the predicted center to `track_truth.recovery_{x,y}_m`. A query without a forecast
    counts as an infinite error.
    - Keys: `forecast_median_t90_m`, `forecast_p80_t90_m`, `forecast_median_t120_m` and
      `forecast_missing_t90`.
  - Linkage and forecast labelling live in a new module, `eval/downstream.py`, so `harness.py` stays
    small. They run after the ranker's timing, so the existing latency keys keep their meaning. New
    report-only keys: `latency_forecast_p50/p95_ms` and `latency_recall_p50/p95_ms` (per match).
  - **Demo rows:**
    - `live_rank1_report_for`: the live query at T+120. The expected incident must be among the top
      3 matched incidents, and its recall rank 1 must be its own report. The observed text names the
      report, its rank among the filtered reports, and its linked clues.
    - `forecast_error_max_m`: the live forecast at T+105, with error ≤ 400 m. The observed text
      gives the error, radius, analogs and roads.

    Both are assertions under `--method dtw` and `info (Euclidean baseline)` under `euclidean`, as
    D-076 did for the top 3. When `evaluate` gets no report index, the recall row reads `pending (no
    report index)`.
  - `GATED` adds `report_linkage` (higher is better) and `forecast_median_t90_m` (lower is better).
    `PENDING` drops both.
  - After the exit check, `eval --baseline` refreshes `reports/baseline.json`. That happens only once
    the same run shows no regression against phase 4's baseline.
  - Truth: `eval/truth.py` adds `recovery_x_m` and `recovery_y_m` to `track_truth`, and a new
    `clue_truth(app)`.
- **A8 (D-089) · Index build wiring.**
  - `make index` (the `index` command) runs `features.build.build_index`, then
    `recall.index.build_reports_index`.
  - `build_reports_index` uses the adapters directly, as the features build does (D-053):
    - it reads the history reports through `DuckTrackStore.sql`;
    - it writes `report_clues` with `write_table`, so `report_clues` joins `DERIVED_DDL`;
    - it writes the LanceDB `reports` table with `replace`.
  - It is deterministic: reports are sorted by `report_id` and nothing is random.
  - The `p1_index` test fixture, and the slow `full` fixture in `tests/slow/test_full_models.py`,
    also build the reports index. This is test setup, not an assertion.
- **A9 (D-090, registered before any build measurement) · Forecast anchor while tonight's target is
  unsettled.**
  - New key `forecast.anchor: target | match_kind`. The initial value is `target`, which is §13 as
    written.
  - `match_kind`: when tonight's target is the fence pseudo-asset and the analog's stored target
    kind exists at tonight's installation (and is not the fence), the analog's relative vectors are
    added to tonight's asset of that kind. In every other case both modes are identical.
  - **Criterion:** prober queries on the training nights (2025-03-01 to 2026-02-28), T = 90 s, the
    shipped model. Adopt `match_kind` if and only if its median error is at least 50 m lower **and**
    its P80 is not higher.
  - The comparison is `uv run python -m kairos_defense.eval.forecast_choice`. It prints both modes and
    writes `reports/forecast_choice.json`.
  - Nothing is special-cased for an incident, actor, base or the demo (D-070).
- **A10 (D-091) · CLI shapes.**
  - `forecast --incident ID --at S [--track T] [--method dtw|euclidean]` prints:
    - tonight's target;
    - the center, as region meters and as "2,164 m at 320° (northwest) of BRAVO-fuel_farm";
    - the radius;
    - each analog (incident, score, recovery point, rotation, anchor, j*);
    - the exit path's ends and point count;
    - the roads crossing the zone.
  - `recall --incident ID --at S [--track T] [--matches 3] [--k 5] [--query TEXT]` prints tonight's
    keyword text and the forecast zone. For each matched incident it gives a table: rank, report,
    source, grade, local event time, score, and the text with clue spans marked (linked spans in
    bold). The link sentences follow the table.
  - Both commands exit 1 with a fix-it message (D-075):
    - unknown incident or track;
    - missing models;
    - missing or stale index, or missing or stale reports index;
    - DTW unavailable.
  - Both print local times using the region's UTC offset, as `match` does. The CLI never reads
    truth, so it prints no error.

## Work breakdown

Run `make check` after every step.

1. **Decisions first.** Write D-090 (A9: criterion, alternative, default) in `docs/DECISIONS.md`
   before any code that could measure it.
2. **Config.**
   - `config/app.yaml`: add `paths.cache: data/cache`. `config/app.py`: add `PathsConfig.cache`.
   - `config/scoring.yaml`: add `forecast.anchor: target`. `config/scoring.py`: add
     `ForecastConfig.anchor: Literal["target", "match_kind"]`.
   - `tests/unit/test_config.py`: two new invalid variants.
3. **Embedders (`src/kairos_defense/recall/__init__.py`, `recall/embed.py`).**
   - `HashingEmbedder(dim=384)` (A2).
   - `FastEmbedEmbedder(model, cache_dir)` (lazy import, `local_files_only=True`).
   - `EmbedderUnavailable`.
   - `make_embedder(app) -> Embedder`.
   - `fetch_model(app, model=None) -> Path`.
   - Tests: `tests/unit/test_embed.py`.
4. **Store.**
   - `store/ddl.py`: add `report_clues` to `DERIVED_DDL`.
   - `store/lance.py`: `FTS_COLUMNS = {"reports": "text"}`, built in `replace`. Add `LanceReportIndex(uri)`
     with `hybrid`, `fts` and `count`. Native-API failures become `NotImplementedError` (A4).
   - Empty results keep the report columns.
   - `REPORT_COLUMNS` follows §7.5, with the vector dropped from results.
5. **Clues (`recall/clues.py`).**
   - `Clue(type, value, start, end)`.
   - `extract_clues(text, road_names) -> list[Clue]`.
   - `LinkedClue` (`linked`, `link`).
   - `link_clues(recalls, zone, roads)` (A5).
   - Tests: `tests/unit/test_clues.py`.
6. **Reports index (`recall/index.py`).**
   - `reports_table(rows, vectors, dim) -> pa.Table` (§7.5 types; `*_ts_ms` int64).
   - `build_reports_index(cfg) -> ReportsSummary` (reports, report_clues rows, clues by type,
     embedder name, elapsed).
   - `check_reports_index(store, vstore, embedder)` raises `ReportIndexStale`.
   - CLI `index` prints the new rows.
   - `tests/conftest.py`: `p1_index` also builds the reports index.
   - Tests: `tests/unit/test_recall_index.py`.
7. **Search (`recall/search.py`).**
   - `TARGET_WORDS`.
   - `query_text(store, q, qsig) -> str`.
   - `fts_text(text) -> str`.
   - `recall_filter(q, msig, centroid, scoring) -> str`.
   - `rrf_fuse(vec_df, fts_df, k) -> DataFrame`.
   - `hybrid_search(index, vstore, text, vector, where, k)`, with the fallback.
   - `RecalledReport`, `MatchRecall` (`to_dict()` shaped like the §16.3 `recall` message).
   - `ReportRecall(store, index, vstore, embedder, scoring)` with `for_match(...)` and
     `for_matches(q, result, zone=None, n=3, k=5, query=None)`. The latter dedupes incidents, runs
     `link_clues`, and returns per-match timings.
   - Tests: `tests/unit/test_recall_search.py`.
8. **Matcher hand-off.** `match/matcher.py`: add the optional `signature` and `signatures` fields to
   `MatchResult`, filled from `Candidates` (A6). Existing tests are unaffected.
9. **Forecast (`src/kairos_defense/forecast/__init__.py`, `forecast/analog.py`).**
   - `Analog`, and `Forecast` with `to_dict()` (`center_x_m`, `center_y_m`, `radius_m`, `path`,
     `roads`, `analogs`, `at_s`, `target_asset_id`).
   - Pure helpers:
     - `combine(points, weights, min_radius, factor)`;
     - `rotate_rel(xy, deg)`;
     - `aligned_index(live, seg, weights)`;
     - `remainder(features, j)`;
     - `resample_path(xy, n=60)`;
     - `anchor_centroid(q, analog_kind, mode)`;
     - `roads_crossing(center, radius, roads)`.
   - `forecast(store, q, result, scoring) -> Forecast | None`.
   - The module stays under 400 lines; if it outgrows that, the pure helpers move to
     `forecast/geometry.py`.
   - Tests: `tests/unit/test_forecast.py`.
10. **CLI.**
    - Remove `recall`, `forecast` and `fetch-models` from `STUBS`.
    - Add real `recall`, `forecast` and `fetch-models` commands. Tables go in `cli_tables.py`, and
      shared lookup and error helpers keep `cli.py` under 400 lines (currently 339).
    - If needed, move the forecast and recall printing into a new `cli_recall.py`.
    - Tests: in `tests/unit/test_cli.py`.
11. **Evaluation.**
    - `eval/truth.py`: recovery columns in `track_truth`, and `clue_truth(app)`.
    - `eval/downstream.py`: `forecast_error`, `linkage_counts`, `ForecastRecall` (built once per run).
    - `eval/metrics.py`:
      - `Outcome` gains `forecast_error_m`, `forecast_ms`, `linkage_hits`, `linkage_total` and
        `recall_ms`;
      - new functions `report_linkage(outcomes, at_s=120)` and
        `forecast_summary(outcomes, at_s) -> (median, p80, n, missing)`.
    - `eval/harness.py`: `evaluate(..., reports=None)` passes a `ReportIndex`; `run_case` calls
      `downstream` at T = 90 and 120.
    - `eval/demo.py`: the two rows (A7).
    - `eval/report.py`: new keys, `GATED`, `PENDING`.
    - `eval/report_md.py`: filled headline rows, and a "Forecast and recall" section.
    - CLI `eval`: `_need_reports_index`.
    - Tests: in `test_eval_metrics.py` and `test_eval_harness.py`.
12. **Forecast anchor choice.**
    - `eval/forecast_choice.py` with `main()`: the training-split comparison and rule from A9.
    - Run it on the real data, record the output in D-090, and set `forecast.anchor` by the rule.
    - Test: `tests/unit/test_forecast_choice.py`.
13. **No-look-ahead tests.** Additions to `tests/unit/test_no_lookahead.py` (below).
14. **Slow tests.**
    - `tests/slow/test_full_models.py`: the `full` fixture builds the reports index;
      `test_full_eval_dtw` passes it and also asserts the phase 5 keys.
    - New `test_full_demo_recall_and_forecast`.
15. **Exit check.** The commands below, recorded in `docs/phases/phase-05/EXIT_CHECK.md`. Then
    `make test-all`.
16. **Documentation.**
    - New `recall/README.md` and `forecast/README.md`.
    - Update the package README `src/kairos_defense/README.md`, which documents `cli.py`, `ports.py`
      and `cli_tables` (details under "Documentation to write or update").
    - Update the `store`, `match`, `eval`, `config` and `features` READMEs and the root README's
      Status.
    - `REPORT.md`, `PROGRESS.md` (session log and one-line evidence; the Status cell is left alone)
      and DECISIONS D-082 to D-091.
    - Commit `phase 5: report recall and analog forecast`.

## Tests

Fast tests start at 443. Three parametrized stub cases leave with their stubs (`recall`, `forecast`,
`fetch-models` in `test_stub_names_its_phase`). About 55 tests are added, so the count should reach
about 495. The exact arithmetic goes into REPORT.md. No test is skipped, marked xfail or deleted.

**`tests/unit/test_embed.py`**
- `test_hashing_embedder_is_deterministic`: two instances, the same texts, identical bytes.
- `test_hashing_rows_are_unit_float32`: shape `(n, 384)`, float32, every norm 1 ± 1e-6.
- `test_hashing_known_answer`: the nonzero indices and signs of `embed(["drone"])` are pinned, as
  `test_rng` does.
- `test_hashing_ignores_case_and_punctuation`: "White Pickup!" equals "white pickup".
- `test_hashing_empty_text_is_zero`: no NaN.
- `test_similar_reports_are_closer`: the DELTA narrative against its blotter version has a higher
  cosine than against a BDOC line from another base.
- `test_fastembed_adapter_never_downloads`: a fake `fastembed` module records
  `local_files_only=True` and the cache folder; the rows are normalized float32.
- `test_make_embedder_without_fastembed_raises`: `sys.modules["fastembed"] = None`, so the message
  names `uv sync --extra fastembed` and `fetch-models`.
- `test_fetch_model_downloads_into_the_cache`: the fake module is called without `local_files_only`.

**`tests/unit/test_recall_index.py`**
- `test_reports_table_holds_history_reports_only` (on `p1_index`): rows = history reports in
  DuckDB, the §7.5 columns and types, no live incident, `*_ts_ms` equal to the DuckDB times.
- `test_fts_finds_an_exact_phrase`: on a small `LanceReportIndex` table, the phrase "County Rd 12"
  returns only the two rows with that phrase. The upper-case blotter row is one of them; "County
  Road 12" and "Rd 12 County" are not.
- `test_filters_exclude_other_bases_and_times`: rows at two installations and three times; hybrid
  and FTS with `recall_filter` return only the requested base inside the window.
- `test_report_clues_are_written` (on `p1_index`): rows equal `extract_clues` on every indexed
  report. The planted DELTA report has `vehicle/white pickup` and `road/County Rd 12`.
- `test_stale_reports_index_is_refused`: another embedder (a fake whose vectors differ) and a count
  mismatch both raise `ReportIndexStale`.

**`tests/unit/test_recall_search.py`**
- `test_recall_filter_known_answer`: the exact filter string for a hand-made signature, including
  `event_ts_ms < start` and `report_ts_ms <= until`.
- `test_query_text_from_signature`: "drone orbit fuel farm vehicle road launch northwest".
  Unknown fields drop their words.
- `test_query_text_prefers_tonights_filed_report`: a fake store has two reports; the latest one
  filed by `until` is used, and one filed after is ignored.
- `test_target_words_agree_with_report_vocabulary`: against `sim.facts.ASSET_NAMES`.
- `test_fts_text_is_sanitized`: colons and quotes are removed and the result is lowercase.
- `test_rrf_fuse_known_answer`: vector [a, b, c] and FTS [b, d] give b, a, d, c, with scores
  1/61 + 1/62, 1/61, 1/62, 1/63.
- `test_fallback_equals_native_hybrid`: on a real small table, the same order and scores
  (1e-9) as native hybrid.
- `test_hybrid_unsupported_falls_back`: a fake index raises `NotImplementedError`, and
  `hybrid_search` returns the RRF result.
- `test_delta_report_is_rank1_for_the_delta_match` (`p1_index`, toy models): the live query at
  T+120; P1-DELTA-260419 is a match; its recall rank 1 is `R-P1-DELTA-260419-1`; the text contains
  "white pickup" and "County Rd 12", and their spans are marked.

**`tests/unit/test_clues.py`**
- `test_extracts_vehicle_and_road_with_spans`: on the planted DELTA text, `text[start:end]` equals
  each phrase.
- `test_blotter_capitals_read_the_same`: "A WHITE PICKUP … COUNTY RD 12" gives the same canonical
  values (D-040).
- `test_only_colored_vehicles_and_gazetteer_roads`: a bare "pickup", "Ridge Rd" and "Quarry Rd"
  are not extracted.
- `test_extraction_agrees_with_clue_truth` (the generator's in-memory truth for the `planted`
  nights): every vehicle clue and every gazetteer road clue in `clue_truth` is extracted from its
  report, and nothing else of those two types.
- `test_clue_linked_across_two_matched_incidents`: "white pickup" in reports of two incidents is
  linked in both. A vehicle seen once is not.
- `test_road_clue_linked_when_it_crosses_the_zone`: County Rd 12 crosses a zone centered on it and
  gets the §12.4 sentence. A zone 1 km off the road leaves it unlinked.

**`tests/unit/test_forecast.py`**
- `test_combine_known_answer`: two points 100 m apart give the midpoint and the floor radius 150 m.
  Points 400 m apart give radius 300 m.
- `test_weighted_center`: weights 3 and 1 put the center a quarter of the way.
- `test_rotation_only_beyond_30_degrees`: a 20° difference is not rotated. A 90° difference turns
  a recovery due north of the target due east (clockwise, D-007).
- `test_aligned_index_on_a_shifted_copy`: tonight's window is rows 100 to 159 of a synthetic
  flight inside its anchored segment, and `lo + j*` = 159 ± 2.
- `test_exit_path_has_60_points_and_ends_at_recovery`.
- `test_top_k_counts_only_known_recoveries`: matches 1 and 3 have no recovery point, so the
  analogs are 2, 4 and 5.
- `test_no_known_recovery_gives_none`.
- `test_roads_crossing_the_zone`: a line 10 m outside the radius is not listed.
- `test_anchor_modes`: with tonight's target the fence and the analog on munitions, `match_kind`
  anchors on tonight's munitions and `target` on the fence. With tonight's target an asset, both
  modes agree.
- `test_live_forecast_on_the_p1_nights` (`p1_index`, toy models, T+105):
  - the center is finite, the radius is at least 150 m, and the path is `(60, 2)`;
  - there are at most 3 analogs, each with a known recovery;
  - `to_dict()` is valid JSON.

**`tests/unit/test_no_lookahead.py`** (+2)
- `test_recall_never_returns_later_reports`: for the live query and every P1 history query at
  T = 120 s, every recalled report has `event_ts` before `q.start_ts` and `report_ts` at or before
  `q.until`.
- `test_forecast_and_recall_ignore_points_after_t`: tampering with the live track's points after T
  leaves the forecast and the recall unchanged.

**`tests/unit/test_eval_metrics.py`** (+2)
- `test_report_linkage_known_answer`: (3/4, 1/1, 0/0) gives 0.8 over 5 reports.
- `test_forecast_summary_known_answer`: the median and P80, and a missing forecast counted as
  infinite.

**`tests/unit/test_eval_harness.py`** (+3, 1 adapted)
- `test_phase5_summary_keys`: in the `dtw_run` fixture, which now passes the `p1_index` report
  index:
  - `report_linkage`, `forecast_median_t90_m` and `forecast_p80_t90_m` are floats;
  - they are not in `pending`;
  - the Markdown has the rows.
- `test_demo_recall_and_forecast_rows`: under DTW both rows are `pass` or `fail`, with observed
  text naming the report and the error. Under Euclidean both are `info`.
- `test_downstream_labels_use_filed_true_clue_reports`: for one case, relevant reports have a true
  clue and `report_ts ≤ until`.
- Adapted, not weakened: `test_cli_eval`'s last line becomes "exit 0 if and only if no demo row
  failed". Today it reads "if and only if the top-3 row passes", and there are now three asserting
  rows.

**`tests/unit/test_cli.py`** (+5, −3 stub cases)
- `test_forecast_cli_runs_on_the_p1_nights`: exit 0; prints the center, radius, analogs and roads.
- `test_recall_cli_runs_on_the_p1_nights`: exit 0; prints `R-P1-DELTA-260419-1`.
- `test_recall_needs_reports_index`: exit 1, "make index".
- `test_forecast_unknown_incident_exits_1`.
- `test_fetch_models_without_fastembed_exits_1`.
- `BUILT` gains the three commands.

**`tests/unit/test_forecast_choice.py`** (+1)
- `test_forecast_choice_runs`: on `p1_index` with toy models and a one-night split, the JSON has
  both modes, their medians and the rule's verdict.

**`tests/unit/test_config.py`** (+2 invalid variants)
- `forecast.anchor: nearest`.
- `paths.cache` missing.

**Slow (`tests/slow/test_full_models.py`)**
- `test_full_demo_recall_and_forecast`:
  - the live T+120 recall has DELTA's report at rank 1 for the DELTA match;
  - the live T+105 forecast error is ≤ 400 m against truth (tests may read truth);
  - `"County Rd 12"` is in the zone's roads;
  - the planted report's County Rd 12 span is linked.
- `test_full_eval_dtw` gains assertions on the phase 5 keys and the two demo rows.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it will produce |
|---|---|---|
| Reports indexed with FTS | `make index` | index table: flight windows unchanged (57,462 / 51,297 / 27,507), `reports indexed 956`, `report_clues rows`, embedder `hashing-v1-384`, FTS on `text` |
| Report linkage ≥ 0.70 | `make eval` | `metrics.report_linkage` (with its report count) in `reports/eval_<date>.json` and the Markdown |
| Forecast median ≤ 400 m | `make eval` | `metrics.forecast_median_t90_m`, `forecast_p80_t90_m` and missing count |
| Demo: DELTA report rank 1 (T+120) | `make eval` | demo row `live_rank1_report_for: pass` with `R-P1-DELTA-260419-1 rank 1 …` |
| Demo: forecast ≤ 400 m (T+105) | `make eval` | demo row `forecast_error_max_m: pass` with the error in meters |
| The SPEC's last command | `uv run kairos-defense forecast --incident DEMO-BRAVO-0828 --at 105` | exit 0; center about 2.1 km northwest of BRAVO's fuel farm, radius, analogs, `roads: County Rd 12` |
| Demo T+120 beat, for the record | `uv run kairos-defense recall --incident DEMO-BRAVO-0828 --at 120` | DELTA report rank 1, with "County Rd 12 runs through tonight's predicted zone." |
| Gate targets (cumulative) | `python3 scripts/check_targets.py 5` | PASS for both phase 5 metrics, both phase 5 demo rows and the phase 4 rows; WARN for the accepted `live_top3_incidents`; exit 0 |
| Anchor rule (A9) | `uv run python -m kairos_defense.eval.forecast_choice` | both modes' median and P80 on the training split; the verdict |
| Regression reference | `uv run kairos-defense eval --baseline` (after the above) | refreshed `reports/baseline.json` with the phase 5 keys |
| Quality | `make check`, `make test-all` | counts; ruff clean |

The SPEC chain `make index && make eval && … forecast …` stops at `make eval`, which exits 1 for
the accepted `live_top3_incidents` failure (the same as phase 4). The gate runs it as
`make eval || echo …`. Each command is therefore run on its own, and EXIT_CHECK.md records every
exit code. `make eval` must print no regression, and no failed demo row other than the accepted
one.

## Documentation to write or update

- `docs/phases/phase-05/EXIT_CHECK.md` and `REPORT.md` (templates).
  - REPORT.md covers the linkage caveat (fact 2), the anchor choice with its numbers, the planning
    disclosure (fact 5), and the test-count arithmetic.
- New `src/kairos_defense/recall/README.md` and `src/kairos_defense/forecast/README.md`, from the
  package template.
- `src/kairos_defense/README.md`, the package README for `cli.py`, `ports.py`, `rng.py`, `geo.py`
  and `cli_tables`:
  - **Public API, `cli.app`:**
    - `recall`, `forecast` and `fetch-models` move from the `STUBS` list (lines 21 and 22 today) to
      "Real commands", with their options (A10);
    - the remaining stubs are `replay`, `memory`, `export`, `verify-evidence`, `api` and `mcp`;
    - `index` now also builds the LanceDB `reports` table with its FTS index, and the DuckDB
      `report_clues` table (A8);
    - the fix-it exits now cover a missing or stale reports index, and a missing embedder;
    - `fetch-models` is the only command that downloads anything, and only when run by hand. Without
      the `fastembed` extra it exits 1 with `uv sync --extra fastembed`. The hashing embedder stays the
      offline default (A3, CLAUDE.md rule 5).
  - **Public API, `cli_tables` (and `cli_recall.py`, if created):** the forecast and recall tables.
  - **Public API, `ports`:** `ReportIndex.hybrid` may raise `NotImplementedError` when the backend has
    no native hybrid search; callers then fuse vector and FTS results themselves (A4). The port's
    signatures are unchanged.
  - **Data in and out:** `cli.py` also wires `recall` and `forecast`.
  - **Configuration:** the new `paths.cache` (the FastEmbed cache) and `forecast.anchor` keys, with
    pointers to `config/README.md`.
  - **Tests:** the stub test now covers six stubs. List the new CLI tests:
    - `test_forecast_cli_runs_on_the_p1_nights`;
    - `test_recall_cli_runs_on_the_p1_nights`;
    - `test_recall_needs_reports_index`;
    - `test_forecast_unknown_incident_exits_1`;
    - `test_fetch_models_without_fastembed_exits_1`.
  - **Changelog:** "Phase 5: `recall`, `forecast` and `fetch-models` became real; `index` also builds
    the `reports` index and `report_clues`; forecast and recall tables."
- Updated READMEs:
  - `features`: one line saying that `kairos-defense index` runs `build_index` and then
    `recall.index.build_reports_index` (`build.py` itself is unchanged);
  - `store` (`LanceReportIndex`, the `reports` table, FTS, `report_clues`);
  - `match` (`MatchResult.signature` and `signatures`);
  - `eval` (truth functions, `downstream.py`, the new metrics, keys and demo rows,
    `forecast_choice`);
  - `config` (`paths.cache`, `forecast.anchor`).
- Root README: the Status row for phase 5 and links.
- `docs/PROGRESS.md`: a session-log entry and the one-line exit-check evidence. The Status cell is
  left to the autopilot.
- `docs/DECISIONS.md`: D-082 to D-091. D-090 is written first.

## Risks and mitigations

- **R1. The forecast median sits near the 400 m target.**
  - As written, it is 384 m on the evaluation queries and 502 m on the training split.
  - Mitigation: the pre-registered anchor alternative (A9), chosen on the training split only.
  - If the target is still missed, REPORT.md and DECISIONS.md give the evidence and the gate decides
    (soft gap, D-063). §13 is not tuned toward the evaluation queries or the demo.
- **R2. The demo forecast depends on which analogs have a known recovery.** Three of the five P1
  flights do not (fact 3). The planning value is 139 m with two P3 flights rotated in.
  - A model or ranking change could move it.
  - `test_full_demo_recall_and_forecast` and the eval demo row catch that.
- **R3. Report linkage is close to trivial on this data** (fact 2). It is reported honestly with the
  filter-window counts. The DELTA rank-1 beat rests on the same fact: DELTA has a lone report (D-011).
- **R4. Fast fixture tests use toy models, so rankings differ from the shipped model.**
  - Fast tests assert structure and the lone-report rank 1.
  - The demo numbers (≤ 400 m, County Rd 12) are asserted on full data in the slow test and in
    `make eval`.
- **R5. LanceDB API drift.** The native hybrid search is verified (fact 1). The §12.5 fallback is
  built and tested against the native result, so a future version that changes the hybrid builder
  degrades instead of breaking.
- **R6. No look-ahead in recall.** The two extra filter lines (A1), a tamper test and a test that
  every returned report predates the query.
- **R7. Test-count gate.** Three stub cases leave and about 55 tests are added. No existing
  assertion is loosened. `test_cli_eval`'s generalization is listed under Tests.
- **R8. Module size.**
  - `eval/downstream.py` keeps `harness.py` small (225 lines now).
  - `cli.py` is at 339 lines, so printing goes to `cli_tables.py`, or a new `cli_recall.py` if
    needed.
  - `forecast/analog.py` splits if it passes 400 lines.
- **R9. Eval run time.** Recall runs only at T = 120 s, for three incidents, and the forecast at
  T = 90 and 120 s. That adds about 23 × (3 hybrid searches + 2 forecasts), a few seconds on
  today's 39 s.
- **R10. Offline rule.** Nothing downloads unless `fetch-models` is run. The FastEmbed tests use a
  fake module. No CDN or network is touched.

## Out of scope

- The accepted `live_top3_incidents` gap (phase 4 GAPS.md, WARN) and the "flown ~18% slower"
  caption (phase 8).
- Appending live reports at replay time and the `recall` and `forecast` stream messages (phase 7),
  apart from the `to_dict()` shapes that phase 7 will send.
- The UI overlay, highlights and the beam to the road (phase 8).
- Agent tools `recall_reports` and `forecast_recovery` (phase 9).
- LLM paraphrase (D-043, phase 9).
- Swarm matching (phase 9).
- Revisiting D-046 (P6, C2 and swarm targets).

## Review changes

### Review 1

- **Blocking: the documentation list left out `src/kairos_defense/README.md`.** That README
  documents `cli.py`. It still lists `recall`, `forecast` and `fetch-models` as stubs (lines 21 and
  22) and describes the stub tests (line 71), but step 10 makes those commands real and A8 changes
  what `index` builds.
  - Resolved by adding it to "Documentation to write or update" and to work-breakdown step 16. The
    update covers:
    - the three commands as real commands, with their options;
    - `fetch-models` and the offline behaviour;
    - `index` also building `reports` and `report_clues`;
    - the new fix-it exits;
    - the `ReportIndex.hybrid` `NotImplementedError` contract;
    - the new config keys;
    - the test notes;
    - a phase 5 changelog line.
  - While checking the other package READMEs for the same gap, I also added a one-line note to the
    `features` README, because its text describes what `kairos-defense index` runs.
