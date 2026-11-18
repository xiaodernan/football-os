"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { Fragment, useState, type ReactNode } from "react";

import { ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import { KNOWLEDGE_DIFFICULTIES, KNOWLEDGE_MODES, KNOWLEDGE_POSITIONS, type KnowledgeAskResponse, type KnowledgeCitation, type KnowledgeDeepAskResponse } from "@/lib/types";

function fmt(value: number | undefined, digits = 3): string {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

function categoryLabel(tk: (key: string) => string, slug: string): string {
  switch (slug) {
    case "tactics":
      return tk("categoryTactics");
    case "training":
      return tk("categoryTraining");
    case "sports-science":
      return tk("categorySportsScience");
    case "match-analysis":
      return tk("categoryMatchAnalysis");
    case "rules":
      return tk("categoryRules");
    case "coaching":
      return tk("categoryCoaching");
    case "history":
      return tk("categoryHistory");
    case "team-profile":
      return tk("categoryTeamProfile");
    case "player-profile":
      return tk("categoryPlayerProfile");
    default:
      return slug.replace(/_/g, " ");
  }
}

function difficultyLabel(tk: (key: string) => string, difficulty: string): string {
  switch (difficulty.toLowerCase()) {
    case "beginner":
      return tk("difficultyBeginner");
    case "intermediate":
      return tk("difficultyIntermediate");
    case "advanced":
      return tk("difficultyAdvanced");
    default:
      return difficulty;
  }
}

/** Turns inline [1], [2] … markers into anchors that jump to the matching citation card. */
function withRefs(text: string, goToCitation: (ref: string) => string): ReactNode[] {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    if (!match) return <Fragment key={index}>{part}</Fragment>;
    const ref = match[1];
    return (
      <a key={index} className="kn-ref" href={`#cite-${ref}`} aria-label={goToCitation(ref)}>
        {part}
      </a>
    );
  });
}

function CitationCard({ citation, index }: { citation: KnowledgeCitation; index: number }) {
  const t = useTranslations("common");
  const tk = useTranslations("knowledge");
  return (
    <div className="kn-cite" id={`cite-${index + 1}`}>
      <div className="between wrap" style={{ gap: "0.5rem" }}>
        <span className="h3">
          <span className="kn-ref">[{index + 1}]</span> {citation.title}
        </span>
        <span className="chip">{tk("citationScore", { value: fmt(citation.score) })}</span>
      </div>
      <span className="muted" style={{ fontSize: "0.82rem" }}>
        {tk("citationMeta", { section: citation.section, category: categoryLabel(tk, citation.category), value: fmt(citation.similarity) })}
      </span>
      <p className="kn-cite__quote">&ldquo;{citation.quote}&rdquo;</p>
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <Link className="kn-ref" href={`/knowledge/${encodeURIComponent(citation.slug)}#${citation.ordinal}`}>
          {t("open")} {tk("openPassage")}
        </Link>
        <span className="kn-prov__text grow">{citation.source}</span>
      </div>
    </div>
  );
}

/** A chapter that travelled in The Deep Read — title, bytes, link to the document. */
function DeepChapterCard({ chapter }: { chapter: { ref: number; slug: string; title: string; score: number; bytes: number } }) {
  const tk = useTranslations("knowledge");
  return (
    <div className="kn-cite" id={`cite-${chapter.ref}`}>
      <div className="between wrap" style={{ gap: "0.5rem" }}>
        <span className="h3">
          <span className="kn-ref">[{chapter.ref}]</span> {chapter.title}
        </span>
        <span className="chip mono">{chapter.bytes.toLocaleString()} B</span>
      </div>
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <Link className="kn-ref" href={`/knowledge/${encodeURIComponent(chapter.slug)}`}>
          {tk("openPassage")}
        </Link>
        <span className="kn-prov__text grow">{chapter.slug}</span>
      </div>
    </div>
  );
}

