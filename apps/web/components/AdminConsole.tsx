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
  verified?: boolean;
  repairs?: number;
  trace?: { node: string; kind: string; ok?: boolean; unmatched?: string[]; dropped?: number; error?: string }[];
};

type BehaviorPayload = {
  available: boolean;
  window_days: number;
  source_note: { seeded_views: number; real_views: number; seeded_sessions: number; real_sessions: number };
  totals: { sessions: number; views: number; unique_paths: number; bounce_rate: number; median_dwell_ms: number };
  daily: { date: string; views: number; sessions: number; bounce_rate: number }[];
  pages: { path: string; views: number; sessions: number; bounce_rate: number; median_dwell_ms: number }[];
  funnels: { id: string; from: string; to: string; rate: number }[];
  forecast: {
    method: string;
    horizon_days: number;
    slope_per_day: number;
    r_squared: number;
    projected_sessions: number[];
    trend_direction?: string;
    /** The API reports a qualitative label ("strong" / "weak"); older builds reported a score. */
    confidence?: number | string;
    projected_7d_sessions?: number;
    projected_14d_sessions?: number;
    busiest_day?: string | null;
    busiest_day_sessions?: number;
  };
  recommendations: { kind: string; path?: string; value?: number }[];
  model: { calls_in_window: number; input_tokens_reported: number; cached_input_tokens: number; cached_share: number };
};

