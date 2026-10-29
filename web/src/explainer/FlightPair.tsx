import type { ExplainFlight } from "../api/messages";

type Pt = [number, number, number]; // t_s, x_rel, y_rel

function pts(f: ExplainFlight): Pt[] {
  const out: Pt[] = [];
  for (const row of f.points) {
    const [t, x, y] = row;
    if (
      t === null ||
      t === undefined ||
      x === null ||
      x === undefined ||
      y === null ||
      y === undefined
    )
      continue;
    out.push([t, x, y]);
  }
  return out;
}

/** One shared extent (meters around the target) so both plots use the same scale. */
function sharedExtent(a: Pt[], b: Pt[]): number {
  let r = 200;
  for (const [, x, y] of [...a, ...b]) r = Math.max(r, Math.abs(x), Math.abs(y));
  return r * 1.08;
}

function Plot(props: {
  title: string;
  points: Pt[];
  extent: number;
  tone: "flash" | "afterglow";
  segment?: [number, number] | null;
  alignment?: [number, number] | null;
  testid: string;
}) {
  const S = 260;
  const k = S / (2 * props.extent);
  const X = (x: number) => S / 2 + x * k;
  const Y = (y: number) => S / 2 - y * k; // north up
  const line = (ps: Pt[]) =>
    ps.map(([, x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ");
  const inside = (r: [number, number] | null | undefined) =>
    r ? props.points.filter(([t]) => t >= r[0] && t <= r[1]) : [];
  const seg = inside(props.segment);
  const al = inside(props.alignment);
  const color = props.tone === "flash" ? "var(--flash)" : "var(--afterglow)";
  return (
    <figure className="flex flex-col items-center gap-1">
      <svg
        width={S}
        height={S}
        viewBox={`0 0 ${S} ${S}`}
        role="img"
        aria-label={`${props.title}: ${props.points.length} seconds of track around the target`}
        data-testid={props.testid}
        className="rounded-panel border border-hairline"
      >
        <circle
          cx={S / 2}
          cy={S / 2}
          r={(200 * k).toFixed(1)}
          fill="none"
          stroke="var(--hairline)"
        />
        <path
          d={`M ${S / 2 - 6} ${S / 2} H ${S / 2 + 6} M ${S / 2} ${S / 2 - 6} V ${S / 2 + 6}`}
          stroke="var(--ink-mid)"
        />
        <polyline
          points={line(props.points)}
          fill="none"
          stroke={color}
          strokeOpacity={props.segment ? 0.45 : 1}
          strokeWidth={props.segment ? 1.2 : 1.8}
        />
        {seg.length ? (
          <polyline
            data-testid={`${props.testid}-segment`}
            points={line(seg)}
            fill="none"
            stroke={color}
            strokeWidth={2.4}
          />
        ) : null}
        {al.length ? (
          <polyline
            data-testid={`${props.testid}-alignment`}
            points={line(al)}
            fill="none"
            stroke="var(--bone)"
            strokeWidth={1.2}
            strokeDasharray="3 4"
          />
        ) : null}
        <text x={S / 2 + 8} y={S / 2 - 8} fontSize={12} fill="var(--ink-mid)">
          Target
        </text>
        <text x={8} y={S - 8} fontSize={12} fill="var(--ink-mid)">
          {Math.round(props.extent)} m to the edge, north up
        </text>
      </svg>
      <figcaption className="text-13 text-ink-hi">{props.title}</figcaption>
    </figure>
  );
}

/**
 * Both flights side by side in target-relative frames (§17.9): tonight up to the rerun second
 * (flash) and the whole past flight (afterglow), with the matcher's window drawn bold and where
 * tonight's distance-to-target window aligns inside it (§10.4 step 6) dashed in bone.
 */
export function FlightPair(props: {
  tonight: ExplainFlight;
  past: ExplainFlight;
  pastTitle: string;
  segment: [number, number];
  alignment: [number, number] | null;
}) {
  const a = pts(props.tonight);
  const b = pts(props.past);
  const extent = sharedExtent(a, b);
  return (
    <div className="flex flex-wrap justify-center gap-4" data-testid="flight-pair">
      <Plot
        title="Tonight, to the rerun second"
        points={a}
        extent={extent}
        tone="flash"
        testid="flight-tonight"
      />
      <Plot
        title={props.pastTitle}
        points={b}
        extent={extent}
        tone="afterglow"
        segment={props.segment}
        alignment={props.alignment}
        testid="flight-past"
      />
    </div>
  );
}
