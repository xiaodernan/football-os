import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable, formatMoment } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { MatchList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return pageMetadata({
    title: tw("sectionFixturesLabel"),
    description:
      "Every fixture in the generated football world, newest first. Scheduled matches show a kick-off time and no score, because no score exists yet.",
    path: "/world/matches",
  });
}

const BASE = "/world/matches";
const PAGE_SIZE = 25;

export default async function MatchesPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = await readWorld<MatchList>("/world/matches", {
    status: query.status,
    season: query.season,
    competition: query.competition,
    page,
    page_size: PAGE_SIZE,
  });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, statuses, total, pages } = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: "Back to Football World" }}
        eyebrow={tw("title")}
        lede={`${total.toLocaleString("en-GB")} fixtures. A row that has not been played carries NULL in the database, so it renders as “not played” rather than 0–0.`}
        provenance={result.data}
        title={tw("sectionFixturesLabel")}
      />

      <Panel eyebrow={tc("filter")} title="By state">
        <FilterChips active={query.status} base={BASE} label={tw("tableHeaderState")} options={statuses} param="status" query={query} />
      </Panel>

      {items.length === 0 ? (
        <div className="empty">
          <strong>No fixture matches that filter</strong>
          <Link className="btn btn--sm" href={BASE}>
            Clear filter
          </Link>
        </div>
      ) : (
        <Panel eyebrow="Names link to the match centre" title="Every fixture">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Kick-off</th>
                  <th scope="col">Competition</th>
                  <th scope="col">Fixture</th>
                  <th scope="col">Score</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td className="muted">
                      <span className="mono">{formatMoment(row.kickoff_at)}</span>
                      <br />
                      {row.round_label}
                    </td>
                    <td className="muted">
                      {row.season} · {row.venue.name}
                    </td>
                    <td>
                      <Link className="world-link" href={row.path}>
                        {row.home?.name ?? "—"} v {row.away?.name ?? "—"}
                      </Link>
                    </td>
                    <td className="num">
                      {row.status === "completed" && row.home_goals !== null && row.away_goals !== null ? (
                        <Link className="world-link mono" href={row.path}>
                          {row.home_goals}–{row.away_goals}
                        </Link>
                      ) : (
                        <span className="unavailable">not played</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <WorldPager build={(next) => buildHref(BASE, query, { page: String(next) })} page={page} pages={pages} total={total} />
      <Provenance provenance={result.data} />
    </div>
  );
}