type CensusFeature = {
  feature: string;
  calls: number;
  failures: number;
  demo_mode_calls: number;
  cached_share_reported: number;
  reported_rows: number;
  output_tokens: number;
  median_latency_ms: number;
  cost_usd: number;
  last_called: string | null;
};
type CensusDaily = { date: string; calls: number; failures: number; input_tokens: number; cached_tokens: number; reported_rows: number; cost_usd: number };
type CensusPayload = {
  available: boolean;
  window_days: number;
  totals: {
    calls: number;
    failures: number;
    failure_rate: number;
    demo_mode_calls: number;
    demo_mode_share: number;
    input_tokens: number;
    output_tokens: number;
    cached_input_tokens: number;
    in_cache_reported: number;
    cached_reported: number;
    cached_share_reported: number;
    reported_rows: number;
    estimated_cost_usd: number;
    actual_cost_usd: number;
    median_latency_ms: number;
  };
  by_feature: CensusFeature[];
  daily: CensusDaily[];
  errors: { sample: string; count: number }[];
  note?: string;
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
  const [censusState, setCensusState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [census, setCensus] = useState<CensusPayload | null>(null);

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

  useEffect(() => {
    if (state !== "ok") return;
    let cancelled = false;
    setCensusState("loading");
    fetch("/api/v1/admin/model-census?window_days=30", { headers: { "x-admin-passphrase": passphrase } })
      .then(async (response) => (response.ok ? ((await response.json()) as CensusPayload) : null))
      .then((payload) => {
        if (cancelled) return;
        setCensus(payload);
        setCensusState(payload ? "ok" : "error");
      })
      .catch(() => {
        if (!cancelled) setCensusState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [state, passphrase]);

  const censusChart = useMemo(() => {
    if (!census) return null;
    const values = census.daily.map((day) => day.calls);
    return {
      calls: chartPoints(values, 640, 150),
      first: census.daily[0]?.date ?? "",
      last: census.daily[census.daily.length - 1]?.date ?? "",
    };
  }, [census]);

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
                {coachData.trace && coachData.trace.length > 0 ? (
                  <p className="admin__coach-meta muted mono" aria-label={t("coachTraceLabel")}>
                    {coachData.trace.map((row) => row.node).join(" → ")}
                    {" · "}{coachData.verified === false ? "✗" : "✓"}
                    {coachData.repairs ? ` · ${coachData.repairs}` : ""}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted">{t("coachReadEmpty")}</p>
            )
          ) : null}
        </div>
      </Panel>

      <Panel eyebrow={t("censusEyebrow")} title={t("censusTitle")}>
        <p className="muted" style={{ maxWidth: "72ch" }}>{t("censusHint")}</p>
        {censusState === "loading" ? <p className="muted">{t("gateEntering")}</p> : null}
        {censusState === "error" ? <p className="admin__gate-error" role="alert">{t("gateError")}</p> : null}
        {censusState === "ok" && census ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem", marginTop: "0.5rem" }}>
            <section className="admin__kpis" aria-label={t("censusTitle")}>
              {[
                { label: t("censusCalls"), value: census.totals.calls.toLocaleString() },
                { label: t("censusFailures", { rate: pct(census.totals.failure_rate) }), value: census.totals.failures.toLocaleString() },
                { label: t("censusCachedShare"), value: pct(census.totals.cached_share_reported) },
                { label: t("censusDemoShare"), value: pct(census.totals.demo_mode_share) },
                { label: t("censusCostEst"), value: `$${census.totals.estimated_cost_usd.toFixed(4)}` },
                { label: t("censusCostActual"), value: `$${census.totals.actual_cost_usd.toFixed(4)}` },
                { label: t("censusMedianLatency"), value: `${census.totals.median_latency_ms} ms` },
              ].map((kpi) => (
                <div key={kpi.label} className="admin__kpi">
                  <span className="admin__kpi-value num">{kpi.value}</span>
                  <span className="admin__kpi-label">{kpi.label}</span>
                </div>
              ))}
            </section>
            {censusChart ? (
              <div className="admin__chartwrap">
                <svg viewBox="0 0 640 150" className="admin__chart" role="img" aria-label={t("censusChartTitle")}>
                  <polyline className="admin__line admin__line--views" points={censusChart.calls} />
                </svg>
                <div className="admin__chartfoot muted">
                  <span className="mono">{censusChart.first}</span>
                  <span className="mono">{censusChart.last}</span>
                </div>
              </div>
            ) : null}
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("censusThFeature")}</th>
                    <th scope="col">{t("censusThCalls")}</th>
                    <th scope="col">{t("censusThCached")}</th>
                    <th scope="col">{t("censusThFailures")}</th>
                    <th scope="col">{t("censusThCost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {census.by_feature.slice(0, 8).map((row) => (
                    <tr key={row.feature}>
                      <td className="mono">{row.feature}</td>
                      <td className="num">{row.calls.toLocaleString()}</td>
                      <td className="num muted">{pct(row.cached_share_reported)}</td>
                      <td className="num">{row.failures.toLocaleString()}</td>
                      <td className="num">{`$${row.cost_usd.toFixed(4)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {census.errors.length > 0 ? (
              <div>
                <p className="eyebrow" style={{ marginBottom: "0.3rem" }}>{t("censusErrorsTitle")}</p>
                <ul className="admin__recs">
                  {census.errors.map((entry) => (
                    <li key={entry.sample}><span className="mono">{entry.sample}</span>{" "}— <span className="num">{entry.count}</span></li>
                  ))}
                </ul>
              </div>
            ) : null}
            <p className="muted" style={{ fontSize: "0.75rem" }}>{t("censusNote")}</p>
          </div>
        ) : null}
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
            <div><dt>{t("forecastProjected")}</dt><dd className="num">{data.forecast.projected_sessions[0]} → {data.forecast.projected_sessions[data.forecast.projected_sessions.length - 1]}</dd></div>
            {data.forecast.trend_direction ? <div><dt>{t("forecastTrend")}</dt><dd className="num">{data.forecast.trend_direction}</dd></div> : null}
            {data.forecast.confidence !== undefined ? <div><dt>{t("forecastConfidence")}</dt><dd className="num">{typeof data.forecast.confidence === "number" ? data.forecast.confidence.toFixed(2) : data.forecast.confidence}</dd></div> : null}
            {data.forecast.projected_7d_sessions !== undefined ? <div><dt>{t("forecast7d")}</dt><dd className="num">{data.forecast.projected_7d_sessions}</dd></div> : null}
            {data.forecast.projected_14d_sessions !== undefined ? <div><dt>{t("forecast14d")}</dt><dd className="num">{data.forecast.projected_14d_sessions}</dd></div> : null}
            {data.forecast.busiest_day ? <div><dt>{t("forecastBusiest")}</dt><dd className="num">{data.forecast.busiest_day}{data.forecast.busiest_day_sessions !== undefined ? ` · ${data.forecast.busiest_day_sessions}` : ""}</dd></div> : null}
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

