import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { ClaimChip, FilterChips, OriginBadge, Provenance, RefLink, WorldHead, WorldPager, WorldUnavailable, formatMoment } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { buildHref, cleanParams, pageOf, readWorld } from "@/lib/world";
import type { NewsList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return pageMetadata({
    title: tw("sectionReportsLabel"),
    description: tw("metaNews"),
    path: "/world/news",
  });
}

const BASE = "/world/news";
const PAGE_SIZE = 20;

export default async function NewsPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const page = pageOf(query);
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = await readWorld<NewsList>("/world/news", {
    category: query.category,
    claim_class: query.claim_class,
    q: query.q,
    page,
    page_size: PAGE_SIZE,
  });

  if (!result.ok) return <WorldUnavailable message={result.message} />;
  const { items, categories, claim_classes: claimClasses, total, pages } = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("title")}
        lede={tw("newsLede", { count: total.toLocaleString("en-GB") })}
        provenance={result.data}
        title={tw("sectionReportsLabel")}
      />

      <div className="grid grid-2">
        <Panel eyebrow={tc("filter")} title={tw("newsByKindTitle")}>
          <FilterChips active={query.category} base={BASE} label={tw("newsCategoryLabel")} options={categories} param="category" query={query} />
        </Panel>
        <Panel eyebrow={tc("filter")} title={tw("newsByClaimTitle")}>
          <FilterChips active={query.claim_class} base={BASE} label={tw("newsClaimClassLabel")} options={claimClasses} param="claim_class" query={query} />
        </Panel>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <strong>{tw("newsEmptyTitle")}</strong>
          <Link className="btn btn--sm" href={BASE}>
            {tw("newsClearFilters")}
          </Link>
        </div>
      ) : (
        <ul className="stack">
          {items.map((article) => (
            <li className="panel" key={article.id}>
              <div className="panel__body stack-sm">
                <div className="between wrap" style={{ gap: "0.5rem" }}>
                  <p className="eyebrow">
                    {article.category.replace(/_/g, " ")} · {formatMoment(article.published_at)}
                  </p>
                  <div className="row wrap" style={{ gap: "0.4rem" }}>
                    <ClaimChip claimClass={article.claim_class} />
                    <OriginBadge provenance={article} />
                  </div>
                </div>
                <h2 className="h3">
                  <Link className="world-link" href={article.path}>
                    {article.title}
                  </Link>
                </h2>
                <p className="muted" style={{ fontSize: "0.9rem" }}>
                  {article.summary}
                </p>
                {article.entity_links.length > 0 && (
                  <div className="tag-list">
                    {article.entity_links.slice(0, 6).map((entity) => (
                      <RefLink target={entity} key={`${entity.type}-${entity.slug}`} />
                    ))}
                  </div>
                )}
                <p className="muted world-section-note">
                  {tw("newsSourceNote", { source: article.source_name })}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <WorldPager build={(next) => buildHref(BASE, query, { page: String(next) })} page={page} pages={pages} total={total} />
      <Provenance provenance={result.data} />
    </div>
  );
}
