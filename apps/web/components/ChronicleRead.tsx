"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";

type ChronicleRead = {
  available: boolean;
  provider?: string;
  model?: string;
  demo_mode?: boolean;
  input_tokens?: number;
  cached_input_tokens?: number;
  output_tokens?: number;
  cache_reported?: boolean;
  latency_ms?: number;
  revision?: string;
  graph_trace?: string[];
  answer?: string;
  error?: string;
};

export function ChronicleReadPanel() {
  const t = useTranslations("worldChronicle");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<ChronicleRead | null>(null);

  const load = () => {
    setState("loading");
    fetch("/api/v1/world/chronicle/coach-read")
      .then(async (response) => (response.ok ? ((await response.json()) as ChronicleRead) : null))
      .then((payload) => {
        setData(payload);
        setState(payload ? "ok" : "error");
      })
      .catch(() => setState("error"));
  };

  const paragraphs = (data?.answer ?? "").split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  const applied = data?.revision === "applied";

  return (
    <Panel eyebrow={t("coachReadEyebrow")} title={t("coachReadTitle")}>
      <p className="muted" style={{ maxWidth: "72ch" }}>{t("coachReadHint")}</p>
      <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {state === "idle" ? (
          <button className="btn btn--primary" type="button" onClick={load}>
            {t("coachReadCta")}
          </button>
        ) : null}
        {state === "loading" ? <p className="muted">{t("coachReadCta")}…</p> : null}
        {state === "error" ? <p className="chronicle-coach__error" role="alert">{t("coachReadEmpty")}</p> : null}
        {state === "ok" && data ? (
          data.available ? (
            <>
              <article className="chronicle-coach__answer">
                {paragraphs.map((block, index) => (
                  <p key={index} style={{ margin: index === 0 ? 0 : "0.75rem 0 0" }}>{block}</p>
                ))}
              </article>
              {Array.isArray(data.graph_trace) && data.graph_trace.length > 0 ? (
                <p className="chronicle-coach__trace mono muted">{t("graphTrace", { trace: data.graph_trace.join(" → ") })}</p>
              ) : null}
              <p className="chronicle-coach__revision muted">{applied ? t("revisionApplied") : t("revisionDraft")}</p>
              <p className="chronicle-coach__meta muted mono">
                {t("coachReadProvider", {
                  provider: data.provider ?? "mock",
                  model: data.model ?? "mock",
                  cached: data.cached_input_tokens ?? 0,
                  prompt: data.input_tokens ?? 0,
                })}
              </p>
            </>
          ) : (
            <p className="muted">{t("coachReadEmpty")}</p>
          )
        ) : null}
      </div>
    </Panel>
  );
}
