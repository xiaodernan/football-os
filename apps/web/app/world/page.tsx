import type { Metadata } from "next";
import Link from "next/link";

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

export const metadata: Metadata = pageMetadata({
  title: "Football World",
  description:
    "Browse the generated football world: competitions, clubs, players, fixtures and match reports — every row labelled synthetic, with the seed and method that produced it.",
  path: "/world",
});

const SECTIONS: { href: string; label: string; note: string; countKey: string }[] = [
  { href: "/world/competitions", label: "Competitions", note: "leagues and cups, with tables built from stored results", countKey: "competitions" },
  { href: "/world/teams", label: "Clubs", note: "squad, stadium, manager, formation", countKey: "teams" },
  { href: "/world/players", label: "Players", note: "attributes, season totals, per-match lines", countKey: "players" },
  { href: "/world/matches", label: "Fixtures & results", note: "match centre with the statistics behind the score", countKey: "matches" },
  { href: "/world/news", label: "Reports & notes", note: "fact / analysis / speculation, always labelled", countKey: "articles" },
];

export default async function WorldIndexPage() {
  const [status, competitions, fixtures, news, players] = await Promise.all([
    readWorld<WorldStatus>("/world/status"),
    readWorld<CompetitionList>("/world/competitions", { page_size: 12 }),
    readWorld<MatchList>("/world/matches", { page_size: 6 }),
    readWorld<NewsList>("/world/news", { page_size: 5 }),
    readWorld<PlayerList>("/world/players", { sort: "overall", page_size: 8 }),
  ]);

  if (!status.ok) {
    return <WorldUnavailable message={status.message} detail="Start the API with scripts/dev.sh, then reload." />;
  }

  const world = status.data;
  const total = Object.values(world.counts).reduce((sum, value) => sum + value, 0);

  if (total === 0) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow="Synthetic dataset" title="Football World" lede="Nothing has been generated yet." provenance={world} />
        <div className="notice notice--warn">
          The world tables are empty. Generate them with <span className="mono">python -m seed</span> in <span className="mono">apps/api</span>, or
          set <span className="mono">WORLD_AUTO_SYNC=true</span>. This page shows nothing rather than placeholder rows.
        </div>
      </div>
    );
  }

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow="Synthetic dataset · generated, not scraped"
        title="Football World"
        lede="One locally generated football world — clubs, squads, fixtures, statistics and reports. Public, browsable, and honest about being invented."
        provenance={world}
      >
        <form action="/world/search" method="get" className="world-search" style={{ marginTop: "1rem" }} role="search">
          <input
            aria-label="Search the generated world"
            className="input"
            maxLength={120}
            name="q"
            placeholder="Search clubs, players, fixtures, reports…"
            type="search"
          />
          <button className="btn btn--primary" type="submit">
            Search
          </button>
        </form>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: "FOOTBALL OS generated world",
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
              Training log
            </Link>
          }
          eyebrow="What is actually in the tables"
          title="Contents, counted on this request"
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Table</th>
                  <th scope="col">Rows</th>
                  <th scope="col">Gate (spec §65)</th>
                  <th scope="col">State</th>
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
                          <span className="muted">not gated</span>
                        ) : count >= gate ? (
                          <span className="badge badge--live">MEETS</span>
                        ) : (
                          <span className="badge badge--demo">BELOW</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel eyebrow="How it was made" title="Generation method">
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>dataset version</dt>
              <dd className="mono">{world.version}</dd>
            </div>
            <div className="world-kv__row">
              <dt>seed</dt>
              <dd className="mono">{world.seed}</dd>
            </div>
            <div className="world-kv__row">
              <dt>auto-sync</dt>
              <dd className="mono">{String(world.auto_sync)}</dd>
            </div>
            <div className="world-kv__row">
              <dt>seasons</dt>
              <dd>{world.seasons.join(" · ")}</dd>
            </div>
            <div className="world-kv__row">
              <dt>positions</dt>
              <dd>{world.positions.join(" · ")}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.75rem" }}>
            Same seed ⇒ same world. Re-running the generator changes rows that were edited upstream, never the ones that were not,
            because each row is keyed by a natural key rather than a random identifier.
          </p>
          <div style={{ marginTop: "0.75rem" }}>
            <Provenance provenance={world} />
          </div>
        </Panel>
      </div>

      <section className="stack">
        <h2 className="h2">Browse</h2>
        <div className="world-cards">
          {SECTIONS.map((section) => (
            <Link className="world-card" href={section.href} key={section.href}>
              <span className="world-card__title">{section.label}</span>
              <span className="world-card__meta">{section.note}</span>
              <span className="chip mono">{(world.counts[section.countKey] ?? 0).toLocaleString("en-GB")} rows</span>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid grid-2">
        <Panel
          eyebrow="Tier 1 first"
          title="Competitions"
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/competitions">
              All
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
                    <span className="num muted">{row.team_count} clubs</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="notice notice--warn">{competitions.message}</div>
          )}
        </Panel>

        <Panel
          eyebrow="Next up"
          title="Fixtures & recent results"
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/matches">
              All
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
          eyebrow="Highest rated"
          title="Players"
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/players">
              All
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
          eyebrow="Latest"
          title="Reports & notes"
          action={
            <Link className="btn btn--ghost btn--sm" href="/world/news">
              All
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
        Nothing on this page came from a feed or a scrape: <span className="mono">source: synthetic-world</span>, generated from seed{" "}
        <span className="mono">{world.seed}</span> by <span className="mono">apps/api/app/services/world</span>. No real club, league or person is
        represented.
      </p>
    </div>
  );
}
