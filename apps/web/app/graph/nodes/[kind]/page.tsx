import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import type { GraphRules } from "@/lib/types";

import "../../../../styles/tactics.css";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ kind: string }> }): Promise<Metadata> {
  const { kind } = await params;
  const tg = await getTranslations("graph");
  const label = kind.charAt(0).toUpperCase() + kind.slice(1);
  return {
    title: tg("nodesTitle", { kind: label }),
    description: tg("kindMetaDescription", { kind }),
    robots: { index: false, follow: false },
  };
}

function KindNodes({ kind, rules }: { kind: string; rules: GraphRules }) {
  const t = useTranslations("common");
  const tg = useTranslations("graph");
  const label = kind.charAt(0).toUpperCase() + kind.slice(1);
  return (
    <Panel title={tg("nodesTitle", { kind: label })} eyebrow={tg("kindEyebrow", { kind })}>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        {tg("kindNote", { depth: rules.max_depth })}
      </p>
      <form action={`/graph/nodes/${kind}`} method="GET" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <label htmlFor="slug" className="muted" style={{ fontSize: "0.85rem" }}>
          {tg("slugLabel")}
        </label>
        <input
          id="slug"
          name="slug"
          type="text"
          placeholder={tg("slugPlaceholder")}
          style={{ minWidth: "180px" }}
        />
        <button className="btn btn--primary" type="submit">{t("open")}</button>
      </form>
      <p className="muted world-section-note">{tg("kindOr")}</p>
    </Panel>
  );
}

function NodeListing({ kind, rules }: { kind: string; rules: GraphRules }) {
  const tg = useTranslations("graph");
  const label = kind.charAt(0).toUpperCase() + kind.slice(1);
  return (
    <Panel title={tg("listingTitle", { kind: label })} eyebrow={tg("kindEyebrow", { kind })}>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        {tg("listingNote")}
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

  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(`/graph/nodes/${kind}`)}`);

  const tg = await getTranslations("graph");
  const rulesResult = await serverFetch<GraphRules>("/graph/rules");
  if (!rulesResult.ok) {
    return (
      <WorldUnavailable
        detail={rulesResult.error.message}
        message={tg("rulesUnavailableMessage")}
        title={tg("unavailableTitle")}
      />
    );
  }
  const rules = rulesResult.data;

  if (!rules.node_kinds.includes(kind)) {
    notFound();
  }

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/graph", label: tg("unavailableTitle") }}
        eyebrow={tg("nodesTitle", { kind: kind.charAt(0).toUpperCase() + kind.slice(1) })}
        lede={tg("kindLede")}
        title={tg("nodesTitle", { kind: kind.charAt(0).toUpperCase() + kind.slice(1) })}
      />

      <KindNodes kind={kind} rules={rules} />
      <NodeListing kind={kind} rules={rules} />

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {tg("provenanceNote")}
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">kind: {kind}</span>
      </p>
    </div>
  );
}

export default GraphNodesKindPage;