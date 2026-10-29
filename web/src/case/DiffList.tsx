import type { CaseDiff } from "../api/pages";

const GROUP_WORDS: Record<string, string> = {
  members_added: "Members added",
  proposals: "Links proposed",
  claims_added: "Claims added",
  claims_retracted: "Claims retracted",
  contradictions: "Contradictions",
  decisions: "Decisions",
  exports: "Evidence exported",
  facts: "Facts recorded",
};

/** What changed about the case between "Known then" and the scrub time, grouped (D-101). */
export function DiffList({ diff }: { diff: CaseDiff | null }) {
  if (!diff) return <p className="text-13 text-ink-mid">Loading the changes</p>;
  const groups = Object.entries(diff.groups).filter(([, items]) => items.length);
  if (!groups.length)
    return (
      <p className="text-13 text-ink-mid" data-testid="diff-empty">
        Nothing changed between Known then and this moment.
      </p>
    );
  return (
    <div className="flex flex-col gap-3" data-testid="case-diff">
      {groups.map(([g, items]) => (
        <section key={g} aria-labelledby={`diff-${g}`} data-testid="diff-group" data-group={g}>
          <h3 id={`diff-${g}`} className="text-13 font-bold text-ink-mid">
            {GROUP_WORDS[g] ?? g} ({items.length})
          </h3>
          <ul className="mt-1 flex flex-col gap-1">
            {items.map((it) => (
              <li key={`${g}-${it.seq}`} className="text-13 text-ink-hi">
                <span className="font-mono text-12 text-ink-mid">#{it.seq}</span> {it.summary}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
