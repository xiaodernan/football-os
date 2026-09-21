"use client";

import Link from "next/link";
import { useState } from "react";

import { AiBadge, DrillMeta, ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CoachAnswer, PlanDay } from "@/lib/types";

const SUGGESTIONS = [
  "What should I train today?",
  "Why am I losing the ball?",
  "How do I become a better pressing midfielder?",
  "Create a 7-day plan",
  "Analyze my last match",
];

const INTENT_LABELS: Record<string, string> = {
  today: "Today's session",
  plan_7: "7-day plan",
  plan_30: "30-day plan",
  plan_90: "90-day plan",
  weak_foot: "Weak foot",
  ball_loss: "Ball loss",
  role_question: "Role / archetype",
  pressing: "Pressing",
  match_review: "Match review",
  explain: "Explain progress",
  general: "General",
};

type Turn = {
  id: number;
  question: string;
  envelope: CoachAnswer | null;
  error: string | null;
};

function PlanPreview({ days }: { days: PlanDay[] }) {
  const withSessions = days.filter((day) => day.sessions.length > 0);
  return (
    <div className="stack-sm">
      <p className="eyebrow">{days.length}-day plan</p>
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
      {withSessions.length > 7 && <span className="muted" style={{ fontSize: "0.82rem" }}>+{withSessions.length - 7} more days in the full plan builder below.</span>}
    </div>
  );
}

export function CoachAsk() {
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
        error: result.ok ? null : errorMessage(result.error, "The coach could not answer that."),
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
          <span className="field__label">Your question</span>
          <textarea
            className="textarea"
            value={question}
            maxLength={800}
            placeholder="e.g. Why am I losing the ball in the middle third?"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <span className="field__hint">3–800 characters. The coach answers from your stored profile and history only.</span>
        </label>

        <div className="form-grid">
          <label className="field">
            <span className="field__label">Available minutes</span>
            <input className="input" type="number" min={5} max={180} value={minutes} onChange={(event) => setMinutes(Number(event.target.value) || 5)} />
          </label>
          <label className="check" style={{ alignSelf: "end" }}>
            <input type="checkbox" checked={hasPitch} onChange={(event) => setHasPitch(event.target.checked)} />
            <span>I have pitch / grass access</span>
          </label>
        </div>

        <div className="row wrap" style={{ gap: "0.4rem" }}>
          {SUGGESTIONS.map((suggestion) => (
            <button type="button" className="chip coach-chip" key={suggestion} onClick={() => setQuestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>

        <div>
          <button type="button" className="btn btn--primary" onClick={ask} disabled={busy || question.trim().length < 3}>
            {busy ? "Asking…" : "Ask the coach"}
          </button>
        </div>
      </div>

      {turns.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Answers appear below. This list lives in your browser only — nothing is replayed from a saved chat, the server keeps its own coach log.
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
                    <span className="chip chip--accent">intent: {INTENT_LABELS[turn.envelope.intent ?? "general"] ?? turn.envelope.intent}</span>
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
                          Open drill
                        </Link>
                      </div>
                      <p className="muted">{turn.envelope.recommendation.objective}</p>
                      <DrillMeta drill={turn.envelope.recommendation} />
                    </div>
                  )}
                  {turn.envelope.plan && turn.envelope.plan.days.length > 0 && <PlanPreview days={turn.envelope.plan.days} />}
                  <ReasonList items={turn.envelope.reasons} title="Why this answer" />
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
