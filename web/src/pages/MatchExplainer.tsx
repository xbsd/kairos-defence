import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { DtwMsg, ExplainResponse, MatchResponse } from "../api/messages";
import { navigate } from "../app/routes";
import { Contributions } from "../explainer/Contributions";
import { FlightPair } from "../explainer/FlightPair";
import { baseName, localDate, tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { TimeWarpLens } from "../lens/TimeWarpLens";
import { DEFAULT_CHANNEL, type LensMode } from "../state/matchStore";
import { reduceMotion, uiStore } from "../state/uiStore";

/** The demo's time-warp moment, used when the URL names no replay second. */
const DEFAULT_AT = 90;

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function href(incident: string, at: number, track: string | null): string {
  const t = track ? `&track=${encodeURIComponent(track)}` : "";
  return `/explainer?incident=${encodeURIComponent(incident)}&at=${at}${t}`;
}

/**
 * Match explainer (SPEC §17.9, D-135): one match at one replay second, the time-warp lens full
 * size, both flights side by side in target-relative frames, and the fusion contributions.
 * The selectors are bound to the URL.
 */
export function MatchExplainer(props: {
  incident: string | null;
  at: number | null;
  track: string | null;
}) {
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const incident = props.incident;
  const at = props.at ?? DEFAULT_AT;
  const key = `${incident ?? ""}|${at}|${props.track ?? ""}`;
  // results keyed by the URL they belong to: a new URL shows nothing stale (no reset needed)
  const [list, setList] = useState<{ key: string; m: MatchResponse } | null>(null);
  const [doc, setDocK] = useState<{ key: string; d: ExplainResponse } | null>(null);
  const [dtw, setDtw] = useState<DtwMsg | null>(null);
  const [channel, setChannel] = useState(DEFAULT_CHANNEL);
  const [mode, setMode] = useState<LensMode>("warped");
  const [err, setErr] = useState<{ key: string; text: string } | null>(null);
  const setError = (text: string) => setErr({ key, text });
  const error = err && err.key === key ? err.text : null;

  // no incident in the URL: the first live single-track one
  useEffect(() => {
    if (props.incident) return;
    let alive = true;
    api
      .liveIncidents()
      .then((l) => {
        const first = (l.find((i) => !i.is_swarm) ?? l[0])?.incident_id ?? null;
        if (alive && first) navigate(href(first, at, props.track), true);
      })
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
    // setError only wraps the current key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.incident, props.track, at]);

  useEffect(() => {
    if (!incident) return;
    let alive = true;
    api
      .match(incident, at)
      .then((m) => {
        if (!alive) return;
        setList({ key, m });
        const top = m.matches[0]?.track_id ?? null;
        if (!props.track && top) navigate(href(incident, at, top), true);
        if (!m.matches.length)
          setError(
            m.waiting_for_s > 0
              ? `No match yet at ${tPlus(at)}: the matcher starts at ${tPlus(at + m.waiting_for_s)}.`
              : `No earlier flight matches at ${tPlus(at)}.`,
          );
      })
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident, at, props.track]);

  const track = props.track;
  useEffect(() => {
    if (!incident || !track) return;
    let alive = true;
    api
      .explain(incident, track, at)
      .then((d) => alive && setDocK({ key, d }))
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident, track, at]);

  useEffect(() => {
    if (!incident || !track) return;
    let alive = true;
    api
      .dtw(incident, track, at, channel)
      .then((d) => alive && setDtw(d))
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident, track, at, channel]);

  const matches =
    list?.key.split("|").slice(0, 2).join("|") === key.split("|").slice(0, 2).join("|")
      ? list.m.matches.slice(0, 10)
      : [];
  const docNow = doc && doc.key === key ? doc.d : null;
  const m = docNow?.match;
  const name = m ? `${baseName(m.installation_id)}, ${localDate(m.local_start)}` : null;
  return (
    <main
      aria-labelledby="explainer-title"
      className="min-h-0 flex-1 overflow-y-auto p-4"
      data-testid="explainer"
    >
      <div className="mx-auto flex max-w-[110rem] flex-col gap-4">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="explainer-title" className="text-24 font-bold text-ink-hi">
              {name ? `Why ${name} matches tonight` : "Match explainer"}
            </h1>
            <p className="text-15 text-ink-mid">
              {incident ?? "–"} at {tPlus(docNow?.t_s ?? at)}
              {docNow ? `, model ${docNow.model_version}, window ${docNow.window_s} s` : ""}
            </p>
          </div>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const t = Number(f.get("at"));
              if (incident && Number.isFinite(t) && t >= 0)
                navigate(href(incident, Math.round(t), null));
            }}
          >
            <label className="flex flex-col gap-1 text-12 text-ink-mid">
              Replay second
              <input
                name="at"
                type="number"
                min={0}
                step={5}
                defaultValue={at}
                className="w-24 rounded-button border border-hairline bg-scope px-2 py-1 font-mono text-13 text-ink-hi"
              />
            </label>
            <button
              type="submit"
              className="rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi hover:border-flash"
            >
              Show
            </button>
          </form>
        </header>
        {error ? (
          <p role="alert" className="text-15 text-alert">
            {error}
          </p>
        ) : null}
        <section
          aria-labelledby="lens-title"
          className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
        >
          <h2 id="lens-title" className="mb-2 text-13 font-bold text-ink-mid">
            Time-warp lens
          </h2>
          {matches.length && track ? (
            <TimeWarpLens
              dtw={dtw && dtw.match_track_id === track ? dtw : null}
              matches={matches}
              track={track}
              channel={channel}
              mode={mode}
              reduce={reduce}
              variant="full"
              onMode={setMode}
              onTrack={(tr) => incident && navigate(href(incident, at, tr))}
              onChannel={setChannel}
            />
          ) : (
            <p className="text-13 text-ink-mid">Loading the matches</p>
          )}
        </section>
        {docNow ? (
          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section
              aria-labelledby="flights-title"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="flights-title" className="mb-2 text-13 font-bold text-ink-mid">
                Both flights, target-relative
              </h2>
              <FlightPair
                tonight={docNow.tonight}
                past={docNow.past}
                pastTitle={`${name ?? docNow.past.incident_id}, whole flight`}
                segment={[docNow.segment.start_s, docNow.segment.end_s]}
                alignment={
                  docNow.alignment ? [docNow.alignment.start_s, docNow.alignment.end_s] : null
                }
              />
              <p className="mt-2 text-13 text-ink-mid">
                Bold: the matcher's {docNow.window_s} s window on the past flight, from{" "}
                {tPlus(docNow.segment.start_s)} to {tPlus(docNow.segment.end_s)}.
                {docNow.alignment
                  ? ` Dashed: where tonight's distance-to-target window aligns inside the whole flight, ${tPlus(docNow.alignment.start_s)} to ${tPlus(docNow.alignment.end_s)}.`
                  : ""}
              </p>
            </section>
            <section
              aria-labelledby="fusion-title"
              className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
            >
              <h2 id="fusion-title" className="mb-2 text-13 font-bold text-ink-mid">
                What the score is made of
              </h2>
              <Contributions
                rows={docNow.contributions}
                intercept={docNow.intercept}
                logit={docNow.logit}
                score={docNow.score}
              />
              {m ? (
                <div className="mt-3 flex flex-col gap-1.5">
                  <ul aria-label="Reasons" className="flex flex-wrap gap-1">
                    {m.reasons.map((r) => (
                      <li
                        key={r}
                        className="rounded-chip border border-hairline px-2 py-0.5 text-12 text-ink-hi"
                      >
                        {r}
                      </li>
                    ))}
                  </ul>
                  <p
                    className={`text-13 ${m.memory_status.startsWith("Closed") ? "text-afterglow" : "text-ink-mid"}`}
                  >
                    {m.memory_status}
                  </p>
                </div>
              ) : null}
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}
