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

// `generateMetadata` rather than a constant, so the tab title follows the reader's locale — same
// shape as the auth pages and /coach.
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("tactics");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/tactics",
  });
}

const BASE = "/tactics";
const PAGE_SIZE = 12;

export default async function TacticsIndexPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");
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
        detail={t("unavailableDetail")}
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
        back={{ href: "/world", label: tn("world") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={world}
        title={tn("tactics")}
      >
        <form action="/tactics" className="world-search" method="get" role="search" style={{ marginTop: "1rem" }}>
          <input
            aria-label={t("searchAriaLabel")}
            className="input"
            defaultValue={query.search ?? ""}
            maxLength={60}
            name="search"
            placeholder={t("searchPlaceholder")}
            type="search"
          />
          <button className="btn btn--primary" type="submit">
            {tc("search")}
          </button>
          <Link className="btn btn--ghost" href="/tactics/compare">
            {t("compareLink")}
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
        <Panel eyebrow={t("storeEyebrow")} title={t("storeTitle")}>
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>{t("labelStored")}</dt>
              <dd className="mono">
                {world.stored} / {world.gate.tactical_systems ?? 50}
              </dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelShapes")}</dt>
              <dd className="mono">
                {world.formations.length} × {world.temperaments.length}
              </dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelFingerprint")}</dt>
              <dd className="mono">{world.catalogue_fingerprint.slice(0, 16)}…</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelReady")}</dt>
              <dd className="mono">{String(world.ready)}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelAutoSync")}</dt>
              <dd className="mono">{String(world.auto_sync)}</dd>
            </div>
          </dl>
          <p className="muted world-section-note" style={{ marginTop: "0.7rem" }}>
            {world.note}
          </p>
        </Panel>

        <Panel eyebrow={t("metricsEyebrow")} title={t("metricsTitle")}>
          {firstDetail?.ok ? (
            <div className="stack-sm">
              <MetricTable metrics={firstDetail.data.metrics_in} />
              <p className="muted world-section-note">{t("metricsNote", { name: firstDetail.data.name })}</p>
            </div>
          ) : (
            <span className="unavailable">{firstDetail?.message ?? t("metricsUnavailable")}</span>
          )}
        </Panel>
      </div>

      {list.ok && (
        <>
          <div className="grid grid-2">
            <Panel eyebrow={tc("filter")} title={t("byShape")}>
              <FilterChips active={query.formation} base={BASE} label={t("shapeFilterLabel")} options={world.formations} param="formation" query={query} />
            </Panel>
            <Panel eyebrow={tc("filter")} title={t("byTemperament")}>
              <FilterChips
                active={query.temperament}
                base={BASE}
                label={t("temperamentFilterLabel")}
                options={world.temperaments}
                param="temperament"
                query={query}
              />
            </Panel>
          </div>

          {list.data.items.length === 0 ? (
            <div className="empty">
              <strong>{t("emptyTitle")}</strong>
              <span className="muted">{t("emptyNote", { count: world.stored })}</span>
              <Link className="btn btn--sm" href={BASE}>
                {t("clearFilters")}
              </Link>
            </div>
          ) : (
            <section className="stack">
              <div className="between wrap">
                <h2 className="h2">{t("systemsHeading")}</h2>
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
        <Panel eyebrow={t("boardEyebrow", { name: firstDetail.data.name })} title={t("boardTitle")}>
          <div className="tac-boards">
            <Pitch
              caption={t("pitchCaption", { count: firstDetail.data.phase_in.length })}
              slots={firstDetail.data.phase_in}
              title={t("pitchTitleIn", { name: firstDetail.data.name })}
            />
            <div className="stack-sm">
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {t("boardNote", { press_line: firstDetail.data.press_line_y, block_depth: firstDetail.data.block_depth })}
              </p>
              <p className="muted world-section-note">
                {t("boardCompareNote", { formation: firstDetail.data.formation, temperament: firstDetail.data.temperament_label.toLowerCase() })}
              </p>
              <Link className="btn btn--sm" href={firstDetail.data.path}>
                {t("openSystem", { name: firstDetail.data.name })}
              </Link>
              <Link className="btn btn--ghost btn--sm" href="/tactics/compare">
                {t("openCompare")}
              </Link>
            </div>
          </div>
        </Panel>
      )}

      <Provenance provenance={world} />
    </div>
  );
}
