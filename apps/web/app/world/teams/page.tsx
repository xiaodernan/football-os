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

export const metadata: Metadata = pageMetadata({
  title: "Clubs",
  description: "Every club in the generated football world: city, stadium, manager, formation, squad size and mean overall rating.",
  path: "/world/teams",
});

const BASE = "/world/teams";
const PAGE_SIZE = 25;

export default async function TeamsPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
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
        back={{ href: "/world", label: "Back to Football World" }}
        eyebrow="Football World"
        lede={`${total.toLocaleString("en-GB")} generated clubs. Overall is the mean of the stored squad, so it moves when a squad does.`}
        provenance={result.data}
        title="Clubs"
      />

      <Panel eyebrow={tc("filter")} title="By nation">
        <div className="stack-sm">
          <FilterChips active={query.nation} base={BASE} label="Nation" options={nations} param="nation" query={query} />
          <p className="muted world-section-note">Seasons in the dataset: {seasons.join(" · ")}</p>
        </div>
      </Panel>

      {items.length === 0 ? (
        <div className="empty">
          <strong>No club matches that filter</strong>
          <Link className="btn btn--sm" href={BASE}>
            Clear filter
          </Link>
        </div>
      ) : (
        <Panel eyebrow="Names link to the club page" title="All clubs">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Club</th>
                  <th scope="col">City / ground</th>
                  <th scope="col">League</th>
                  <th scope="col">Manager</th>
                  <th scope="col">Shape</th>
                  <th scope="col">Squad</th>
                  <th scope="col">OVR</th>
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
                        <span className="unavailable">no league</span>
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
