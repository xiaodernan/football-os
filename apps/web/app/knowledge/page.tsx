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

export const metadata: Metadata = pageMetadata({
  title: "Football Knowledge",
  description:
    "The project-authored football knowledge base: browse the library, run hybrid retrieval, and ask questions answered only from cited passages.",
  path: "/knowledge",
});

const SECTIONS = [
  { id: "library", text: "Library" },
  { id: "search", text: "Search" },
  { id: "ask", text: "Ask" },
];

/** The library corpus is authored for this project; only answer generation is in demo mode. */
function AuthoredBadge() {
  return (
    <span className="badge badge--authored" title="Every document here was written for this project — no external text is reproduced. This is not demo data.">
      PROJECT AUTHORED
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
        <p className="eyebrow">Football Knowledge · RAG</p>
        <h1 className="h1">The football knowledge base</h1>
        <p className="lede">
          {statusResult.ok
            ? `${statusResult.data.documents} project-authored documents, ${statusResult.data.chunks} indexed passages. `
            : "Browse the library, "}
          Search runs hybrid retrieval over the corpus; Ask answers only from passages it can cite. The documents are real
          editorial content — what runs in demo mode is the answer generation, not the library.
        </p>
      </div>

      {statusResult.ok && statusResult.data.demo_mode && (
        <div className="notice notice--warn" style={{ fontSize: "0.85rem" }}>
          <span className="badge badge--demo" title="No language-model key is configured — ask/search answers are assembled extractively from the cited passages, never generated.">
            {tc("demoMode")}
          </span>{" "}
          Answer generation is running without a language model ({String(statusResult.data.providers.reranker ?? "")} reranker,{" "}
          {statusResult.data.embedding_models.join(", ") || "no"} embeddings). Retrieval and citations are fully live.
        </div>
      )}

      <nav className="kn-tabs" aria-label="Knowledge sections">
        {SECTIONS.map((section) => (
          <a className="kn-tabs__link" href={`#${section.id}`} key={section.id}>
            {section.text}
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
                  {count} document{count === 1 ? "" : "s"}
                </span>
              </Link>
            ))}
        </div>
      )}

      <section id="library" className="stack">
        <Panel
          eyebrow="Library"
          title="Document library"
          action={<AuthoredBadge />}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              Read from <span className="mono">GET /knowledge/documents</span>. Provenance, difficulty and chunk counts are
              the API&rsquo;s own fields — nothing here is modelled or decorative.
            </span>
          }
        >
          {!docsResult.ok ? (
            <div className="notice notice--warn">
              {errorMessage(docsResult.error, "The document library is unavailable right now.")}
            </div>
          ) : (
            <div className="stack">
              <div className="between wrap" style={{ gap: "0.6rem" }}>
                <p className="muted" style={{ fontSize: "0.85rem" }}>
                  {docsResult.data.total} document{docsResult.data.total === 1 ? "" : "s"}
                  {category ? ` in ${category.replace(/_/g, " ")}` : ""}
                  {q ? ` matching “${q}”` : ""}.
                </p>
                <form method="get" action="/knowledge" className="kn-form-row">
                  <input type="hidden" name="category" value={category ?? ""} />
                  <label className="field" style={{ minWidth: "200px" }}>
                    <span className="field__label">Filter title / source</span>
                    <input className="input" id="klib-q" type="search" name="q" defaultValue={q ?? ""} placeholder="e.g. press, hamstring" />
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
                <Empty title="No documents match this filter" body="Clear the filter or pick another category." href="/knowledge" cta="Show the full library" />
              ) : (
                <div className="grid-2">
                  {docsResult.data.items.map((doc) => (
                    <Link key={doc.slug} href={`/knowledge/${encodeURIComponent(doc.slug)}`} className="kn-card">
                      <span className="h3">{doc.title}</span>
                      <span className="muted kn-card__summary upper">{doc.category.replace(/_/g, " ")} · difficulty {doc.difficulty}</span>
                      <div className="tag-list">
                        {doc.applies_to.slice(0, 4).map((role) => (
                          <span className="chip" key={role}>
                            {role}
                          </span>
                        ))}
                        <span className="chip">{doc.chunk_count} passages</span>
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
                          {doc.source} · last reviewed {formatDay(doc.last_reviewed)}
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
          title="Hybrid retrieval over the corpus"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              Every score, cosine similarity, bm25 value and reason is returned by{" "}
              <span className="mono">POST /knowledge/search</span>.
            </span>
          }
        >
          <KnowledgeSearch signedIn={signedIn} categories={docsResult.ok ? docsResult.data.categories : []} />
        </Panel>
      </section>

      <section id="ask" className="stack">
        <Panel
          eyebrow="Ask"
          title="Ask the library"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              Answers cite passages verbatim via <span className="mono">POST /knowledge/ask</span>. When the corpus cannot
              support an answer, it says so rather than inventing one.
            </span>
          }
        >
          <KnowledgeAsk signedIn={signedIn} categories={docsResult.ok ? docsResult.data.categories : []} />
        </Panel>
      </section>
    </div>
  );
}
