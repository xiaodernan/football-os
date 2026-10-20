import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { EntityLink, JsonLd, KeyValueGrid, MatchRow, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { CompetitionDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

async function load(slug: string, season?: string) {
  return readWorld<CompetitionDetail>(`/world/competitions/${encodeURIComponent(slug)}`, season ? { season } : undefined);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const competition = result.ok ? result.data.competition : null;
  const t = await getTranslations("worldCompetition");
  const name = competition?.name ?? slug.replace(/-/g, " ");
  return pageMetadata({
    title: `${name} — ${t("metaTitleKind", {
      kind: competition?.kind === "league" ? t("kindLeague") : t("kindCup"),
    })}`,
    description: competition
      ? `${competition.summary.slice(0, 220)}`
      : t("metaDescriptionFallback"),
    path: `/competition/${slug}`,
  });
}

export default async function CompetitionDetailPage({ params, searchParams }: Props) {
  const [{ slug }, rawQuery] = await Promise.all([params, searchParams]);
  const query = cleanParams(rawQuery);
  const result = await load(slug, query.season);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { competition, standings, teams, fixtures, completed, scheduled, format_note: formatNote, season } = result.data;
  const t = await getTranslations("worldCompetition");
  const path = `/competition/${competition.slug}`;
  const isLeague = standings.length > 0;
  const entrants = teams.filter((team): team is NonNullable<typeof team> => Boolean(team));

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/competitions", label: t("backLabel") }}
        eyebrow={t("eyebrow", {
          kind: competition.kind,
          tier: competition.tier,
          region: competition.region,
        })}
        lede={competition.summary}
        provenance={result.data}
        title={competition.name}
      >
        <div className="tag-list" style={{ marginTop: "0.75rem" }}>
          <span className="chip">{competition.country}</span>
          <span className="chip">{season}</span>
          <span className="chip num">{t("chipPlayed", { count: completed })}</span>
          <span className="chip num">{t("chipScheduled", { count: scheduled })}</span>
          <span className="chip num">{t("chipClubs", { count: teams.length })}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsOrganization",
          name: competition.name,
          description: competition.summary,
          url: absolute(path),
          sport: "Association Football",
          member: entrants.slice(0, 40).map((team) => ({ "@type": "SportsTeam", name: team.name, url: absolute(team.path) })),
        }}
      />

      <Panel eyebrow={t("claimEyebrow")} title={t("claimTitle")}>
        <div className="stack">
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {formatNote}
          </p>
          <KeyValueGrid
            rows={[
              [t("rowFormat"), competition.kind],
              [t("rowTier"), competition.tier],
              [t("rowRegion"), competition.region],
              [t("rowCountry"), competition.country],
              [t("rowSeasonShown"), season],
              [t("rowRowsOnPage"), `${completed + scheduled} fixtures · ${standings.length} table rows`],
            ]}
          />
        </div>
      </Panel>

      <Panel
        eyebrow={t("tableEyebrow", { count: standings.length })}
        title={t("tableTitle")}
      >
        {isLeague ? (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">#</th>
                  <th scope="col">{t("thClub")}</th>
                  <th scope="col">{t("thP")}</th>
                  <th scope="col">{t("thW")}</th>
                  <th scope="col">{t("thD")}</th>
                  <th scope="col">{t("thL")}</th>
                  <th scope="col">{t("thGf")}</th>
                  <th scope="col">{t("thGa")}</th>
                  <th scope="col">{t("thGd")}</th>
                  <th scope="col">{t("thPts")}</th>
                </tr>
              </thead>
              <tbody>
                {standings.map((row) => (
                  <tr key={row.team_id}>
                    <td className="num muted">{row.position}</td>
                    <td>
                      <EntityLink href={row.team?.path} label={row.name} />
                    </td>
                    <td className="num">{row.played}</td>
                    <td className="num">{row.won}</td>
                    <td className="num">{row.drawn}</td>
                    <td className="num">{row.lost}</td>
                    <td className="num">{row.goals_for}</td>
                    <td className="num">{row.goals_against}</td>
                    <td className="num">{row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}</td>
                    <td className="num" style={{ fontWeight: 700 }}>
                      {row.points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="stack-sm">
            <span className="unavailable">{t("noLeagueTable")}</span>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              {t("cupNote", { kind: competition.kind, count: fixtures.length })}
            </p>
          </div>
        )}
      </Panel>

      <Panel
        eyebrow={t("entrantsEyebrow", { count: entrants.length })}
        title={t("entrantsTitle")}
      >
        <div className="tag-list">
          {entrants.map((team) => (
            <Link className="chip" href={team.path} key={team.id}>
              {team.name}
            </Link>
          ))}
        </div>
      </Panel>

      <Panel
        eyebrow={t("fixturesEyebrow", { count: fixtures.length, season })}
        title={t("fixturesTitle")}
      >
        <ul className="world-list">
          {fixtures.map((match) => (
            <MatchRow match={match} key={match.id} />
          ))}
        </ul>
      </Panel>

      <Provenance provenance={result.data} />
    </div>
  );
}
