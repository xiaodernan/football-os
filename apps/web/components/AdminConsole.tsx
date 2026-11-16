"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { Panel } from "@/components/ui";
import "@/styles/admin.css";

type CoachReadPayload = {
  available: boolean;
  window_days: number;
  provider?: string;
  model?: string;
  demo_mode?: boolean;
  cached_input_tokens?: number;
  input_tokens?: number;
  cache_reported?: boolean;
  output_tokens?: number;
  latency_ms?: number;
  answer?: string;
  error?: string;
};

type BehaviorPayload = {
  available: boolean;
  window_days: number;
  source_note: { seeded_views: number; real_views: number; seeded_sessions: number; real_sessions: number };
  totals: { sessions: number; views: number; unique_paths: number; bounce_rate: number; median_dwell_ms: number };
  daily: { date: string; views: number; sessions: number; bounce_rate: number }[];
  pages: { path: string; views: number; sessions: number; bounce_rate: number; median_dwell_ms: number }[];
  funnels: { id: string; from: string; to: string; rate: number }[];
  forecast: { method: string; horizon_days: number; slope_per_day: number; r_squared: number; projected_sessions: number[] };
  recommendations: { kind: string; path?: string; value?: number }[];
  model: { calls_in_window: number; input_tokens_reported: number; cached_input_tokens: number; cached_share: number };
};

const SESSION_KEY = "fo_admin_pass";

function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

function dwellLabel(ms: number): string {
  return `${Math.round(ms / 1000)}s`;
}

function chartPoints(values: number[], width: number, height: number, pad = 6): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 1);
  const step = (width - pad * 2) / (values.length - 1);
  return values
    .map((value, index) => `${(pad + index * step).toFixed(1)},${(height - pad - (value / max) * (height - pad * 2)).toFixed(1)}`)
    .join(" ");
}

