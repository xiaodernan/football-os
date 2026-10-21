import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { ClaimChip, JsonLd, KeyValueGrid, OriginBadge, Provenance, RefLink, WorldHead, WorldUnavailable, formatMoment } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { NewsDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return readWorld<NewsDetail>(`/world/news/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const article = result.ok ? result.data.article : null;
  const t = await getTranslations("worldNews");
  return pageMetadata({
    title: article?.title ?? slug.replace(/-/g, " "),
    description: article
      ? t("metaDescription", { summary: article.summary, claim: article.claim_class })
      : t("metaDescriptionFallback"),
    path: `/news/${slug}`,
    type: "article",
  });
}

export default async function NewsDetailPage({ params }: Props) {
  const { slug } = await params;
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { article, body, related, editorial_note: editorialNote } = result.data;
  const t = await getTranslations("worldNews");
  const path = `/news/${article.slug}`;
  const paragraphs = body.split(/\n+/).filter((line) => line.trim().length > 0);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/news", label: t("backLabel") }}
        eyebrow={t("eyebrow", {
          category: article.category.replace(/_/g, " "),
          published: formatMoment(article.published_at),
        })}
        lede={article.summary}
        provenance={result.data}
        title={article.title}
      >
        <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <ClaimChip claimClass={article.claim_class} />
          <OriginBadge provenance={article} />
          <span className="chip mono">{t("chipSource", { source: article.source_name })}</span>
          {article.author && <span className="chip">{t("chipAuthor", { author: article.author })}</span>}
          <span className="chip">{article.season}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          headline: article.title,
          description: t("jsonLdDescription", { summary: article.summary, claim: article.claim_class }),
          url: absolute(path),
          mainEntityOfPage: { "@type": "WebPage", "@id": absolute(path) },
          datePublished: article.published_at,
          dateModified: article.published_at,
          author: { "@type": "Organization", name: article.source_name },
          publisher: { "@type": "Organization", name: t("publisherName") },
          inLanguage: "en",
          isAccessibleForFree: true,
          articleSection: article.category,
          ...(article.topics.length > 0 ? { keywords: article.topics.join(", ") } : {}),
        }}
      />

      <article className="panel">
        <div className="panel__body news-body">
          {paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        <footer className="panel__foot">
          <div className="stack-sm">
            <p className="eyebrow">{t("claimClassEyebrow", { claim: article.claim_class })}</p>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {article.claim_class === "fact"
                ? t("claimFact")
                : article.claim_class === "analysis"
                  ? t("claimAnalysis")
                  : t("claimSpeculation")}
            </p>
            <p className="muted world-section-note">{editorialNote}</p>
          </div>
        </footer>
      </article>

      <div className="grid grid-2">
        <Panel eyebrow={t("linkedEyebrow")} title={t("linkedTitle")}>
          <div className="stack">
            {related.length > 0 ? (
              <div className="tag-list">
                {related.map((entity) => (
                  <RefLink target={entity} key={`${entity.type}-${entity.slug}`} />
                ))}
              </div>
            ) : (
              <span className="unavailable">{t("noEntityLink")}</span>
            )}
            <p className="muted world-section-note">
              {t("linksNote", { table: "news_article_links" })}
            </p>
          </div>
        </Panel>

        <Panel eyebrow={t("recordEyebrow")} title={t("recordTitle")}>
          <KeyValueGrid
            rows={[
              [
                t("rowCanonicalPath"),
                <Link className="world-link mono" href={path} key="canonical-path">
                  {article.url ?? path}
                </Link>,
              ],
              [t("rowCategory"), article.category],
              [t("rowClaimClass"), article.claim_class],
              [t("rowSeason"), article.season],
              [t("rowPublished"), <span className="mono" key="published">{formatMoment(article.published_at)}</span>],
              [t("rowSource"), <span className="mono" key="source">{article.source_name}</span>],
              [t("rowAuthor"), article.author ?? <span className="unavailable">{t("notAttributed")}</span>],
              [t("rowTopics"), article.topics.length > 0 ? article.topics.join(", ") : <span className="unavailable">{t("rowNoTopics")}</span>],
            ]}
          />
        </Panel>
      </div>

      <Provenance provenance={result.data} />
    </div>
  );
}
