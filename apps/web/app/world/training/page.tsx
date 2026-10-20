import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { WorldTrainingList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  const tt = await getTranslations("worldTraining");
  return pageMetadata({
    // The key is spelled …Link because the world index reached this page through a link; the page's own
    // heading already reads the same key, so the tab and the heading cannot drift apart.
    title: tw("trainingLogLink"),
    description: tw("metaTraining"),
    path: "/world/training",
  });
}

const BASE = "/world/training";
const PAGE_SIZE = 25;

export default async function WorldTrainingPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const tt = await getTranslations("worldTraining");
  const result = await readWorld<WorldTrainingList>("/world/training", {
    player: query.player,
    team: query.team,
    category: query.category,
    page,
    page_size: PAGE_SIZE,
  });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, categories, total, pages, page_totals: totals, gate, filters } = result.data;
  const scoped = filters.player ?? filters.team ?? null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("title")}
        lede={tt("lede")}
        provenance={result.data}
        title={tw("trainingLogLink")}
      />

      <div className="grid grid-2">
        <Panel eyebrow={tc("filter")} title={tt("byFocusTitle")}>
          <FilterChips active={query.category} base={BASE} label={tt("focusLabel")} options={categories} param="category" query={query} />
        </Panel>
        <Panel eyebrow={tt("pageEyebrow")} title={tt("pageTitle")}>
          <dl className="world-kv">
            <div>
              <dt>{tt("rowSessionsListed")}</dt>
              <dd>{total.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>{tt("rowGate")}</dt>
              <dd>{gate.training_sessions?.toLocaleString("en-GB") ?? "—"}</dd>
            </div>
            <div>
              <dt>{tt("rowMinutesOnPage")}</dt>
              <dd>{totals.total_minutes.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>{tt("rowLoadOnPage")}</dt>
              <dd>{totals.total_load.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>{tt("rowMeanRpe")}</dt>
              <dd>{totals.mean_rpe}</dd>
            </div>
            <div>
              <dt>{tt("rowFormula")}</dt>
              <dd className="mono">{totals.load_formula}</dd>
            </div>
            <div>
              <dt>{tt("rowDrillsUsed")}</dt>
              <dd>{totals.drills.length}</dd>
            </div>
          </dl>
          {scoped ? (
            <p className="muted">
              {tt("filteredBy", {
                filter: filters.player ? `player=${filters.player}` : `team=${filters.team}`,
              })}
              <Link href={BASE}>{tt("clear")}</Link>
            </p>
          ) : null}
          <p className="muted">{tt("drillsNote")}</p>
        </Panel>
      </div>

      {items.length === 0 ? (
        <div className="empty">
            <strong>{tt("emptyTitle")}</strong>
          <Link className="btn btn--sm" href={BASE}>
            {tt("clearFilters")}
          </Link>
        </div>
      ) : (
        <Panel
          eyebrow={tt("sessionsEyebrow", {
            shown: items.length,
            total: total.toLocaleString("en-GB"),
          })}
          title={tt("sessionsTitle")}
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{tt("thDate")}</th>
                  <th scope="col">{tt("thPlayer")}</th>
                  <th scope="col">{tt("thPos")}</th>
                  <th scope="col">{tt("thDrill")}</th>
                  <th scope="col">{tt("thFocus")}</th>
                  <th scope="col">{tt("thMin")}</th>
                  <th scope="col">{tt("thRpe")}</th>
                  <th scope="col">{tt("thLoad")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{row.date}</td>
                    <td>
                      <Link className="world-link" href={row.player_path}>
                        {row.player_name}
                      </Link>
                    </td>
                    <td>
                      <span className="world-pos">{row.position}</span>
                    </td>
                    <td>
                      <Link className="world-link" href={row.drill_path}>
                        {row.drill_title}
                      </Link>
                    </td>
                    <td className="muted">{row.category}</td>
                    <td className="num">{row.duration_min}</td>
                    <td className="num">{row.rpe}</td>
                    <td className="num">{row.load_units}</td>
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
