import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { ShiftDeltaDoc } from "../api/pages";
import { Link } from "../app/Link";
import { navigate } from "../app/routes";
import { localStamp } from "../case/time";
import { useThrottledStore } from "../lib/useThrottledStore";
import { sceneStore } from "../state/sceneStore";

const DELTA_GROUPS: [string, string][] = [
  ["incidents", "New incidents"],
  ["reports", "Reports"],
  ["proposals", "Links proposed"],
  ["links_approved", "Links approved"],
  ["links_rejected", "Links rejected"],
  ["assessments_added", "Assessments added"],
  ["assessments_retracted", "Assessments retracted"],
  ["retractions", "Other retractions"],
  ["contradictions_opened", "Contradictions opened"],
  ["decisions", "Decisions"],
  ["exports", "Evidence exported"],
  ["models", "Models registered"],
];

const DAY_MS = 24 * 3600_000;

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** "2026-08-28T16:41" for a datetime-local input at an offset from UTC. */
function toLocalInput(ms: number, offsetH: number): string {
  return new Date(ms + offsetH * 3600_000).toISOString().slice(0, 16);
}

function fromLocalInput(v: string, offsetH: number): number {
  return Date.parse(`${v}:00Z`) - offsetH * 3600_000;
}

/**
 * Shift delta (SPEC §15.8, §17.9): what the memory learned since a chosen time, grouped; each
 * item that belongs to a case links to its node on the Case board.
 */
export function ShiftDelta({ since }: { since: string | null }) {
  const installations = useThrottledStore(sceneStore, (s) => s.installations, 2);
  const [offset, setOffset] = useState<number | null>(null);
  const [doc, setDoc] = useState<ShiftDeltaDoc | null>(null);
  const [error, setError] = useState<string | null>(null);

  // the live installation's offset: the picker speaks its local time
  useEffect(() => {
    api
      .liveIncidents()
      .then((l) => {
        const inst = (l.find((i) => !i.is_swarm) ?? l[0])?.installation_id;
        const off = installations.find((i) => i.installation_id === inst)?.utc_offset_hours;
        if (off !== undefined) setOffset(off);
        else if (installations.length) setOffset(0);
      })
      .catch(() => setOffset(0));
  }, [installations]);

  // no "since" in the URL: 24 h before the ledger head
  useEffect(() => {
    if (since) return;
    let alive = true;
    api
      .ledgerVerify()
      .then((v) => (v.head_seq !== null ? api.ledgerRecord(v.head_seq) : null))
      .then((r) => {
        if (alive && r)
          navigate(
            `/delta?since=${new Date(Date.parse(r.recorded_at) - DAY_MS).toISOString()}`,
            true,
          );
      })
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
  }, [since]);

  useEffect(() => {
    if (!since) return;
    let alive = true;
    api
      .delta(since)
      .then((d) => alive && setDoc(d))
      .catch((e: unknown) => alive && setError(errText(e)));
    return () => {
      alive = false;
    };
  }, [since]);

  const off = offset ?? 0;
  const sinceMs = since ? Date.parse(since) : null;
  return (
    <main
      aria-labelledby="delta-title"
      className="min-h-0 flex-1 overflow-y-auto p-4"
      data-testid="shift-delta"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="delta-title" className="text-24 font-bold text-ink-hi">
              Shift delta
            </h1>
            <p className="text-15 text-ink-mid">
              {doc
                ? `${doc.count} change${doc.count === 1 ? "" : "s"} from ${localStamp(doc.since, off)} to ${localStamp(doc.until, off)}`
                : "What the memory learned since a chosen time"}
            </p>
          </div>
          {sinceMs !== null && Number.isFinite(sinceMs) && offset !== null ? (
            <label className="flex flex-col gap-1 text-12 text-ink-mid">
              Since (local time)
              <input
                type="datetime-local"
                defaultValue={toLocalInput(sinceMs, off)}
                onChange={(e) => {
                  const t = fromLocalInput(e.target.value, off);
                  if (Number.isFinite(t))
                    navigate(`/delta?since=${new Date(t).toISOString()}`, true);
                }}
                className="rounded-button border border-hairline bg-scope px-2 py-1 font-mono text-13 text-ink-hi"
              />
            </label>
          ) : null}
        </header>
        {error ? (
          <p role="alert" className="text-15 text-alert">
            {error}
          </p>
        ) : null}
        {doc ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {DELTA_GROUPS.filter(([g]) => (doc.groups[g] ?? []).length).map(([g, title]) => (
              <section
                key={g}
                aria-labelledby={`dg-${g}`}
                data-testid="delta-group"
                data-group={g}
                className="rounded-panel border border-hairline bg-glass p-3 backdrop-blur-glass"
              >
                <h2 id={`dg-${g}`} className="text-13 font-bold text-ink-mid">
                  {title} ({doc.groups[g]?.length ?? 0})
                </h2>
                <ul className="mt-1 flex flex-col gap-1">
                  {(doc.groups[g] ?? []).map((it) => (
                    <li key={`${g}-${it.seq}`} className="text-13 text-ink-hi">
                      <span className="font-mono text-12 text-ink-mid">#{it.seq}</span>{" "}
                      {it.case_id ? (
                        <Link
                          to={`/cases/${it.case_id}?focus=${encodeURIComponent(it.subject_id ?? "")}`}
                          className="text-flash underline-offset-2 hover:underline"
                        >
                          {it.summary}
                        </Link>
                      ) : (
                        it.summary
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            {doc.count === 0 ? (
              <p className="text-15 text-ink-mid">Nothing changed in this window.</p>
            ) : null}
          </div>
        ) : (
          <p className="text-15 text-ink-mid">Loading</p>
        )}
      </div>
    </main>
  );
}
