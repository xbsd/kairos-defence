import type { MatcherTraceMsg } from "../api/messages";
import { ms, num, tPlus } from "../lib/format";
import { CostThumb, TraceCurves } from "./TraceViews";
import { headline, RATES, stateAt, type Aligned, type WbState } from "./workbenchMachine";

const SHORTLIST_ROWS = 12;
const RANK_ROWS = 8;
const ROW_PX = 26;

function day(msUtc: number): string {
  return msUtc ? new Date(msUtc).toISOString().slice(0, 10) : "–";
}

function Shortlist({ msg, landed }: { msg: MatcherTraceMsg; landed: number }) {
  const p = msg.trace.prefilter;
  const rows = p.track_id.slice(0, SHORTLIST_ROWS);
  return (
    <section aria-labelledby="wb-shortlist" className="min-w-0">
      <h3 id="wb-shortlist" className="text-13 font-bold text-ink-mid">
        1. Shortlist: {p.candidates} tracks by vector distance, in {ms(p.ms)}
      </h3>
      <ol className="mt-1 font-mono text-12" aria-label="Shortlist, nearest first">
        {rows.map((t, i) => (
          <li
            key={t}
            className={`flex justify-between gap-2 border-t border-hairline px-1 py-0.5 ${
              i < landed ? "text-ink-hi" : "text-ink-mid"
            }`}
          >
            <span className="truncate">
              {i + 1}. {p.incident_id[i]}
            </span>
            <span>{num(p.distance[i] ?? null, 3)}</span>
          </li>
        ))}
      </ol>
      {p.candidates > SHORTLIST_ROWS ? (
        <p className="mt-1 text-12 text-ink-mid">and {p.candidates - SHORTLIST_ROWS} more</p>
      ) : null}
    </section>
  );
}

function Current({ msg, cur }: { msg: MatcherTraceMsg; cur: Aligned | null }) {
  const q = msg.trace.query;
  if (!cur)
    return (
      <section aria-labelledby="wb-align" className="min-w-0">
        <h3 id="wb-align" className="text-13 font-bold text-ink-mid">
          2. DTW alignment
        </h3>
        <p className="mt-2 text-13 text-ink-mid">The alignments start after the shortlist.</p>
      </section>
    );
  const m = cur.m ?? cur.detail.curve.length;
  const what = `${cur.incident} (vector rank ${cur.order + 1})`;
  return (
    <section aria-labelledby="wb-align" className="min-w-0" data-track={cur.track}>
      <h3 id="wb-align" className="text-13 font-bold text-ink-mid">
        2. DTW alignment: {what}
      </h3>
      <div className="mt-1 grid grid-cols-[minmax(0,1fr)_9rem] items-start gap-3">
        <TraceCurves
          query={q.curve}
          detail={cur.detail}
          n={q.n}
          m={m}
          label={`Tonight's distance to target (blue, ${q.n} s) aligned to ${cur.incident} (amber, ${m} s) along the warping path`}
        />
        <CostThumb
          detail={cur.detail}
          n={q.n}
          m={m}
          label={`Cost matrix of ${q.n} by ${m} cells with the warping path`}
        />
      </div>
      <dl
        className="mt-1 grid grid-cols-[auto_1fr_auto_1fr] gap-x-3 font-mono text-12"
        data-testid="workbench-readout"
      >
        <dt className="text-ink-mid">DTW distance</dt>
        <dd>{num(cur.distance, 2)}</dd>
        <dt className="text-ink-mid">Similarity</dt>
        <dd className="text-afterglow">{num(cur.shapeSim, 3)}</dd>
        <dt className="text-ink-mid">Normalized</dt>
        <dd>{num(cur.dNorm, 3)}</dd>
        <dt className="text-ink-mid">Computed in</dt>
        <dd>{ms(cur.ms)}</dd>
        <dt className="text-ink-mid">Matrix</dt>
        <dd>
          {q.n} × {m}, band {cur.band ?? "–"}
        </dd>
        <dt className="text-ink-mid">Path</dt>
        <dd>{cur.detail.path_len} steps</dd>
      </dl>
      <p className="mt-1 text-12 text-ink-mid">
        Path: the full-matrix alignment with the segment's ends relaxed (the distance is banded).
      </p>
    </section>
  );
}

