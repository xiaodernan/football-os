"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import { KNOWLEDGE_DIFFICULTIES, KNOWLEDGE_MODES, KNOWLEDGE_POSITIONS, type KnowledgeSearchResponse } from "@/lib/types";

function fmt(value: number | undefined, digits = 3): string {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export function KnowledgeSearch({ signedIn, categories }: { signedIn: boolean; categories: string[] }) {
  const t = useTranslations("common");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<string>("hybrid");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [position, setPosition] = useState("");
  const [busy, setBusy] = useState(false);
  const [promptSignIn, setPromptSignIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<KnowledgeSearchResponse | null>(null);

  async function run() {
    const trimmed = query.trim();
    if (trimmed.length < 2 || busy) return;
    setBusy(true);
    setError(null);
    setPromptSignIn(false);
    const result = await browserFetch<KnowledgeSearchResponse>("/knowledge/search", {
      method: "POST",
      body: {
        query: trimmed,
        mode,
        top_k: 5,
        category: category || undefined,
        difficulty: difficulty || undefined,
        position: position || undefined,
      },
    });
    if (!result.ok) {
      setData(null);
      if (result.status === 401) setPromptSignIn(true);
      else setError(errorMessage(result.error, "Search failed."));
    } else {
      setData(result.data);
    }
    setBusy(false);
  }

  if (!signedIn) {
    return (
      <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
        Search reads the whole corpus through your authenticated session.{" "}
        <Link className="kn-ref" href="/login?next=%2Fknowledge">
          Sign in
        </Link>{" "}
        to run it. The library above stays open without an account.
      </div>
    );
  }

  const answerability = data?.answerability;

  return (
    <div className="stack">
      <div className="kn-form-row">
        <label className="field" style={{ flex: "2 1 240px" }}>
          <span className="field__label">Query</span>
          <input
            className="input"
            id="ksearch-query"
            type="search"
            value={query}
            maxLength={400}
            placeholder="e.g. how do teams press high"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void run();
            }}
          />
        </label>
        <label className="field">
          <span className="field__label">Mode</span>
          <select className="select" value={mode} onChange={(event) => setMode(event.target.value)}>
            {KNOWLEDGE_MODES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Category</span>
          <select className="select" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">all</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Difficulty</span>
          <select className="select" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
            <option value="">any</option>
            {KNOWLEDGE_DIFFICULTIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Position</span>
          <select className="select" value={position} onChange={(event) => setPosition(event.target.value)}>
            <option value="">any</option>
            {KNOWLEDGE_POSITIONS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn--primary" onClick={run} disabled={busy || query.trim().length < 2}>
          {busy ? "Searching…" : "Run search"}
        </button>
      </div>

      {promptSignIn && (
        <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
          Your session expired.{" "}
          <Link className="kn-ref" href="/login?next=%2Fknowledge">
            Sign in again
          </Link>{" "}
          to keep searching.
        </div>
      )}
      {error && <div className="notice notice--warn">{error}</div>}

      {data && (
        <div className="stack">
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {data.demo_mode ? (
              <span className="badge badge--demo" title="No language-model key is configured; ranking uses the feature reranker and results are shown verbatim.">
                {t("demoMode")}
              </span>
            ) : (
              <span className="badge badge--live">AI-ranked</span>
            )}
            <span className="chip">{data.mode}</span>
            <span className="chip mono">{data.retrieval_backend}</span>
            <span className="chip">{data.scanned_chunks} chunks scanned</span>
            <span className="chip">top score {fmt(data.top_score)}</span>
            <span className="chip">confidence {Math.round(data.confidence * 100)}%</span>
          </div>

          <div
            className="notice"
            style={{
              fontSize: "0.85rem",
              background: answerability?.answerable ? "var(--accent-soft)" : "rgba(255, 182, 72, 0.09)",
              borderColor: answerability?.answerable ? "rgba(53, 240, 164, 0.3)" : "rgba(255, 182, 72, 0.35)",
            }}
          >
            <strong>{answerability?.answerable ? "The corpus covers this query" : "Weak coverage for this query"}</strong>
            <div className="kn-explain">
              {answerability
                ? `Rare terms from your query found in the top passage: ${answerability.discriminative_matches.length}/${answerability.discriminative_terms.length} (coverage ${fmt(
                    answerability.discriminative_coverage,
                    2,
                  )}, floor ${fmt(answerability.coverage_floor, 2)}).`
                : ""}
            </div>
          </div>

          <ReasonList items={data.reasons} title="Why these ranked this way" />

          <div className="stack">
            {data.results.length === 0 ? (
              <p className="muted">No passages matched the query with these filters.</p>
            ) : (
              data.results.map((hit) => (
                <div className="kn-result" key={hit.chunk_id}>
                  <div className="row wrap" style={{ gap: "0.6rem" }}>
                    <span className="kn-rank" aria-label={`Rank ${hit.rank}`}>
                      {hit.rank}
                    </span>
                    <div className="grow">
                      <Link className="h3" href={`/knowledge/${encodeURIComponent(hit.document_slug)}#${hit.ordinal}`}>
                        {hit.title}
                      </Link>
                      <div className="muted" style={{ fontSize: "0.82rem" }}>
                        {hit.heading} · {hit.category.replace(/_/g, " ")} · difficulty {hit.difficulty}
                      </div>
                    </div>
                  </div>
                  <p className="kn-excerpt">{hit.excerpt}</p>
                  <div className="kn-metrics">
                    <span className="chip">score {fmt(hit.score)}</span>
                    <span className="chip">cosine {fmt(hit.similarity)}</span>
                    <span className="chip">bm25 {fmt(hit.lexical)}</span>
                    {Object.entries(hit.features ?? {}).map(([feature, value]) => (
                      <span className="chip mono" key={feature}>
                        {feature} {typeof value === "number" ? value.toFixed(3) : "—"}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <p className="muted kn-explain">
            timings_ms {JSON.stringify(data.timings_ms)} · model <span className="mono">{data.model}</span> · provider{" "}
            <span className="mono">{data.provider}</span>
          </p>
          <p className="muted kn-disclaimer">{data.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
