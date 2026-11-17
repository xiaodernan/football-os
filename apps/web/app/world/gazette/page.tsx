import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import { GazetteCoachRead } from "@/components/GazetteCoachRead";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/gazette.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldGazette");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/gazette",
    images: [{ url: absolute("/world/gazette/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type SideBrief = { id: string; slug: string; name: string; path: string } | null;
type FixtureBrief = {
  id: string;
  slug: string;
  path: string;
  kickoff: string | null;
  venue: string | null;
  city: string | null;
  home: SideBrief;
  away: SideBrief;
  home_goals?: number;
  away_goals?: number;
  score?: string;
};
type TableRow = {
  position: number;
  team: SideBrief;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
};
type GazettePayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  edition?: number;
  total_editions?: number;
  published_at?: string;
  competition?: { name: string; slug: string; path: string };
  scorecard?: FixtureBrief[];
  table_after?: TableRow[];
  table_leader?: TableRow | null;
  table_gap?: number;
  lead?: FixtureBrief;
  hot_hand?: { team: SideBrief; goals: number };
  number?: { goals_this_round: number; draws: number; clean_sheets: number; season_average_goals: number; fixtures: number };
  archive?: number[];
  out_of_range?: boolean;
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function GazettePage({ searchParams }: Props) {
  const t = await getTranslations("worldGazette");
  const tw = await getTranslations("world");
  const params = await searchParams;
  const raw = Array.isArray(params?.edition) ? params.edition[0] : params?.edition;
  const parsed = raw ? Number.parseInt(raw, 10) : NaN;
  const edition = Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;

  const result = await readWorld<GazettePayload>("/world/gazette", { edition });
  if (!result.ok) {
    return (
      <div className="container page stack" style={{ gap: "1.5rem" }}>
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="muted">{t("editionMissing")}</p>
        <Link href="/world/gazette" className="timeline__tile-eyebrow" style={{ color: "var(--accent)" }}>{t("latestEditionLink")}</Link>
      </div>
    );
  }
  if (!result.data.available) {
    return (
      <div className="container page stack" style={{ gap: "1.5rem" }}>
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="muted">{result.data.out_of_range ? t("editionMissing") : t("unavailable")}</p>
        <Link href="/world/gazette" style={{ color: "var(--accent)", fontWeight: 700 }}>{t("latestEditionLink")}</Link>
      </div>
    );
  }

  const { season, competition, edition: editionNow, total_editions, published_at, scorecard, table_after, table_leader, table_gap, lead, hot_hand, number: figures, archive } = result.data;
  const currentEdition = editionNow as number;
  const totalEditions = total_editions as number;

  return (
    <div className="container page stack" style={{ gap: "1.6rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div>
        <div className="gazette__masthead">
          <span className="gazette__kicker">{competition?.name} · {season.label}</span>
          <span className="gazette__edition">{t("mastheadEdition", { edition: currentEdition, total: totalEditions })}</span>
        </div>
        <div className="gazette__rule">
          <span>{t("mastheadKicker", { n: currentEdition })}</span>
          <span>{t("printedLine", { date: formatDay(published_at) })}</span>
        </div>
      </div>

      {lead && (
        <article className="gazette__lead">
          <span className="gazette__lead-eyebrow">{t("leadLabel")}</span>
          <h2 className="gazette__lead-title">
            <Link href={lead.path}>
              {lead.home?.name} <span className="gazette__score">{lead.home_goals}–{lead.away_goals}</span> {lead.away?.name}
            </Link>
          </h2>
          <p className="gazette__lead-body">{t("leadBody", { goals: (lead.home_goals ?? 0) + (lead.away_goals ?? 0), venue: lead.venue ?? t("unknownVenue") })}</p>
        </article>
      )}

      <div className="gazette__grid">
        <section className="gazette__panel">
          <span className="gazette__panel-eyebrow">{t("tableLabel")}</span>
          <h3>{t("tableTitle", { n: currentEdition })}</h3>
          <div className="table-wrap">
            <table className="gazette__table table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("tableTeamHead")}</th>
                <th scope="col">{t("tablePlayedHead")}</th>
                <th scope="col">{t("tableGoalsHead")}</th>
                <th scope="col">{t("tablePointsHead")}</th>
              </tr>
            </thead>
            <tbody>
              {(table_after ?? []).map((row) => (
                <tr key={row.position} data-leader={row.team?.id === table_leader?.team?.id ? "true" : undefined}>
                  <td>{row.position}</td>
                  <td>{row.team?.path ? <Link href={row.team.path}>{row.team.name}</Link> : row.team?.name}</td>
                  <td>{row.played}</td>
                  <td>{row.goals_for}:{row.goals_against}</td>
                  <td><strong>{row.points}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <p className="muted" style={{ fontSize: "0.76rem", margin: "0.45rem 0 0" }}>
            {table_leader ? t("tableBody", { leader: table_leader.team?.name ?? t("tableUnknown"), points: table_leader.points, gap: table_gap ?? 0, gd: table_leader.goal_difference >= 0 ? `+${table_leader.goal_difference}` : `${table_leader.goal_difference}` }) : ""}
          </p>
        </section>

        <div style={{ display: "grid", gap: "0.75rem" }}>
          <section className="gazette__panel">
            <span className="gazette__panel-eyebrow">{t("scorecardLabel")}</span>
            <h3>{t("scorecardTitle")}</h3>
            {(scorecard ?? []).map((match) => (
              <div key={match.id} className="gazette__fixture">
                <span className="gazette__fixture-time">{formatDay(match.kickoff)}</span>
                <span>
                  <Link href={match.home?.path ?? "#"}>{match.home?.name}</Link> v <Link href={match.away?.path ?? "#"}>{match.away?.name}</Link>
                </span>
                <Link href={match.path} className="gazette__fixture-score">{match.score}</Link>
              </div>
            ))}
          </section>

          <section className="gazette__panel gazette__hot">
            <span className="gazette__panel-eyebrow">{t("hotLabel")}</span>
            <div className="gazette__number">
              <span className="gazette__number-big">{hot_hand?.goals ?? 0}</span>
              <span className="gazette__number-caption">
                {hot_hand?.team ? t("hotBody", { name: hot_hand.team.name ?? "", goals: hot_hand.goals ?? 0 }) : t("unavailable")}
              </span>
            </div>
          </section>

          <section className="gazette__panel">
            <span className="gazette__panel-eyebrow">{t("numberLabel")}</span>
            <div className="gazette__number">
              <span className="gazette__number-big">{figures?.goals_this_round ?? 0}</span>
              <span className="gazette__number-caption">{t("numberBody", { average: figures?.season_average_goals ?? 0 })}</span>
            </div>
            <p className="muted" style={{ fontSize: "0.76rem", margin: "0.35rem 0 0" }}>
              {t("shutoutsLine", { count: figures?.clean_sheets ?? 0, draws: figures?.draws ?? 0, fixtures: figures?.fixtures ?? 0 })}
            </p>
          </section>
        </div>
      </div>

      <section>
        <span className="gazette__panel-eyebrow">{t("archiveLabel")}</span>
        <p className="muted" style={{ margin: "0.15rem 0 0.5rem", fontSize: "0.8rem" }}>{t("archiveLede")}</p>
        <div className="gazette__archive">
          {(archive ?? []).map((n) => (
            <Link
              key={n}
              href={n === totalEditions ? "/world/gazette" : `/world/gazette?edition=${n}`}
              className="gazette__edition-link"
              data-current={n === currentEdition ? "true" : undefined}
            >
              {n}
            </Link>
          ))}
        </div>
      </section>

      <GazetteCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}
