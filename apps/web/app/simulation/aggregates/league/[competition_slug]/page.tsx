import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimAggLeagueLedger } from "@/lib/types";

import "../../../../../styles/tactics.css";
import "../../../../../styles/simulate.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("simulationAggregates");
  return {
    title: t("leagueMetaTitle"),
    description: t("leagueMetaDescription"),
    robots: { index: false, follow: false },
  };
}

export default async function LeagueLedgerPage({ params }: { params: Promise<{ competition_slug: string }> }) {
  const { competition_slug } = await params;
  const t = await getTranslations("simulationAggregates");

  const user = await currentUser();
  if (!user) redirect(`/login?next=%2Fsimulation%2Faggregates%2Fleague%2F${encodeURIComponent(competition_slug)}`);

  const ledgerResult = await serverFetch<SimAggLeagueLedger>(`/simulation/aggregates/league/${encodeURIComponent(competition_slug)}`);
  if (!ledgerResult.ok) {
    if (ledgerResult.status === 404 || ledgerResult.error.code === "not_found") notFound();
    return (
      <WorldUnavailable
        detail={ledgerResult.error.message}
        message={t("leagueUnavailableDetail")}
        title={t("leagueMetaTitle")}
      />
    );
  }

  const ledger = ledgerResult.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulation/aggregates", label: t("backLabel") }}
        eyebrow={t("leagueEyebrow", {
          fixtures: ledger.fixtures_played,
          players: ledger.players_with_events,
          goals: ledger.totals.goals,
        })}
        lede={t("leagueLede")}
        title={ledger.competition.name}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("competitionSlugTitle")} data-competition-slug>
            {ledger.competition.slug}
          </span>
          <span className="chip num">
            {t("leagueTracedPlayed", { traced: ledger.fixtures_traced, played: ledger.fixtures_played })}
          </span>
          <span className="chip num">{t("leaguePlayersWithEvents", { players: ledger.players_with_events })}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: `${ledger.competition.name} — ${t("leagueMetaTitle")}`,
          url: absolute(`/simulation/aggregates/league/${ledger.competition.slug}`),
          license: t("jsonLdLicense"),
          isAccessibleForFree: false,
        }}
      />

      <div className="tac-boards">
        <Panel eyebrow={t("leagueTotalsEyebrow")} title={t("leagueTotalsTitle")} data-testid="league-totals">
          <div className="grid grid-3">
            <div className="stack-sm">
              <dt className="muted">{t("labelTotalEvents")}</dt>
              <dd className="num mono">{ledger.totals.events}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelGoals")}</dt>
              <dd className="num mono">{ledger.totals.goals}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelExpectedGoals")}</dt>
              <dd className="num mono">{ledger.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelAttempts")}</dt>
              <dd className="num mono">{ledger.totals.attempts}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelYellowCards")}</dt>
              <dd className="num mono">{ledger.totals.yellow_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelRedCards")}</dt>
              <dd className="num mono">{ledger.totals.red_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelInjuries")}</dt>
              <dd className="num mono">{ledger.totals.injuries}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelExpectedGoals")}</dt>
              <dd className="num mono">{ledger.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelFixturesTraced")}</dt>
              <dd className="num mono">{ledger.fixtures_traced} / {ledger.fixtures_played}</dd>
            </div>
          </div>
          <p className="tac-formula">{ledger.formula}</p>
          <p className="tac-formula">{ledger.consistency_formula}</p>
          <p className="tac-formula">{ledger.attribution_formula}</p>
          <p className="notice notice--warn">{ledger.disclaimer}</p>
        </Panel>

        <Panel
          eyebrow={t("consistencyEyebrow", { traced: ledger.fixtures_traced, untraced: ledger.fixtures_untraced })}
          title={t("consistencyTitle")}
          data-testid="league-consistency"
        >
          <p className="muted">{ledger.consistency}</p>
        </Panel>

        <Panel
          eyebrow={t("byTypeEyebrow", { events: ledger.totals.events, players: ledger.players_with_events })}
          title={t("byTypeTitle")}
          data-testid="league-by-type"
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thType")}</th>
                  <th scope="col">{t("thEvents")}</th>
                  <th scope="col">{t("thIdentified")}</th>
                  <th scope="col">{t("thAmbiguous")}</th>
                  <th scope="col">{t("thUnnamed")}</th>
                  <th scope="col">{t("thExpectedGoals")}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ledger.by_type).map(([type, entry]) => (
                  <tr key={type}>
                    <td className="mono">{type}</td>
                    <td className="num mono">{entry.events}</td>
                    <td className="num mono">{entry.identified}</td>
                    <td className="num mono">{entry.ambiguous}</td>
                    <td className="num mono">{entry.unnamed}</td>
                    <td className="num mono">{entry.expected_goals.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel
          eyebrow={t("unattributedEyebrow", {
            ambiguous: ledger.unattributed.events.ambiguous,
            unnamed: ledger.unattributed.events.unnamed,
          })}
          title={t("unattributedTitle")}
          data-testid="league-unattributed"
        >
          {ledger.unattributed.ambiguous_names.length > 0 && (
            <p className="muted world-section-note">
              {t("ambiguousNames", { names: ledger.unattributed.ambiguous_names.join(", ") })}
            </p>
          )}
          {ledger.unattributed.unnamed_names.length > 0 && (
            <p className="muted world-section-note">
              {t("unnamedNames", { names: ledger.unattributed.unnamed_names.join(", ") })}
            </p>
          )}
          {ledger.unattributed.ambiguous_names.length === 0 && ledger.unattributed.unnamed_names.length === 0 && (
            <p className="muted">{t("noUnattributed")}</p>
          )}
        </Panel>

        <Panel
          eyebrow={t("leagueTopPlayersEyebrow", { players: ledger.players_with_events, shown: ledger.players_shown })}
          title={t("leagueTopPlayersTitle")}
          data-testid="league-players"
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thPlayer")}</th>
                  <th scope="col">{t("thPosition")}</th>
                  <th scope="col">{t("thMatches")}</th>
                  <th scope="col">{t("thGoals")}</th>
                  <th scope="col">{t("thAttempts")}</th>
                  <th scope="col">{t("thXg")}</th>
                  <th scope="col">{t("thYellow")}</th>
                  <th scope="col">{t("thRed")}</th>
                  <th scope="col">{t("thInjuries")}</th>
                </tr>
              </thead>
              <tbody>
                {ledger.players.map((player) => (
                  <tr key={player.player_id}>
                    <td>
                      <Link className="world-link" href={player.player_path ?? "#"}>
                        {player.name}
                      </Link>
                    </td>
                    <td className="mono">{player.position}</td>
                    <td className="num mono">{player.matches_with_events}</td>
                    <td className="num mono">{player.goals}</td>
                    <td className="num mono">{player.attempts}</td>
                    <td className="num mono">{player.expected_goals.toFixed(3)}</td>
                    <td className="num mono">{player.yellow_cards}</td>
                    <td className="num mono">{player.red_cards}</td>
                    <td className="num mono">{player.injuries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ledger.truncated && (
            <p className="muted world-section-note">
              {t("showingPlayers", { shown: ledger.players_shown, total: ledger.players_with_events })}
            </p>
          )}
        </Panel>

        <Provenance
          provenance={{ data_origin: ledger.data_origin, is_demo_data: ledger.is_demo_data, disclaimer: ledger.disclaimer }}
          extra={<span className="chip">{ledger.scope}</span>}
        />
      </div>
    </div>
  );
}
