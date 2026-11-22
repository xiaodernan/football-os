"use client";

import { useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Panel } from "@/components/ui";
import { browserFetch } from "@/lib/api";

type TraceStep = { node: string; detail: string };

type DossierPayload = {
  available: boolean;
  focus: string;
  depth: string;
  seed: number;
  target_tokens: number;
  estimated_input_tokens: number;
  dossier_tokens: number;
  dossier_chars: number;
  source_count: number;
  sources: string[];
  chapter: string;
  verified: boolean;
  drifted_decimals: string[];
  trace: TraceStep[];
  provider: string;
  model: string;
  demo_mode: boolean;
  input_tokens: number;
  cached_input_tokens: number;
  cache_reported: boolean;
  output_tokens: number;
  error: string;
};

export function DeepDossierPanel() {
  const t = useTranslations("worldDossier");
  const locale = useLocale();
  const [focus, setFocus] = useState(() => t("defaultFocus"));
  const [depth, setDepth] = useState("deep");
  const [seed, setSeed] = useState(42);
  const [state, setState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [data, setData] = useState<DossierPayload | null>(null);
  const [binding, setBinding] = useState(false);
  const [bound, setBound] = useState<{ slug: string; created: boolean } | null>(null);
  const [bindError, setBindError] = useState(false);

  const compose = () => {
    const trimmed = focus.trim();
    if (trimmed.length < 3) return;
    setState("loading");
    setBound(null);
    setBindError(false);
    const query = new URLSearchParams({
      focus: trimmed,
      depth,
      seed: String(Number.isFinite(seed) ? Math.max(0, Math.trunc(seed)) : 0),
    });
    browserFetch<DossierPayload>(`/world/deep-dossier?${query.toString()}`)
      .then((result) => {
        if (!result.ok) {
          setData(null);
          setState("error");
          return;
        }
        setData(result.data);
        setState(result.data.available ? "ok" : "error");
      })
      .catch(() => setState("error"));
  };

  const bind = () => {
    if (!data) return;
    setBinding(true);
    setBindError(false);
    browserFetch<{ slug: string; created: boolean }>("/world/deep-dossier/volumes", {
      method: "POST",
      body: { focus: data.focus, depth: data.depth, seed: data.seed, locale },
    })
      .then((result) => {
        if (!result.ok) {
          setBindError(true);
          return;
        }
        setBound({ slug: result.data.slug, created: result.data.created });
      })
      .catch(() => setBindError(true))
      .finally(() => setBinding(false));
  };

  const hit = data?.cache_reported && data.input_tokens > 0
    ? Math.round((data.cached_input_tokens / data.input_tokens) * 1000) / 10
    : null;
  const trace = data?.trace?.map((step) => step.node).join(" → ") ?? "";

  return (
    <div className="dossier-grid">
      <Panel eyebrow={t("teachEyebrow")} title={t("teachTitle")}>
        <ol className="dossier-teach">
          <li>{t("teachOne")}</li>
          <li>{t("teachTwo")}</li>
          <li>{t("teachThree")}</li>
        </ol>
      </Panel>

      <Panel eyebrow={t("formEyebrow")} title={t("formTitle")}>
        <p className="muted dossier-note">{t("hint")}</p>
        <form
          className="dossier-form"
          onSubmit={(event) => {
            event.preventDefault();
            compose();
          }}
        >
          <label className="dossier-field">
            <span>{t("focusLabel")}</span>
            <input
              type="text"
              value={focus}
              onChange={(event) => setFocus(event.target.value)}
              placeholder={t("focusPlaceholder")}
              maxLength={200}
            />
          </label>
          <label className="dossier-field">
            <span>{t("depthLabel")}</span>
            <select value={depth} onChange={(event) => setDepth(event.target.value)}>
              <option value="standard">{t("depthStandard")}</option>
              <option value="deep">{t("depthDeep")}</option>
              <option value="epic">{t("depthEpic")}</option>
            </select>
          </label>
          <label className="dossier-field dossier-field--seed">
            <span>{t("seedLabel")}</span>
            <input
              type="number"
              min={0}
              max={2147483647}
              value={seed}
              onChange={(event) => setSeed(Number(event.target.value))}
            />
          </label>
          <button className="btn btn--primary" type="submit" disabled={state === "loading" || focus.trim().length < 3}>
            {t("cta")}
          </button>
        </form>
        {state === "loading" ? <p className="muted dossier-status">{t("thinking")}</p> : null}
        {state === "error" ? <p className="dossier-error" role="alert">{data?.error || t("error")}</p> : null}
      </Panel>

      {state === "ok" && data ? (
        <>
          <Panel eyebrow={t("metricsEyebrow")} title={t("metricsTitle")}>
            <dl className="dossier-metrics">
              <div><dt>{t("statTokens")}</dt><dd className="num">{data.estimated_input_tokens.toLocaleString()}</dd></div>
              <div><dt>{t("statSources")}</dt><dd className="num">{data.source_count}</dd></div>
              <div><dt>{t("statChars")}</dt><dd className="num">{data.dossier_chars.toLocaleString()}</dd></div>
              <div><dt>{t("statInput")}</dt><dd className="num">{(data.input_tokens || 0).toLocaleString()}</dd></div>
              <div><dt>{t("statCached")}</dt><dd className="num">{(data.cached_input_tokens || 0).toLocaleString()}</dd></div>
              <div><dt>{t("statHit")}</dt><dd className="num">{hit === null ? "—" : `${hit}%`}</dd></div>
            </dl>
            <p className="muted mono dossier-trace">{t("traceLabel", { trace })}</p>
            <p className={`dossier-verify ${data.verified ? "dossier-verify--ok" : "dossier-verify--drift"}`}>
              {data.verified ? t("verificationOk") : t("verificationDrift", { values: data.drifted_decimals.slice(0, 4).join(", ") })}
            </p>
            <p className="muted mono dossier-model">{data.provider} · {data.model}</p>
          </Panel>

          <Panel eyebrow={t("chapterEyebrow")} title={t("chapterTitle")}>
            <article className="dossier-chapter">{data.chapter}</article>
            {data.sources.length > 0 ? (
              <p className="muted mono dossier-sources">{t("sourcesLabel", { sources: data.sources.slice(0, 6).join(" · ") })}</p>
            ) : null}
            <div className="dossier-bind">
              {bound ? (
                <p className="dossier-bind__done" role="status">
                  {t(bound.created ? "bindSaved" : "bindExisting")}{" "}
                  <Link href={`/world/dossier-library/${bound.slug}`}>{t("bindOpen")}</Link>
                </p>
              ) : (
                <button className="btn btn--primary" type="button" onClick={bind} disabled={binding}>
                  {binding ? t("binding") : t("bindCta")}
                </button>
              )}
              <p className="muted dossier-bind__note">{t("bindNote")}</p>
              {bindError ? <p className="dossier-error" role="alert">{t("bindError")}</p> : null}
            </div>
          </Panel>
        </>
      ) : null}
    </div>
  );
}
