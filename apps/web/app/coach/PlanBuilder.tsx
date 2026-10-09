"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AiBadge, ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { GeneratedPlan, PlanDay } from "@/lib/types";

const TYPE_ORDER: PlanDay["type"][] = ["training", "test", "recovery", "rest"];
const TYPE_KEYS: Record<PlanDay["type"], string> = {
  training: "typeTraining",
  test: "typeTest",
  recovery: "typeRecovery",
  rest: "typeRest",
};

export function PlanBuilder() {
  const t = useTranslations("coach");
  const [horizon, setHorizon] = useState(7);
  const [minutes, setMinutes] = useState(25);
  const [daysPerWeek, setDaysPerWeek] = useState(4);
  const [hasPitch, setHasPitch] = useState(true);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [result, setResult] = useState<GeneratedPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function build() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    setResult(null);
    const response = await browserFetch<GeneratedPlan>("/coach/plan", {
      method: "POST",
      body: { horizon_days: horizon, available_minutes: minutes, days_per_week: daysPerWeek, has_pitch: hasPitch },
    });
    if (response.ok) {
      setResult(response.data);
      setSaved(response.status === 200);
    } else {
      setError(errorMessage(response.error, t("planFailed")));
    }
    setBusy(false);
  }

  const days = result?.days ?? [];
  const grouped = TYPE_ORDER.map((type) => ({ type, rows: days.filter((day) => day.type === type) })).filter((group) => group.rows.length > 0);

  return (
    <div className="stack">
      <div className="form-grid">
        <label className="field">
          <span className="field__label">{t("horizonLabel")}</span>
          <select className="select" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>
            <option value={7}>{t("days7")}</option>
            <option value={30}>{t("days30")}</option>
            <option value={90}>{t("days90")}</option>
          </select>
        </label>
        <label className="field">
          <span className="field__label">{t("sessionsPerWeek", { count: daysPerWeek })}</span>
          <select className="select" value={daysPerWeek} onChange={(event) => setDaysPerWeek(Number(event.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7].map((value) => (
              <option value={value} key={value}>
                {value === 1 ? t("dayOne", { count: value }) : t("dayMany", { count: value })}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">{t("minutesPerSession", { count: minutes })}</span>
          <input className="plan-range" type="range" min={5} max={180} step={5} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} />
        </label>
        <label className="check" style={{ alignSelf: "end" }}>
          <input type="checkbox" checked={hasPitch} onChange={(event) => setHasPitch(event.target.checked)} />
          <span>{t("pitchAccess")}</span>
        </label>
      </div>

      <div>
        <button type="button" className="btn btn--primary" onClick={build} disabled={busy}>
          {busy ? t("building") : t("buildPlan", { days: horizon })}
        </button>
      </div>

      {error && <div className="notice notice--warn">{error}</div>}

      {result && (
        <div className="stack">
          <AiBadge demo_mode={result.demo_mode} provider={result.provider} model={result.model} confidence={result.confidence} />
          {saved && <div className="notice">{t("planSaved")}</div>}

          {grouped.map((group) => (
            <div className="stack-sm" key={group.type}>
              <p className="eyebrow">{t(TYPE_KEYS[group.type])}</p>
              <ul className="list plan-group">
                {group.rows.map((day) => (
                  <li className="list__item" key={`${group.type}-${day.day}`}>
                    <span className="chip chip--accent">D{day.day}</span>
                    <div className="grow">
                      <span className="muted" style={{ fontSize: "0.8rem" }}>
                        {day.date}
                      </span>
                      {day.sessions.length > 0 ? (
                        day.sessions.map((session) => (
                          <div className="plan-group__row" key={`${day.day}-${session.drill_id}`}>
                            <Link href={`/training/${session.slug}`} className="plan-group__title">
                              {session.title}
                            </Link>
                            <span className="muted" style={{ fontSize: "0.82rem" }}>
                              {session.duration_min} min · {session.category.replace(/_/g, " ")}
                            </span>
                            <span className="plan-group__why">{session.why}</span>
                          </div>
                        ))
                      ) : (
                        <span className="muted" style={{ fontSize: "0.88rem" }}>
                          {day.note || t("noSession")}
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <ReasonList items={result.reasons} title={t("loadSpread")} />
          <p className="muted coach-disclaimer">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
