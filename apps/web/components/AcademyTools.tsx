"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import { refusalFigures, type ConsentList } from "@/lib/club";

type Note = { text: string; figures: string[]; refused: boolean; action: string };
type SheetChild = { age: number; is_minor: boolean; name: string; slug: string; team: string };
type Scopes = { scopes: string[]; default_granted: string[]; rule: string };

/**
 * §40's writes, and only the ones a page should be trusted with.
 *
 * A guardian's yes, a coach's plan, a review and a note. What is *not* here is on purpose: video evidence
 * needs a clip the caller uploaded to M5 and the API already answers `no_such_clip` for one they do not
 * own, and erasure is deliberately not a button — `DELETE …/players/{child}/data` wants a `confirm` echo of
 * the row count it is about to act on, which is a decision a page should not be able to make in one click.
 *
 * Every control is rendered whatever the caller's standing, and the API answers. `consent.grant_own` is a
 * parent's right and a coach does not have it, so a coach pressing *Grant* sees `insufficient_role` with
 * `required_role` beside it. That is the rule working, and a form that hid the button would be hiding the
 * evidence.
 */
function useAcademyCall() {
  const router = useRouter();
  const t = useTranslations("academy");
  const tCommon = useTranslations("common");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Note | null>(null);

  async function call(action: string, path: string, init: { body?: unknown; method?: string } = {}) {
    setBusy(action);
    const method = (init.method ?? "POST").toUpperCase();
    const result = await browserFetch<Record<string, unknown>>(path, { body: init.body, method });
    setBusy(null);
    if (!result.ok) {
      setNote({ action, figures: [`${result.error.code}: ${errorMessage(result.error, tCommon("requestFailed"))}`, ...refusalFigures(result.error.details)], refused: true, text: t("refusedWith", { method, path, status: result.status }) });
      return null;
    }
    setNote({ action, figures: [], refused: false, text: t("answeredWith", { method, path, status: result.status }) });
    router.refresh();
    return result.data;
  }

  return { busy, call, note };
}

function Answer({ note }: { note: Note | null }) {
  if (!note) return null;
  return (
    <div className={note.refused ? "notice notice--warn" : "notice"} data-note={note.action}>
      <p style={{ margin: 0 }}>{note.text}</p>
      {note.figures.map((figure) => (
        <p className="mono" key={figure} style={{ fontSize: "0.8rem", margin: "0.25rem 0 0" }}>
          {figure}
        </p>
      ))}
    </div>
  );
}

