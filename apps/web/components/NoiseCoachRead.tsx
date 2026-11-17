"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";

type NoiseCoachRead = {
  available: boolean;
  provider?: string;
  model?: string;
  demo_mode?: boolean;
  input_tokens?: number;
  cached_input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  answer?: string;
  error?: string;
};

export function NoiseCoachRead() {
  const t = useTranslations("worldNoise");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<NoiseCoachRead | null>(null);

  const load = () => {
    setState("loading");
    fetch("/api/v1/world/noise/coach-read")
      .then(async (response) => (response.ok ? ((await response.json()) as NoiseCoachRead) : null))
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
        {state === "error" ? <p className="noise-coach__error" role="alert">{t("coachReadEmpty")}</p> : null}
        {state === "ok" && data ? (
          data.available ? (
            <>
              <div className="noise-coach__answer">{data.answer}</div>
              <p className="noise-coach__meta muted mono">
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
