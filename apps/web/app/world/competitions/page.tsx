import type { Metadata } from "next";
import Link from "next/link";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { CompetitionList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export const metadata: Metadata = pageMetadata({
  title: "Competitions",
  description: "Every league and cup in the generated football world, with the number of clubs each one actually contains.",
  path: "/world/competitions",
});

const BASE = "/world/competitions";
const PAGE_SIZE = 20;

export default async function CompetitionsPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const result = await readWorld<CompetitionList>("/world/competitions", { kind: query.kind, page, page_size: PAGE_SIZE });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, kinds, total, pages } = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: "Back to Football World" }}
        eyebrow="Football World"
        lede={`${total.toLocaleString("en-GB")} generated competitions. A cup reports the clubs its drawn fixtures name, not a membership table.`}
        provenance={result.data}
        title="Competitions"
      />

      {kinds.length > 1 && (
        <Panel eyebrow="Filter" title="By format">
          <FilterChips active={query.kind} base={BASE} label="Format" options={kinds} param="kind" query={query} />
        </Panel>
      )}

      {items.length === 0 ? (
        <div className="empty">
          <strong>No competition matches that filter</strong>
          <span className="muted">The table is not empty — the filter is.</span>
          <Link className="btn btn--sm" href={BASE}>
            Clear filter
          </Link>
        </div>
      ) : (
        <Panel eyebrow="Names link to the competition page" title="All competitions">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Format</th>
                  <th scope="col">Region</th>
                  <th scope="col">Season</th>
                  <th scope="col">Tier</th>
                  <th scope="col">Clubs</th>
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
                    <td className="num">{row.tier}</td>
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
