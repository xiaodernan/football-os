"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";

type SimulationCoachRead = {
  available: boolean;
  provider?: string;
  model?: string;
  demo_mode?: boolean;
  input_tokens?: number;
  cached_input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  answer?: string;
  /** The graph writes three named sections; older gateways that answer with one paragraph leave this absent. */
  sections?: { statistics?: string; moments?: string; tactics?: string };
  /** One row per node — which wrote prose and which was a deterministic rule. */
  trace?: { node: string; kind: string; model?: string }[];
  error?: string;
};

const SECTION_KEYS = ["statistics", "moments", "tactics"] as const;
const SECTION_LABEL: Record<(typeof SECTION_KEYS)[number], string> = {
  statistics: "secStatistics",
  moments: "secMoments",
  tactics: "secTactics",
};

export function SimulateCoachRead({ ident }: { ident: string }) {
  const t = useTranslations("simulate");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<SimulationCoachRead | null>(null);

  const load = () => {
    setState("loading");
    fetch(`/api/v1/simulate/${encodeURIComponent(ident)}/analysis`)
      .then(async (response) => (response.ok ? ((await response.json()) as SimulationCoachRead) : null))
      .then((payload) => {
        setData(payload);
        setState(payload ? "ok" : "error");
      })
      .catch(() => setState("error"));
  };

  return (
    <Panel eyebrow={t("coachReadEyebrow")} title={t("coachReadTitle")}>
      <p className="muted" style={{ maxWidth: "72ch" }}>{t("coachReadHint")}</p>
      <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {state === "idle" ? (
          <button className="btn btn--primary" type="button" onClick={load}>
            {t("coachReadCta")}
          </button>
        ) : null}
        {state === "loading" ? <p className="muted">{t("coachReadCta")}…</p> : null}
        {state === "error" ? <p className="sim-coach__error" role="alert">{t("coachReadEmpty")}</p> : null}
        {state === "ok" && data ? (
          data.available ? (
            <>
              {SECTION_KEYS.filter((key) => data.sections?.[key]).map((key) => (
                <div className="sim-coach__section" key={key}>
                  <span className="sim-coach__section-label">{t(SECTION_LABEL[key])}</span>
                  <div className="sim-coach__answer">{data.sections?.[key]}</div>
                </div>
              ))}
              {!data.sections && <div className="sim-coach__answer">{data.answer}</div>}
              {data.trace?.some((row) => row.kind === "model") ? (
                <p className="sim-coach__trace muted mono">{t("traceLabel")}</p>
              ) : null}
              <p className="sim-coach__meta muted mono">
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
