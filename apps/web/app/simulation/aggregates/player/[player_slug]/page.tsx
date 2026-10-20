import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimAggPlayerAggregate } from "@/lib/types";

import "../../../../../styles/tactics.css";
import "../../../../../styles/simulate.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("simulationAggregates");
  return {
    title: t("playerMetaTitle"),
    description: t("playerMetaDescription"),
    robots: { index: false, follow: false },
  };
}

export default async function PlayerAggregatePage({ params }: { params: Promise<{ player_slug: string }> }) {
  const { player_slug } = await params;
  const tw = await getTranslations("world");
  const t = await getTranslations("simulationAggregates");

  const user = await currentUser();
  if (!user) redirect(`/login?next=%2Fsimulation%2Faggregates%2Fplayer%2F${encodeURIComponent(player_slug)}`);

  const result = await serverFetch<SimAggPlayerAggregate>(`/simulation/aggregates/player/${encodeURIComponent(player_slug)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return (
      <WorldUnavailable
        detail={result.error.message}
        message={t("playerUnavailableDetail")}
        title={t("playerMetaTitle")}
      />
    );
  }

  const aggregate = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulation/aggregates", label: t("backLabel") }}
        eyebrow={t("playerEyebrow", {
          careers: aggregate.careers.length,
          fixtures: aggregate.fixtures_played,
          goals: aggregate.totals.goals,
        })}
        lede={t("playerLede")}
        title={aggregate.player.name}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("playerSlugTitle")}>
            {aggregate.player.slug}
          </span>
          <span className="chip mono" title={t("positionTitle")}>
            {aggregate.player.position ?? "—"}
          </span>
          <span className="chip num">{t("fixturesChip", { count: aggregate.fixtures_played })}</span>
          <span className="chip num">{t("goalsChip", { count: aggregate.totals.goals })}</span>
          <span className="chip mono" data-player-slug>{aggregate.player.slug}</span>
          <span className="chip mono" data-player-name>{aggregate.player.name}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: `${aggregate.player.name} — ${t("playerMetaTitle")}`,
          url: absolute(`/simulation/aggregates/player/${player_slug}`),
          license: t("jsonLdLicense"),
          isAccessibleForFree: false,
        }}
      />

      <div className="tac-boards">
        <Panel
          eyebrow={t("careersEyebrow", { count: aggregate.careers.length })}
          title={t("careersTitle")}
          data-testid="agg-careers"
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thCareer")}</th>
                  <th scope="col">{t("thClub")}</th>
                  <th scope="col">{t("thSlug")}</th>
                </tr>
              </thead>
              <tbody>
                {aggregate.careers.map((career) => (
                  <tr key={career.id}>
                    <td className="mono">{career.slug}</td>
                    <td className="mono">{career.club_name} ({career.club_short})</td>
                    <td className="mono">{career.slug}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {aggregate.career_notice !== "" && (
            <p className="muted world-section-note" data-testid="agg-career-notice">
              {aggregate.career_notice}
            </p>
          )}
        </Panel>

        <Panel
          eyebrow={t("playerTotalsEyebrow")}
          title={t("playerTotalsTitle")}
          data-testid="player-totals"
        >
          <div className="grid grid-3">
            <div className="stack-sm">
              <dt className="muted">{t("labelTotalEvents")}</dt>
              <dd className="num mono">{aggregate.totals.events}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelGoals")}</dt>
              <dd className="num mono">{aggregate.totals.goals}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelExpectedGoals")}</dt>
              <dd className="num mono">{aggregate.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelAttempts")}</dt>
              <dd className="num mono">{aggregate.totals.attempts}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelYellowCards")}</dt>
              <dd className="num mono">{aggregate.totals.yellow_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelRedCards")}</dt>
              <dd className="num mono">{aggregate.totals.red_cards}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelInjuries")}</dt>
              <dd className="num mono">{aggregate.totals.injuries}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelExpectedGoals")}</dt>
              <dd className="num mono">{aggregate.totals.expected_goals.toFixed(3)}</dd>
            </div>
            <div className="stack-sm">
              <dt className="muted">{t("labelFixturesPlayed")}</dt>
              <dd className="num mono">{aggregate.fixtures_played}</dd>
            </div>
          </div>
          <p className="tac-formula">{aggregate.formula}</p>
          <p className="tac-formula">{aggregate.consistency_formula}</p>
          <p className="tac-formula">{aggregate.attribution_formula}</p>
          <p className="notice notice--warn">{aggregate.disclaimer}</p>
        </Panel>

        <Panel
          eyebrow={t("consistencyEyebrow", { traced: aggregate.fixtures_traced, untraced: aggregate.fixtures_untraced })}
          title={t("consistencyTitle")}
        >
          <p className="muted">{aggregate.consistency}</p>
        </Panel>

        <Panel
          eyebrow={t("byTypeEyebrow", { events: aggregate.totals.events, players: aggregate.players_with_events })}
          title={t("byTypeTitle")}
          data-testid="agg-by-type"
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
                {Object.entries(aggregate.by_type).map(([type, entry]) => (
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
            ambiguous: aggregate.unattributed.events.ambiguous,
            unnamed: aggregate.unattributed.events.unnamed,
          })}
          title={t("unattributedTitle")}
          data-testid="agg-unattributed"
        >
          {aggregate.unattributed.ambiguous_names.length > 0 && (
            <p className="muted world-section-note">
              {t("ambiguousNames", { names: aggregate.unattributed.ambiguous_names.join(", ") })}
            </p>
          )}
          {aggregate.unattributed.unnamed_names.length > 0 && (
            <p className="muted world-section-note">
              {t("unnamedNames", { names: aggregate.unattributed.unnamed_names.join(", ") })}
            </p>
          )}
          {aggregate.unattributed.ambiguous_names.length === 0 && aggregate.unattributed.unnamed_names.length === 0 && (
            <p className="muted">{t("noUnattributed")}</p>
          )}
        </Panel>

        <Panel
          eyebrow={t("byTypeEyebrow", { events: aggregate.totals.events, players: aggregate.players_with_events })}
          title={tw("sectionPlayersLabel")}
          data-testid="agg-players"
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
                {aggregate.players.map((player) => (
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
          {aggregate.truncated && (
            <p className="muted world-section-note">
              {t("showingPlayers", { shown: aggregate.players_shown, total: aggregate.players_with_events })}
            </p>
          )}
        </Panel>

        <Provenance
          provenance={{ data_origin: aggregate.data_origin, is_demo_data: aggregate.is_demo_data, disclaimer: aggregate.disclaimer }}
          extra={<span className="chip">{aggregate.scope}</span>}
        />
      </div>
    </div>
  );
}