function Ranking({ st }: { st: WbState }) {
  const rows = st.ranking.slice(0, RANK_ROWS);
  return (
    <section aria-labelledby="wb-rank" className="min-w-0">
      <h3 id="wb-rank" className="text-13 font-bold text-ink-mid">
        3. Ranking by shape similarity ({st.step} aligned)
      </h3>
      <ol
        aria-label="Aligned candidates by shape similarity, best first"
        className="relative mt-1 font-mono text-12"
        style={{ height: `${rows.length * ROW_PX}px` }}
        data-testid="workbench-ranking"
      >
        {rows.map((a, i) => (
          <li
            key={a.track}
            data-track={a.track}
            className="absolute inset-x-0 flex h-[26px] items-center justify-between gap-2 border-t border-hairline px-1 transition-transform duration-(--dur-panel) ease-(--ease-out) motion-reduce:transition-none"
            style={{ transform: `translateY(${i * ROW_PX}px)` }}
          >
            <span className="truncate">
              {i + 1}. {a.incident}, {day(a.startMs)}
            </span>
            <span className="text-afterglow">{num(a.shapeSim, 3)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Fusion({ msg }: { msg: MatcherTraceMsg }) {
  const f = msg.trace.fusion;
  return (
    <section aria-labelledby="wb-fusion" className="min-w-0" data-testid="workbench-fusion">
      <h3 id="wb-fusion" className="text-13 font-bold text-ink-mid">
        4. Fusion: score = sigmoid(Σ coefficient × feature + intercept) over {f.features.length}{" "}
        features, in {ms(f.ms)}
      </h3>
      <ol aria-label="Fused top 5" className="mt-1 text-13">
        {msg.trace.ranking.slice(0, 5).map((r) => (
          <li
            key={r.track_id}
            data-track={r.track_id}
            className="border-t border-hairline px-1 py-1"
          >
            <span className="flex justify-between gap-2 font-mono text-12">
              <span className="truncate text-ink-hi">
                {r.rank}. {r.incident_id}
              </span>
              <span className="text-afterglow">{num(r.score, 3)}</span>
            </span>
            {r.reasons.length ? (
              <span className="block truncate text-12 text-ink-mid">{r.reasons.join("; ")}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The DTW workbench (D-189): the slow-motion replay of one rerun's recorded computation. */
export function WorkbenchPanel(props: {
  msg: MatcherTraceMsg;
  items: Aligned[];
  elapsed: number;
  rate: number;
  playing: boolean;
  onPlaying: (p: boolean) => void;
  onStep: () => void;
  onReplay: () => void;
  onRate: (r: number) => void;
}) {
  const st = stateAt(props.items, props.elapsed, props.rate);
  const t = props.msg.trace;
  return (
    <div
      data-testid="workbench"
      data-stage={st.stage}
      data-step={st.step}
      data-t={t.t_s}
      data-track={st.current?.track ?? ""}
      className="flex flex-col gap-3"
    >
      <p className="text-13 text-ink-hi" data-testid="workbench-headline">
        {headline(t, props.rate)}
      </p>
      <p className="text-12 text-ink-mid">
        The matcher took {ms(t.total_ms)} for the whole rerun at {tPlus(t.query.at_s)} ({t.query.n}{" "}
        s of tonight's track); recording this trace took {ms(t.trace_ms)} more.
      </p>
      <div role="group" aria-label="Replay controls" className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => props.onPlaying(!props.playing)}
          className="rounded-button border border-hairline px-2.5 py-0.5 text-13 hover:border-flash"
        >
          {props.playing ? "Pause" : "Play"}
        </button>
        <button
          type="button"
          onClick={props.onStep}
          className="rounded-button border border-hairline px-2.5 py-0.5 text-13 hover:border-flash"
        >
          Step
        </button>
        <button
          type="button"
          onClick={props.onReplay}
          className="rounded-button border border-hairline px-2.5 py-0.5 text-13 hover:border-flash"
        >
          Replay
        </button>
        <label className="flex items-center gap-1 text-12 text-ink-mid">
          Speed
          <select
            aria-label="Candidates per second"
            value={props.rate}
            onChange={(e) => props.onRate(Number(e.target.value))}
            className="rounded-button border border-hairline bg-scope px-1 py-0.5 text-13 text-ink-hi"
          >
            {RATES.map((r) => (
              <option key={r} value={r}>
                {r} per second
              </option>
            ))}
          </select>
        </label>
        <span className="text-12 text-ink-mid" role="status">
          {st.stage === "shortlist"
            ? "Vector search"
            : st.stage === "align"
              ? `Aligning ${st.step} of ${props.items.length}`
              : st.stage === "fusion"
                ? "Fusing shape and context"
                : "Done"}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
        <Shortlist msg={props.msg} landed={st.step} />
        <Current msg={props.msg} cur={st.current} />
        {st.stage === "fusion" || st.stage === "done" ? (
          <Fusion msg={props.msg} />
        ) : (
          <Ranking st={st} />
        )}
      </div>
    </div>
  );
}
