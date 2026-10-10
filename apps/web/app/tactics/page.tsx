import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Pitch } from "@/components/pitch";
import { BandLegend, MetricTable, SystemCard } from "@/components/tactics";
import { Panel } from "@/components/ui";
import { FilterChips, JsonLd, Provenance, WorldHead, WorldPager, WorldUnavailable } from "@/components/world";
import { pageMetadata, SITE_NAME, absolute } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { SystemBrief, SystemDetail, SystemList, TacticsStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export const metadata: Metadata = pageMetadata({
  title: "Tactical Lab",
  description:
    "Fifty authored tactical systems — ten shapes times five temperaments — with the width, spacing and space behind the back line measured from their own coordinates, in metres.",
  path: "/tactics",
});

const BASE = "/tactics";
const PAGE_SIZE = 12;

export default async function TacticsIndexPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tn = await getTranslations("nav");
  const [status, list] = await Promise.all([
    readWorld<TacticsStatus>("/tactics/status"),
    readWorld<SystemList>("/tactics", {
      formation: query.formation,
      temperament: query.temperament,
      search: query.search,
      page,
      page_size: PAGE_SIZE,
    }),
  ]);

  if (!status.ok) {
    return (
      <WorldUnavailable
        eyebrow={tn("tactics")}
        message={status.message}
        title={tn("tactics")}
        detail="The catalogue is stored on boot by apps/api; start it with scripts/dev.sh."
      />
    );
  }

  const world = status.data;
  const sample: SystemBrief | undefined = list.ok ? list.data.items[0] : undefined;

  // One real system on the index: its own board, its own eight measures, its own formulas. Reading the
  // list row alone would print the status endpoint's sample values beside a different system's name.
  const firstDetail = sample ? await readWorld<SystemDetail>(`/tactics/${encodeURIComponent(sample.slug)}`) : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: "Football World" }}
        eyebrow="Authored coaching structures · measured in metres"
        lede="Ten shapes × five temperaments = the fifty systems this lab stores. Nothing here is a real team's play: the coordinates are written by this project, and every figure is measured from them."
        provenance={world}
        title={tn("tactics")}
      >
        <form action="/tactics" className="world-search" method="get" role="search" style={{ marginTop: "1rem" }}>
          <input
            aria-label="Search the tactical catalogue"
            className="input"
            defaultValue={query.search ?? ""}
            maxLength={60}
            name="search"
            placeholder="Search a shape, e.g. 3-4-2-1…"
            type="search"
          />
          <button className="btn btn--primary" type="submit">
            {tc("search")}
          </button>
          <Link className="btn btn--ghost" href="/tactics/compare">
            Compare two
          </Link>
        </form>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: "FOOTBALL OS tactical systems",
          description: world.disclaimer,
          url: absolute("/tactics"),
          creator: { "@type": "Organization", name: SITE_NAME, url: absolute("/") },
          isAccessibleForFree: true,
          measurementTechnique: world.metrics.map((metric) => `${metric.label}: ${metric.formula}`).join(" · "),
          variableMeasured: world.metric_keys.join(", "),
          spatialCoverage: "68 m × 105 m pitch, Law 1",
        }}
      />

      <div className="grid grid-2">
        <Panel eyebrow="Store" title="What is here">
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>systems stored</dt>
              <dd className="mono">
                {world.stored} / {world.gate.tactical_systems ?? 50}
              </dd>
            </div>
            <div className="world-kv__row">
              <dt>shapes × temperaments</dt>
              <dd className="mono">
                {world.formations.length} × {world.temperaments.length}
              </dd>
            </div>
            <div className="world-kv__row">
              <dt>catalogue fingerprint</dt>
              <dd className="mono">{world.catalogue_fingerprint.slice(0, 16)}…</dd>
            </div>
            <div className="world-kv__row">
              <dt>ready</dt>
              <dd className="mono">{String(world.ready)}</dd>
            </div>
            <div className="world-kv__row">
              <dt>auto-sync</dt>
              <dd className="mono">{String(world.auto_sync)}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.7rem" }}>
            {world.note}
          </p>
        </Panel>

        <Panel eyebrow="The eight measurements" title="Every figure on this site, and its formula">
          {firstDetail?.ok ? (
            <div className="stack-sm">
              <MetricTable metrics={firstDetail.data.metrics_in} />
              <p className="muted world-section-note">
                These are the in-possession numbers of one row — {firstDetail.data.name}. Each system&apos;s page prints all eight for both
                phases, and a measure is never printed without the rule that produced it.
              </p>
            </div>
          ) : (
            <span className="unavailable">{firstDetail?.message ?? "The metrics table needs at least one stored system."}</span>
          )}
        </Panel>
      </div>

      {list.ok && (
        <>
          <div className="grid grid-2">
            <Panel eyebrow={tc("filter")} title="By shape">
              <FilterChips active={query.formation} base={BASE} label="Shape" options={world.formations} param="formation" query={query} />
            </Panel>
            <Panel eyebrow={tc("filter")} title="By temperament">
              <FilterChips
                active={query.temperament}
                base={BASE}
                label="Temperament"
                options={world.temperaments}
                param="temperament"
                query={query}
              />
            </Panel>
          </div>

          {list.data.items.length === 0 ? (
            <div className="empty">
              <strong>No system matches those filters</strong>
              <span className="muted">The catalogue holds {world.stored} rows; the filter is what is empty.</span>
              <Link className="btn btn--sm" href={BASE}>
                Clear filters
              </Link>
            </div>
          ) : (
            <section className="stack">
              <div className="between wrap">
                <h2 className="h2">Systems</h2>
                <BandLegend />
              </div>
              <div className="tac-cards">
                {list.data.items.map((item) => (
                  <SystemCard item={item} key={item.slug} />
                ))}
              </div>
            </section>
          )}

          <WorldPager build={(next) => buildHref(BASE, query, { page: String(next) })} page={page} pages={list.data.pages} total={list.data.total} />
        </>
      )}

      {!list.ok && <div className="notice notice--warn">{list.message}</div>}

      {firstDetail?.ok && (
        <Panel eyebrow={`${firstDetail.data.name} · in possession`} title="What a board looks like">
          <div className="tac-boards">
            <Pitch
              caption={`${firstDetail.data.phase_in.length} positions · metres, 68 × 105 (Law 1) · attack upward`}
              slots={firstDetail.data.phase_in}
              title={`${firstDetail.data.name} in possession`}
            />
            <div className="stack-sm">
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                Each card above prints three of its measured numbers; opening a system draws both phases, lists all eight measures with
                their formulas, and offers the six counterfactuals. The press line sits at {firstDetail.data.press_line_y} m and the
                defending block is {firstDetail.data.block_depth} m deep — those two authored values are what the out-of-possession board
                is derived from.
              </p>
              <p className="muted world-section-note">
                This one is {firstDetail.data.formation} under {firstDetail.data.temperament_label.toLowerCase()}. Compare the same shape
                under a different temperament to see the trade: the same eleven players, measured both ways.
              </p>
              <Link className="btn btn--sm" href={firstDetail.data.path}>
                Open {firstDetail.data.name}
              </Link>
              <Link className="btn btn--ghost btn--sm" href="/tactics/compare">
                Open the comparison board
              </Link>
            </div>
          </div>
        </Panel>
      )}

      <Provenance provenance={world} />
    </div>
  );
}
