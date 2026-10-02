import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { serverFetch } from "@/lib/server";
import type { GraphRules } from "@/lib/types";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ kind: string }> }): Promise<Metadata> {
  const { kind } = await params;
  return {
    title: `${kind.charAt(0).toUpperCase() + kind.slice(1)} nodes`,
    description: `Browse all ${kind} nodes in the football knowledge graph.`,
    robots: { index: false, follow: false },
  };
}

function KindNodes({ kind, rules }: { kind: string; rules: GraphRules }) {
  return (
    <Panel title={`${kind.charAt(0).toUpperCase() + kind.slice(1)} nodes`} eyebrow={`nodes of kind ${kind}`}>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        Select a node to see its typed edges and walk its neighbourhood up to depth {rules.max_depth}.
      </p>
      <form action={`/graph/nodes/${kind}`} method="GET" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <label htmlFor="slug" className="muted" style={{ fontSize: "0.85rem" }}>
          slug:
        </label>
        <input id="slug" name="slug" type="text" placeholder="slug" style={{ minWidth: "180px" }} />
        <button className="btn btn--primary" type="submit">Open</button>
      </form>
      <p className="muted world-section-note">
        Or browse a node by its slug. The node door prints the node and all its typed edges.
      </p>
    </Panel>
  );
}

function NodeListing({ kind, rules }: { kind: string; rules: GraphRules }) {
  return (
    <Panel title={`${kind.charAt(0).toUpperCase() + kind.slice(1)}`} eyebrow={`nodes of kind ${kind}`}>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        This is a placeholder. The list view would paginate through all nodes of this kind.
        For now, use the form above to open a specific node by slug.
      </p>
      <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
        {rules.node_kinds.map((k) => (
          <Link key={k} className="btn" href={`/graph/nodes/${k}`}>
            {k}
          </Link>
        ))}
      </div>
    </Panel>
  );
}

async function GraphNodesKindPage({ params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;

  const rulesResult = await serverFetch<GraphRules>("/graph/rules");
  if (!rulesResult.ok) {
    return <WorldUnavailable detail={rulesResult.error.message} message="The graph rules door did not answer." title="Knowledge Graph" />;
  }
  const rules = rulesResult.data;

  if (!rules.node_kinds.includes(kind)) {
    notFound();
  }

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/graph", label: "Knowledge Graph" }}
        eyebrow={`${kind.charAt(0).toUpperCase() + kind.slice(1)} nodes`}
        lede="Pick a node by its slug to see its typed edges and walk its neighbourhood."
        title={`${kind.charAt(0).toUpperCase() + kind.slice(1)} nodes`}
      />

      <KindNodes kind={kind} rules={rules} />
      <NodeListing kind={kind} rules={rules} />

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        All graph reads are public and carry the same provenance envelope as the world routes:
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {kind}</span>
      </p>
    </div>
  );
}

export default GraphNodesKindPage;