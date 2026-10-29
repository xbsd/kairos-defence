# kairos_defense.recall

Report recall (SPEC §12): find the paperwork behind each matched past flight with hybrid
(vector + keyword) search, and mark and link the clues in it.

## Responsibilities

- Embed report text offline and deterministically (`embed.py`, `HashingEmbedder`, the default), or
  with an optional FastEmbed model that is never downloaded at runtime (§12.1, D-083, D-084).
- Build the LanceDB `reports` table (history reports only, full-text index on `text`) and the
  DuckDB `report_clues` table on `make index` (`index.py`, §12.2, D-089), and refuse a stale one.
- For tonight's query and each matched track: build the keyword text and the §12.3 filter (plus
  no look-ahead, D-082), run the hybrid search (native, or the §12.5 RRF fallback, D-085) and
  return the top k reports (`search.py`).
- Extract vehicle and road clues with spans, and link them across matched incidents and to the
  forecast zone (`clues.py`, §12.4, D-086).
- Depend on the ports only (rule 6); the index build uses the adapters, like the track index
  (D-053). Never read truth.

## Public API

- `embed`:
  - `HashingEmbedder(dim=384)`: `embed(texts) -> (n, dim) float32`, unit rows (all-zero for a text
    with no token); `name` `hashing-v1-384`; `features(text) -> list[str]`.
  - `FastEmbedEmbedder(model, cache_dir, dim)`: from the local cache only
    (`local_files_only=True`), refuses to start when the model folder is absent.
  - `make_embedder(app) -> Embedder` (by `embeddings.provider`); `fetch_model(app, model=None) ->
    Path` (the only downloader, `kairos-defense fetch-models`); `EmbedderUnavailable`;
    `TOKEN_RE`.
- `index`:
  - `build_reports_index(cfg) -> ReportsSummary` (`reports`, `live_reports_skipped`, `clue_rows`,
    `clues_by_type`, `reports_with_clues`, `embedder`, `dim`, `elapsed_s`);
  - `check_reports_index(store, vstore, embedder) -> probe report id` / `ReportIndexStale`;
  - `history_reports(store)`, `clue_rows(reports, road_names)`, `reports_table(rows, vectors,
    dim) -> pyarrow.Table` (§7.5; `*_ts_ms` int64 epoch ms; `vector` float32[dim]).
- `clues`:
  - `Clue(type, value, start, end)`: `text[start:end]` is the phrase as written;
  - `extract_clues(text, road_names) -> list[Clue]` (vehicles `[<color>] <type>`, gazetteer
    roads; case-insensitive);
  - `link_clues(reports, zone_roads) -> {incident: {report_id: [LinkedClue]}}`;
    `LinkedClue(..., links)` with `linked` and `to_dict()`.
- `search`:
  - `signature_words(qsig)`, `query_text(store, q, qsig)` (tonight's latest report filed by T,
    else the signature words), `fts_text(text)` (sanitized keywords), `TARGET_WORDS`;
  - `recall_filter(q, msig, centroid, scoring) -> str`;
  - `rrf_fuse(vec, fts, k)` (§12.5), `hybrid_search(index, vstore, text, vector, where, k)`;
  - `ReportRecall(store, index, vstore, embedder, scoring)`: `for_match(q, msig, text, vector,
    k)` and `for_matches(q, result, zone_roads=(), n=3, k=None, query=None) -> RecallResult`;
  - `RecallResult` (`query_text`, `matches`, `zone_roads`, `timings`; `to_dict()` is the content
    of the §16.3 `recall` message), `MatchRecall`, `RecalledReport`.

## Data in and out

- In: DuckDB `reports`, `roads`, `incidents`, `installations`, `assets`, `track_signatures`
  (through `TrackStore`); LanceDB `reports` (through `ReportIndex` and `VectorStore`).
- Out (`make index`): LanceDB `reports` (§7.5, FTS on `text`) and DuckDB `report_clues`
  (`report_id, clue_type, clue_value`, §7.2). Search writes nothing.

## How it works

- Hashing embedder (§12.1, D-083): lowercase `[a-z0-9]+` tokens; features `t:<token>` and the
  3-grams of `<token>`; `stable_int` gives index (`h % dim`) and sign (bit 32); sum; L2-normalize.
- The filter for match m (D-082): m's base; `event_ts_ms` within m's flight ± `hours_window`; a
  box of `radius_m` around m's target centroid and launch point; and `event_ts_ms` before
  tonight's first contact, `report_ts_ms` at or before the replay time.
- Keyword text (§12.3): tonight's latest report if one was filed by T, else "drone [orbit]
  <target words> vehicle road launch [compass word of the approach]", e.g. "drone orbit fuel farm
  vehicle road launch northwest" for the demo at T+120.
- Hybrid search: LanceDB's native hybrid with RRF (K = 60, ties by `report_id`); if the backend
  lacks it, the vector and FTS searches run with the same filter and k and are fused with
  Σ 1/(60 + rank). Both paths give the same rows and scores (D-085).
- Clues are linked when the same clue is in reports of two matched incidents, or when a road
  crosses tonight's forecast zone (`forecast.analog.roads_crossing`), with the sentence the UI shows.

## Configuration

- `scoring.recall`: `hours_window` (3), `radius_m` (5,000), `k` (5).
- `app.embeddings`: `provider` (`hashing` | `fastembed`), `dim` (384), `fastembed_model`.
- `app.paths.cache` (the FastEmbed cache) and `app.paths.lancedb`.

## Tests

- `tests/unit/test_embed.py`: determinism, unit float32 rows, a pinned known answer, case and
  punctuation, empty text, similar reports closer; FastEmbed never downloads, missing package,
  `fetch_model` (a fake `fastembed` module, no skip).
- `tests/unit/test_recall_index.py`: the `reports` schema and history-only rows, an exact phrase
  (blotter capitals match, "County Road 12" does not), filters exclude other bases and times,
  `report_clues`, the stale guard (another embedder, a missing row, no table), a deterministic
  rebuild.
- `tests/unit/test_recall_search.py`: the filter's exact text, the keyword text, tonight's filed
  report, `TARGET_WORDS`, sanitizing, the RRF known answer, native equals fallback, the fallback
  path, and the planted DELTA report at rank 1 for the DELTA match (spans marked).
- `tests/unit/test_clues.py`: spans, blotter capitals, lexicon and gazetteer only, agreement with
  the generator's `clue_truth`, cross-match and zone links.
- `tests/unit/test_no_lookahead.py`: no recalled report started after tonight's first contact or
  was filed after T; points after T change nothing.
- Slow: `tests/slow/test_full_models.py::test_full_demo_recall_and_forecast` and
  `test_full_report_clues_equal_clue_truth`.
- Run: `uv run pytest tests/unit -q -k "embed or recall or clues"`.

## Gotchas

- Index and query vectors must come from the same embedder. Switching `embeddings.provider` needs
  `make index`; `recall` and `eval` refuse a stale index ("run `make index`").
- LanceDB filters reject float literals on int64 columns: keep `*_ts_ms` bounds integers.
- Report linkage is close to trivial on this data (at most 4 reports per incident in a filter
  window, k = 5): it tests the filter more than the ranking (D-088).
- A report recalled for two matches does not link a clue with itself.
- `fetch-models` is the only network access in the project; nothing else may download (rule 5).

## Changelog

- Phase 5: the package (`embed.py`, `index.py`, `clues.py`, `search.py`); D-082 to D-086, D-089.
