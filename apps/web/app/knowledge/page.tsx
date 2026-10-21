import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Empty, Panel } from "@/components/ui";
import { KnowledgeAsk } from "@/app/knowledge/KnowledgeAsk";
import { KnowledgeSearch } from "@/app/knowledge/KnowledgeSearch";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import { pageMetadata } from "@/lib/site";
import type { KnowledgeDocumentList, KnowledgeStatus } from "@/lib/types";

import "./knowledge.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("knowledge");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/knowledge",
  });
}

const SECTIONS = [
  { id: "library", key: "tabLibrary" },
  { id: "search", key: "tabSearch" },
  { id: "ask", key: "tabAsk" },
] as const;

/** The library corpus is authored for this project; only answer generation is in demo mode. */
async function AuthoredBadge() {
  const t = await getTranslations("knowledge");
  return (
    <span className="badge badge--authored" title={t("authoredBadgeTitle")}>
      {t("authoredBadge")}
    </span>
  );
}

function formatDay(iso: string | null): string {
  if (!iso) return "—";
  const stamp = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp);
}

export default async function KnowledgePage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; q?: string }>;
}) {
  const user = await currentUser();
  const params = await searchParams;
  const category = params.category;
  const q = params.q;
  const tc = await getTranslations("common");
  const t = await getTranslations("knowledge");

  // Library + status are public reads (no bearer token on the backend), so this renders
  // for a signed-out visitor; only search/ask need the session, handled in the client halves.
  const [statusResult, docsResult] = await Promise.all([
    serverFetch<KnowledgeStatus>("/knowledge/status"),
    serverFetch<KnowledgeDocumentList>("/knowledge/documents", { query: { category, q } }),
  ]);

  const signedIn = Boolean(user);

  return (
    <div className="container page stack">
      <div>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">
          {statusResult.ok
            ? t("ledeCounts", { documents: statusResult.data.documents, chunks: statusResult.data.chunks })
            : t("ledeNoCounts")}
          {t("ledeRest")}
        </p>
      </div>

      {statusResult.ok && statusResult.data.demo_mode && (
        <div className="notice notice--warn" style={{ fontSize: "0.85rem" }}>
          <span className="badge badge--demo" title={t("noModelKeyTitle")}>
            {tc("demoMode")}
          </span>{" "}
          {t("demoNotice", {
            reranker: String(statusResult.data.providers.reranker ?? ""),
            embeddings: statusResult.data.embedding_models.join(", ") || "no",
          })}
        </div>
      )}

      <nav className="kn-tabs" aria-label={t("sectionsLabel")}>
        {SECTIONS.map((section) => (
          <a className="kn-tabs__link" href={`#${section.id}`} key={section.id}>
            {t(section.key)}
          </a>
        ))}
      </nav>

      {statusResult.ok && (
        <div className="grid grid-4">
          {Object.entries(statusResult.data.categories)
            .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            .map(([name, count]) => (
              <Link key={name} href={`/knowledge?category=${encodeURIComponent(name)}`} className="kn-card">
                <span className="h3 upper">{name.replace(/_/g, " ")}</span>
                <span className="muted kn-card__summary">
                  {t("resultLineOne", { total: count, s: count === 1 ? "" : "s" })}
                </span>
              </Link>
            ))}
        </div>
      )}

      <section id="library" className="stack">
        <Panel
          eyebrow={t("libraryEyebrow")}
          title={t("libraryTitle")}
          action={<AuthoredBadge />}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("libraryFooter")}
            </span>
          }
        >
          {!docsResult.ok ? (
            <div className="notice notice--warn">
              {errorMessage(docsResult.error, t("libraryUnavailable"))}
            </div>
          ) : (
            <div className="stack">
              <div className="between wrap" style={{ gap: "0.6rem" }}>
                <p className="muted" style={{ fontSize: "0.85rem" }}>
                  {t("resultLine", {
                    total: docsResult.data.total,
                    s: docsResult.data.total === 1 ? "" : "s",
                    category: category ? ` in ${category.replace(/_/g, " ")}` : "",
                    query: q ? ` matching “${q}”` : "",
                  })}
                </p>
                <form method="get" action="/knowledge" className="kn-form-row">
                  <input type="hidden" name="category" value={category ?? ""} />
                  <label className="field" style={{ minWidth: "200px" }}>
                    <span className="field__label">{t("filterLabel")}</span>
                    <input className="input" id="klib-q" type="search" name="q" defaultValue={q ?? ""} placeholder={t("queryPlaceholder")} />
                  </label>
                  <button type="submit" className="btn btn--primary">
                    {tc("search")}
                  </button>
                  {(category || q) && (
                    <Link className="btn btn--ghost" href="/knowledge">
                      {tc("clear")}
                    </Link>
                  )}
                </form>
              </div>

              <div className="row wrap" style={{ gap: "0.4rem" }}>
                <Link className={`chip ${!category ? "chip--accent" : ""}`} href={q ? `/knowledge?q=${encodeURIComponent(q)}` : "/knowledge"}>
                  {tc("all")}
                </Link>
                {docsResult.data.categories.map((name) => (
                  <Link
                    key={name}
                    className={`chip kn-filter-chip ${category === name ? "chip--accent" : ""}`}
                    href={`/knowledge?category=${encodeURIComponent(name)}${q ? `&q=${encodeURIComponent(q)}` : ""}`}
                  >
                    {name.replace(/_/g, " ")}
                  </Link>
                ))}
              </div>

              {docsResult.data.items.length === 0 ? (
                <Empty title={t("noMatchesTitle")} body={t("noMatchesBody")} href="/knowledge" cta={t("showFullLibrary")} />
              ) : (
                <div className="grid-2">
                  {docsResult.data.items.map((doc) => (
                    <Link key={doc.slug} href={`/knowledge/${encodeURIComponent(doc.slug)}`} className="kn-card">
                      <span className="h3">{doc.title}</span>
                      <span className="muted kn-card__summary upper">{t("cardMeta", { category: doc.category.replace(/_/g, " "), difficulty: doc.difficulty })}</span>
                      <div className="tag-list">
                        {doc.applies_to.slice(0, 4).map((role) => (
                          <span className="chip" key={role}>
                            {role}
                          </span>
                        ))}
                        <span className="chip">{t("passagesCount", { count: doc.chunk_count })}</span>
                      </div>
                      {doc.tags.length > 0 && (
                        <div className="tag-list">
                          {doc.tags.slice(0, 5).map((tag) => (
                            <span className="chip" key={tag}>
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="kn-prov">
                        <AuthoredBadge />
                        <span className="kn-prov__text">
                          {t("cardSource", { source: doc.source, date: formatDay(doc.last_reviewed) })}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}
        </Panel>
      </section>

      <section id="search" className="stack">
        <Panel
          eyebrow={tc("search")}
          title={t("searchEyebrow")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("searchFooter")}
            </span>
          }
        >
          <KnowledgeSearch signedIn={signedIn} categories={docsResult.ok ? docsResult.data.categories : []} />
        </Panel>
      </section>

      <section id="ask" className="stack">
        <Panel
          eyebrow={t("askEyebrow")}
          title={t("askLibrary")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("askFooter")}
            </span>
          }
        >
          <KnowledgeAsk signedIn={signedIn} categories={docsResult.ok ? docsResult.data.categories : []} />
        </Panel>
      </section>
    </div>
  );
}
