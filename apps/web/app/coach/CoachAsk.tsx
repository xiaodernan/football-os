"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AiBadge, DrillMeta, ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CoachAnswer, PlanDay } from "@/lib/types";

// Keys, not sentences: the suggestions and the intent labels were two more English tables in a component whose
// page reads a catalogue, so the Chinese reader got translated panel titles above English chips.
const SUGGESTIONS = ["suggestionToday", "suggestionBall", "suggestionPressing", "suggestionPlan", "suggestionMatch"] as const;

const INTENT_KEYS: Record<string, string> = {
  today: "intentToday",
  plan_7: "intentPlan7",
  plan_30: "intentPlan30",
  plan_90: "intentPlan90",
  weak_foot: "intentWeakFoot",
  ball_loss: "intentBallLoss",
  role_question: "intentRole",
  pressing: "intentPressing",
  match_review: "intentMatchReview",
  explain: "intentExplain",
  general: "intentGeneral",
};

type Turn = {
  id: number;
  question: string;
  envelope: CoachAnswer | null;
  error: string | null;
};

function PlanPreview({ days }: { days: PlanDay[] }) {
  const t = useTranslations("coach");
  const withSessions = days.filter((day) => day.sessions.length > 0);
  return (
    <div className="stack-sm">
      <p className="eyebrow">{t("planDays", { days: days.length })}</p>
      <ul className="list coach-planlist">
        {withSessions.slice(0, 7).map((day) => (
          <li className="list__item" key={day.day}>
            <span className="chip chip--accent">D{day.day}</span>
            <div className="grow">
              <span className="upper muted" style={{ fontSize: "0.8rem" }}>
                {day.type}
              </span>
              {day.sessions.map((session) => (
                <div className="coach-planlist__row" key={`${day.day}-${session.drill_id}`}>
                  <Link className="h3" href={`/training/${session.slug}`}>
                    {session.title}
                  </Link>
                  <span className="muted" style={{ fontSize: "0.82rem" }}>
                    {session.duration_min} min — {session.why}
                  </span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
      {withSessions.length > 7 && <span className="muted" style={{ fontSize: "0.82rem" }}>{t("planMoreDays", { count: withSessions.length - 7 })}</span>}
    </div>
  );
}

export function CoachAsk() {
  const t = useTranslations("coach");
  const [question, setQuestion] = useState("");
  const [minutes, setMinutes] = useState(25);
  const [hasPitch, setHasPitch] = useState(true);
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);

  async function ask() {
    const trimmed = question.trim();
    if (trimmed.length < 3 || busy) return;
    setBusy(true);
    const result = await browserFetch<CoachAnswer>("/coach/ask", {
      method: "POST",
      body: { question: trimmed, available_minutes: minutes, has_pitch: hasPitch, equipment: [] },
    });
    setTurns((previous) => [
      {
        id: Date.now(),
        question: trimmed,
        envelope: result.ok ? result.data : null,
        error: result.ok ? null : errorMessage(result.error, t("askFailed")),
      },
      ...previous,
    ]);
    setQuestion("");
    setBusy(false);
  }

  return (
    <div className="stack">
      <div className="stack-sm">
        <label className="field">
          <span className="field__label">{t("questionLabel")}</span>
          <textarea
            className="textarea"
            value={question}
            maxLength={800}
            placeholder={t("questionPlaceholder")}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <span className="field__hint">{t("questionHint")}</span>
        </label>

        <div className="form-grid">
          <label className="field">
            <span className="field__label">{t("minutesLabel")}</span>
            <input className="input" type="number" min={5} max={180} value={minutes} onChange={(event) => setMinutes(Number(event.target.value) || 5)} />
          </label>
          <label className="check" style={{ alignSelf: "end" }}>
            <input type="checkbox" checked={hasPitch} onChange={(event) => setHasPitch(event.target.checked)} />
            <span>{t("pitchAccess")}</span>
          </label>
        </div>

        <div className="row wrap" style={{ gap: "0.4rem" }}>
          {SUGGESTIONS.map((suggestion) => (
            <button type="button" className="chip coach-chip" key={suggestion} onClick={() => setQuestion(t(suggestion))}>
              {t(suggestion)}
            </button>
          ))}
        </div>

        <div>
          <button type="button" className="btn btn--primary" onClick={ask} disabled={busy || question.trim().length < 3}>
            {busy ? t("asking") : t("ask")}
          </button>
        </div>
      </div>

      {turns.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {t("answerEmpty")}
        </p>
      ) : (
        <div className="stack">
          {turns.map((turn) => (
            <div className="coach-answer" key={turn.id}>
              <p className="coach-answer__q">“{turn.question}”</p>
              {turn.error ? (
                <div className="notice notice--warn">{turn.error}</div>
              ) : turn.envelope ? (
                <div className="stack">
                  <div className="row wrap" style={{ gap: "0.4rem" }}>
                    <span className="chip chip--accent">
                      {t("intentLabel", { intent: INTENT_KEYS[turn.envelope.intent ?? "general"] ? t(INTENT_KEYS[turn.envelope.intent ?? "general"]) : (turn.envelope.intent ?? t("intentGeneral")) })}
                    </span>
                    <AiBadge
                      demo_mode={turn.envelope.demo_mode}
                      provider={turn.envelope.provider}
                      model={turn.envelope.model}
                      confidence={turn.envelope.confidence}
                    />
                  </div>
                  {turn.envelope.message && <p className="lede">{turn.envelope.message}</p>}
                  {turn.envelope.recommendation && (
                    <div className="coach-rec">
                      <div className="between wrap">
                        <h3 className="h3">{turn.envelope.recommendation.title}</h3>
                        <Link className="btn btn--ghost btn--sm" href={`/training/${turn.envelope.recommendation.slug}`}>
                          {t("openDrill")}
                        </Link>
                      </div>
                      <p className="muted">{turn.envelope.recommendation.objective}</p>
                      <DrillMeta drill={turn.envelope.recommendation} />
                    </div>
                  )}
                  {turn.envelope.plan && turn.envelope.plan.days.length > 0 && <PlanPreview days={turn.envelope.plan.days} />}
                  <ReasonList items={turn.envelope.reasons} title={t("whyAnswer")} />
                  <p className="muted coach-disclaimer">{turn.envelope.disclaimer}</p>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
