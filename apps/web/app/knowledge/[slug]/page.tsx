import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";
import { absolute, pageMetadata, SITE_NAME } from "@/lib/site";
import type { KnowledgeDocumentDetail } from "@/lib/types";

import "../knowledge.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await serverFetch<KnowledgeDocumentDetail>(`/knowledge/documents/${encodeURIComponent(slug)}`);
  const title = result.ok ? result.data.title : slug.replace(/-/g, " ");
  const description = result.ok
    ? `${result.data.category.replace(/_/g, " ")} · ${result.data.chunk_count} cited passages · ${result.data.source}`
    : "Football knowledge document.";
  return pageMetadata({ title, description, path: `/knowledge/${slug}`, type: "article" });
}

function formatDay(iso: string | null): string {
  if (!iso) return "—";
  const stamp = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp);
}

export default async function KnowledgeDocumentPage({ params }: Props) {
  const { slug } = await params;
  const tc = await getTranslations("common");
  const result = await serverFetch<KnowledgeDocumentDetail>(`/knowledge/documents/${encodeURIComponent(slug)}`);

  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return (
      <div className="container page stack">
        <h1 className="h1">Knowledge document</h1>
        <div className="notice notice--warn">{errorMessage(result.error, "This document could not be loaded right now.")}</div>
      </div>
    );
  }

  const doc = result.data;

  return (
    <div className="container page stack">
      <div>
        <Link href="/knowledge" className="muted" style={{ fontSize: "0.85rem" }}>
          ← Back to the library
        </Link>
        <div className="between wrap" style={{ gap: "0.6rem", marginTop: "0.5rem" }}>
          <div>
            <p className="eyebrow">{doc.category.replace(/_/g, " ")}</p>
            <h1 className="h1">{doc.title}</h1>
          </div>
          <span className="badge badge--authored" title="Written for this project — no external text reproduced. This is not demo data.">
            PROJECT AUTHORED
          </span>
        </div>
        <div className="tag-list" style={{ marginTop: "0.6rem" }}>
          <span className="chip">difficulty {doc.difficulty}</span>
          <span className="chip">{doc.chunk_count} passages</span>
          <span className="chip">{doc.char_count.toLocaleString()} characters</span>
          <span className="chip">editorial confidence: {doc.editorial_confidence}</span>
          <span className="chip">last reviewed {formatDay(doc.last_reviewed)}</span>
        </div>
        {doc.applies_to.length > 0 && (
          <div className="tag-list" style={{ marginTop: "0.4rem" }}>
            {doc.applies_to.map((role) => (
              <span className="chip chip--accent" key={role}>
                {role}
              </span>
            ))}
          </div>
        )}
      </div>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            headline: doc.title,
            description: `Project-authored ${doc.category.replace(/_/g, " ")} document with ${doc.chunk_count} indexed passages.`,
            url: absolute(`/knowledge/${doc.slug}`),
            mainEntityOfPage: { "@type": "WebPage", "@id": absolute(`/knowledge/${doc.slug}`) },
            author: { "@type": "Organization", name: SITE_NAME },
            publisher: { "@type": "Organization", name: SITE_NAME },
            inLanguage: "en",
            isAccessibleForFree: true,
            ...(doc.last_reviewed ? { dateModified: doc.last_reviewed } : {}),
            ...(doc.tags.length > 0 ? { keywords: doc.tags.join(", ") } : {}),
          }),
        }}
      />

      <Panel
        eyebrow="Provenance"
        title="Where this text comes from"
        footer={
          <span className="kn-prov__text">
            data_origin: <span className="mono">{doc.data_origin}</span> · is_demo_data:{" "}
            <span className="mono">{String(doc.is_demo_data)}</span> · embedding model: <span className="mono">{doc.embedding_model}</span>
            {" · "}
            {doc.source}
          </span>
        }
      >
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          This document is project-authored editorial content, not demo data. The <span className="mono">{tc("demoMode")}</span>{" "}
          badge elsewhere on the site applies to how answers are generated, never to these passages. Use the anchors below —
          a citation link like <span className="mono">#0</span> jumps to the exact passage it quotes.
        </p>
        {doc.tags.length > 0 && (
          <div className="tag-list" style={{ marginTop: "0.6rem" }}>
            {doc.tags.map((tag) => (
              <span className="chip" key={tag}>
                #{tag}
              </span>
            ))}
          </div>
        )}
      </Panel>

      <section className="stack">
        <h2 className="h2">Passages</h2>
        <div className="kn-sections">
          {doc.sections.map((section) => (
            <article className="kn-section" id={String(section.ordinal)} key={section.ordinal}>
              <div className="kn-section__head">
                <span className="h3">
                  <a href={`#${section.ordinal}`} className="mono" style={{ color: "var(--accent)" }}>
                    #{section.ordinal}
                  </a>{" "}
                  {section.heading}
                </span>
                <span className="chip">{section.char_count} chars</span>
              </div>
              <p className="kn-section__text">{section.text}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