export function AdminConsole() {
  const t = useTranslations("admin");
  const [input, setInput] = useState("");
  const [passphrase, setPassphrase] = useState<string>(() =>
    typeof window !== "undefined" ? window.sessionStorage.getItem(SESSION_KEY) ?? "" : "",
  );
  const [state, setState] = useState<"idle" | "loading" | "ok" | "wrong" | "error">("idle");
  const [data, setData] = useState<BehaviorPayload | null>(null);
  const [coachState, setCoachState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [coachData, setCoachData] = useState<CoachReadPayload | null>(null);

  useEffect(() => {
    if (!passphrase) return;
    let cancelled = false;
    setState("loading");
    fetch("/api/v1/admin/behavior", { headers: { "x-admin-passphrase": passphrase } })
      .then(async (response) => {
        if (!response.ok) throw { status: response.status };
        return (await response.json()) as BehaviorPayload;
      })
      .then((payload) => {
        if (cancelled) return;
        setData(payload);
        setState("ok");
        setCoachState("idle");
        setCoachData(null);
      })
      .catch((error: { status?: number }) => {
        if (cancelled) return;
        if (error?.status === 401) {
          window.sessionStorage.removeItem(SESSION_KEY);
          setState("wrong");
          setPassphrase("");
        } else {
          setState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [passphrase]);

  const loadCoachRead = () => {
    setCoachState("loading");
    fetch("/api/v1/admin/coach-read", { headers: { "x-admin-passphrase": passphrase } })
      .then(async (response) => (response.ok ? ((await response.json()) as CoachReadPayload) : null))
      .then((payload) => {
        if (!payload) {
          setCoachState("error");
          return;
        }
        setCoachData(payload);
        setCoachState("ok");
      })
      .catch(() => setCoachState("error"));
  };

  const chart = useMemo(() => {
    if (!data) return null;
    const views = data.daily.map((day) => day.views);
    const sessions = data.daily.map((day) => day.sessions);
    return {
      views: chartPoints(views, 640, 150),
      sessions: chartPoints(sessions, 640, 150),
      first: data.daily[0]?.date ?? "",
      last: data.daily[data.daily.length - 1]?.date ?? "",
      max: Math.max(...views, 1),
    };
  }, [data]);

  if (!data || state !== "ok") {
    return (
      <div className="container page stack" style={{ gap: "2rem" }}>
        <Panel eyebrow={t("eyebrow")} title={t("gateTitle")}>
          <p className="muted" style={{ maxWidth: "56ch" }}>{t("gateLede")}</p>
          <form
            className="admin__gate"
            onSubmit={(event) => {
              event.preventDefault();
              const value = input.trim();
              if (!value) return;
              window.sessionStorage.setItem(SESSION_KEY, value);
              setPassphrase(value);
            }}
          >
            <input
              autoFocus
              className="input"
              type="password"
              inputMode="numeric"
              autoComplete="off"
              placeholder={t("gatePlaceholder")}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              aria-label={t("gatePlaceholder")}
            />
            <button className="btn btn--primary" type="submit" disabled={state === "loading" || !input.trim()}>
              {state === "loading" ? t("gateEntering") : t("gateEnter")}
            </button>
          </form>
          {state === "wrong" ? <p className="admin__gate-error" role="alert">{t("gateWrong")}</p> : null}
          {state === "error" ? <p className="admin__gate-error" role="alert">{t("gateError")}</p> : null}
        </Panel>
      </div>
    );
  }

  const share = data.source_note.seeded_views > 0 && data.source_note.real_views > 0
    ? t("sourceMixed", { seeded: data.source_note.seeded_views, real: data.source_note.real_views })
    : data.source_note.real_views > 0
      ? t("sourceReal", { real: data.source_note.real_views, sessions: data.source_note.real_sessions })
      : t("sourceSeeded", { seeded: data.source_note.seeded_views, sessions: data.source_note.seeded_sessions });

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <header className="admin__header">
        <span className="admin__eyebrow">{t("eyebrow")}</span>
        <h1 className="h1">{t("title")}</h1>
        <p className="muted" style={{ maxWidth: "72ch" }}>{t("lede")}</p>
        <p className="admin__source">{share}</p>
      </header>

      <section className="admin__kpis" aria-label={t("statsLabel")}>
        {[
          { label: t("statSessions"), value: data.totals.sessions.toLocaleString() },
          { label: t("statViews"), value: data.totals.views.toLocaleString() },
          { label: t("statPaths"), value: data.totals.unique_paths.toLocaleString() },
          { label: t("statBounce"), value: pct(data.totals.bounce_rate) },
          { label: t("statDwell"), value: dwellLabel(data.totals.median_dwell_ms) },
        ].map((kpi) => (
          <div key={kpi.label} className="admin__kpi">
            <span className="admin__kpi-value num">{kpi.value}</span>
            <span className="admin__kpi-label">{kpi.label}</span>
          </div>
        ))}
      </section>

      <Panel eyebrow={t("coachReadEyebrow")} title={t("coachReadTitle")}>
        <p className="muted" style={{ maxWidth: "72ch" }}>{t("coachReadHint")}</p>
        <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {coachState === "idle" ? (
            <button className="btn btn--primary" type="button" onClick={loadCoachRead}>
              {t("coachReadCta")}
            </button>
          ) : null}
          {coachState === "loading" ? <p className="muted">{t("gateEntering")}</p> : null}
          {coachState === "error" ? <p className="admin__gate-error" role="alert">{t("gateError")}</p> : null}
          {coachState === "ok" && coachData ? (
            coachData.available ? (
              <>
                <div className="admin__coach-answer">{coachData.answer}</div>
                <p className="admin__coach-meta muted mono">
                  {t("coachReadProvider", {
                    provider: coachData.provider ?? "mock",
                    model: coachData.model ?? "mock",
                    cached: coachData.cached_input_tokens ?? 0,
                    prompt: coachData.input_tokens ?? 0,
                  })}
                </p>
              </>
            ) : (
              <p className="muted">{t("coachReadEmpty")}</p>
            )
          ) : null}
        </div>
      </Panel>

      {chart ? (
        <Panel eyebrow={t("dailyTitle")} title={t("dailyTitle")}>
          <div className="admin__chartwrap">
            <svg viewBox="0 0 640 150" className="admin__chart" role="img" aria-label={t("dailyTitle")}>
              <polyline className="admin__line admin__line--views" points={chart.views} />
              <polyline className="admin__line admin__line--sessions" points={chart.sessions} />
            </svg>
            <div className="admin__chartfoot muted">
              <span className="mono">{chart.first}</span>
              <span className="admin__legend">
                <i className="admin__dot admin__dot--views" /> {t("legendViews")}
                <i className="admin__dot admin__dot--sessions" /> {t("legendSessions")}
              </span>
              <span className="mono">{chart.last}</span>
            </div>
          </div>
        </Panel>
      ) : null}

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Panel eyebrow={t("funnelTitle")} title={t("funnelTitle")}>
          <ul className="admin__funnels">
            {data.funnels.map((funnel) => (
              <li key={funnel.id}>
                <span className="mono admin__funnel-id">{funnel.from} 鈫?{funnel.to}</span>
                <span className="admin__funnel-track" aria-hidden="true">
                  <span className="admin__funnel-fill" style={{ width: `${Math.round(funnel.rate * 100)}%` }} />
                </span>
                <span className="num admin__funnel-rate">{pct(funnel.rate)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel eyebrow={t("forecastTitle")} title={t("forecastTitle")}>
          <dl className="admin__kv">
            <div><dt>{t("forecastSlope")}</dt><dd className="num">{data.forecast.slope_per_day >= 0 ? "+" : ""}{data.forecast.slope_per_day.toFixed(2)}</dd></div>
            <div><dt>{t("forecastR2")}</dt><dd className="num">{data.forecast.r_squared.toFixed(2)}</dd></div>
            <div><dt>{t("forecastProjected")}</dt><dd className="num">{data.forecast.projected_sessions[0]} 鈫?{data.forecast.projected_sessions[data.forecast.projected_sessions.length - 1]}</dd></div>
          </dl>
        </Panel>
      </div>

      <Panel eyebrow={t("pagesTitle")} title={t("pagesTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thPath")}</th>
                <th scope="col">{t("thViews")}</th>
                <th scope="col">{t("thBounce")}</th>
                <th scope="col">{t("thDwell")}</th>
              </tr>
            </thead>
            <tbody>
              {data.pages.map((page) => (
                <tr key={page.path}>
                  <td className="mono">{page.path}</td>
                  <td className="num">{page.views.toLocaleString()}</td>
                  <td className="num">{pct(page.bounce_rate)}</td>
                  <td className="num muted">{dwellLabel(page.median_dwell_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Panel eyebrow={t("modelTitle")} title={t("modelTitle")}>
          <p className="muted">{t("modelNote")}</p>
          <dl className="admin__kv">
            <div><dt>{t("modelCalls")}</dt><dd className="num">{data.model.calls_in_window.toLocaleString()}</dd></div>
            <div><dt>{t("modelCachedShare")}</dt><dd className="num">{pct(data.model.cached_share)}</dd></div>
          </dl>
        </Panel>

        <Panel eyebrow={t("recsTitle")} title={t("recsTitle")}>
          <p className="muted" style={{ fontSize: "0.8rem" }}>{t("recDisclaimer")}</p>
          <ul className="admin__recs">
            {data.recommendations.map((rec, index) => {
              let text: string;
              switch (rec.kind) {
                case "high_bounce_page": text = t("recHighBounce", { path: rec.path ?? "?", value: pct(rec.value ?? 0) }); break;
                case "low_dwell_page": text = t("recLowDwell", { path: rec.path ?? "?", value: dwellLabel(rec.value ?? 0) }); break;
                case "tutorial_drop": text = t("recTutorialDrop", { value: pct(rec.value ?? 0) }); break;
                case "forecast_flat": text = t("recForecastFlat"); break;
                case "forecast_rising": text = t("recForecastRising", { value: rec.value?.toFixed(2) ?? "0" }); break;
                case "forecast_falling": text = t("recForecastFalling", { value: rec.value?.toFixed(2) ?? "0" }); break;
                case "strong_page": text = t("recStrongPage", { path: rec.path ?? "?" }); break;
                default: text = rec.kind;
              }
              return <li key={`${rec.kind}-${index}`}>{text}</li>;
            })}
          </ul>
        </Panel>
      </div>
    </div>
  );
}

