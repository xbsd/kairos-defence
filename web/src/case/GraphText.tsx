import type { CaseGraph } from "../api/pages";

const KIND: Record<string, string> = {
  member_of: "is a member of",
  proposed: "is proposed for",
  report_of: "is a report about",
  assessed: "assesses",
};

/** The graph in words for screen readers (§17.12): every node and edge as known at this time. */
export function GraphText({ graph }: { graph: CaseGraph }) {
  return (
    <div className="sr-only" data-testid="graph-text">
      <h3>Nodes as of {graph.as_of}</h3>
      <ul>
        {graph.nodes.map((n) => (
          <li key={n.id}>
            {n.kind} {n.kind === "assessment" ? `"${n.label ?? ""}"` : n.id}
            {n.base ? `, base ${n.base}` : ""}
            {n.member ? ", member" : ""}
            {n.contradiction ? ", contradiction" : ""}
          </li>
        ))}
      </ul>
      <h3>Links</h3>
      <ul>
        {graph.edges.map((e) => (
          <li key={`${e.kind}-${e.source}-${e.target}-${e.seq}`}>
            {e.source} {KIND[e.kind] ?? e.kind} {e.target}
          </li>
        ))}
      </ul>
    </div>
  );
}
