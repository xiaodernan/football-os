import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { CompetitionList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return pageMetadata({
    title: tw("sectionCompetitionsLabel"),
    description: tw("metaCompetitions"),
    path: "/world/competitions",
  });
}

const BASE = "/world/competitions";
const PAGE_SIZE = 20;

export default async function CompetitionsPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = await readWorld<CompetitionList>("/world/competitions", { kind: query.kind, page, page_size: PAGE_SIZE });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, kinds, total, pages } = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("title")}
        lede={tw("competitionsLede", { count: total.toLocaleString("en-GB") })}
        provenance={result.data}
        title={tw("sectionCompetitionsLabel")}
      />

      {kinds.length > 1 && (
        <Panel eyebrow={tc("filter")} title={tw("competitionsByFormatTitle")}>
          <FilterChips active={query.kind} base={BASE} label={tw("competitionsFormatLabel")} options={kinds} param="kind" query={query} />
        </Panel>
      )}

      {items.length === 0 ? (
        <div className="empty">
          <strong>{tw("competitionsEmptyTitle")}</strong>
          <span className="muted">{tw("competitionsEmptyNote")}</span>
          <Link className="btn btn--sm" href={BASE}>
            {tw("competitionsClearFilter")}
          </Link>
        </div>
      ) : (
        <Panel eyebrow={tw("competitionsPanelEyebrow")} title={tw("competitionsPanelTitle")}>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{tc("name")}</th>
                  <th scope="col">{tw("thFormat")}</th>
                  <th scope="col">{tw("thRegion")}</th>
                  <th scope="col">{tw("thSeason")}</th>
                  <th scope="col">{tw("thTier")}</th>
                  <th scope="col">{tw("thClubs")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link className="world-link" href={row.path}>
                        {row.name}
                      </Link>
                    </td>
                    <td className="muted">{row.kind}</td>
                    <td className="muted">{row.region}</td>
                    <td className="num">{row.season}</td>
                    <td className="num">{row.kind === "league" ? row.tier : "—"}</td>
                    <td className="num">{row.team_count}</td>
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
