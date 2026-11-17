"use client";

import Link from "next/link";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";
import { browserFetch } from "@/lib/api";

type NextPod = { href: string; titleKey: string };const NEXT_BY_INTENT: Record<string, NextPod[]> = {
  getting_started: [
    { href: "/coach", titleKey: "tour2t" },
    { href: "/world", titleKey: "tour3t" },
    { href: "/tutorial", titleKey: "tour16t" },
    { href: "/my-football", titleKey: "tour1t" },
  ],
  tour: [
    { href: "/world/gazette", titleKey: "tour11t" },
    { href: "/world/timeline", titleKey: "tour10t" },
    { href: "/world/champions", titleKey: "tour19t" },
    { href: "/world/story", titleKey: "tour5t" },
    { href: "/world/spotlight", titleKey: "tour9t" },
  ],
  glossary: [
    { href: "/world/records", titleKey: "tour6t" },
    { href: "/world/champions", titleKey: "tour19t" },
    { href: "/world/noise", titleKey: "tour13t" },
  ],
  rules: [
    { href: "/world/creed", titleKey: "tour20t" },
    { href: "/world/dynasties", titleKey: "tour15t" },
  ],
  admin: [
    { href: "/admin", titleKey: "askAdminChip" },
  ],
  faq: [
    { href: "/manual", titleKey: "askManualChip" },
    { href: "/tutorial", titleKey: "tour16t" },
  ],
  get_value: [
    { href: "/admin", titleKey: "askAdminChip" },
  ],
};

const DEFAULT_PODS: NextPod[] = [
  { href: "/world/gazette", titleKey: "tour11t" },
  { href: "/world/champions", titleKey: "tour19t" },
  { href: "/world/timeline", titleKey: "tour10t" },
];

function nextPods(intent: string | undefined): NextPod[] {
  if (intent && NEXT_BY_INTENT[intent]) return NEXT_BY_INTENT[intent];
  return DEFAULT_PODS;
}

type ManualAskPayload = {
  available: boolean;
  intent?: string;
  graph_trace?: string[];
  provider?: string;
  model?: string;
  demo_mode?: boolean;
  input_tokens?: number;
  cached_input_tokens?: number;
  cache_reported?: boolean;
  output_tokens?: number;
  latency_ms?: number;
  answer?: string | null;
  error?: string;
};

export function ManualAskPanel() {
  const t = useTranslations("manual");
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<ManualAskPayload | null>(null);

  const ask = () => {
    const trimmed = question.trim();
    if (trimmed.length < 3) return;
    setState("loading");
    browserFetch<ManualAskPayload>("/manual/ask", {
      method: "POST",
      body: { question: trimmed, locale: (typeof navigator !== "undefined" ? (navigator.language || "en").slice(0, 2) : "en") },
    })
      .then((result) => {
        if (!result.ok) {
          setData(null);
          setState("error");
          return;
        }
        setData(result.data);
        setState("ok");
      })
      .catch(() => setState("error"));
  };

  const trace = Array.isArray(data?.graph_trace) ? data?.graph_trace.join(" → ") : null;

  return (
    <Panel eyebrow={t("askEyebrow")} title={t("askTitle")}>
      <p className="muted" style={{ maxWidth: "72ch" }}>{t("askHint")}</p>
      <form
        className="manual-ask__form"
        onSubmit={(event) => {
          event.preventDefault();
          ask();
        }}
      >
        <label htmlFor="manual-ask-question" style={{ position: "absolute", width: 1, height: 1, margin: -1, overflow: "hidden", clipPath: "inset(50%)" }}>{t("askInputLabel")}</label>
        <input
          id="manual-ask-question"
          className="manual-ask__input"
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t("askPlaceholder")}
          maxLength={280}
        />
        <button className="btn btn--primary" type="submit" disabled={state === "loading" || question.trim().length < 3}>
          {t("askCta")}
        </button>
      </form>
      {state === "loading" ? <p className="muted" style={{ marginTop: "0.5rem" }}>{t("askThinking")}</p> : null}
      {state === "error" ? <p className="manual-ask__error" role="alert">{t("askError")}</p> : null}
      {state === "ok" && data ? (
        data.answer ? (
          <>
            {data.intent ? <p className="manual-ask__intent" style={{ margin: "0.6rem 0 0" }}>{t("askIntent", { intent: data.intent })}</p> : null}
            <p className="manual-ask__answer">{data.answer}</p>
            {trace ? <p className="manual-ask__trace mono muted">{t("askTrace", { trace })}</p> : null}
            <p className="manual-ask__meta muted mono">
              {t("askProvider", {
                provider: data.provider ?? "mock",
                model: data.model ?? "mock",
                cached: data.cached_input_tokens ?? 0,
                prompt: data.input_tokens ?? 0,
              })}
            </p>
            <nav aria-label={t("askNextDoors")} style={{ marginTop: "0.6rem" }}>
              <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>{t("askNextDoors")}</p>
              <ul style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", listStyle: "none", padding: 0, marginTop: "0.35rem" }}>
                {nextPods(data.intent).map((pod) => (
                  <li key={pod.href}>
                    <Link className="chip mono world-link" href={pod.href}>{t(pod.titleKey as Parameters<typeof t>[0])}</Link>
                  </li>
                ))}
              </ul>
            </nav>
          </>
        ) : (
          <p className="muted">{t("askError")}</p>
        )
      ) : null}
    </Panel>
  );
}
