import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { GraphRules } from "@/lib/types";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("graph");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/graph") },
  };
}

function RulesPanel({ rules, t }: { rules: GraphRules; t: (key: string, values?: Record<string, string | number | Date>) => string }) {
  return (
    <Panel
      title={t("rulesTitle")}
      eyebrow={t("rulesEyebrow", {
        kinds: rules.node_kinds.length,
        verbs: rules.edge_verbs.length,
        depth: rules.max_depth,
        edges: rules.max_edges,
        nodes: rules.max_nodes,
      })}
    >
      <div className="stack">
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {t("rulesNote")}
        </p>

        <div className="row wrap" style={{ gap: "0.5rem" }}>
          <Panel className="grow" title={t("nodeKindsTitle")} eyebrow={rules.node_kinds.length.toString()}>
            <ul className="stack-sm" data-testid="graph-kinds" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {rules.node_kinds.map((kind) => (
                <li key={kind}>
                  <Link className="world-link" href={`/graph/nodes/${kind}`}>
                    {kind}
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel className="grow" title={t("edgeVerbsTitle")} eyebrow={rules.edge_verbs.length.toString()}>
            <ul className="stack-sm" data-testid="graph-verbs" style={{ margin: 0, paddingLeft: "1.1rem" }}>
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

        <Panel title={t("ceilingsTitle")} eyebrow={rules.routes.length.toString()}>
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            <li><span className="mono">max_depth</span> = {rules.max_depth}</li>
            <li><span className="mono">max_edges</span> = {rules.max_edges}</li>
            <li><span className="mono">max_nodes</span> = {rules.max_nodes}</li>
          </ul>
        </Panel>

        {rules.spec_verbs_declined && Object.keys(rules.spec_verbs_declined).length > 0 && (
          <Panel title={t("declinedVerbsTitle")} eyebrow={Object.keys(rules.spec_verbs_declined).length.toString()}>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {t("declinedVerbsNote")}
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

        <Panel title={t("declinedClausesTitle")} eyebrow={rules.clauses_declined.toString()}>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {t("declinedClausesNote")}
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

        <Panel title={t("privateTablesTitle")} eyebrow={rules.private_tables_excluded.toString()}>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {t("privateTablesNote")}
          </p>
        </Panel>
      </div>
    </Panel>
  );
}

async function GraphPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fgraph");

  const tn = await getTranslations("nav");
  const t = await getTranslations("graph");
  const rulesResult = await serverFetch<GraphRules>("/graph/rules");
  if (!rulesResult.ok) {
    return (
      <WorldUnavailable
        detail={rulesResult.error.message}
        message={t("rulesUnavailableMessage")}
        title={t("unavailableTitle")}
      />
    );
  }

  const rules = rulesResult.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={t("eyebrow", {
          kinds: rules.node_kinds.length,
          verbs: rules.edge_verbs.length,
          depth: rules.max_depth,
        })}
        lede={t("lede")}
        title={t("title")}
      />

      <RulesPanel rules={rules} t={t} />

      <Panel title={t("browseTitle")} eyebrow={t("browseEyebrow")}>
        <div className="row wrap" style={{ gap: "0.5rem" }}>
          {rules.node_kinds.map((kind) => (
            <Link key={kind} className="btn" href={`/graph/nodes/${kind}`}>
              {kind} <span className="mono">→</span>
            </Link>
          ))}
        </div>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {t("provenanceNote")}
        <span className="chip mono">data_origin: synthetic</span>
        <span className="chip mono">is_demo_data: true</span>
        <span className="chip mono">{t("verbsChip", { verbs: rules.edge_verbs.length })}</span>
        <span className="chip mono">depth ≤ {rules.max_depth}</span>
        <span className="chip mono">edges ≤ {rules.max_edges}</span>
        <span className="chip mono">nodes ≤ {rules.max_nodes}</span>
        <span className="chip">{t("privateTablesChip", { count: rules.private_tables_excluded })}</span>
      </p>
    </div>
  );
}

export default GraphPage;