import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { OriginBadge, Provenance, WorldHead, WorldUnavailable, JsonLd } from "@/components/world";
import { absolute, SITE_NAME } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { WorldSearchResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

/**
 * A query page is not a content page: it is the same thin shell with a different word in it, so
 * it stays out of the index while its result links remain crawlable.
 */
export async function generateMetadata(): Promise<Metadata> {
  const tw = await getTranslations("world");
  return {
    title: tw("searchMetaTitle"),
    description: tw("searchMetaDescription"),
    robots: { index: false, follow: true },
    alternates: { canonical: absolute("/world/search") },
  };
}

const TYPES = ["competitions", "teams", "players", "matches", "news"] as const;

export default async function WorldSearchPage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const term = query.q ?? "";
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const result = term ? await readWorld<WorldSearchResponse>("/world/search", { q: term, types: query.types, limit_rows: 40 }) : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tw("searchEyebrow")}
        title={tw("searchTitle")}
        lede={tw("searchLede")}
        provenance={result?.ok ? result.data : undefined}
      >
        <form action="/world/search" method="get" className="world-search" style={{ marginTop: "1rem" }} role="search">
          <input
            aria-label={tw("searchAriaLabel")}
            className="input"
            defaultValue={term}
            maxLength={120}
            name="q"
            placeholder={tw("searchPlaceholder")}
            type="search"
          />
          <select aria-label={tw("searchTypesAria")} className="select" defaultValue={query.types ?? ""} name="types">
            <option value="">{tw("searchAllTypes")}</option>
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button className="btn btn--primary" type="submit">
            {tc("search")}
          </button>
        </form>
      </WorldHead>

      {!term && (
        <div className="empty">
          <strong>{tw("searchEmptyTitle")}</strong>
          <span className="muted">
            {tw("searchEmptyNote")}
          </span>
        </div>
      )}

      {result && !result.ok && result.status === 422 && (
        <div className="notice notice--warn">
          {result.message} {tw("searchTooLong")}
        </div>
      )}
      {result && !result.ok && result.status !== 422 && <WorldUnavailable message={result.message} />}

      {result?.ok && (
        <>
          <JsonLd
            data={{
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: SITE_NAME,
              url: absolute("/"),
              potentialAction: {
                "@type": "SearchAction",
                target: { "@type": "EntryPoint", urlTemplate: `${absolute("/world/search")}?q={search_term_string}` },
                "query-input": "required name=search_term_string",
              },
            }}
          />
          <Panel
            eyebrow={tw("searchHitsEyebrow", {
              total: result.data.total,
              query: result.data.query,
            })}
            title={tw("searchResultsTitle")}
            action={
              result.data.types.length > 0 ? (
                <div className="tag-list">
                  {result.data.types.map((type) => (
                    <Link className="chip" href={`/world/search?q=${encodeURIComponent(result.data.query)}&types=${type}`} key={type}>
                      {type}
                    </Link>
                  ))}
                </div>
              ) : null
            }
          >
            {result.data.results.length === 0 ? (
              <div className="stack-sm">
                <p className="muted">
                  {tw("searchEmpty", { query: result.data.query })}
                </p>
                <p className="muted world-section-note">{result.data.note}</p>
              </div>
            ) : (
              <ul className="world-list">
                {result.data.results.map((hit) => (
                  <li className="world-fixture" key={`${hit.type}-${hit.slug}`}>
                    <div className="world-fixture__when">
                      <span className="world-pos">{hit.type}</span>
                      <span className="world-fixture__round mono">{tw("scoreChip", { score: hit.score })}</span>
                    </div>
                    <div className="world-fixture__teams" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.2rem" }}>
                      <Link className="world-link" href={hit.path}>
                        {hit.title}
                      </Link>
                      <span className="muted" style={{ fontWeight: 400, fontSize: "0.85rem" }}>
                        {hit.subtitle}
                      </span>
                      <span className="muted mono" style={{ fontSize: "0.75rem" }}>
                        {hit.reasons.join(" · ")}
                      </span>
                    </div>
                    <div className="world-fixture__score">
                      <OriginBadge provenance={hit} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Provenance provenance={result.data} />
        </>
      )}
    </div>
  );
}
