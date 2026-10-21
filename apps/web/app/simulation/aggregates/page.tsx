import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import { readWorld } from "@/lib/world";
import type { CompetitionList, SimAggLeagueRules } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("simulationAggregates");
  return {
    title: t("indexMetaTitle"),
    description: t("indexMetaDescription"),
    robots: { index: false, follow: false },
  };
}

/**
 * The index the two aggregate doors' back links promised: `/simulation/aggregates/league` and
 * `/simulation/aggregates` were both dead until this page existed — the walk's console gate
 * caught the 404s. One ledger per competition, reached through the world's own competition
 * list; the player door is explained rather than enumerated (the world has hundreds of players,
 * and a list nobody paged through is not an index).
 */
export default async function AggregatesIndexPage() {
  const user = await currentUser();

  const t = await getTranslations("simulationAggregates");
  if (!user) redirect("/login?next=%2Fsimulation%2Faggregates");

  const [comps, rules] = await Promise.all([
    readWorld<CompetitionList>("/world/competitions", { page_size: 50 }),
    serverFetch<SimAggLeagueRules>("/simulation/aggregates/rules"),
  ]);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulate", label: t("backSimulation") }}
        eyebrow={t("indexEyebrow")}
        title={t("indexTitle")}
        lede={t("indexLede")}
      />

      <Panel eyebrow={t("leagueLedgersEyebrow")} title={t("leagueLedgersTitle")}>
        {comps.ok ? (
          <div className="stack-sm">
            <ul className="list">
              {comps.data.items.map((competition) => (
                <li className="list__item" key={competition.slug}>
                  <Link className="h3" href={`/simulation/aggregates/league/${competition.slug}`}>
                    {competition.name}
                  </Link>
                  <span className="muted" style={{ fontSize: "0.82rem" }}>
                    {t("teamsChip", { kind: competition.kind, teams: competition.team_count })} · {competition.season}
                  </span>
                </li>
              ))}
            </ul>
            <p className="muted world-section-note">
              {t("leagueLedgersNote")}
            </p>
          </div>
        ) : (
          <WorldUnavailable message={comps.message} title={t("leagueLedgersUnavailableTitle")} />
        )}
      </Panel>

      <Panel eyebrow={t("playerAggregatesEyebrow")} title={t("playerAggregatesTitle")}>
        <div className="stack-sm">
          <p className="muted">
            {t("playerAggregatesNote")}
          </p>
          <Link className="btn btn--sm" href="/world/players">
            {t("browsePlayers")}
          </Link>
        </div>
      </Panel>

      {rules.ok && (
        <Panel eyebrow={t("vocabularyEyebrow")} title={t("vocabularyTitle")}>
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>{t("nodeKinds")}</dt>
              <dd className="mono">{rules.data.node_kinds.join(", ")}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("edgeVerbs")}</dt>
              <dd className="mono">{rules.data.edge_verbs.join(", ")}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.7rem" }}>
            {t("vocabularyNote")}
          </p>
        </Panel>
      )}
    </div>
  );
}
