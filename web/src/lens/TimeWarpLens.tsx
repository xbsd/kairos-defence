import { useRef } from "react";

import type { DtwMsg, MatchItem } from "../api/messages";
import { baseName, localDate } from "../lib/format";
import { useWidth } from "../lib/useWidth";
import type { LensMode } from "../state/matchStore";
import { CostMatrix } from "./CostMatrix";
import { LensCurves } from "./LensCurves";
import { CHANNELS, paceWords } from "./lensMath";

export interface LensProps {
  dtw: DtwMsg | null;
  matches: MatchItem[];
  track: string | null;
  channel: string;
  mode: LensMode;
  reduce: boolean;
  variant: "compact" | "full";
  /** Height available to the curves and the matrix together (compact variant), px. */
  budget?: number;
  onMode: (m: LensMode) => void;
  onTrack: (track: string) => void;
  onChannel: (channel: string) => void;
}

function matchName(m: MatchItem): string {
  return `${baseName(m.installation_id)}, ${localDate(m.local_start)}`;
}

/**
 * The time-warp lens (SPEC §17.7): Same time / Warped, the match and channel selectors, the
 * curves and connectors, the cost matrix with its path, and the readouts in words.
 */
export function TimeWarpLens(p: LensProps) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box);
  const unit = CHANNELS.find((c) => c.key === p.channel)?.unit ?? "";
  const full = p.variant === "full";
  // the compact lens shares the memory rail: split what is left after the controls (D-145)
  const room = Math.max(120, (p.budget ?? 230) - 24); // less the matrix caption and the gap
  const curvesH = full ? 300 : Math.round(Math.min(190, room * 0.62));
  const matrixH = full ? 300 : Math.round(Math.min(130, room * 0.38));
  const d = p.dtw;
  return (
    <div ref={box} className="flex min-h-0 flex-col gap-2" data-testid="time-warp-lens">
      <div className="flex flex-wrap items-center gap-1.5">
        <div
          role="group"
          aria-label="Connector mode"
          className="flex rounded-button border border-hairline"
        >
          {(
            [
              ["same", "Same time"],
              ["warped", "Warped"],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              aria-pressed={p.mode === m}
              onClick={() => p.onMode(m)}
              className={`px-2 py-1 text-13 whitespace-nowrap transition-colors duration-(--dur-micro) ease-(--ease-out) ${
                p.mode === m ? "bg-hairline text-flash" : "text-ink-mid hover:text-ink-hi"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex min-w-0 items-center gap-1 text-12 text-ink-mid">
          <span className="sr-only">Match</span>
          <select
            aria-label="Match"
            value={p.track ?? ""}
            onChange={(e) => p.onTrack(e.target.value)}
            className="max-w-[8.5rem] truncate rounded-button border border-hairline bg-scope px-1 py-1 text-13 text-ink-hi"
          >
            {p.matches.map((m) => (
              <option key={m.track_id} value={m.track_id}>
                {matchName(m)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-0 items-center gap-1 text-12 text-ink-mid">
          <span className="sr-only">Channel</span>
          <select
            aria-label="Channel"
            value={p.channel}
            onChange={(e) => p.onChannel(e.target.value)}
            className="max-w-[7.5rem] truncate rounded-button border border-hairline bg-scope px-1 py-1 text-13 text-ink-hi"
          >
            {CHANNELS.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {d ? (
        <>
          <dl className="grid grid-cols-3 gap-2 text-12 text-ink-mid" data-testid="lens-readouts">
            <div>
              <dt>DTW distance</dt>
              <dd className="font-mono text-13 text-afterglow" data-testid="lens-dtw">
                {d.dtw_distance.toFixed(1)} {unit}
              </dd>
            </div>
            <div>
              <dt>Same-time distance</dt>
              <dd className="font-mono text-13 text-ink-hi" data-testid="lens-euclid">
                {d.euclid_distance.toFixed(1)} {unit}
              </dd>
            </div>
            <div>
              <dt>Pace</dt>
              <dd className="text-13 leading-tight text-ink-hi" data-testid="lens-pace">
                {paceWords(d.warp_text)}
              </dd>
            </div>
          </dl>
          <div className={full ? "grid grid-cols-1 gap-3 lg:grid-cols-2" : "flex flex-col gap-1.5"}>
            <LensCurves
              dtw={d}
              mode={p.mode}
              reduce={p.reduce}
              width={full ? Math.max(200, Math.floor((width - 12) / 2)) : width}
              height={curvesH}
            />
            <CostMatrix dtw={d} reduce={p.reduce} height={matrixH} />
          </div>
        </>
      ) : (
        <p className="text-13 text-ink-mid" data-testid="lens-loading">
          Loading the alignment
        </p>
      )}
    </div>
  );
}
