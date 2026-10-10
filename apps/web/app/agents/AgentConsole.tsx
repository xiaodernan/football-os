"use client";

import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { AgentCompositeResponse, AgentMemoryRow, AgentRunResponse } from "@/lib/types";

// Keys, not sentences — same rule as CoachAsk's intent map: the roster arrives as the registry's
// raw type names, and the description for each is a catalogue key, so a locale switch repaints it.
const AGENT_KEYS: Record<string, string> = {
  research: "agentResearch",
  coach: "agentCoach",
  tactical: "agentTactical",
  scout: "agentScout",
  simulation: "agentSimulation",
  video: "agentVideo",
};

// Each suggestion carries the mode and agent that make it a fair example — the tactical chip must
// not leave the console in composite mode, and the composite chip must not leave an agent picked.
const SUGGESTIONS: { key: string; mode: "single" | "composite"; agent: string }[] = [
  { key: "suggestionResearch", mode: "single", agent: "research" },
  { key: "suggestionCoach", mode: "single", agent: "coach" },
  { key: "suggestionTactical", mode: "single", agent: "tactical" },
  { key: "suggestionScout", mode: "single", agent: "scout" },
  { key: "suggestionSimulation", mode: "single", agent: "simulation" },
  { key: "suggestionComposite", mode: "composite", agent: "research" },
];

type Turn = {
  id: number;
  question: string;
  agent: string;
  run: AgentRunResponse | null;
  composite: AgentCompositeResponse | null;
  error: string | null;
};

function agentLabel(type: string, t: (key: string) => string): string {
  const key = AGENT_KEYS[type];
  if (!key) return type;
  // agentCoach reads "Coach — training plans and drills"; the roster chip shows the whole
  // sentence, a step row keeps just the part before the dash so the list stays scannable.
  return t(key).split("—")[0].trim();
}

