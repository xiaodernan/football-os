import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { JsonLd, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { GraphNode, GraphLink, GraphNeighborhood } from "@/lib/types";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ kind: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { kind, slug } = await params;
  return {
    title: `${kind}: ${slug}`,
    description: `Knowledge graph node: ${kind} ${slug}`,
    robots: { index: false, follow: false },
  };
}

function EdgesPanel({ links, verb, direction }: { links: GraphLink[]; verb: string; direction: string }) {
  if (!links.length) {
    return (
      <Panel title="No edges" eyebrow={`no ${verb || "edges"} found`}>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          This node has no edges matching the filter.
        </p>
      </Panel>
    );
  }

  return (
    <Panel title={`edges: ${links.length}`} eyebrow={`verb: ${verb || "all"} · direction: ${direction}`}>
      <div className="world-tablewrap" data-testid="graph-edges">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Verb</th>
              <th scope="col">Direction</th>
              <th scope="col">Other</th>
              <th scope="col">Facts</th>
              <th scope="col">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {links.map((link, idx) => (
              <tr key={idx}>
                <td className="mono">{link.verb}</td>
                <td className="mono">{link.direction}</td>
                <td>
                  <Link className="world-link" href={`/graph/nodes/${link.other.kind}/${link.other.slug}`}>
                    {link.other.kind}: {link.other.label}
                  </Link>
                </td>
                <td className="mono" style={{ maxWidth: "240px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {JSON.stringify(link.facts).slice(0, 120)}
                </td>
                <td className="mono muted" style={{ fontSize: "0.75rem" }}>
                  carrier: {link.evidence.carrier} · row: {link.evidence.row} · col: {link.evidence.column}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function NeighborhoodPanel({ data }: { data: GraphNeighborhood }) {
  return (
    <Panel title={`Neighbourhood (depth ${data.depth})`} eyebrow={`${data.node_count} nodes · ${data.edge_count} edges`}>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        Breadth-first walk capped at depth {data.depth}, max {data.node_count} nodes, {data.edge_count} edges.
      </p>
      <div className="world-tablewrap" data-testid="graph-neighborhood">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Hop</th>
              <th scope="col">From</th>
              <th scope="col">To</th>
              <th scope="col">Verb</th>
              <th scope="col">Direction</th>
            </tr>
          </thead>
          <tbody>
            {data.edges.map((edge, idx) => (
              <tr key={idx}>
                <td className="num mono">{edge.hop}</td>
                <td className="mono">{edge.from}</td>
                <td><Link className="world-link" href={`/graph/nodes/${edge.to.split("/")[0]}/${edge.to.split("/")[1]}`}>{edge.to}</Link></td>
                <td className="mono">{edge.verb}</td>
                <td className="mono">{edge.direction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted world-section-note">
        {data.node_count} nodes · {data.edge_count} edges · max depth {data.depth}
      </p>
    </Panel>
  );
}

export default async function GraphNodeDetailPage({ params }: { params: Promise<{ kind: string; slug: string }> }) {
  const { kind, slug } = await params;

  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(`/graph/nodes/${kind}/${slug}`)}`);

  const [nodeResult, edgesResult, neighborhoodResult] = await Promise.all([
    serverFetch<{ node: GraphNode; verb: string; direction: string; edges: GraphLink[]; outgoing_count: number; incoming_count: number; verbs_here: string[] }>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}`),
    serverFetch<{ edges: GraphLink[] }>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}?direction=both`),
    serverFetch<GraphNeighborhood>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}/neighborhood`),
  ]);

  if (!nodeResult.ok) {
    if (nodeResult.status === 404 || nodeResult.error.code === "no_such_node") notFound();
    return <WorldUnavailable detail={nodeResult.error.message} message="The graph node door did not answer." title={`Graph node: ${kind}:${slug}`} />;
  }

  const nodeData = nodeResult.data;
  const edgesData = edgesResult.ok ? edgesResult.data : { edges: [] };
  const neighborhoodData = neighborhoodResult.ok ? neighborhoodResult.data : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/graph/nodes/${kind}`, label: `${kind.charAt(0).toUpperCase() + kind.slice(1)} nodes` }}
        eyebrow={`kind: ${kind} · {nodeData.outgoing_count} out · {nodeData.incoming_count} in`}
        lede={nodeData.verbs_here.length ? `Verbs here: ${nodeData.verbs_here.join(", ")}` : "No edges at this node."}
        title={`${kind.charAt(0).toUpperCase() + kind.slice(1)}: ${slug}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Kind of this node">{kind}</span>
          <span className="chip mono" title="Public slug">{slug}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Thing",
          name: slug,
          additionalType: kind,
          url: absolute(`/graph/nodes/${kind}/${slug}`),
        }}
      />

      <Panel title="Node">
        <dl className="world-kv">
          <div className="world-kv__row"><dt>Kind</dt><dd className="mono">{kind}</dd></div>
          <div className="world-kv__row"><dt>Slug</dt><dd className="mono">{slug}</dd></div>
          <div className="world-kv__row"><dt>Label</dt><dd className="mono" data-testid="graph-node-label">{nodeData.node.label}</dd></div>
          <div className="world-kv__row"><dt>Path</dt><dd className="mono">{nodeData.node.path}</dd></div>
          <div className="world-kv__row"><dt>Data origin</dt><dd className="mono">{nodeData.node.data_origin}</dd></div>
          <div className="world-kv__row"><dt>Demo data</dt><dd className="mono">{String(nodeData.node.is_demo_data)}</dd></div>
        </dl>
        <p className="muted world-section-note">Canonical path: <Link className="world-link" href={nodeData.node.path}>{nodeData.node.path}</Link></p>
      </Panel>

      <EdgesPanel links={edgesData.edges} verb="" direction="both" />

      {neighborhoodData && <NeighborhoodPanel data={neighborhoodData} />}

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        Graph provenance:
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {kind}</span>
        <span className="chip mono">slug: {slug}</span>
      </p>
    </div>
  );
}