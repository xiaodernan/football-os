"use client";

import Link from "next/link";
import { Fragment, useState, type ReactNode } from "react";

import { ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import { KNOWLEDGE_DIFFICULTIES, KNOWLEDGE_MODES, KNOWLEDGE_POSITIONS, type KnowledgeAskResponse, type KnowledgeCitation } from "@/lib/types";

function fmt(value: number | undefined, digits = 3): string {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

/** Turns inline [1], [2] … markers into anchors that jump to the matching citation card. */
function withRefs(text: string): ReactNode[] {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    if (!match) return <Fragment key={index}>{part}</Fragment>;
    const ref = match[1];
    return (
      <a key={index} className="kn-ref" href={`#cite-${ref}`} aria-label={`Go to citation ${ref}`}>
        {part}
      </a>
    );
  });
}

function CitationCard({ citation, index }: { citation: KnowledgeCitation; index: number }) {
  return (
    <div className="kn-cite" id={`cite-${index + 1}`}>
      <div className="between wrap" style={{ gap: "0.5rem" }}>
        <span className="h3">
          <span className="kn-ref">[{index + 1}]</span> {citation.title}
        </span>
        <span className="chip">score {fmt(citation.score)}</span>
      </div>
      <span className="muted" style={{ fontSize: "0.82rem" }}>
        {citation.section} · {citation.category.replace(/_/g, " ")} · cosine {fmt(citation.similarity)}
      </span>
      <p className="kn-cite__quote">&ldquo;{citation.quote}&rdquo;</p>
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <Link className="kn-ref" href={`/knowledge/${encodeURIComponent(citation.slug)}#${citation.ordinal}`}>
          Open this passage →
        </Link>
        <span className="kn-prov__text grow">{citation.source}</span>
      </div>
    </div>
  );
}

export function KnowledgeAsk({ signedIn, categories }: { signedIn: boolean; categories: string[] }) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [position, setPosition] = useState("");
  const [busy, setBusy] = useState(false);
  const [promptSignIn, setPromptSignIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KnowledgeAskResponse | null>(null);

  async function ask() {
    const trimmed = question.trim();
    if (trimmed.length < 3 || busy) return;
    setBusy(true);
    setError(null);
    setPromptSignIn(false);
    const response = await browserFetch<KnowledgeAskResponse>("/knowledge/ask", {
      method: "POST",
      body: {
        question: trimmed,
        mode,
        top_k: 5,
        category: category || undefined,
        difficulty: difficulty || undefined,
        position: position || undefined,
      },
    });
    if (!response.ok) {
      setResult(null);
      if (response.status === 401) setPromptSignIn(true);
      else setError(errorMessage(response.error, "The library could not answer that."));
    } else {
      setResult(response.data);
      setQuestion("");
    }
    setBusy(false);
  }

  if (!signedIn) {
    return (
      <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
        Asking the library uses your authenticated session.{" "}
        <Link className="kn-ref" href="/login?next=%2Fknowledge">
          Sign in
        </Link>{" "}
        to ask. You can still browse every document above without an account.
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="stack-sm">
        <label className="field">
          <span className="field__label">Your question</span>
          <textarea
            className="kn-textarea"
            id="kask-question"
            value={question}
            maxLength={500}
            placeholder="e.g. How should a team build out against a high press?"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <span className="field__hint">3–500 characters. Answers come only from passages the library can cite — nothing is generated from outside the corpus.</span>
        </label>

        <div className="kn-form-row">
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
        </div>

        <div>
          <button type="button" className="btn btn--primary" onClick={ask} disabled={busy || question.trim().length < 3}>
            {busy ? "Asking…" : "Ask the library"}
          </button>
        </div>
      </div>

      {promptSignIn && (
        <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
          Your session expired.{" "}
          <Link className="kn-ref" href="/login?next=%2Fknowledge">
            Sign in again
          </Link>{" "}
          to keep asking.
        </div>
      )}
      {error && <div className="notice notice--warn">{error}</div>}

      {result && (
        <div className="kn-answer-block stack">
          <p className="kn-answer-q">&ldquo;{result.question}&rdquo;</p>
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {result.demo_mode ? (
              <span className="badge badge--demo" title="No language-model key is configured; this answer is assembled extractively from the cited passages, not generated.">
                DEMO MODE · extractive answer
              </span>
            ) : (
              <span className="badge badge--live">AI-generated</span>
            )}
            <span className="chip">confidence {Math.round(result.confidence * 100)}%</span>
            <span className="chip mono">{result.model}</span>
            <span className="chip mono">{result.retrieval_backend}</span>
          </div>

          {result.answered ? (
            <div className="stack-sm">
              <span className="eyebrow">Answer</span>
              <p className="kn-answer">{withRefs(result.answer)}</p>
            </div>
          ) : (
            <div className="notice notice--warn">
              <span className="eyebrow" style={{ color: "var(--warn)" }}>
                No grounded answer
              </span>
              <p style={{ marginTop: "0.3rem" }}>{result.answer}</p>
            </div>
          )}

          <ReasonList items={result.reasons} title="Why this answer (or refusal)" />

          {result.citations.length > 0 && (
            <div className="stack-sm">
              <span className="eyebrow">Cited passages</span>
              {result.citations.map((citation, index) => (
                <CitationCard key={`${citation.chunk_id}-${index}`} citation={citation} index={index} />
              ))}
            </div>
          )}

          <p className="muted kn-disclaimer">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
