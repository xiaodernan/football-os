import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { PlayerList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return pageMetadata({
    title: tw("sectionPlayersLabel"),
    description: tw("metaPlayers"),
    path: "/world/players",
  });
}

const BASE = "/world/players";
const PAGE_SIZE = 25;

export default async function PlayersPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = await readWorld<PlayerList>("/world/players", {
    position: query.position,
    sort: query.sort,
    order: query.order,
    page,
    page_size: PAGE_SIZE,
  });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, positions, sorts, total, pages } = result.data;
  const sort = query.sort ?? "overall";
  const order = query.order ?? "desc";

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("title")}
        lede={tw("playersLede", { count: total.toLocaleString("en-GB") })}
        provenance={result.data}
        title={tw("sectionPlayersLabel")}
      />

      <div className="grid grid-2">
        <Panel eyebrow={tc("filter")} title={tw("playersByPositionTitle")}>
          <FilterChips active={query.position} base={BASE} label={tw("playersPositionLabel")} options={positions} param="position" query={query} />
        </Panel>
        <Panel eyebrow={tw("playersOrderEyebrow")} title={tw("playersSortTitle")}>
          <FilterChips active={sort} base={BASE} drop={["order"]} label={tw("playersSortLabel")} options={sorts} param="sort" query={query} />
        </Panel>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <strong>{tw("playersEmptyTitle")}</strong>
          <Link className="btn btn--sm" href={BASE}>
            {tw("playersClearFilters")}
          </Link>
        </div>
      ) : (
        <Panel
          eyebrow={tw("playersSortedBy", { sort, order })}
          title={tw("sectionPlayersLabel")}
          action={
            <Link className="btn btn--ghost btn--sm" href={buildHref(BASE, query, { order: order === "desc" ? "asc" : "desc" }, ["page"])}>
              {order === "desc" ? tw("playersLowestFirst") : tw("playersHighestFirst")}
            </Link>
          }
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{tw("thPos")}</th>
                  <th scope="col">{tc("personName")}</th>
                  <th scope="col">{tw("thClub")}</th>
                  <th scope="col">{tw("thAge")}</th>
                  <th scope="col">{tw("thOvr")}</th>
                  <th scope="col">{tw("thPot")}</th>
                  <th scope="col">{tw("thGoals")}</th>
                  <th scope="col">{tw("thAssists")}</th>
                  <th scope="col">{tw("thMinutes")}</th>
                  <th scope="col">{tw("thRating")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="world-pos">{row.position}</span>
                    </td>
                    <td>
                      <Link className="world-link" href={row.path}>
                        {row.name}
                      </Link>
                    </td>
                    <td className="muted">{row.club?.name ?? <span className="unavailable">{tw("noClub")}</span>}</td>
                    <td className="num">{row.age}</td>
                    <td className="num">{row.overall}</td>
                    <td className="num muted">{row.potential}</td>
                    <td className="num">{row.goals}</td>
                    <td className="num">{row.assists}</td>
                    <td className="num muted">{row.minutes}</td>
                    <td className="num">{row.rating.toFixed(2)}</td>
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