export function KnowledgeAsk({ signedIn, categories }: { signedIn: boolean; categories: string[] }) {
  const t = useTranslations("common");
  const tk = useTranslations("knowledge");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [position, setPosition] = useState("");
  const [busy, setBusy] = useState(false);
  const [promptSignIn, setPromptSignIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KnowledgeAskResponse | null>(null);
  const [deepResult, setDeepResult] = useState<KnowledgeDeepAskResponse | null>(null);
  const [depth, setDepth] = useState<"passage" | "deep">("passage");

  async function ask() {
    const trimmed = question.trim();
    if (trimmed.length < 3 || busy) return;
    setBusy(true);
    setError(null);
    setPromptSignIn(false);
    if (depth === "deep") {
      const response = await browserFetch<KnowledgeDeepAskResponse>("/knowledge/deep-ask", {
        method: "POST",
        body: {
          question: trimmed,
          category: category || undefined,
          difficulty: difficulty || undefined,
          position: position || undefined,
        },
      });
      if (!response.ok) {
        setDeepResult(null);
        if (response.status === 401) setPromptSignIn(true);
        else setError(errorMessage(response.error, tk("askFailed")));
      } else {
        setDeepResult(response.data);
        setResult(null);
        setQuestion("");
      }
      setBusy(false);
      return;
    }
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
      else setError(errorMessage(response.error, tk("askFailed")));
    } else {
      setResult(response.data);
      setDeepResult(null);
      setQuestion("");
    }
    setBusy(false);
  }

  if (!signedIn) {
    return (
      <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
        {tk("askSignedOut")}{" "}
        <Link className="kn-ref" href="/login?next=%2Fknowledge">
          {tk("searchSignIn")}
        </Link>{" "}
        {tk("askSignInTail")}
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="stack-sm">
        <label className="field">
          <span className="field__label">{tk("questionLabel")}</span>
          <textarea
            className="kn-textarea"
            id="kask-question"
            value={question}
            maxLength={500}
            placeholder={tk("questionPlaceholder")}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <span className="field__hint">{tk("questionHint")}</span>
        </label>

        <div className="kn-form-row">
          <label className="field">
            <span className="field__label">{tk("modeLabel")}</span>
            <select className="select" value={mode} onChange={(event) => setMode(event.target.value)}>
              {KNOWLEDGE_MODES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">{tk("categoryLabel")}</span>
            <select className="select" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">{t("all")}</option>
              {categories.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">{tk("difficultyLabel")}</span>
            <select className="select" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
              <option value="">{tk("anyOption")}</option>
              {KNOWLEDGE_DIFFICULTIES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">{tk("positionLabel")}</span>
            <select className="select" value={position} onChange={(event) => setPosition(event.target.value)}>
              <option value="">{tk("anyOption")}</option>
              {KNOWLEDGE_POSITIONS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset className="kn-depth">
          <legend className="field__label">{tk("depthLabel")}</legend>
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <label className={`chip${depth === "passage" ? " chip--accent" : ""}`} style={{ cursor: "pointer" }}>
              <input type="radio" name="knowledge-depth" value="passage" checked={depth === "passage"} onChange={() => setDepth("passage")} style={{ marginRight: "0.35rem" }} />
              {tk("depthPassage")}
            </label>
            <label className={`chip${depth === "deep" ? " chip--accent" : ""}`} style={{ cursor: "pointer" }}>
              <input type="radio" name="knowledge-depth" value="deep" checked={depth === "deep"} onChange={() => setDepth("deep")} style={{ marginRight: "0.35rem" }} />
              {tk("depthDeep")}
            </label>
          </div>
          <p className="field__hint" style={{ marginTop: "0.3rem" }}>{tk("depthHint")}</p>
        </fieldset>

        <div>
          <button type="button" className="btn btn--primary" onClick={ask} disabled={busy || question.trim().length < 3}>
            {busy ? tk("asking") : tk("askLibrary")}
          </button>
        </div>
      </div>

      {promptSignIn && (
        <div className="notice notice--warn" style={{ fontSize: "0.88rem" }}>
          {tk("sessionExpired")}{" "}
          <Link className="kn-ref" href="/login?next=%2Fknowledge">
            {tk("signInAgain")}
          </Link>{" "}
          {tk("keepAsking")}
        </div>
      )}
      {error && <div className="notice notice--warn">{error}</div>}

      {depth === "deep" && deepResult && (
        <div className="kn-answer-block stack">
          <p className="kn-answer-q">&ldquo;{deepResult.question}&rdquo;</p>
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {deepResult.demo_mode ? (
              <span className="badge badge--demo" title={tk("demoExtractiveTitle")}>
                {tk("demoModeExtractive")}
              </span>
            ) : (
              <span className="badge badge--live">{tk("aiGenerated")}</span>
            )}
            <span className="chip">{tk("confidence", { percent: Math.round(deepResult.confidence * 100) })}</span>
            {typeof deepResult.input_tokens === "number" && (
              <span className="chip mono">
                {tk("deepContextLine", {
                  bytes: (deepResult.context_bytes ?? 0).toLocaleString(),
                  tokens: deepResult.input_tokens.toLocaleString(),
                  cached: deepResult.cache_reported
                    ? `${Math.round(((deepResult.cached_input_tokens ?? 0) / Math.max(1, deepResult.input_tokens)) * 100)}%`
                    : "0%",
                })}
              </span>
            )}
            <span className={`chip ${deepResult.verify.ok ? "chip--accent" : "chip--warn"}`}>
              {deepResult.verify.ok ? tk("verifyOk") : tk("verifyFail")}
            </span>
            {deepResult.verify.repair_passes > 0 && <span className="chip">{tk("deepRepairRan")}</span>}
            <span className="chip mono">{deepResult.model}</span>
          </div>

          <div className="stack-sm">
            <span className="eyebrow">{tk("answerEyebrow")}</span>
            <p className="kn-answer">{withRefs(deepResult.answer, (ref) => tk("goToCitation", { ref }))}</p>
          </div>

          <ReasonList items={deepResult.reasons} title={tk("whyAnswer")} />

          <div className="stack-sm">
            <span className="eyebrow">{tk("deepChaptersTitle")}</span>
            {deepResult.chapters_used.map((chapter) => (
              <DeepChapterCard key={`${chapter.slug}-${chapter.ref}`} chapter={chapter} />
            ))}
          </div>

          {deepResult.graph_trace.length > 0 && (
            <span className="chip mono" title={tk("deepTraceLine", { nodes: deepResult.graph_trace.join(" » ") })}>
              {tk("deepTraceLine", { nodes: deepResult.graph_trace.join(" » ") })}
            </span>
          )}

          <p className="muted kn-disclaimer">{deepResult.disclaimer}</p>
        </div>
      )}

      {depth === "passage" && result && (
        <div className="kn-answer-block stack">
          <p className="kn-answer-q">&ldquo;{result.question}&rdquo;</p>
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {result.demo_mode ? (
              <span className="badge badge--demo" title={tk("demoExtractiveTitle")}>
                {tk("demoModeExtractive")}
              </span>
            ) : (
              <span className="badge badge--live">{tk("aiGenerated")}</span>
            )}
            <span className="chip">{tk("confidence", { percent: Math.round(result.confidence * 100) })}</span>
            {result.answered_from_cache && (
              <span className="chip chip--accent" title={tk("cachedPhrasingTitle")}>
                {tk("cachedPhrasing")}
              </span>
            )}
            <span className="chip mono">{result.model}</span>
            <span className="chip mono">{result.retrieval_backend}</span>
          </div>

          {result.answered ? (
            <div className="stack-sm">
              <span className="eyebrow">{tk("answerEyebrow")}</span>
              <p className="kn-answer">{withRefs(result.answer, (ref) => tk("goToCitation", { ref }))}</p>
            </div>
          ) : (
            <div className="notice notice--warn">
              <span className="eyebrow" style={{ color: "var(--warn)" }}>
                {tk("noGroundedAnswer")}
              </span>
              <p style={{ marginTop: "0.3rem" }}>{result.answer}</p>
            </div>
          )}

          <ReasonList items={result.reasons} title={tk("whyAnswer")} />

          {result.citations.length > 0 && (
            <div className="stack-sm">
              <span className="eyebrow">{tk("citedPassages")}</span>
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
