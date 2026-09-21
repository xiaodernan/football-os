import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

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
  return pageMetadata({
    title: article?.title ?? slug.replace(/-/g, " "),
    description: article
      ? `${article.summary} (generated report, claim class: ${article.claim_class})`
      : "Report from the FOOTBALL OS generated football world.",
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
  const path = `/news/${article.slug}`;
  const paragraphs = body.split(/\n+/).filter((line) => line.trim().length > 0);

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world/news", label: "All reports" }}
        eyebrow={`Football World · ${article.category.replace(/_/g, " ")} · ${formatMoment(article.published_at)}`}
        lede={article.summary}
        provenance={result.data}
        title={article.title}
      >
        <div className="row wrap" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
          <ClaimChip claimClass={article.claim_class} />
          <OriginBadge provenance={article} />
          <span className="chip mono">source: {article.source_name}</span>
          {article.author && <span className="chip">by {article.author}</span>}
          <span className="chip">{article.season}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          headline: article.title,
          description: `${article.summary} Generated content — claim class ${article.claim_class}.`,
          url: absolute(path),
          mainEntityOfPage: { "@type": "WebPage", "@id": absolute(path) },
          datePublished: article.published_at,
          dateModified: article.published_at,
          author: { "@type": "Organization", name: article.source_name },
          publisher: { "@type": "Organization", name: "FOOTBALL OS generated world" },
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
            <p className="eyebrow">Claim class · {article.claim_class}</p>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {article.claim_class === "fact"
                ? "A statement about rows in the generated dataset — it can be checked against the tables linked below."
                : article.claim_class === "analysis"
                  ? "An interpretation of those rows, not a neutral report of them."
                  : "Speculation generated inside the dataset. Nothing here predicts or describes a real event."}
            </p>
            <p className="muted world-section-note">{editorialNote}</p>
          </div>
        </footer>
      </article>

      <div className="grid grid-2">
        <Panel eyebrow="Linked rows" title="What this report is about">
          <div className="stack">
            {related.length > 0 ? (
              <div className="tag-list">
                {related.map((entity) => (
                  <RefLink target={entity} key={`${entity.type}-${entity.slug}`} />
                ))}
              </div>
            ) : (
              <span className="unavailable">No entity link is stored for this article.</span>
            )}
            <p className="muted world-section-note">
              Links come from <span className="mono">news_article_links</span>, the same rows the API filters on — not from a keyword guess
              made in the browser.
            </p>
          </div>
        </Panel>

        <Panel eyebrow="Record" title="Editorial fields">
          <KeyValueGrid
            rows={[
              [
                "Canonical path",
                <Link className="world-link mono" href={path} key="canonical-path">
                  {article.url ?? path}
                </Link>,
              ],
              ["Category", article.category],
              ["Claim class", article.claim_class],
              ["Season", article.season],
              ["Published", <span className="mono" key="published">{formatMoment(article.published_at)}</span>],
              ["Source", <span className="mono" key="source">{article.source_name}</span>],
              ["Author", article.author ?? <span className="unavailable">not attributed</span>],
              ["Topics", article.topics.length > 0 ? article.topics.join(", ") : <span className="unavailable">none</span>],
            ]}
          />
        </Panel>
      </div>

      <Provenance provenance={result.data} />
    </div>
  );
}
