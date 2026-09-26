"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch } from "@/lib/api";
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
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Note | null>(null);

  async function call(action: string, path: string, init: { body?: unknown; method?: string } = {}) {
    setBusy(action);
    const method = (init.method ?? "POST").toUpperCase();
    const result = await browserFetch<Record<string, unknown>>(path, { body: init.body, method });
    setBusy(null);
    if (!result.ok) {
      setNote({ action, figures: [`${result.error.code}: ${result.error.message}`, ...refusalFigures(result.error.details)], refused: true, text: `${method} ${path} was refused with ${result.status}` });
      return null;
    }
    setNote({ action, figures: [], refused: false, text: `${method} ${path} answered ${result.status}. The tables on this page were re-read from the server afterwards.` });
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
  const { busy, call, note } = useAcademyCall();
  return (
    <div className="stack">
      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Child</th>
              <th scope="col">Age</th>
              <th scope="col">Guardian</th>
              <th scope="col">Purposes agreed</th>
              <th scope="col">State</th>
              <th scope="col">Live plans</th>
              <th scope="col">Answer</th>
            </tr>
          </thead>
          <tbody>
            {consents.items.map((row) => (
              <tr data-consent={row.id} key={row.id}>
                <td>{row.player.name}</td>
                <td className="num">
                  {row.player.age}
                  {row.player.is_minor && <span className="chip mono"> minor</span>}
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
                    Withdraw
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
  const { busy, call, note } = useAcademyCall();
  const [child, setChild] = useState(sheets[0]?.slug ?? "");
  const [agreed, setAgreed] = useState<string[]>(scopes.default_granted);
  const [reviewWeeks, setReviewWeeks] = useState("6");
  const [focus, setFocus] = useState("");
  const [goal, setGoal] = useState({ title: "", measure: "", by: "" });

  const chosen = sheets.find((row) => row.slug === child);

  return (
    <div className="stack">
      <h3 className="panel__title">Answer for a child on a sheet</h3>
      {sheets.length === 0 ? (
        <p className="muted">No player is on a sheet in this tenant yet, so there is nobody to consent for and nobody to plan for.</p>
      ) : (
        <>
          <div className="grid grid-2">
            <label className="field">
              <span>Child (only players on this tenant&apos;s sheets can be named)</span>
              <select aria-label="Child" onChange={(event) => setChild(event.target.value)} value={child}>
                {sheets.map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name} · {row.age} · {row.team}
                  </option>
                ))}
              </select>
            </label>
            <div className="field">
              <span>Purposes agreed — leaving one off stops any record of it</span>
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
              {busy === "grant" ? "Writing…" : "Grant consent"}
            </button>
            {chosen?.is_minor && (
              <span className="chip mono">
                {chosen.name} is {chosen.age} — under the published threshold, so no plan can open without this row
              </span>
            )}
          </div>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {scopes.rule}
          </p>

          <h3 className="panel__title">Open a development plan</h3>
          <div className="grid grid-2">
            <label className="field">
              <span>Review cadence (weeks)</span>
              <input aria-label="Review weeks" onChange={(event) => setReviewWeeks(event.target.value)} type="text" value={reviewWeeks} />
            </label>
            <label className="field">
              <span>Focus areas — up to six, comma separated</span>
              <input aria-label="Focus areas" onChange={(event) => setFocus(event.target.value)} placeholder="technique, tactics" type="text" value={focus} />
            </label>
            <label className="field">
              <span>Goal title</span>
              <input aria-label="Goal title" onChange={(event) => setGoal({ ...goal, title: event.target.value })} type="text" value={goal.title} />
            </label>
            <label className="field">
              <span>How it is measured</span>
              <input aria-label="Goal measure" onChange={(event) => setGoal({ ...goal, measure: event.target.value })} type="text" value={goal.measure} />
            </label>
            <label className="field">
              <span>By when (ISO date)</span>
              <input aria-label="Goal date" onChange={(event) => setGoal({ ...goal, by: event.target.value })} placeholder="2026-12-31" type="text" value={goal.by} />
            </label>
          </div>
          <div className="row wrap">
            <button className="btn btn--sm" data-testid="plan-open" disabled={busy !== null || child === ""} onClick={() => void call("plan", `/club/academy/${encodeURIComponent(ident)}/plans`, { body: { player: child, review_weeks: Number(reviewWeeks), focus: focus.split(",").map((row) => row.trim()).filter(Boolean), goals: goal.title ? [goal] : [] } })} type="button">
              {busy === "plan" ? "Opening…" : "Open plan"}
            </button>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              A second open plan for the same child is refused by name: `plan_already_open` says which plan holds the seat.
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
  const { busy, call, note } = useAcademyCall();
  const today = new Date().toISOString().slice(0, 10);
  const [assessed, setAssessed] = useState({ on: today, strengths: "", areas: "", next_focus: "" });
  const [ratings, setRatings] = useState<Record<string, string>>(Object.fromEntries(axes.map((axis) => [axis, "50"])));
  const [feedback, setFeedback] = useState({ message: "", shared: true });

  return (
    <div className="stack">
      <h3 className="panel__title">File a review</h3>
      <div className="grid grid-2">
        <label className="field">
          <span>Assessed on (ISO day, not in the future, not before the plan opened)</span>
          <input aria-label="Assessed on" onChange={(event) => setAssessed({ ...assessed, on: event.target.value })} type="text" value={assessed.on} />
        </label>
        <div className="field">
          <span>
            The published axes, {range[0]}–{range[1]}
          </span>
          <div className="grid grid-2">
            {axes.map((axis) => (
              <label className="row" data-axis={axis} key={axis} style={{ gap: "0.4rem" }}>
                <span className="mono" style={{ fontSize: "0.82rem" }}>
                  {axis}
                </span>
                <input aria-label={`Rating for ${axis}`} max={range[1]} min={range[0]} onChange={(event) => setRatings({ ...ratings, [axis]: event.target.value })} type="number" value={ratings[axis] ?? ""} />
              </label>
            ))}
          </div>
        </div>
        <label className="field">
          <span>Strengths</span>
          <input aria-label="Strengths" onChange={(event) => setAssessed({ ...assessed, strengths: event.target.value })} type="text" value={assessed.strengths} />
        </label>
        <label className="field">
          <span>Areas to work on</span>
          <input aria-label="Areas" onChange={(event) => setAssessed({ ...assessed, areas: event.target.value })} type="text" value={assessed.areas} />
        </label>
        <label className="field">
          <span>Next focus</span>
          <input aria-label="Next focus" onChange={(event) => setAssessed({ ...assessed, next_focus: event.target.value })} type="text" value={assessed.next_focus} />
        </label>
      </div>
      <div className="row wrap">
        <button className="btn btn--sm" data-testid="assessment-add" disabled={busy !== null} onClick={() => void call("assess", `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/assessments`, { body: { assessed_on: assessed.on, ratings: Object.fromEntries(Object.entries(ratings).filter(([, value]) => String(value).trim() !== "").map(([axis, value]) => [axis, Number(value)])), strengths: assessed.strengths, areas: assessed.areas, next_focus: assessed.next_focus } })} type="button">
          {busy === "assess" ? "Filing…" : "File review"}
        </button>
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          An axis nobody rated is not a zero: the review lists it under `axes_missing` instead.
        </span>
      </div>

      <h3 className="panel__title">Write to the child or their guardian</h3>
      <label className="field">
        <span>Note</span>
        <input aria-label="Feedback message" onChange={(event) => setFeedback((current) => ({ ...current, message: event.target.value }))} placeholder="What you saw, in one or two sentences" type="text" value={feedback.message} />
      </label>
      <div className="row wrap">
        <label className="row" style={{ gap: "0.4rem" }}>
          <input aria-label="Share with guardian" checked={feedback.shared} onChange={(event) => setFeedback((current) => ({ ...current, shared: event.target.checked }))} type="checkbox" />
          <span>shared_with_guardian</span>
        </label>
        <button className="btn btn--sm" data-testid="feedback-add" disabled={busy !== null || feedback.message.trim() === ""} onClick={() => void call("feedback", `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}/feedback`, { body: { message: feedback.message.trim(), shared_with_guardian: feedback.shared } })} type="button">
          {busy === "feedback" ? "Writing…" : "Add note"}
        </button>
      </div>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        A note withheld from the guardian stays counted on this page rather than vanishing from it: `withheld.coach_feedback` is the tenant&apos;s own total of what you have written that a family cannot see.
      </p>

      <h3 className="panel__title">Close the plan</h3>
      <div className="row wrap">
        {(["paused", "closed"] as const).map((status) => (
          <button className="btn btn--sm btn--ghost" data-status={status} disabled={busy !== null} key={status} onClick={() => void call(`status-${status}`, `/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan)}`, { body: { status }, method: "PATCH" })} type="button">
            Mark {status}
          </button>
        ))}
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          Closing frees the child&apos;s seat for a new plan and refuses further writes to this one.
        </span>
      </div>
      <Answer note={note} />
    </div>
  );
}
