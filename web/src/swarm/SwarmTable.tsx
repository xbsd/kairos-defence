import type { SwarmResponse } from "../api/messages";
import { tPlus } from "../lib/format";
import { tableRows } from "./swarmMath";

function v(x: number | null | undefined, d = 0): string {
  return x === null || x === undefined || !Number.isFinite(x) ? "–" : x.toFixed(d);
}

/**
 * The text equivalent of the Swarm view (§17.12): tonight's descriptors every 30 s and the
 * matched swarm's at the DTW-aligned second. Read by screen readers; the charts are its picture.
 */
export function SwarmTable({ doc, names }: { doc: SwarmResponse; names: [string, string | null] }) {
  const q = doc.query.curves;
  const m = doc.match?.curves ?? null;
  return (
    <table className="sr-only" data-testid="swarm-table">
      <caption>
        Swarm descriptors every 30 seconds: {names[0]}
        {names[1] ? `, and ${names[1]} at the second the DTW path aligns with it` : ""}
      </caption>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Drones</th>
          <th scope="col">Spread (m)</th>
          <th scope="col">Pair distance median (m)</th>
          <th scope="col">Rotation (°/s)</th>
          {m ? (
            <>
              <th scope="col">Matched time</th>
              <th scope="col">Matched spread (m)</th>
              <th scope="col">Matched pair median (m)</th>
              <th scope="col">Matched rotation (°/s)</th>
            </>
          ) : null}
        </tr>
      </thead>
      <tbody>
        {tableRows(doc).map((i) => {
          const j = doc.aligned[i];
          return (
            <tr key={i}>
              <th scope="row">{tPlus(q.t_s[i])}</th>
              <td>{q.n_drones[i] ?? "–"}</td>
              <td>{v(q.spread_m[i])}</td>
              <td>{v(q.pd_q50_m[i])}</td>
              <td>{v(q.rot_rate_dps[i], 1)}</td>
              {m ? (
                <>
                  <td>{j === undefined ? "–" : tPlus(m.t_s[j])}</td>
                  <td>{j === undefined ? "–" : v(m.spread_m[j])}</td>
                  <td>{j === undefined ? "–" : v(m.pd_q50_m[j])}</td>
                  <td>{j === undefined ? "–" : v(m.rot_rate_dps[j], 1)}</td>
                </>
              ) : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
