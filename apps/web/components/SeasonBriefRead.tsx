"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";

type SeasonBrief = {
  answered: boolean;
  headline?: string | null;
  themes?: string[];
  arc?: { day: number; focus: string; minutes: number; blocks: string[] }[];
  one_more?: string | null;
  evidence?: string[];
  chapters_used?: { ref: number; slug: string; title: string; score: number }[];
  verify?: { ok: boolean; repair_passes: number; failures: string[] };
  provider?: string;
  model?: string;
  error?: string;
};

export function SeasonBriefRead() {
  const t = useTranslations("training");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<SeasonBrief | null>(null);

  const load = () => {
    setState("loading");
    fetch("/api/v1/trainings/season-brief", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    })
      .then(async (response) => (response.ok ? ((await response.json()) as SeasonBrief) : null))
      .then((payload) => {
        setData(payload);
        setState(payload ? "ok" : "error");
      })
      .catch(() => setState("error"));
  };

  return (
    <Panel eyebrow={t("seasonBriefEyebrow")} title={t("seasonBriefTitle")}>
      <p className="muted" style={{ maxWidth: "72ch" }}>{t("seasonBriefHint")}</p>

      <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {state === "idle" ? (
          <button className="btn btn--primary" type="button" onClick={load}>
            {t("seasonBriefCta")}
          </button>
        ) : null}
        {state === "loading" ? <p className="muted">{t("seasonBriefLoading")}</p> : null}
        {state === "error" || (state === "ok" && (!data || !data.answered)) ? (
          <p role="alert" className="season-brief__error">{t("seasonBriefEmpty")}</p>
        ) : null}
        {state === "ok" && data && data.answered ? (
          <>
            {data.headline ? <h3 className="season-brief__headline">{data.headline}</h3> : null}
            {Array.isArray(data.themes) && data.themes.length ? (
              <div className="season-brief__themes">
                {data.themes.map((theme) => (
                  <span key={theme} className="badge">{theme}</span>
                ))}
              </div>
            ) : null}
            {Array.isArray(data.arc) && data.arc.length ? (
              <ol className="season-brief__arc">
                {data.arc.map((block) => (
                  <li key={block.day} className="season-brief__day">
                    <strong>Day {block.day} · {block.focus} · {block.minutes}’</strong>
                    <span className="muted">{(block.blocks ?? []).join(" · ")}</span>
                  </li>
                ))}
              </ol>
            ) : null}
            {data.one_more ? <p className="muted" style={{ margin: 0 }}>{data.one_more}</p> : null}
            <p className="season-brief__meta muted mono">
              {t("seasonBriefMeta", {
                provider: data.provider ?? "mock",
                model: data.model ?? "mock",
                cached: (data as unknown as { cached_input_tokens?: number }).cached_input_tokens ?? 0,
                prompt: (data as unknown as { input_tokens?: number }).input_tokens ?? 0,
              })}
            </p>
          </>
        ) : null}
      </div>
    </Panel>
  );
}
