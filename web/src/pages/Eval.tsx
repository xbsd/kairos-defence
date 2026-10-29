import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { EvalReport } from "../api/pages";
import { ErrorHistogram, LiftChart, RecallChart } from "../eval/Charts";
import {
  demoRows,
  forecastErrors,
  histogram,
  recallSeries,
  tiles,
  type TileStatus,
} from "../eval/evalView";

const STATUS: Record<TileStatus, { word: string; icon: string; tone: string }> = {
  pass: { word: "Meets target", icon: "✓", tone: "text-verified" },
  gap: { word: "Below target", icon: "!", tone: "text-alert" },
  "report only": { word: "Reported, not gating (D-060)", icon: "·", tone: "text-ink-mid" },
  pending: { word: "Pending", icon: "…", tone: "text-ink-mid" },
  missing: { word: "Not in this report", icon: "?", tone: "text-ink-mid" },
};

/**
 * Eval (SPEC §17.9, §19.4, D-140): the newest evaluation report as written by `make eval`:
 * metric tiles against the targets, recall against seconds of flight, DTW against Euclidean, the
 * forecast error distribution and the demo assertions.
 */
export function Eval() {
  const [r, setR] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .evalLatest()
      .then(setR)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  const ts = r ? tiles(r) : null;
  const target90 = r?.targets?.find((t) => t.key === "forecast_median_t90_m")?.value ?? null;
  return (
    <main
      aria-labelledby="eval-title"
      className="min-h-0 flex-1 overflow-y-auto p-4"
      data-testid="eval"
    >
      <div className="mx-auto flex max-w-[100rem] flex-col gap-4">
        <header>
          <h1 id="eval-title" className="text-24 font-bold text-ink-hi">
            Eval
          </h1>
          <p className="text-15 text-ink-mid">
            {r
              ? `${r.file}: ${r.method === "dtw" ? "DTW and fusion" : r.method}, model ${r.model_version ?? "–"}, run ${r.created_at.slice(0, 16).replace("T", " ")} UTC`
              : "The newest evaluation report"}
          </p>
        </header>
        {error ? (
          <p role="alert" className="text-15 text-alert">
            {error}
          </p>
        ) : null}
        {r && !ts ? (
          <p role="status" className="text-15 text-alert" data-testid="eval-stale">
            This report has no targets; rerun <code className="font-mono">make eval</code>.
          </p>
        ) : null}
        {ts ? (
          <ul
            className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-5"
            aria-label="Metrics against targets"
          >
            {ts.map((t) => {
              const s = STATUS[t.status];
              return (
                <li
                  key={t.key}
                  data-testid="eval-tile"
                  data-status={t.status}
                  className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
                >
                  <p className="text-13 text-ink-mid">
                    {t.label} <span className="text-12">({t.spec})</span>
                  </p>
                  <p className="mt-1 font-mono text-24 text-ink-hi">{t.value}</p>
                  <p className="text-13 text-ink-mid">Target {t.target}</p>
                  <p className={`mt-1 text-13 ${s.tone}`}>
                    <span aria-hidden="true" className="mr-1 font-mono">
                      {s.icon}
                    </span>
                    {s.word}
                  </p>
                </li>
              );
            })}
          </ul>
        ) : null}
        {r ? (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <section
              aria-labelledby="ch-recall"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="ch-recall" className="mb-2 text-13 font-bold text-ink-mid">
                Recall against seconds of flight (probers)
              </h2>
              <RecallChart series={recallSeries(r)} />
            </section>
            <section
              aria-labelledby="ch-lift"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="ch-lift" className="mb-2 text-13 font-bold text-ink-mid">
                DTW against Euclidean
              </h2>
              <LiftChart
                dtw={r.metrics["recall_at_5_t120"] ?? null}
                euclid={r.metrics["recall_at_5_t120_baseline"] ?? null}
                lift={r.metrics["dtw_lift"] ?? null}
              />
            </section>
            <section
              aria-labelledby="ch-fc"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="ch-fc" className="mb-2 text-13 font-bold text-ink-mid">
                Forecast error at T = 90 s (probers)
              </h2>
              <ErrorHistogram
                bins={histogram(forecastErrors(r, 90), 100)}
                median={r.metrics["forecast_median_t90_m"] ?? null}
                p80={r.metrics["forecast_p80_t90_m"] ?? null}
                target={target90}
              />
            </section>
          </div>
        ) : null}
        {r ? (
          <section
            aria-labelledby="demo-title"
            className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
          >
            <h2 id="demo-title" className="mb-2 text-13 font-bold text-ink-mid">
              Demo assertions (scenario_demo.yaml)
            </h2>
            <table className="w-full text-left text-13" data-testid="demo-table">
              <thead className="text-ink-mid">
                <tr>
                  <th scope="col" className="py-1">
                    Expectation
                  </th>
                  <th scope="col">Expected</th>
                  <th scope="col">Observed</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {demoRows(r).map((d) => (
                  <tr
                    key={d.key}
                    data-testid="demo-row"
                    data-status={d.status}
                    className="border-t border-hairline align-top text-ink-hi"
                  >
                    <td className="py-1.5 pr-3 font-mono text-12">{d.key}</td>
                    <td className="pr-3">{d.expected}</td>
                    <td className="pr-3">{d.observed}</td>
                    <td
                      className={
                        d.status === "pass"
                          ? "text-verified"
                          : d.status === "fail"
                            ? "text-alert"
                            : "text-ink-mid"
                      }
                    >
                      {d.word}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}
      </div>
    </main>
  );
}
