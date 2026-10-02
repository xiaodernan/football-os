import type { Metadata } from "next";
import Link from "next/link";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";
import type { GraphRules } from "@/lib/types";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Knowledge Graph",
  description: "Browse the football knowledge graph: nodes, edges, and the vocabulary that connects them.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/graph") },
};

function RulesPanel({ rules }: { rules: GraphRules }) {
  return (
    <Panel title="Graph Rules" eyebrow={`${rules.node_kinds.length} kinds · ${rules.edge_verbs.length} verbs · depth ≤ ${rules.max_depth} · edges ≤ ${rules.max_edges} · nodes ≤ ${rules.max_nodes}`}>
      <div className="stack">
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          The graph is a read-time projection over the schema&apos;s own foreign keys. No `graph_edges` table exists;
          every edge is a clause that already lives in the world tables. The ceiling figures below are the same
          ones the walk guards with.
        </p>

        <div className="row wrap" style={{ gap: "0.5rem" }}>
          <Panel className="grow" title="Node Kinds" eyebrow={rules.node_kinds.length.toString()}>
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {rules.node_kinds.map((kind) => (
                <li key={kind}>
                  <Link className="world-link" href={`/graph/nodes/${kind}`}>
                    {kind}
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel className="grow" title="Edge Verbs" eyebrow={rules.edge_verbs.length.toString()}>
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {rules.edge_verbs.map((verb) => (
                <li key={verb}>
                  <Link className="world-link" href={`/graph/nodes/player?verb=${verb}`}>
                    {verb}
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <Panel title="Ceilings" eyebrow={rules.routes.length.toString()}>
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            <li><span className="mono">max_depth</span> = {rules.max_depth}</li>
            <li><span className="mono">max_edges</span> = {rules.max_edges}</li>
            <li><span className="mono">max_nodes</span> = {rules.max_nodes}</li>
          </ul>
        </Panel>

        {rules.spec_verbs_declined && Object.keys(rules.spec_verbs_declined).length > 0 && (
          <Panel title="Declined Spec Verbs" eyebrow={Object.keys(rules.spec_verbs_declined).length.toString()}>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              These verbs appear in §30 but the schema has no clause to project them. Each is recorded with the
              measurement that forced the decline, so nothing is quietly dropped.
            </p>
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {Object.entries(rules.spec_verbs_declined).map(([verb, reason]) => (
                <li key={verb} style={{ fontSize: "0.85rem" }}>
                  <span className="mono">{verb}</span> — {reason}
                </li>
              ))}
            </ul>
          </Panel>
        )}

        <Panel title="Declined Clauses" eyebrow={rules.clauses_declined.toString()}>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            Public foreign keys the graph does not traverse. Each names the clause and the reason it is not walked.
          </p>
          {rules.declined_clauses && rules.declined_clauses.length > 0 && (
            <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {rules.declined_clauses.map((item: { clause: string; reason: string }, idx: number) => (
                <li key={idx} style={{ fontSize: "0.85rem" }}>
                  <span className="mono">{item.clause}</span> — {item.reason}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Private Tables Excluded" eyebrow={rules.private_tables_excluded.toString()}>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            Tables that reach a user or organisation (directly or transitively) are excluded from the graph.
            The graph only projects relations over purely world data.
          </p>
        </Panel>
      </div>
    </Panel>
  );
}

async function GraphPage() {
  const rulesResult = await serverFetch<GraphRules>("/graph/rules");
  if (!rulesResult.ok) {
    return <WorldUnavailable detail={rulesResult.error.message} message="The graph rules door did not answer." title="Knowledge Graph" />;
  }

  const rules = rulesResult.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: "Home" }}
        eyebrow={`${rules.node_kinds.length} kinds · ${rules.edge_verbs.length} verbs · depth ≤ ${rules.max_depth}`}
        lede="The football knowledge graph is a read-time projection over the schema's own foreign keys. No `graph_edges` table exists; every relation is a clause that already lives in the world tables. This page lets you browse nodes, follow typed edges, and walk the neighbourhood up to the published ceilings."
        title="Knowledge Graph"
      />

      <RulesPanel rules={rules} />

      <Panel title="Browse Nodes" eyebrow={`pick a kind to list its nodes`}>
        <div className="row wrap" style={{ gap: "0.5rem" }}>
          {rules.node_kinds.map((kind) => (
            <Link key={kind} className="btn" href={`/graph/nodes/${kind}`}>
              {kind} <span className="mono">→</span>
            </Link>
          ))}
        </div>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        All graph reads are public and carry the same provenance envelope as the world routes:
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">{rules.edge_verbs.length} verbs</span>
        <span className="chip mono">depth ≤ {rules.max_depth}</span>
        <span className="chip mono">edges ≤ {rules.max_edges}</span>
        <span className="chip mono">nodes ≤ {rules.max_nodes}</span>
        <span className="chip">{rules.private_tables_excluded} private tables excluded</span>
      </p>
    </div>
  );
}

export default GraphPage;