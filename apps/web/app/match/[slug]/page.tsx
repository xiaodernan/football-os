import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel, ReasonList } from "@/components/ui";
import {
  EntityLink,
  JsonLd,
  KeyValueGrid,
  OriginBadge,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatMoment,
} from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { MatchDetail, StatPair } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<MatchDetail>(`/world/matches/${encodeURIComponent(slug)}`);
}

function isPair(value: number | StatPair | Record<string, string>): value is StatPair {
  return typeof value === "object" && "home" in value && "away" in value;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const match = result.ok ? result.data.match : null;
  const t = await getTranslations("worldMatch");
  const title = match
    ? `${match.home?.name ?? t("homeFallback")} v ${match.away?.name ?? t("awayFallback")}`
    : slug.replace(/-/g, " ");
  return pageMetadata({
    title: `${title}${t("metaTitleSuffix")}`,
    description: match
      ? match.status === "completed"
        ? t("metaDescriptionPlayed", { round: match.round_label, season: match.season, summary: match.summary })
        : t("metaDescriptionScheduled", { round: match.round_label, season: match.season })
      : t("metaDescriptionFallback"),
    path: `/match/${slug}`,
  });
}

export default async function MatchDetailPage({ params }: Props) {
  const { slug } = await params;
  const t = await getTranslations("worldMatch");
  const tw = await getTranslations("world");
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { match, line_ups: lineUps, stat_lines: statLines, available, note, method, goals_check: goalsCheck } = result.data;
  const path = `/match/${match.slug}`;
  const title = `${match.home?.name ?? t("homeFallback")} v ${match.away?.name ?? t("awayFallback")}`;
  const metrics = Object.entries(match.stats).filter(
    ([key, value]) => key !== "method" && (typeof value === "number" || isPair(value)),
  ) as [string, number | StatPair][];
  const played = available && match.home_goals !== null && match.away_goals !== null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/matches", label: t("backLabel") }}
        eyebrow={t("eyebrow", {
          world: tw("title"),
          competition: match.competition?.name ?? t("fixtureFallback"),
          round: match.round_label,
        })}
        lede={match.summary}
        provenance={result.data}
        title={title}
      >
        <div className="world-scoreline" style={{ marginTop: "0.9rem" }}>
          <div className="world-scoreline__side">
            <EntityLink href={match.home?.path} label={match.home?.name} />
            <span className="muted world-section-note">{t("homeLabel")}</span>
          </div>
          <div className="world-scoreline__score">
            {played ? (
              <span className="num">
                {match.home_goals} – {match.away_goals}
              </span>
            ) : (
              <span className="unavailable">{t("noScoreYet")}</span>
            )}
            <span className="eyebrow">{played ? t("fullTime") : match.status}</span>
          </div>
          <div className="world-scoreline__side world-scoreline__side--away">
            <EntityLink href={match.away?.path} label={match.away?.name} />
            <span className="muted world-section-note">{t("awayLabel")}</span>
          </div>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsEvent",
          name: title,
          description: match.summary,
          url: absolute(path),
          startDate: match.kickoff_at,
          eventStatus: played ? "https://schema.org/EventCompleted" : "https://schema.org/EventScheduled",
          eventAttendance: typeof match.stats.attendance === "number" ? match.stats.attendance : undefined,
          location: { "@type": "SportsLocation", name: match.venue.name, address: match.venue.city },
          homeTeam: match.home ? { "@type": "SportsTeam", name: match.home.name, url: absolute(match.home.path) } : undefined,
          awayTeam: match.away ? { "@type": "SportsTeam", name: match.away.name, url: absolute(match.away.path) } : undefined,
          organizer: match.competition
            ? { "@type": "SportsOrganization", name: match.competition.name, url: absolute(match.competition.path) }
            : undefined,
          sport: "Association Football",
        }}
      />

      {!played && (
        <div className="notice notice--warn">
          {note ?? t("noticeScheduled")} {t("noticeScheduledTail")}
        </div>
      )}

      <div className="grid grid-2">
        <Panel eyebrow={t("fixtureEyebrow")} title={t("whenWhereTitle")}>
          <KeyValueGrid
            rows={[
              [t("rowKickoff"), <span className="mono" key="kickoff">{formatMoment(match.kickoff_at)}</span>],
              [t("rowVenue"), `${match.venue.name}, ${match.venue.city}`],
              [t("rowCompetition"), match.competition ? <Link className="world-link" href={match.competition.path}>{match.competition.name}</Link> : "—"],
              [t("rowSeason"), match.season],
              [t("rowRound"), match.round_label],
              [t("rowStatus"), match.status],
              [t("rowAttendance"), typeof match.stats.attendance === "number" ? match.stats.attendance.toLocaleString("en-GB") : <span className="unavailable">{t("notRecorded")}</span>],
            ]}
          />
        </Panel>

        <Panel
          eyebrow={t("statsEyebrow")}
          title={t("statsTitle")}
          action={<OriginBadge provenance={match} />}
        >
          {metrics.length > 0 ? (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("thHome")}</th>
                    <th scope="col">{t("thMetric")}</th>
                    <th scope="col">{t("thAway")}</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(([key, value]) => (
                    <tr key={key}>
                      <td className="num" style={{ textAlign: "right" }}>
                        {isPair(value) ? (typeof value.home === "number" ? value.home.toFixed(1).replace(/\.0$/, "") : "—") : "—"}
                      </td>
                      <td className="muted center" style={{ textTransform: "capitalize" }}>
                        {key.replace(/_/g, " ")}
                      </td>
                      <td className="num">
                        {isPair(value) ? (typeof value.away === "number" ? value.away.toFixed(1).replace(/\.0$/, "") : "—") : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span className="unavailable">{t("noStats")}</span>
          )}
          {played && (
            <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.6rem" }}>
              <span className="chip" title={t("goalsInScoreTitle")}>
                {t("goalsInScore", { count: goalsCheck.match_goals })}
              </span>
              <span className="chip" title={t("goalsInLinesTitle")}>
                {t("goalsInLines", { count: goalsCheck.line_up_goals })}
              </span>
              {goalsCheck.match_goals === goalsCheck.line_up_goals ? (
                <span className="badge badge--live">{t("reconciles")}</span>
              ) : (
                <span className="badge badge--demo">{t("doesNotReconcile")}</span>
              )}
            </div>
          )}
        </Panel>
      </div>

      {played && (
        <div className="grid grid-2">
          {(["home", "away"] as const).map((side) => {
            const group = lineUps[side];
            return (
              <Panel
                eyebrow={t("lineUpEyebrow", {
                  side,
                  starters: group.starters.length,
                  substitutes: group.substitutes.length,
                })}
                title={group.team?.name ?? t("teamFallback")}
                key={side}
              >
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">{t("thRole")}</th>
                        <th scope="col">{t("thPlayer")}</th>
                        <th scope="col">{t("thPos")}</th>
                        <th scope="col">{t("thMin")}</th>
                        <th scope="col">{t("thG")}</th>
                        <th scope="col">{t("thA")}</th>
                        <th scope="col">{t("thSh")}</th>
                        <th scope="col">{t("thP")}</th>
                        <th scope="col">{t("thTk")}</th>
                        <th scope="col">{t("thSv")}</th>
                        <th scope="col">{t("thRt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...group.starters, ...group.substitutes].map((line) => (
                        <tr key={line.id}>
                          <td className="muted">{line.role}</td>
                          <td>
                            <EntityLink href={line.player?.path} label={line.player?.name} />
                          </td>
                          <td>
                            <span className="world-pos">{line.position}</span>
                          </td>
                          <td className="num">{line.minutes}</td>
                          <td className="num">{line.goals}</td>
                          <td className="num">{line.assists}</td>
                          <td className="num">{line.shots}</td>
                          <td className="num muted">
                            {line.passes_accurate}/{line.passes}
                          </td>
                          <td className="num">{line.tackles}</td>
                          <td className="num">{line.saves}</td>
                          <td className="num">{line.rating.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            );
          })}
        </div>
      )}

      {played && statLines.length > 0 && (
        <Panel eyebrow={t("scorersEyebrow", { count: statLines.length })} title={t("scorersTitle")}>
          {statLines.some((line) => line.goals > 0) ? (
            <ul className="reasons">
              {statLines
                .filter((line) => line.goals > 0)
                .map((line) => (
                  <li className="reasons__item" key={line.id}>
                    <strong>{line.goals}×</strong> <EntityLink href={line.player?.path} label={line.player?.name} />{" "}
                    <span className="muted">
                      {t("scorersLine", {
                        side: line.team_id === match.home?.id ? t("homeLabel") : t("awayLabel"),
                        minutes: line.minutes,
                        rating: line.rating.toFixed(2),
                      })}
                    </span>
                  </li>
                ))}
            </ul>
          ) : (
            <span className="unavailable">{t("noScorer")}</span>
          )}
          <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
            {t("scorersNote")}
          </p>
        </Panel>
      )}

      {Object.keys(method).length > 0 && (
        <Panel eyebrow={t("methodEyebrow")} title={t("methodTitle")}>
          <ReasonList
            items={Object.entries(method).map(([key, value]) => `${key}: ${value}`)}
            title={t("formulasTitle")}
          />
        </Panel>
      )}

      <Provenance provenance={result.data} />
    </div>
  );
}
