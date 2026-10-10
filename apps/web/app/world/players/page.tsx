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

export const metadata: Metadata = pageMetadata({
  title: "Players",
  description:
    "Every generated footballer: position, age, overall and potential, plus the season totals that the per-match statistic lines add up to.",
  path: "/world/players",
});

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
        back={{ href: "/world", label: "Back to Football World" }}
        eyebrow={tw("title")}
        lede={`${total.toLocaleString("en-GB")} generated players. Attributes come from the player's archetype and season output, and the page for each one lists why every number is what it is.`}
        provenance={result.data}
        title={tw("sectionPlayersLabel")}
      />

      <div className="grid grid-2">
        <Panel eyebrow={tc("filter")} title="By position">
          <FilterChips active={query.position} base={BASE} label="Position" options={positions} param="position" query={query} />
        </Panel>
        <Panel eyebrow="Order" title="Sort by">
          <FilterChips active={sort} base={BASE} drop={["order"]} label="Sort" options={sorts} param="sort" query={query} />
        </Panel>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <strong>No player matches that filter</strong>
          <Link className="btn btn--sm" href={BASE}>
            Clear filters
          </Link>
        </div>
      ) : (
        <Panel
          eyebrow={`sorted by ${sort} (${order})`}
          title={tw("sectionPlayersLabel")}
          action={
            <Link className="btn btn--ghost btn--sm" href={buildHref(BASE, query, { order: order === "desc" ? "asc" : "desc" }, ["page"])}>
              {order === "desc" ? "Lowest first" : "Highest first"}
            </Link>
          }
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Pos</th>
                  <th scope="col">{tc("personName")}</th>
                  <th scope="col">Club</th>
                  <th scope="col">Age</th>
                  <th scope="col">OVR</th>
                  <th scope="col">POT</th>
                  <th scope="col">G</th>
                  <th scope="col">A</th>
                  <th scope="col">Min</th>
                  <th scope="col">Rating</th>
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
                    <td className="muted">{row.club?.name ?? <span className="unavailable">no club</span>}</td>
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
