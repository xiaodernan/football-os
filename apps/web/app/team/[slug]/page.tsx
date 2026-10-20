import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel, ReasonList } from "@/components/ui";
import {
  CompetitionLink,
  Crest,
  EntityLink,
  JsonLd,
  KeyValueGrid,
  MatchRow,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatDay,
} from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { brandColor, readWorld } from "@/lib/world";
import type { TeamDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<TeamDetail>(`/world/teams/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const team = result.ok ? result.data.team : null;
  const name = team?.name ?? slug.replace(/-/g, " ");
  const t = await getTranslations("worldTeam");
  return pageMetadata({
    title: `${name}${t("metaTitleSuffix")}`,
    description: team
      ? `${team.summary.slice(0, 220)}${t("metaDescriptionSuffix")}`
      : t("metaDescriptionFallback"),
    path: `/team/${slug}`,
  });
}

export default async function TeamDetailPage({ params }: Props) {
  const { slug } = await params;
  const tc = await getTranslations("common");
  const t = await getTranslations("worldTeam");
  const tw = await getTranslations("world");
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { team, squad, fixtures, recent_stat_lines: recentLines, squad_notes: squadNotes } = result.data;
  const path = `/team/${team.slug}`;
  const played = fixtures.filter((match) => match.status === "completed");
  const upcoming = fixtures.filter((match) => match.status !== "completed");
  const lineGroups = recentLines.reduce<Record<string, typeof recentLines>>((groups, line) => {
    const key = line.match_slug ?? "unknown";
    (groups[key] ??= []).push(line);
    return groups;
  }, {});

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/teams", label: t("backLabel") }}
        eyebrow={t("eyebrow", { world: tw("title"), nation: team.nation })}
        lede={team.summary}
        provenance={result.data}
        title={team.name}
      >
        <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <Crest color={brandColor(team.brand_color)} name={team.short_name || team.name} />
          <div className="tag-list">
            <span className="chip mono">{team.short_name}</span>
            <span className="chip">{team.formation}</span>
            <span className="chip num">{team.overall} OVR</span>
            <span className="chip num">{t("squadChip", { count: team.squad_size })}</span>
            <span className="chip">
              <CompetitionLink competition={team.competition} />
            </span>
            <span className="chip">{team.season}</span>
          </div>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsTeam",
          name: team.name,
          description: team.summary,
          url: absolute(path),
          sport: "Association Football",
          address: { "@type": "PostalAddress", addressLocality: team.city, addressCountry: team.nation },
          ...(team.competition
            ? { organizer: { "@type": "SportsOrganization", name: team.competition.name, url: absolute(team.competition.path) } }
            : {}),
          athlete: squad.slice(0, 25).map((player) => ({ "@type": "Person", name: player.name, url: absolute(player.path) })),
        }}
      />

      <div className="grid grid-2">
        <Panel eyebrow={t("identityEyebrow")} title={t("identityTitle")}>
          <KeyValueGrid
            rows={[
              [t("rowCity"), team.city],
              [t("rowGround"), team.stadium],
              [t("rowCapacity"), team.capacity.toLocaleString("en-GB")],
              [t("rowManager"), team.manager_name],
              [t("rowShape"), <span className="mono" key="shape">{team.formation}</span>],
              [t("rowSeason"), team.season],
              [
                t("rowLeague"),
                team.competition ? (
                  <Link className="world-link" href={team.competition.path}>
                    {team.competition.name}
                  </Link>
                ) : (
                  <span className="unavailable">{t("noLeague")}</span>
                ),
              ],
              [
                t("rowMeanOverall"),
                <span key="mean-overall" title={t("meanOverallTitle")}>{team.overall}</span>,
              ],
            ]}
          />
        </Panel>

        <Panel eyebrow={t("derivationEyebrow")} title={t("derivationTitle")}>
          <div className="stack">
            <ReasonList items={squadNotes} title={t("derivationReasonTitle")} />
            <p className="muted world-section-note">
              {t("derivationNote", { played: played.length, upcoming: upcoming.length })}
            </p>
          </div>
        </Panel>
      </div>

      <Panel eyebrow={t("squadEyebrow", { count: squad.length })} title={t("squadTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thPos")}</th>
                <th scope="col">{tc("personName")}</th>
                <th scope="col">{t("thAge")}</th>
                <th scope="col">{t("thNation")}</th>
                <th scope="col">{t("thFoot")}</th>
                <th scope="col">{t("thOvr")}</th>
                <th scope="col">{t("thPot")}</th>
                <th scope="col">{t("thGoals")}</th>
                <th scope="col">{t("thAssists")}</th>
                <th scope="col">{t("thMinutes")}</th>
                <th scope="col">{t("thRating")}</th>
              </tr>
            </thead>
            <tbody>
              {squad.map((player) => (
                <tr key={player.id}>
                  <td>
                    <span className="world-pos">{player.position}</span>
                  </td>
                  <td>
                    <EntityLink href={player.path} label={player.name} />
                  </td>
                  <td className="num">{player.age}</td>
                  <td className="muted">{player.nation}</td>
                  <td className="muted">{player.preferred_foot}</td>
                  <td className="num">{player.overall}</td>
                  <td className="num muted">{player.potential}</td>
                  <td className="num">{player.goals}</td>
                  <td className="num">{player.assists}</td>
                  <td className="num muted">{player.minutes}</td>
                  <td className="num">{player.rating.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
          {t("squadNote")}
        </p>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={t("playedEyebrow", { count: played.length })} title={t("playedTitle")}>
          {played.length > 0 ? (
            <ul className="world-list">
              {played.slice(0, 12).map((match) => (
                <MatchRow match={match} key={match.id} />
              ))}
            </ul>
          ) : (
            <span className="unavailable">{t("noCompletedFixture")}</span>
          )}
        </Panel>
        <Panel eyebrow={t("upcomingEyebrow", { count: upcoming.length })} title={t("upcomingTitle")}>
          {upcoming.length > 0 ? (
            <ul className="world-list">
              {upcoming.slice(0, 12).map((match) => (
                <MatchRow match={match} key={match.id} />
              ))}
            </ul>
          ) : (
            <span className="unavailable">{t("nothingScheduled")}</span>
          )}
        </Panel>
      </div>

      {Object.keys(lineGroups).length > 0 && (
        <Panel eyebrow={t("linesEyebrow")} title={t("linesTitle")}>
          <div className="stack">
            {Object.entries(lineGroups)
              .slice(0, 3)
              .map(([matchSlug, lines]) => (
                <div className="stack-sm" key={matchSlug}>
                  <p className="eyebrow">
                    <Link className="world-link" href={lines[0]?.match_path ?? "/world/matches"}>
                      {t("linesLink", {
                        day: formatDay(lines[0]?.kickoff_at),
                        competition: lines[0]?.competition?.name ?? t("matchFallback"),
                        count: lines.length,
                      })}
                    </Link>
                  </p>
                  <div className="world-tablewrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th scope="col">{t("thPlayer")}</th>
                          <th scope="col">{t("thRole")}</th>
                          <th scope="col">{t("thMin")}</th>
                          <th scope="col">{t("thG")}</th>
                          <th scope="col">{t("thA")}</th>
                          <th scope="col">{t("thShots")}</th>
                          <th scope="col">{t("thPasses")}</th>
                          <th scope="col">{t("thTkl")}</th>
                          <th scope="col">{t("thRating")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lines.map((line) => (
                          <tr key={line.id}>
                            <td>
                              <EntityLink href={line.player?.path} label={line.player?.name} />
                            </td>
                            <td className="muted">{line.role}</td>
                            <td className="num">{line.minutes}</td>
                            <td className="num">{line.goals}</td>
                            <td className="num">{line.assists}</td>
                            <td className="num">{line.shots}</td>
                            <td className="num muted">
                              {line.passes_accurate}/{line.passes}
                            </td>
                            <td className="num">{line.tackles}</td>
                            <td className="num">{line.rating.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
          </div>
        </Panel>
      )}

      <Provenance provenance={result.data} />
    </div>
  );
}
