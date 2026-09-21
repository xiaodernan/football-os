"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AiBadge, ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CompletionResult, SessionListItem } from "@/lib/types";

const RATINGS = [1, 2, 3, 4, 5];

function ratingLabel(kind: string, value: number): string {
  const map: Record<string, string[]> = {
    execution: ["Poor", "Rough", "Solid", "Sharp", "Excellent"],
    focus: ["Distracted", "Patchy", "Steady", "Locked in", "Total"],
    difficulty_experience: ["Too easy", "Easy", "Balanced", "Hard", "Very hard"],
  };
  return map[kind]?.[value - 1] ?? String(value);
}

export function SessionLogger({ session }: { session: SessionListItem }) {
  const router = useRouter();
  const [execution, setExecution] = useState(3);
  const [focus, setFocus] = useState(3);
  const [difficulty, setDifficulty] = useState(3);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CompletionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function complete() {
    if (busy) return;
    setBusy(true);
    setError(null);
    const response = await browserFetch<CompletionResult>(`/trainings/sessions/${session.id}/complete`, {
      method: "POST",
      body: {
        execution,
        focus,
        difficulty_experience: difficulty,
        self_notes: notes.trim() ? notes.trim().slice(0, 1200) : undefined,
      },
    });
    if (response.ok) {
      setResult(response.data);
      router.refresh();
    } else if (response.status === 409 && response.error.code === "already_completed") {
      setError(response.error.message || "This session is already logged.");
    } else {
      setError(errorMessage(response.error, "This session could not be logged."));
    }
    setBusy(false);
  }

  return (
    <div className="session-card">
      <div className="between wrap" style={{ gap: "0.5rem" }}>
        <div>
          <p className="eyebrow">{session.drill.category.replace(/_/g, " ")} · planned {session.planned_date}</p>
          <Link href={session.drill.slug ? `/training/${session.drill.slug}` : "/training"} className="h3">
            {session.drill.title}
          </Link>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {session.drill.duration_min} min · difficulty {session.drill.difficulty}/5 · DEMO drill
          </p>
        </div>
        <span className="chip">{session.status}</span>
      </div>

      {result ? (
        <div className="stack-sm session-card__result">
          <div className="notice">
            +{result.xp_awarded} XP · {result.xp_formula}
          </div>
          {result.level_changed && <div className="notice notice--warn">Level up — you are now level {result.player_level}.</div>}
          <div className="row wrap" style={{ gap: "0.5rem" }}>
            <span className="chip">Streak {result.streak_days} d</span>
            <span className="chip">Form {result.form}</span>
            <span className="chip">OVR {result.player.overall}</span>
          </div>

          {result.attribute_changes.length > 0 && (
            <div className="stack-sm">
              <p className="eyebrow">Attribute changes</p>
              <ul className="list">
                {result.attribute_changes.map((change, index) => (
                  <li className="list__item" key={`${change.attribute}-${index}`}>
                    <span className="chip">{change.attribute.replace(/_/g, " ")}</span>
                    <span className="grow num mono">
                      {change.before} → {change.after} ({change.delta >= 0 ? "+" : ""}
                      {change.delta})
                    </span>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {change.reason}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.skill_progress && result.skill_progress.length > 0 && (
            <div className="stack-sm">
              <p className="eyebrow">Skill points banked</p>
              <ul className="list">
                {result.skill_progress.map((row) => (
                  <li className="list__item" key={row.attribute}>
                    <span className="chip">{row.attribute.replace(/_/g, " ")}</span>
                    <span className="grow num mono">
                      {row.banked}/{row.needed}
                    </span>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {row.ceiling
                        ? `Banked, no point added — ${row.ceiling} reached.`
                        : `+${row.earned} from this session; ${Math.max(0, row.needed - row.banked)} more raises ${row.value} → ${row.value + 1}.`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.new_achievements.length > 0 && (
            <div className="stack-sm">
              <p className="eyebrow">New achievements</p>
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                {result.new_achievements.map((slug) => (
                  <span className="badge badge--live" key={slug} title={`Achievement slug: ${slug}`}>
                    {slug.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="stack-sm">
            <p className="eyebrow">Coach feedback</p>
            <AiBadge demo_mode={result.coach_feedback ? result.demo_mode : undefined} confidence={result.coach_feedback?.confidence} provider="rule-engine" />
            {result.coach_feedback && <p className="lede">{result.coach_feedback.content}</p>}
            {result.coach_feedback && <ReasonList items={result.coach_feedback.reasons} title="Why this feedback" />}
          </div>
        </div>
      ) : (
        <div className="stack-sm">
          {error && <div className="notice notice--warn">{error}</div>}
          <div className="session-card__ratings">
            <label className="field">
              <span className="field__label">Execution: {ratingLabel("execution", execution)}</span>
              <select className="select" value={execution} onChange={(event) => setExecution(Number(event.target.value))}>
                {RATINGS.map((value) => (
                  <option value={value} key={value}>
                    {value} — {ratingLabel("execution", value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Focus: {ratingLabel("focus", focus)}</span>
              <select className="select" value={focus} onChange={(event) => setFocus(Number(event.target.value))}>
                {RATINGS.map((value) => (
                  <option value={value} key={value}>
                    {value} — {ratingLabel("focus", value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Felt: {ratingLabel("difficulty_experience", difficulty)}</span>
              <select className="select" value={difficulty} onChange={(event) => setDifficulty(Number(event.target.value))}>
                {RATINGS.map((value) => (
                  <option value={value} key={value}>
                    {value} — {ratingLabel("difficulty_experience", value)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="field">
            <span className="field__label">Notes (optional)</span>
            <textarea className="textarea" value={notes} maxLength={1200} placeholder="What clicked, what to fix next time?" onChange={(event) => setNotes(event.target.value)} />
          </label>
          <div>
            <button type="button" className="btn btn--primary btn--sm" onClick={complete} disabled={busy}>
              {busy ? "Logging…" : "Log this session"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
