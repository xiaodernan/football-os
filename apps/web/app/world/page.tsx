import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import {
  CompetitionLink,
  EntityLink,
  JsonLd,
  MatchRow,
  OriginBadge,
  Provenance,
  WorldHead,
  WorldUnavailable,
  formatDay,
} from "@/components/world";
import { pageMetadata, SITE_NAME, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { MatchList, NewsList, PlayerList, CompetitionList, WorldStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("world");
  return pageMetadata({
    title: t("title"),
    description: t("description"),
    path: "/world",
  });
}

export default async function WorldIndexPage() {
  const t = await getTranslations("world");
  
  const sections = [
    { href: "/world/competitions", label: t("sectionCompetitionsLabel"), note: t("sectionCompetitionsNote"), countKey: "competitions" },
    { href: "/world/teams", label: t("sectionClubsLabel"), note: t("sectionClubsNote"), countKey: "teams" },
    { href: "/world/players", label: t("sectionPlayersLabel"), note: t("sectionPlayersNote"), countKey: "players" },
    { href: "/world/matches", label: t("sectionFixturesLabel"), note: t("sectionFixturesNote"), countKey: "matches" },
    { href: "/world/news", label: t("sectionReportsLabel"), note: t("sectionReportsNote"), countKey: "articles" },
  ];

  const [status, competitions, fixtures, news, players] = await Promise.all([
    readWorld<WorldStatus>("/world/status"),
    readWorld<CompetitionList>("/world/competitions", { page_size: 12 }),
    readWorld<MatchList>("/world/matches", { page_size: 6 }),
    readWorld<NewsList>("/world/news", { page_size: 5 }),
    readWorld<PlayerList>("/world/players", { sort: "overall", page_size: 8 }),
  ]);

  if (!status.ok) {
    return <WorldUnavailable message={status.message} detail={t("unavailableDetail")} />;
  }

  const world = status.data;
  const total = Object.values(world.counts).reduce((sum, value) => sum + value, 0);

  if (total === 0) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} lede={t("emptyLede")} provenance={world} />
        <div className="notice notice--warn">
          {t.rich("emptyNotice", {
            mono: (chunks) => <span className="mono">{chunks}</span>,
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={world}
      >
        <form action="/world/search" method="get" className="world-search" style={{ marginTop: "1rem" }} role="search">
          <input
            aria-label={t("searchAriaLabel")}
            className="input"
            maxLength={120}
            name="q"
            placeholder={t("searchPlaceholder")}
            type="search"
          />
          <button className="btn btn--primary" type="submit">
            {t("searchButton")}
          </button>
        </form>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: t("publisherName"),
          description: world.disclaimer,
          url: absolute("/world"),
          creator: { "@type": "Organization", name: SITE_NAME, url: absolute("/") },
          isAccessibleForFree: true,
          measurementTechnique: world.stat_method.rating,
          temporalCoverage: world.seasons.join(" / "),
          variableMeasured: Object.keys(world.counts).join(", "),
        }}
      />

      <div className="grid grid-2">
        <Panel
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/training">
              {t("trainingLogLink")}
            </Link>
          }
          eyebrow={t("contentsEyebrow")}
          title={t("contentsTitle")}
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableHeaderTable")}</th>
                  <th scope="col">{t("tableHeaderRows")}</th>
                  <th scope="col">{t("tableHeaderGate")}</th>
                  <th scope="col">{t("tableHeaderState")}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(world.counts).map(([table, count]) => {
                  const gate = world.gate[table];
                  return (
                    <tr key={table}>
                      <td className="mono">{table}</td>
                      <td className="num">{count.toLocaleString("en-GB")}</td>
                      <td className="num muted">{gate === undefined ? "—" : gate.toLocaleString("en-GB")}</td>
                      <td>
                        {gate === undefined ? (
                          <span className="muted">{t("stateNotGated")}</span>
                        ) : count >= gate ? (
                          <span className="badge badge--live">{t("badgeMeets")}</span>
                        ) : (
                          <span className="badge badge--demo">{t("badgeBelow")}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel eyebrow={t("generationEyebrow")} title={t("generationTitle")}>
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>{t("labelDatasetVersion")}</dt>
              <dd className="mono">{world.version}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelSeed")}</dt>
              <dd className="mono">{world.seed}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelAutoSync")}</dt>
              <dd className="mono">{String(world.auto_sync)}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelSeasons")}</dt>
              <dd>{world.seasons.join(" · ")}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelPositions")}</dt>
              <dd>{world.positions.join(" · ")}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.75rem" }}>
            {t("generationNote")}
          </p>
          <div style={{ marginTop: "0.75rem" }}>
            <Provenance provenance={world} />
          </div>
        </Panel>
      </div>

      <section className="stack">
        <h2 className="h2">{t("browseTitle")}</h2>
        <div className="world-cards">
          {sections.map((section) => (
            <Link className="world-card" href={section.href} key={section.href}>
              <span className="world-card__title">{section.label}</span>
              <span className="world-card__meta">{section.note}</span>
              <span className="chip mono">{(world.counts[section.countKey] ?? 0).toLocaleString("en-GB")} {t("rowsUnit")}</span>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid grid-2">
        <Panel
          eyebrow={t("panelCompetitionsEyebrow")}
          title={t("panelCompetitionsTitle")}
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/competitions">
              {t("panelCompetitionsAction")}
            </Link>
          }
        >
          {competitions.ok ? (
            <ul className="world-list">
              {competitions.data.items.slice(0, 8).map((row) => (
                <li className="world-fixture" key={row.id}>
                  <div className="world-fixture__when">
                    <span className="mono muted">{row.kind}</span>
                    <span className="world-fixture__round">tier {row.tier}</span>
                  </div>
                  <div className="world-fixture__teams">
                    <CompetitionLink competition={{ id: row.id, slug: row.slug, name: row.name, kind: row.kind, path: row.path }} />
                  </div>
                  <div className="world-fixture__score">
                    <span className="num muted">{row.team_count} {t("clubsUnit")}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="notice notice--warn">{competitions.message}</div>
          )}
        </Panel>

        <Panel
          eyebrow={t("panelFixturesEyebrow")}
          title={t("panelFixturesTitle")}
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/matches">
              {t("panelFixturesAction")}
            </Link>
          }
        >
          {fixtures.ok ? (
            <ul className="world-list">
              {fixtures.data.items.map((match) => (
                <MatchRow match={match} key={match.id} />
              ))}
            </ul>
          ) : (
            <div className="notice notice--warn">{fixtures.message}</div>
          )}
        </Panel>
      </div>

      <div className="grid grid-2">
        <Panel
          eyebrow={t("panelPlayersEyebrow")}
          title={t("panelPlayersTitle")}
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/players">
              {t("panelPlayersAction")}
            </Link>
          }
        >
          {players.ok ? (
            <ul className="world-list">
              {players.data.items.map((player) => (
                <li className="world-fixture" key={player.id}>
                  <div className="world-fixture__when">
                    <span className="world-pos">{player.position}</span>
                    <span className="world-fixture__round">age {player.age}</span>
                  </div>
                  <div className="world-fixture__teams">
                    <EntityLink href={player.path} label={player.name} />
                    <span className="muted" style={{ fontWeight: 400 }}>
                      <EntityLink href={player.club?.path ?? null} label={player.club?.name} fallback="no club" />
                    </span>
                  </div>
                  <div className="world-fixture__score">
                    <span className="num mono">{player.overall} OVR</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="notice notice--warn">{players.message}</div>
          )}
        </Panel>

        <Panel
          eyebrow={t("panelReportsEyebrow")}
          title={t("panelReportsTitle")}
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/news">
              {t("panelReportsAction")}
            </Link>
          }
        >
          {news.ok ? (
            <ul className="world-list">
              {news.data.items.map((article) => (
                <li className="world-fixture" key={article.id}>
                  <div className="world-fixture__when">
                    <span className="mono muted">{formatDay(article.published_at)}</span>
                    <span className="world-fixture__round">{article.claim_class}</span>
                  </div>
                  <div className="world-fixture__teams">
                    <EntityLink href={article.path} label={article.title} />
                  </div>
                  <div className="world-fixture__score">
                    <OriginBadge provenance={article} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="notice notice--warn">{news.message}</div>
          )}
        </Panel>
      </div>

      <p className="muted world-section-note">
        {t.rich("footerNote", {
          seed: world.seed,
          mono: (chunks) => <span className="mono">{chunks}</span>,
        })}
      </p>
    </div>
  );
}
