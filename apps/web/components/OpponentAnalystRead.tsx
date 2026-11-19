"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";

type Analyst = {
  answered: boolean;
  headline?: string | null;
  phases?: { name: string; trigger: string; action: string }[];
  blocks?: string[];
  counters?: string[];
  one_more?: string | null;
  evidence?: string[];
  chapters_used?: { ref: number; slug: string; title: string; score: number }[];
  verify?: { ok: boolean; repair_passes: number; failures: string[] };
  provider?: string;
  model?: string;
  error?: string;
};

export function OpponentAnalystRead() {
  const t = useTranslations("tactics");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<Analyst | null>(null);
  const [ownShape, setOwnShape] = useState("4-2-3-1");
  const [opponentShape, setOpponentShape] = useState(() => t("analystOpponentShapeDefault"));
  const [levers, setLevers] = useState(() => t("analystLeversDefault"));

  const ask = () => {
    setState("loading");
    fetch("/api/v1/tactics/opponent-brief", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ opponent_shape: opponentShape, own_shape: ownShape, levers }),
    })
      .then(async (response) => (response.ok ? ((await response.json()) as Analyst) : null))
      .then((payload) => {
        setData(payload);
        setState(payload ? "ok" : "error");
      })
      .catch(() => setState("error"));
  };

  return (
    <Panel eyebrow={t("opponentAnalystEyebrow")} title={t("opponentAnalystTitle")}>
      <p className="muted" style={{ maxWidth: "72ch" }}>{t("opponentAnalystHint")}</p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
        style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.6rem" }}
      >
        <label style={{ flex: "1 1 14ch", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span className="muted" style={{ fontSize: "0.78rem" }}>{t("analystOwnShapeLabel")}</span>
          <input className="input" value={ownShape} onChange={(e) => setOwnShape(e.target.value)} />
        </label>
        <label style={{ flex: "1 1 14ch", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span className="muted" style={{ fontSize: "0.78rem" }}>{t("analystOpponentShapeLabel")}</span>
          <input className="input" value={opponentShape} onChange={(e) => setOpponentShape(e.target.value)} />
        </label>
        <label style={{ flex: "1 1 14ch", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span className="muted" style={{ fontSize: "0.78rem" }}>{t("analystLeversLabel")}</span>
          <input className="input" value={levers} onChange={(e) => setLevers(e.target.value)} />
        </label>
        <button className="btn btn--primary" type="submit" style={{ alignSelf: "flex-end" }}>
          {t("opponentAnalystCta")}
        </button>
      </form>

      <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {state === "loading" ? <p className="muted">{t("opponentAnalystLoading")}</p> : null}
        {state === "error" || (state === "ok" && (!data || !data.answered)) ? (
          <p role="alert" className="opponent-analyst__error">{t("opponentAnalystEmpty")}</p>
        ) : null}
        {state === "ok" && data && data.answered ? (
          <>
            {data.headline ? <h3 className="opponent-analyst__headline">{data.headline}</h3> : null}
            {Array.isArray(data.phases) && data.phases.length ? (
              <ol className="opponent-analyst__phases">
                {data.phases.map((phase, i) => (
                  <li key={i} className="opponent-analyst__phase">
                    <strong>{phase.name}</strong>
                    <span className="muted">{phase.trigger}</span>
                    <span>{phase.action}</span>
                  </li>
                ))}
              </ol>
            ) : null}
            {Array.isArray(data.counters) && data.counters.length ? (
              <ol className="opponent-analyst__counters">
                {data.counters.map((counter, i) => (
                  <li key={i}>{counter}</li>
                ))}
              </ol>
            ) : null}
            {data.one_more ? <p className="muted" style={{ margin: 0 }}>{data.one_more}</p> : null}
            <p className="opponent-analyst__meta muted mono">
              {t("opponentAnalystMeta", {
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