export function AgentConsole({ agents, rosterError }: { agents: string[]; rosterError: string | null }) {
  const t = useTranslations("agents");
  const [mode, setMode] = useState<"single" | "composite">("single");
  const [agent, setAgent] = useState("research");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [memories, setMemories] = useState<AgentMemoryRow[] | null>(null);
  const [memoriesBusy, setMemoriesBusy] = useState(false);

  // One session per visit: the agents' memories are scoped to it, so the context panel below
  // shows what this conversation actually stored, and a reload starts a clean one.
  const sessionRef = useRef<string>("");
  if (!sessionRef.current) sessionRef.current = crypto.randomUUID();

  const loadContext = useCallback(async (agentType: string) => {
    setMemoriesBusy(true);
    const result = await browserFetch<{ memories: AgentMemoryRow[] }>(
      `/agents/context?agent_type=${encodeURIComponent(agentType)}&session_id=${encodeURIComponent(sessionRef.current)}`,
    );
    setMemories(result.ok ? result.data.memories : null);
    setMemoriesBusy(false);
  }, []);

  async function ask() {
    const trimmed = question.trim();
    if (trimmed.length < 5 || busy) return;
    setBusy(true);
    const result =
      mode === "composite"
        ? await browserFetch<AgentCompositeResponse>("/agents/composite", {
            method: "POST",
            body: { query: trimmed, session_id: sessionRef.current },
          })
        : await browserFetch<AgentRunResponse>("/agents/run", {
            method: "POST",
            body: { query: trimmed, agent_type: agent, session_id: sessionRef.current },
          });
    setTurns((previous) => [
      {
        id: Date.now(),
        question: trimmed,
        agent,
        run: result.ok && !("steps" in result.data) ? result.data : null,
        composite: result.ok && "steps" in result.data ? result.data : null,
        error: result.ok ? null : errorMessage(result.error, t("askFailed")),
      },
      ...previous,
    ]);
    setQuestion("");
    setBusy(false);
    void loadContext(agent);
  }

  const valid = question.trim().length >= 5;

  return (
    <div className="stack">
      {rosterError && <div className="notice notice--warn">{rosterError}</div>}

      <div className="row wrap" style={{ gap: "0.4rem" }}>
        <span className="eyebrow">{t("modeLabel")}</span>
        <button type="button" className={`chip coach-chip${mode === "single" ? " chip--accent" : ""}`} onClick={() => setMode("single")}>
          {t("modeSingle")}
        </button>
        <button type="button" className={`chip coach-chip${mode === "composite" ? " chip--accent" : ""}`} onClick={() => setMode("composite")}>
          {t("modeComposite")}
        </button>
      </div>

      {mode === "single" && (
        <div className="stack-sm">
          <span className="eyebrow">{t("rosterLabel")}</span>
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {agents.map((type) => (
              <button
                type="button"
                key={type}
                className={`chip coach-chip${agent === type ? " chip--accent" : ""}`}
                onClick={() => {
                  setAgent(type);
                  void loadContext(type);
                }}
              >
                {AGENT_KEYS[type] ? t(AGENT_KEYS[type]) : type}
              </button>
            ))}
          </div>
        </div>
      )}

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

        <div className="row wrap" style={{ gap: "0.4rem" }}>
          {SUGGESTIONS.map((suggestion) => (
            <button
              type="button"
              className="chip coach-chip"
              key={suggestion.key}
              onClick={() => {
                setMode(suggestion.mode);
                setAgent(suggestion.agent);
                setQuestion(t(suggestion.key));
              }}
            >
              {t(suggestion.key)}
            </button>
          ))}
        </div>

        <div>
          <button type="button" className="btn btn--primary" onClick={ask} disabled={busy || !valid}>
            {busy ? t("running") : mode === "composite" ? t("runComposite") : t("run")}
          </button>
        </div>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">{t("contextTitle")}</span>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {t("contextHint")}
        </p>
        {memoriesBusy && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {t("running")}
          </p>
        )}
        {memories !== null &&
          (memories.length === 0 ? (
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {t("contextEmpty")}
            </p>
          ) : (
            <ul className="list">
              {memories.map((memory) => (
                <li className="list__item" key={memory.key}>
                  <span className="chip">{memory.key}</span>
                  <code style={{ fontSize: "0.8rem" }}>{JSON.stringify(memory.value).slice(0, 240)}</code>
                </li>
              ))}
            </ul>
          ))}
      </div>

      {turns.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {t("turnsEmpty")}
        </p>
      ) : (
        <div className="stack">
          {turns.map((turn) => (
            <div className="coach-answer" key={turn.id}>
              <p className="coach-answer__q">“{turn.question}”</p>
              {turn.error ? (
                <div className="notice notice--warn">{turn.error}</div>
              ) : turn.composite ? (
                <div className="stack">
                  <div className="row wrap" style={{ gap: "0.4rem" }}>
                    <span className="chip chip--accent">{t("modeComposite")}</span>
                    {turn.composite.from_cache && <span className="badge badge--demo">{t("cachedLabel")}</span>}
                    {turn.composite.confidence !== null && (
                      <span className="muted" style={{ fontSize: "0.82rem" }}>
                        {t("confidenceLabel")}: {(turn.composite.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p className="lede">{turn.composite.answer}</p>
                  <div className="stack-sm">
                    <span className="eyebrow">{t("stepsLabel")}</span>
                    <ol className="list">
                      {turn.composite.steps.map((step, index) => (
                        <li className="list__item" key={`${step.agent_type}-${index}`}>
                          <span className="chip">{agentLabel(step.agent_type, t)}</span>
                          <div className="grow">
                            <span style={{ fontSize: "0.85rem" }}>{step.query}</span>
                            {step.result_summary && (
                              <span className="muted" style={{ fontSize: "0.82rem", display: "block" }}>
                                {step.result_summary}
                              </span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              ) : turn.run ? (
                <div className="stack">
                  <div className="row wrap" style={{ gap: "0.4rem" }}>
                    <span className="chip chip--accent">{agentLabel(turn.agent, t)}</span>
                    {turn.run.from_cache && <span className="badge badge--demo">{t("cachedLabel")}</span>}
                  </div>
                  <p className="lede">{turn.run.answer}</p>
                  {turn.run.citations && turn.run.citations.length > 0 && (
                    <div className="stack-sm">
                      <span className="eyebrow">{t("citationsLabel")}</span>
                      <ul className="reasons">
                        {turn.run.citations.map((citation, index) => (
                          <li className="reasons__item" key={index}>
                            {Object.entries(citation)
                              .map(([key, value]) => `${key}: ${value}`)
                              .join(" · ")}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {turn.run.confidence !== null && (
                    <p className="muted" style={{ fontSize: "0.82rem" }}>
                      {t("confidenceLabel")}: {(turn.run.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
