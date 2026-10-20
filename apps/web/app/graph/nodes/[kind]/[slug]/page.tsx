import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { GraphNode, GraphLink, GraphNeighborhood } from "@/lib/types";

import "../../../../../styles/tactics.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ kind: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { kind, slug } = await params;
  const t = await getTranslations("graph");
  return {
    title: `${kind}: ${slug}`,
    description: t("nodeMetaDescription", { kind, slug }),
    robots: { index: false, follow: false },
  };
}

function EdgesPanel({
  links,
  verb,
  direction,
  t,
}: {
  links: GraphLink[];
  verb: string;
  direction: string;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  if (!links.length) {
    return (
      <Panel title={t("noEdgesTitle")} eyebrow={t("noEdgesEyebrow", { verb: verb || t("noEdgesTitle") })}>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {t("noEdgesNote")}
        </p>
      </Panel>
    );
  }

  return (
    <Panel title={t("edgesTitle", { count: links.length })} eyebrow={t("edgesEyebrow", { verb: verb || "all", direction })}>
      <div className="world-tablewrap" data-testid="graph-edges">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("thVerb")}</th>
              <th scope="col">{t("thDirection")}</th>
              <th scope="col">{t("thOther")}</th>
              <th scope="col">{t("thFacts")}</th>
              <th scope="col">{t("thEvidence")}</th>
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
                  {t("evidenceLine", {
                    carrier: link.evidence.carrier,
                    row: link.evidence.row,
                    column: link.evidence.column,
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function NeighborhoodPanel({
  data,
  t,
}: {
  data: GraphNeighborhood;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  return (
    <Panel
      title={t("neighborhoodTitle", { depth: data.depth })}
      eyebrow={t("neighborhoodEyebrow", { nodes: data.node_count, edges: data.edge_count })}
    >
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        {t("neighborhoodNote", { depth: data.depth, nodes: data.node_count, edges: data.edge_count })}
      </p>
      <div className="world-tablewrap" data-testid="graph-neighborhood">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("thHop")}</th>
              <th scope="col">{t("thFrom")}</th>
              <th scope="col">{t("thTo")}</th>
              <th scope="col">{t("thVerb")}</th>
              <th scope="col">{t("thDirection")}</th>
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
        {t("neighborhoodSummary", { nodes: data.node_count, edges: data.edge_count, depth: data.depth })}
      </p>
    </Panel>
  );
}

export default async function GraphNodeDetailPage({ params }: { params: Promise<{ kind: string; slug: string }> }) {
  const { kind, slug } = await params;

  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(`/graph/nodes/${kind}/${slug}`)}`);

  const t = await getTranslations("graph");

  const [nodeResult, edgesResult, neighborhoodResult] = await Promise.all([
    serverFetch<{ node: GraphNode; verb: string; direction: string; edges: GraphLink[]; outgoing_count: number; incoming_count: number; verbs_here: string[] }>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}`),
    serverFetch<{ edges: GraphLink[] }>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}?direction=both`),
    serverFetch<GraphNeighborhood>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}/neighborhood`),
  ]);

  if (!nodeResult.ok) {
    if (nodeResult.status === 404 || nodeResult.error.code === "no_such_node") notFound();
    return (
      <WorldUnavailable
        detail={nodeResult.error.message}
        message={t("nodeUnavailableMessage")}
        title={t("nodeUnavailableTitle", { kind, slug })}
      />
    );
  }

  const nodeData = nodeResult.data;
  const edgesData = edgesResult.ok ? edgesResult.data : { edges: [] };
  const neighborhoodData = neighborhoodResult.ok ? neighborhoodResult.data : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{
          href: `/graph/nodes/${kind}`,
          label: t("nodesTitle", { kind: kind.charAt(0).toUpperCase() + kind.slice(1) }),
        }}
        eyebrow={t("nodeEyebrow", {
          kind,
          out: nodeData.outgoing_count,
          in: nodeData.incoming_count,
        })}
        lede={
          nodeData.verbs_here.length
            ? t("verbsHere", { verbs: nodeData.verbs_here.join(", ") })
            : t("noEdgesHere")
        }
        title={`${kind.charAt(0).toUpperCase() + kind.slice(1)}: ${slug}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("kindTitle")}>
            {kind}
          </span>
          <span className="chip mono" title={t("publicSlug")}>
            {slug}
          </span>
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

      <Panel title={t("nodePanelTitle")}>
        <dl className="world-kv">
          <div className="world-kv__row">
            <dt>{t("kvKind")}</dt>
            <dd className="mono">{kind}</dd>
          </div>
          <div className="world-kv__row">
            <dt>{t("kvSlug")}</dt>
            <dd className="mono">{slug}</dd>
          </div>
          <div className="world-kv__row">
            <dt>{t("kvLabel")}</dt>
            <dd className="mono" data-testid="graph-node-label">
              {nodeData.node.label}
            </dd>
          </div>
          <div className="world-kv__row">
            <dt>{t("kvPath")}</dt>
            <dd className="mono">{nodeData.node.path}</dd>
          </div>
          <div className="world-kv__row">
            <dt>{t("kvDataOrigin")}</dt>
            <dd className="mono">{nodeData.node.data_origin}</dd>
          </div>
          <div className="world-kv__row">
            <dt>{t("kvDemoData")}</dt>
            <dd className="mono">{String(nodeData.node.is_demo_data)}</dd>
          </div>
        </dl>
        <p className="muted world-section-note">
          {t("canonicalPath")} <Link className="world-link" href={nodeData.node.path}>{nodeData.node.path}</Link>
        </p>
      </Panel>

      <EdgesPanel links={edgesData.edges} verb="" direction="both" t={t} />

      {neighborhoodData && <NeighborhoodPanel data={neighborhoodData} t={t} />}

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {t("graphProvenance")}
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {kind}</span>
        <span className="chip mono">slug: {slug}</span>
      </p>
    </div>
  );
}