/** The consent rows themselves: who claimed which child, for which purposes, and whether it still stands. */
export function ConsentTable({ consents, ident }: { consents: ConsentList; ident: string }) {
  const t = useTranslations("academy");
  const { busy, call, note } = useAcademyCall();
  return (
    <div className="stack">
      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("thChild")}</th>
              <th scope="col">{t("thAge")}</th>
              <th scope="col">{t("thGuardian")}</th>
              <th scope="col">{t("thPurposes")}</th>
              <th scope="col">{t("thState")}</th>
              <th scope="col">{t("thLivePlans")}</th>
              <th scope="col">{t("thAnswer")}</th>
            </tr>
          </thead>
          <tbody>
            {consents.items.map((row) => (
              <tr data-consent={row.id} key={row.id}>
                <td>{row.player.name}</td>
                <td className="num">
                  {row.player.age}
                  {row.player.is_minor && <span className="chip mono">{t("minorChip")}</span>}
                </td>
                <td className="muted">
                  {row.guardian.display_name}
                  <div className="mono" style={{ fontSize: "0.76rem" }}>
                    {row.guardian.email}
                  </div>
                </td>
                <td className="mono">{row.scopes.join(", ")}</td>
                <td>
                  <span className={row.state === "granted" ? "badge badge--live" : "badge badge--demo"}>{row.state.toUpperCase()}</span>
                </td>
                <td className="num">{row.plans_for_this_child}</td>
                <td>
                  <button className="btn btn--sm btn--ghost" data-act="withdraw" disabled={busy !== null || row.state !== "granted"} onClick={() => void call(`withdraw-${row.player.slug}`, `/club/academy/${encodeURIComponent(ident)}/consents/${encodeURIComponent(row.player.slug)}`, { method: "DELETE" })} type="button">
                    {t("withdraw")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Answer note={note} />
    </div>
  );
}

/** A guardian's yes, and a coach's first plan for a child that yes permits. */
export function AcademyTools({ ident, scopes, sheets }: { ident: string; scopes: Scopes; sheets: SheetChild[] }) {
  const ta = useTranslations("academy");
  const { busy, call, note } = useAcademyCall();
  const [child, setChild] = useState(sheets[0]?.slug ?? "");
  const [agreed, setAgreed] = useState<string[]>(scopes.default_granted);
  const [reviewWeeks, setReviewWeeks] = useState("6");
  const [focus, setFocus] = useState("");
  const [goal, setGoal] = useState({ title: "", measure: "", by: "" });

  const chosen = sheets.find((row) => row.slug === child);

  return (
    <div className="stack">
      <h3 className="panel__title">{ta("answerForChildTitle")}</h3>
      {sheets.length === 0 ? (
        <p className="muted">{ta("noSheetNote")}</p>
      ) : (
        <>
          <div className="grid grid-2">
            <label className="field">
              <span>{ta("childLabel")}</span>
              <select aria-label={ta("childAria")} onChange={(event) => setChild(event.target.value)} value={child}>
                {sheets.map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name} · {row.age} · {row.team}
                  </option>
                ))}
              </select>
            </label>
            <div className="field">
              <span>{ta("purposesLabel")}</span>
              <div className="row wrap">
                {scopes.scopes.map((scope) => (
                  <label className="row" data-scope={scope} key={scope} style={{ gap: "0.3rem" }}>
                    <input
                      checked={agreed.includes(scope)}
                      onChange={(event) => setAgreed((current) => (event.target.checked ? [...current, scope] : current.filter((row) => row !== scope)))}
                      type="checkbox"
                      value={scope}
                    />
                    <span className="mono">{scope}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <div className="row wrap">
            <button className="btn btn--sm" data-testid="consent-grant" disabled={busy !== null || child === "" || agreed.length === 0} onClick={() => void call("grant", `/club/academy/${encodeURIComponent(ident)}/consents`, { body: { player: child, scopes: agreed } })} type="button">
              {busy === "grant" ? ta("granting") : ta("grantConsent")}
            </button>
            {chosen?.is_minor && (
              <span className="chip mono">
                {ta("minorThreshold", { name: chosen.name, age: chosen.age })}
              </span>
            )}
          </div>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {scopes.rule}
          </p>

          <h3 className="panel__title">{ta("openPlanTitle")}</h3>
          <div className="grid grid-2">
            <label className="field">
              <span>{ta("reviewCadenceLabel")}</span>
              <input aria-label={ta("reviewWeeksAria")} onChange={(event) => setReviewWeeks(event.target.value)} type="text" value={reviewWeeks} />
            </label>
            <label className="field">
              <span>{ta("focusLabel")}</span>
              <input aria-label={ta("focusAria")} onChange={(event) => setFocus(event.target.value)} placeholder={ta("focusPlaceholder")} type="text" value={focus} />
            </label>
            <label className="field">
              <span>{ta("goalTitleLabel")}</span>
              <input aria-label={ta("goalTitleAria")} onChange={(event) => setGoal({ ...goal, title: event.target.value })} type="text" value={goal.title} />
            </label>
            <label className="field">
              <span>{ta("goalMeasureLabel")}</span>
              <input aria-label={ta("goalMeasureAria")} onChange={(event) => setGoal({ ...goal, measure: event.target.value })} type="text" value={goal.measure} />
            </label>
            <label className="field">
              <span>{ta("goalDateLabel")}</span>
              <input aria-label={ta("goalDateAria")} onChange={(event) => setGoal({ ...goal, by: event.target.value })} placeholder="2026-12-31" type="text" value={goal.by} />
            </label>
          </div>
          <div className="row wrap">
            <button className="btn btn--sm" data-testid="plan-open" disabled={busy !== null || child === ""} onClick={() => void call("plan", `/club/academy/${encodeURIComponent(ident)}/plans`, { body: { player: child, review_weeks: Number(reviewWeeks), focus: focus.split(",").map((row) => row.trim()).filter(Boolean), goals: goal.title ? [goal] : [] } })} type="button">
              {busy === "plan" ? ta("openingPlan") : ta("openPlan")}
            </button>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {ta("planOpenNote")}
            </span>
          </div>
        </>
      )}
      <Answer note={note} />
    </div>
  );
}

/** The review and the note: the two writes a plan page is asked for, with the axes the tier publishes. */
export function PlanTools({ axes, ident, plan, range }: { axes: string[]; ident: string; plan: string; range: [number, number] }) {
  const t = useTranslations("academy");
  const { busy, call, note } = useAcademyCall();
  const today = new Date().toISOString().slice(0, 10);
  const [assessed, setAssessed] = useState({ on: today, strengths: "", areas: "", next_focus: "" });
  const [ratings, setRatings] = useState<Record<string, string>>(Object.fromEntries(axes.map((axis) => [axis, "50"])));
  const [feedback, setFeedback] = useState({ message: "", shared: true });

  return (
    <div className="stack">
      <h3 className="panel__title">{t("fileReviewTitle")}</h3>
      <div className="grid grid-2">
        <label className="field">
          <span>{t("assessedOnLabel")}</span>
          <input aria-label={t("assessedOnAria")} onChange={(event) => setAssessed({ ...assessed, on: event.target.value })} type="text" value={assessed.on} />
        </label>
        <div className="field">
          <span>
            {t("axesLabel", { from: range[0], to: range[1] })}
          </span>
          <div className="grid grid-2">
            {axes.map((axis) => (
              <label className="row" data-axis={axis} key={axis} style={{ gap: "0.4rem" }}>
                <span className="mono" style={{ fontSize: "0.82rem" }}>
                  {axis}
                </span>
                <input aria-label={t("ratingForAria", { axis })} max={range[1]} min={range[0]} onChange={(event) => setRatings({ ...ratings, [axis]: event.target.value })} type="number" value={ratings[axis] ?? ""} />
              </label>
            ))}
          </div>
        </div>
        <label className="field">
          <span>{t("strengthsLabel")}</span>
          <input aria-label={t("strengthsAria")} onChange={(event) => setAssessed({ ...assessed, strengths: event.target.value })} type="text" value={assessed.strengths} />
        </label>
        <label className="field">
          <span>{t("areasLabel")}</span>
          <input aria-label={t("areasAria")} onChange={(event) => setAssessed({ ...assessed, areas: event.target.value })} type="text" value={assessed.areas} />
        </label>
        <label className="field">
          <span>{t("nextFocusLabel")}</span>
          <input aria-label={t("nextFocusAria")} onChange={(event) => setAssessed({ ...assessed, next_focus: event.target.value })} type="text" value={assessed.next_focus} />
        </label>
      </div>
      <div className="row wrap">
        <button className="btn btn--sm" data-testid="assessment-add" disabled={busy !== null} onClick={() => void call("assess", `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/assessments`, { body: { assessed_on: assessed.on, ratings: Object.fromEntries(Object.entries(ratings).filter(([, value]) => String(value).trim() !== "").map(([axis, value]) => [axis, Number(value)])), strengths: assessed.strengths, areas: assessed.areas, next_focus: assessed.next_focus } })} type="button">
          {busy === "assess" ? t("filing") : t("fileReview")}
        </button>
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          {t("axesMissingNote")}
        </span>
      </div>

      <h3 className="panel__title">{t("writeToTitle")}</h3>
      <label className="field">
        <span>{t("noteLabel")}</span>
        <input aria-label={t("feedbackAria")} onChange={(event) => setFeedback((current) => ({ ...current, message: event.target.value }))} placeholder={t("feedbackPlaceholder")} type="text" value={feedback.message} />
      </label>
      <div className="row wrap">
        <label className="row" style={{ gap: "0.4rem" }}>
          <input aria-label={t("shareWithGuardianAria")} checked={feedback.shared} onChange={(event) => setFeedback((current) => ({ ...current, shared: event.target.checked }))} type="checkbox" />
          <span>{t("sharedWithGuardian")}</span>
        </label>
        <button className="btn btn--sm" data-testid="feedback-add" disabled={busy !== null || feedback.message.trim() === ""} onClick={() => void call("feedback", `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/feedback`, { body: { message: feedback.message.trim(), shared_with_guardian: feedback.shared } })} type="button">
          {busy === "feedback" ? t("writing") : t("addNote")}
        </button>
      </div>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        {t("withheldNote")}
      </p>

      <h3 className="panel__title">{t("closePlanTitle")}</h3>
      <div className="row wrap">
        {(["paused", "closed"] as const).map((status) => (
          <button className="btn btn--sm btn--ghost" data-status={status} disabled={busy !== null} key={status} onClick={() => void call(`status-${status}`, `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}`, { body: { status }, method: "PATCH" })} type="button">
            {t("markStatus", { status })}
          </button>
        ))}
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          {t("closingNote")}
        </span>
      </div>
      <Answer note={note} />
    </div>
  );
}
