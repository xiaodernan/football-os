import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import type { GraphNeighborhood } from "@/lib/types";

import "../../../../../../styles/tactics.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("graph");
  return {
    title: t("hoodMetaTitle"),
    description: t("hoodMetaDescription"),
    robots: { index: false, follow: false },
  };
}

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

  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(`/graph/nodes/${kind}/${slug}/neighborhood`)}`);

  const t = await getTranslations("graph");

  const result = await serverFetch<GraphNeighborhood>(`/graph/nodes/${encodeURIComponent(kind)}/${encodeURIComponent(slug)}/neighborhood`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "no_such_node") notFound();
    return (
      <WorldUnavailable
        detail={result.error.message}
        message={t("hoodUnavailableMessage")}
        title={t("hoodUnavailableTitle")}
      />
    );
  }

  const data = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: `/graph/nodes/${kind}/${slug}`, label: t("backLabel", { kind, slug }) }}
        eyebrow={t("hoodEyebrow", { depth: data.depth, nodes: data.node_count, edges: data.edge_count })}
        lede={t("hoodLede")}
        title={t("hoodTitle", { kind, slug })}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("walkDepth")}>
            {t("depthChip", { depth: data.depth })}
          </span>
          <span className="chip num">{t("nodesChip", { count: data.node_count })}</span>
          <span className="chip num">{t("edgesChip", { count: data.edge_count })}</span>
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

      <Panel
        title={t("neighborhoodTitle", { depth: data.depth })}
        eyebrow={t("neighborhoodEyebrow", { nodes: data.node_count, edges: data.edge_count })}
      >
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {t("neighborhoodNote", { depth: data.depth, nodes: data.node_count, edges: data.edge_count })}
        </p>
        <div className="world-tablewrap">
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
                <EdgeRow key={idx} edge={edge} idx={idx} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted world-section-note">
          {t("neighborhoodSummary", { nodes: data.node_count, edges: data.edge_count, depth: data.depth })}
        </p>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {t("graphProvenance")}
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {data.node.kind}</span>
        <span className="chip mono">slug: {data.node.slug}</span>
        <span className="chip mono">depth: {data.depth}</span>
      </p>
    </div>
  );
}