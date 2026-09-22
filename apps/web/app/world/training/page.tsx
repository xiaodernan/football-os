import type { Metadata } from "next";
import Link from "next/link";

import { Panel } from "@/components/ui";
import { FilterChips, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { WorldTrainingList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export const metadata: Metadata = pageMetadata({
  title: "Training log",
  description:
    "The generated world's training log: every session names the player, the catalogue drill, the minutes and the RPE, and the load figure is those last two multiplied.",
  path: "/world/training",
});

const BASE = "/world/training";
const PAGE_SIZE = 25;

export default async function WorldTrainingPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
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
        back={{ href: "/world", label: "Back to Football World" }}
        eyebrow="Football World"
        lede="What the generated squad did between fixtures. Each row names a catalogue drill this repository authored, the synthetic player who is said to have run it, and the two figures the load number is made from — there is no tracking data and no person behind any of it."
        provenance={result.data}
        title="Training log"
      />

      <div className="grid grid-2">
        <Panel eyebrow="Filter" title="By focus">
          <FilterChips active={query.category} base={BASE} label="Focus" options={categories} param="category" query={query} />
        </Panel>
        <Panel eyebrow="This page" title="Session load, measured from the rows below">
          <dl className="world-kv">
            <div>
              <dt>Sessions listed</dt>
              <dd>{total.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>Gate (spec §65)</dt>
              <dd>{gate.training_sessions?.toLocaleString("en-GB") ?? "—"}</dd>
            </div>
            <div>
              <dt>Minutes on this page</dt>
              <dd>{totals.total_minutes.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>Load on this page</dt>
              <dd>{totals.total_load.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>Mean RPE</dt>
              <dd>{totals.mean_rpe}</dd>
            </div>
            <div>
              <dt>Formula</dt>
              <dd className="mono">{totals.load_formula}</dd>
            </div>
            <div>
              <dt>Drills used here</dt>
              <dd>{totals.drills.length}</dd>
            </div>
          </dl>
          {scoped ? (
            <p className="muted">
              Filtered by <span className="mono">{filters.player ? `player=${filters.player}` : `team=${filters.team}`}</span> ·{" "}
              <Link href={BASE}>clear</Link>
            </p>
          ) : null}
          <p className="muted">Drill names link into the Training Academy, which asks for an account. Nothing else on this page does.</p>
        </Panel>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <strong>No session matches that filter</strong>
          <Link className="btn btn--sm" href={BASE}>
            Clear filters
          </Link>
        </div>
      ) : (
        <Panel eyebrow={`${items.length} of ${total.toLocaleString("en-GB")} rows`} title="Sessions">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Player</th>
                  <th scope="col">Pos</th>
                  <th scope="col">Drill</th>
                  <th scope="col">Focus</th>
                  <th scope="col">Min</th>
                  <th scope="col">RPE</th>
                  <th scope="col">Load</th>
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
