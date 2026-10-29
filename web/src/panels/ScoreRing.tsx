import { useEffect, useRef } from "react";

export type RingState = "pending" | "approved" | "rejected";

const R = 15;
const C = 2 * Math.PI * R;

/** A match score as a ring that fills over 600 ms (§17.8); approved turns green, rejected dims. */
export function ScoreRing({
  score,
  state,
  reduce,
}: {
  score: number;
  state: RingState;
  reduce: boolean;
}) {
  const target = C * (1 - Math.min(Math.max(score, 0), 1));
  const arc = useRef<SVGCircleElement>(null);
  // the arc starts empty and fills on the next frame, so the 600 ms transition runs on mount
  useEffect(() => {
    const el = arc.current;
    if (!el) return;
    const set = () => {
      el.style.strokeDashoffset = String(target);
    };
    if (reduce || typeof requestAnimationFrame !== "function") {
      set();
      return;
    }
    const id = requestAnimationFrame(set);
    return () => cancelAnimationFrame(id);
  }, [target, reduce]);
  const stroke =
    state === "approved"
      ? "stroke-verified"
      : state === "rejected"
        ? "stroke-ink-mid"
        : "stroke-afterglow";
  return (
    <svg
      viewBox="0 0 36 36"
      width="40"
      height="40"
      aria-hidden="true"
      data-testid="score-ring"
      data-state={state}
      className={`shrink-0 ${state === "rejected" ? "opacity-50" : ""}`}
    >
      <circle cx="18" cy="18" r={R} className="fill-none stroke-hairline" strokeWidth="3" />
      <circle
        ref={arc}
        cx="18"
        cy="18"
        r={R}
        data-testid="score-arc"
        className={`fill-none ${stroke}`}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={C}
        strokeDashoffset={C}
        transform="rotate(-90 18 18)"
        style={{
          transition: reduce
            ? "stroke 120ms linear"
            : "stroke-dashoffset 600ms cubic-bezier(0.22, 1, 0.36, 1), stroke 240ms linear",
        }}
      />
      {state === "approved" ? (
        <path d="M12.5 18.5l3.5 3.5 7-7.5" className="fill-none stroke-verified" strokeWidth="2" />
      ) : null}
    </svg>
  );
}
