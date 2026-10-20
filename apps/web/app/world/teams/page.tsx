import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Crest, FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { brandColor, buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { TeamList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return pageMetadata({
    title: tw("sectionClubsLabel"),
    description: tw("metaTeams"),
    path: "/world/teams",
  });
}

const BASE = "/world/teams";
const PAGE_SIZE = 25;

export default async function TeamsPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = await readWorld<TeamList>("/world/teams", {
    competition: query.competition,
    nation: query.nation,
    page,
    page_size: PAGE_SIZE,
  });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, nations, seasons, total, pages } = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("title")}
        lede={tw("teamsLede", { count: total.toLocaleString("en-GB") })}
        provenance={result.data}
        title={tw("sectionClubsLabel")}
      />

      <Panel eyebrow={tc("filter")} title={tw("teamsByNationTitle")}>
        <div className="stack-sm">
          <FilterChips active={query.nation} base={BASE} label={tw("teamsNationLabel")} options={nations} param="nation" query={query} />
          <p className="muted world-section-note">{tw("teamsSeasonsNote", { seasons: seasons.join(" · ") })}</p>
        </div>
      </Panel>

      {items.length === 0 ? (
        <div className="empty">
            <strong>{tw("teamsEmptyTitle")}</strong>
          <Link className="btn btn--sm" href={BASE}>
            {tw("teamsClearFilter")}
          </Link>
        </div>
      ) : (
        <Panel eyebrow={tw("teamsPanelEyebrow")} title={tw("teamsPanelTitle")}>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{tw("thClub")}</th>
                  <th scope="col">{tw("thCityGround")}</th>
                  <th scope="col">{tw("thLeague")}</th>
                  <th scope="col">{tw("thManager")}</th>
                  <th scope="col">{tw("thShape")}</th>
                  <th scope="col">{tw("thSquad")}</th>
                  <th scope="col">{tw("thOvr")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="row" style={{ gap: "0.6rem" }}>
                        <Crest color={brandColor(row.brand_color)} name={row.short_name || row.name} />
                        <Link className="world-link" href={row.path}>
                          {row.name}
                        </Link>
                      </span>
                    </td>
                    <td className="muted">
                      {row.city} · {row.stadium}
                    </td>
                    <td className="muted">
                      {row.competition ? (
                        <Link className="world-link" href={row.competition.path}>
                          {row.competition.name}
                        </Link>
                      ) : (
                        <span className="unavailable">{tw("noLeague")}</span>
                      )}
                    </td>
                    <td className="muted">{row.manager_name}</td>
                    <td className="mono">{row.formation}</td>
                    <td className="num">{row.squad_size}</td>
                    <td className="num">{row.overall}</td>
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
