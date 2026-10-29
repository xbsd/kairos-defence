import type { ContributionRow } from "../api/messages";

const FEATURE_WORDS: Record<string, string> = {
  shape_sim: "Shape similarity (DTW)",
  rf_match: "RF family",
  bearing_sim: "Approach bearing",
  tod_sim: "Time of night",
  launch_sim: "Launch area",
  radius_sim: "Orbit radius",
  alt_sim: "Altitude",
};

const sign = (v: number, d = 2) => `${v < 0 ? "−" : "+"}${Math.abs(v).toFixed(d)}`;

/**
 * The fused score taken apart (§10.7, §17.9): one signed horizontal bar per feature,
 * coefficient × value, largest first; then the sum in words. Positive pushes toward a match
 * (afterglow, to the right of zero), negative away (to the left).
 */
export function Contributions(props: {
  rows: ContributionRow[];
  intercept: number;
  logit: number;
  score: number;
}) {
  const { rows, intercept, logit, score } = props;
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.contribution)));
  const neg = rows.some((r) => r.contribution < 0);
  const zero = neg ? 35 : 0; // percent of the bar track left of zero
  const sum = rows.reduce((a, r) => a + r.contribution, 0);
  return (
    <figure className="flex flex-col gap-2" data-testid="contributions">
      <ol className="flex flex-col gap-1.5">
        {rows.map((r) => {
          const w = (Math.abs(r.contribution) / max) * (100 - zero);
          const left = r.contribution >= 0 ? zero : zero - (Math.abs(r.contribution) / max) * zero;
          return (
            <li
              key={r.feature}
              data-testid="contribution-bar"
              data-feature={r.feature}
              data-value={r.contribution}
              className="grid grid-cols-[11rem_minmax(0,1fr)_5.5rem] items-center gap-3 text-13"
            >
              <span className="truncate text-ink-hi">{FEATURE_WORDS[r.feature] ?? r.feature}</span>
              <span className="relative h-3 rounded-button bg-hairline/40" aria-hidden="true">
                {neg ? (
                  <span
                    className="absolute inset-y-0 w-px bg-ink-mid"
                    style={{ left: `${zero}%` }}
                  />
                ) : null}
                <span
                  className={`absolute inset-y-0 rounded-button ${r.contribution >= 0 ? "bg-afterglow" : "bg-ink-mid"}`}
                  style={{ left: `${left}%`, width: `${Math.max(0.5, w)}%` }}
                />
              </span>
              <span className="text-right font-mono text-ink-hi">{sign(r.contribution)}</span>
            </li>
          );
        })}
      </ol>
      <figcaption className="text-13 text-ink-mid" data-testid="logit-line">
        Intercept {sign(intercept)} and contributions {sign(sum)} give a logit of {sign(logit)}; the
        score is sigmoid({logit.toFixed(2)}) ={" "}
        <span className="font-mono text-afterglow">{score.toFixed(3)}</span>.
      </figcaption>
      <table className="sr-only">
        <caption>Fusion contributions</caption>
        <thead>
          <tr>
            <th scope="col">Feature</th>
            <th scope="col">Value</th>
            <th scope="col">Coefficient</th>
            <th scope="col">Contribution</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.feature}>
              <th scope="row">{FEATURE_WORDS[r.feature] ?? r.feature}</th>
              <td>{r.value.toFixed(3)}</td>
              <td>{r.coefficient.toFixed(3)}</td>
              <td>{r.contribution.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
