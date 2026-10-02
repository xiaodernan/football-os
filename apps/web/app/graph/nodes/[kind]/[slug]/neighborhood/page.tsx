import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel } from "@/components/ui";
import { JsonLd, WorldHead, WorldUnavailable } from "@/components/world";
import { serverFetch } from "@/lib/server";
import type { GraphNeighborhood } from "@/lib/types";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Neighbourhood",
  description: "Breadth-first walk from a graph node.",
  robots: { index: false, follow: false },
};

function EdgeRow({ edge, idx }: { edge: { hop: number; from: string; to: string; verb: string; direction: string }; idx: number }) {
  return (
    <tr key={idx}>
      <td className="num mono">{edge.hop}</td>
      <td className="mono">{edge.from}</td>
      <td>
        <Link className="world-link" href={`/graph/nodes/${edge.to.split("/")[0]}/${edge.to.split("/")[1]}`}>
          {edge.to}
        </Link>
      </td>
      <td className="mono">{edge.verb}</td>
      <td className="mono">{edge.direction}</td>
    </tr>
  );
}

export default async function GraphNeighborhoodPage({ params }: { params: Promise<{ kind: string; slug: string }> }) {
  const { kind, slug } = await params;

  const result = await serverFetch<GraphNeighborhood>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}/neighborhood`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "no_such_node") notFound();
    return <WorldUnavailable detail={result.error.message} message="The neighbourhood door did not answer." title="Neighbourhood" />;
  }

  const data = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/graph/nodes/${kind}/${slug}`, label: `${kind.charAt(0).toUpperCase() + kind.slice(1)}: ${slug}` }}
        eyebrow={`depth {data.depth} · {data.node_count} nodes · {data.edge_count} edges`}
        lede="Breadth-first walk capped by the published ceilings. Each edge carries its evidence (carrier table, row, column)."
        title={`Neighbourhood: ${kind}:${slug}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Walk depth">depth {data.depth}</span>
          <span className="chip num">{data.node_count} nodes</span>
          <span className="chip num">{data.edge_count} edges</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "ItemList",
          name: `Neighbourhood of ${kind}:${slug}`,
          itemListElement: data.edges.map((edge, idx) => ({
            "@type": "ListItem",
            position: idx + 1,
            item: { "@type": "Thing", name: edge.to },
          })),
        }}
      />

      <Panel title={`Neighbourhood (depth {data.depth})`} eyebrow={`${data.node_count} nodes · {data.edge_count} edges`}>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Breadth-first walk capped at depth {data.depth}, max {data.node_count} nodes, {data.edge_count} edges.
        </p>
        <div className="world-tablewrap">
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
                <EdgeRow key={idx} edge={edge} idx={idx} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted world-section-note">
          {data.node_count} nodes · {data.edge_count} edges · max depth {data.depth}
        </p>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        Graph provenance:
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {data.node.kind}</span>
        <span className="chip mono">slug: {data.node.slug}</span>
        <span className="chip mono">depth: {data.depth}</span>
      </p>
    </div>
  );
}