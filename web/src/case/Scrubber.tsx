import { localStamp } from "./time";

/**
 * The "as of" scrubber (§17.9): a range from the case's first event to the ledger head, with a
 * tick at every event's recorded time and the "Known then" / "Known now" jumps.
 */
export function Scrubber(props: {
  t0: number;
  t1: number;
  value: number;
  ticks: number[];
  then: number;
  offsetH: number;
  onChange: (t: number) => void;
}) {
  const { t0, t1, value, ticks, then, offsetH, onChange } = props;
  const span = Math.max(1, t1 - t0);
  const iso = new Date(value).toISOString();
  const atThen = Math.abs(value - then) < 1000;
  const atNow = Math.abs(value - t1) < 1000;
  return (
    <div className="flex flex-col gap-2" data-testid="scrubber" data-as-of={iso}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-pressed={atThen}
          onClick={() => onChange(then)}
          className={`rounded-button border px-3 py-1 text-13 ${atThen ? "border-afterglow text-afterglow" : "border-hairline text-ink-hi hover:border-afterglow"}`}
        >
          Known then
        </button>
        <button
          type="button"
          aria-pressed={atNow}
          onClick={() => onChange(t1)}
          className={`rounded-button border px-3 py-1 text-13 ${atNow ? "border-flash text-flash" : "border-hairline text-ink-hi hover:border-flash"}`}
        >
          Known now
        </button>
        <span className="ml-auto font-mono text-13 text-ink-hi" data-testid="scrub-time">
          As of {localStamp(iso, offsetH)}
        </span>
      </div>
      <div className="relative pt-1">
        <input
          type="range"
          aria-label="As of (transaction time)"
          min={t0}
          max={t1}
          step={60_000}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full accent-flash"
        />
        <div aria-hidden="true" className="relative h-2">
          {ticks.map((t, i) => (
            <span
              key={`${t}-${i}`}
              className="absolute top-0 h-2 w-px bg-afterglow"
              style={{ left: `${((t - t0) / span) * 100}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
