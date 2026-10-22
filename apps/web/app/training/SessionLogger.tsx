"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AiBadge, ReasonList } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CompletionResult, SessionListItem } from "@/lib/types";

const RATINGS = [1, 2, 3, 4, 5];

// Three five-point scales, as keys rather than sentences. A rating that falls outside 1–5 has no key and keeps
// its raw number, which is what the old `?? String(value)` did.
const RATING_KEYS: Record<string, string[]> = {
  execution: ["ratingExec1", "ratingExec2", "ratingExec3", "ratingExec4", "ratingExec5"],
  focus: ["ratingFocus1", "ratingFocus2", "ratingFocus3", "ratingFocus4", "ratingFocus5"],
  difficulty_experience: ["ratingDiff1", "ratingDiff2", "ratingDiff3", "ratingDiff4", "ratingDiff5"],
};

export function SessionLogger({ session }: { session: SessionListItem }) {
  const t = useTranslations("training");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const ratingLabel = (kind: string, value: number): string => {
    const key = RATING_KEYS[kind]?.[value - 1];
    return key ? t(key) : String(value);
  };

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
      setError(response.error.message || t("alreadyLogged"));
    } else {
      setError(errorMessage(response.error, t("logFailed")));
    }
    setBusy(false);
  }

  return (
    <div className="session-card">
      <div className="between wrap" style={{ gap: "0.5rem" }}>
        <div>
          <p className="eyebrow">{t("plannedOn", { category: session.drill.category.replace(/_/g, " "), date: session.planned_date })}</p>
          <Link href={session.drill.slug ? `/training/${session.drill.slug}` : "/training"} className="h3">
            {session.drill.title}
          </Link>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {t("drillMeta", { minutes: session.drill.duration_min, difficulty: session.drill.difficulty })}
          </p>
        </div>
        <span className="chip">{session.status}</span>
      </div>

      {result ? (
        <div className="stack-sm session-card__result">
          <div className="notice">
            {t("xpAwarded", { xp: result.xp_awarded, formula: result.xp_formula })}
          </div>
          {result.level_changed && <div className="notice notice--warn">{t("levelUp", { level: result.player_level })}</div>}
          <div className="row wrap" style={{ gap: "0.5rem" }}>
            <span className="chip">{t("streakChip", { days: result.streak_days })}</span>
            <span className="chip">{t("formChip", { value: result.form })}</span>
            <span className="chip">{t("overallChip", { value: result.player.overall })}</span>
          </div>

          {result.attribute_changes.length > 0 && (
            <div className="stack-sm">
              <p className="eyebrow">{t("attributeChanges")}</p>
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
              <p className="eyebrow">{t("skillPoints")}</p>
              <ul className="list">
                {result.skill_progress.map((row) => (
                  <li className="list__item" key={row.attribute}>
                    <span className="chip">{row.attribute.replace(/_/g, " ")}</span>
                    <span className="grow num mono">
                      {row.banked}/{row.needed}
                    </span>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {row.ceiling
                        ? t("skillCeiling", { ceiling: row.ceiling })
                        : t("skillProgress", { earned: row.earned, remaining: Math.max(0, row.needed - row.banked), value: row.value, next: row.value + 1 })}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.new_achievements.length > 0 && (
            <div className="stack-sm">
              <p className="eyebrow">{t("newAchievements")}</p>
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                {result.new_achievements.map((slug) => (
                  <span className="badge badge--live" key={slug} title={t("achievementSlug", { slug })}>
                    {slug.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="stack-sm">
            <p className="eyebrow">{t("coachFeedback")}</p>
            <AiBadge demo_mode={result.coach_feedback ? result.demo_mode : undefined} confidence={result.coach_feedback?.confidence} provider="rule-engine" />
            {result.coach_feedback && <p className="lede">{result.coach_feedback.content}</p>}
            {result.coach_feedback && <ReasonList items={result.coach_feedback.reasons} title={t("whyFeedback")} />}
          </div>
        </div>
      ) : (
        <div className="stack-sm">
          {error && <div className="notice notice--warn">{error}</div>}
          <div className="session-card__ratings">
            <label className="field">
              <span className="field__label">{t("executionLabel", { label: ratingLabel("execution", execution) })}</span>
              <select className="select" value={execution} onChange={(event) => setExecution(Number(event.target.value))}>
                {RATINGS.map((value) => (
                  <option value={value} key={value}>
                    {value} — {ratingLabel("execution", value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">{t("focusLabel", { label: ratingLabel("focus", focus) })}</span>
              <select className="select" value={focus} onChange={(event) => setFocus(Number(event.target.value))}>
                {RATINGS.map((value) => (
                  <option value={value} key={value}>
                    {value} — {ratingLabel("focus", value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">{t("feltLabel", { label: ratingLabel("difficulty_experience", difficulty) })}</span>
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
            <span className="field__label">{t("notesLabel")}</span>
            <textarea className="textarea" value={notes} maxLength={1200} placeholder={t("notesPlaceholder")} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <div>
            <button type="button" className="btn btn--primary btn--sm" onClick={complete} disabled={busy}>
              {busy ? t("logging") : t("logSession")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
